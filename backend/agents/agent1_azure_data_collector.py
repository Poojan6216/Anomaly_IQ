"""
Agent 1 — Azure Data Collector
Fetches cost data from Azure Cost Management API, Azure Monitor metrics,
and Azure Activity Log events.
All credentials loaded from environment variables.

Required env vars:
    AZURE_SUBSCRIPTION_ID   — Azure subscription ID
    AZURE_TENANT_ID         — Azure AD tenant ID
    AZURE_CLIENT_ID         — Service principal client/app ID
    AZURE_CLIENT_SECRET     — Service principal client secret
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Azure credentials (loaded from environment)
# ---------------------------------------------------------------------------

_SUBSCRIPTION_ID: str = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
_TENANT_ID: str = os.environ.get("AZURE_TENANT_ID", "")
_CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "")
_CLIENT_SECRET: str = os.environ.get("AZURE_CLIENT_SECRET", "")


def _get_credential():
    """Return an Azure ClientSecretCredential."""
    from azure.identity import ClientSecretCredential  # type: ignore
    return ClientSecretCredential(
        tenant_id=_TENANT_ID,
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
    )


def _with_backoff(fn, *args, max_retries: int = 5, base_delay: float = 1.0, **kwargs):
    """Call *fn* with exponential back-off on throttling (429) errors."""
    from azure.core.exceptions import HttpResponseError  # type: ignore

    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except HttpResponseError as exc:
            if exc.status_code == 429:
                delay = base_delay * (2 ** attempt)
                retry_after = exc.response.headers.get("Retry-After", delay)
                logger.warning("Azure rate-limited. Retrying in %.1fs…", float(retry_after))
                time.sleep(float(retry_after))
            else:
                raise
    raise RuntimeError(f"Azure call failed after {max_retries} retries.")


# ---------------------------------------------------------------------------
# Main collection functions
# ---------------------------------------------------------------------------


def collect_cost_data() -> List[Dict[str, Any]]:
    """
    Fetch the current month's daily cost data from Azure Cost Management API,
    grouped by SERVICE_NAME and RESOURCE_LOCATION, and persist to MongoDB.

    Returns the list of stored billing records.
    """
    from backend.database.mongodb import get_db
    from pymongo import UpdateOne

    if not all([_SUBSCRIPTION_ID, _TENANT_ID, _CLIENT_ID, _CLIENT_SECRET]):
        logger.warning(
            "Azure credentials not configured (AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, "
            "AZURE_CLIENT_ID, AZURE_CLIENT_SECRET). Skipping Azure data collection."
        )
        return []

    try:
        from azure.mgmt.costmanagement import CostManagementClient  # type: ignore
        from azure.mgmt.costmanagement.models import (  # type: ignore
            QueryDefinition,
            QueryTimePeriod,
            QueryDataset,
            QueryAggregation,
            QueryGrouping,
        )
    except ImportError:
        logger.error(
            "azure-mgmt-costmanagement not installed. "
            "Run: pip install azure-mgmt-costmanagement azure-identity"
        )
        return []

    credential = _get_credential()
    client = CostManagementClient(credential)

    now = datetime.now(timezone.utc)
    start = now.replace(day=1).strftime("%Y-%m-%dT00:00:00Z")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    scope = f"/subscriptions/{_SUBSCRIPTION_ID}"

    logger.info("Collecting Azure cost data from %s to %s", start, end)

    query = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(from_property=start, to=end),
        dataset=QueryDataset(
            granularity="Daily",
            aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            grouping=[
                QueryGrouping(type="Dimension", name="ServiceName"),
                QueryGrouping(type="Dimension", name="ResourceLocation"),
            ],
        ),
    )

    all_rows: List[Any] = []
    try:
        result = _with_backoff(client.query.usage, scope=scope, parameters=query)
        columns = [col.name for col in result.columns]
        all_rows = result.rows or []
    except Exception as exc:
        logger.error("Failed to fetch Azure cost data: %s", exc)
        return []

    # Map column names to indices
    col_idx = {name: i for i, name in enumerate(columns)}
    cost_idx = col_idx.get("Cost", col_idx.get("totalCost", 0))
    service_idx = col_idx.get("ServiceName", 1)
    location_idx = col_idx.get("ResourceLocation", 2)
    date_idx = col_idx.get("UsageDate", col_idx.get("BillingMonth", 3))

    db = get_db()
    records: List[Dict[str, Any]] = []

    for row in all_rows:
        try:
            raw_date = str(row[date_idx])
            if len(raw_date) == 8:
                period_start = datetime.strptime(raw_date, "%Y%m%d").replace(tzinfo=timezone.utc)
            else:
                period_start = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except (ValueError, IndexError):
            period_start = datetime.now(timezone.utc)

        service = str(row[service_idx]) if service_idx < len(row) else "Unknown"
        region = str(row[location_idx]) if location_idx < len(row) else "global"
        cost = float(row[cost_idx]) if cost_idx < len(row) else 0.0

        record: Dict[str, Any] = {
            "provider": "azure",
            "timestamp": period_start,
            "service": service,
            "region": region,
            "cost": cost,
            "usage_quantity": 0.0,
            "currency": "USD",
            "created_at": datetime.now(timezone.utc),
        }
        records.append(record)

    if records:
        try:
            ops = [
                UpdateOne(
                    {"provider": r["provider"], "timestamp": r["timestamp"], "service": r["service"], "region": r["region"]},
                    {"$set": r},
                    upsert=True,
                )
                for r in records
            ]
            result = db["billing_raw"].bulk_write(ops, ordered=False)
            logger.info(
                "Azure: upserted %d billing records (%d inserted, %d updated).",
                len(records), result.upserted_count, result.modified_count,
            )
        except Exception as exc:
            logger.error("Failed to store Azure billing records: %s", exc)

    return records


def collect_azure_monitor_metrics(
    resource_ids: List[str],
    metric_name: str = "Percentage CPU",
    hours: int = 24,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch a metric (e.g. Percentage CPU) for the given Azure resource IDs
    over the last *hours* hours from Azure Monitor.

    Returns a dict mapping resource_id -> list of {timestamp, average} dicts.
    """
    if not all([_TENANT_ID, _CLIENT_ID, _CLIENT_SECRET]):
        logger.warning("Azure credentials not configured — skipping Monitor metrics.")
        return {}

    try:
        from azure.mgmt.monitor import MonitorManagementClient  # type: ignore
    except ImportError:
        logger.error("azure-mgmt-monitor not installed. Run: pip install azure-mgmt-monitor")
        return {}

    credential = _get_credential()
    monitor_client = MonitorManagementClient(credential, _SUBSCRIPTION_ID)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)
    results: Dict[str, List[Dict[str, Any]]] = {}

    for resource_id in resource_ids:
        try:
            response = _with_backoff(
                monitor_client.metrics.list,
                resource_uri=resource_id,
                timespan=f"{start_time.isoformat()}/{now.isoformat()}",
                interval="PT1H",
                metricnames=metric_name,
                aggregation="Average",
            )
            datapoints = []
            for metric in response.value:
                for ts in metric.timeseries or []:
                    for dp in ts.data or []:
                        if dp.average is not None:
                            datapoints.append({
                                "timestamp": dp.time_stamp.isoformat(),
                                "average": dp.average,
                            })
            results[resource_id] = sorted(datapoints, key=lambda d: d["timestamp"])
        except Exception as exc:
            logger.warning("Azure Monitor error for %s: %s", resource_id, exc)
            results[resource_id] = []

    logger.info("Collected Azure Monitor metrics for %d resources.", len(resource_ids))
    return results


def collect_activity_log_events(hours: int = 1) -> List[Dict[str, Any]]:
    """
    Fetch recent Azure Activity Log events (write operations only) that
    could indicate infrastructure changes causing cost spikes.

    Returns a list of simplified event dicts.
    """
    if not all([_SUBSCRIPTION_ID, _TENANT_ID, _CLIENT_ID, _CLIENT_SECRET]):
        logger.warning("Azure credentials not configured — skipping Activity Log.")
        return []

    try:
        from azure.mgmt.monitor import MonitorManagementClient  # type: ignore
    except ImportError:
        logger.error("azure-mgmt-monitor not installed.")
        return []

    credential = _get_credential()
    monitor_client = MonitorManagementClient(credential, _SUBSCRIPTION_ID)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    relevant_operations = {
        "Microsoft.Compute/virtualMachines/write",
        "Microsoft.Compute/virtualMachines/start/action",
        "Microsoft.Compute/virtualMachines/deallocate/action",
        "Microsoft.Compute/virtualMachineScaleSets/write",
        "Microsoft.DBforPostgreSQL/servers/write",
        "Microsoft.Sql/servers/databases/write",
        "Microsoft.Storage/storageAccounts/write",
        "Microsoft.Network/loadBalancers/write",
        "Microsoft.Cache/Redis/write",
        "Microsoft.DocumentDB/databaseAccounts/write",
        "Microsoft.Web/sites/write",
    }

    events: List[Dict[str, Any]] = []

    try:
        filter_str = (
            f"eventTimestamp ge '{start_time.isoformat()}' "
            f"and eventTimestamp le '{now.isoformat()}' "
            f"and status/value eq 'Succeeded'"
        )
        activity_logs = _with_backoff(
            monitor_client.activity_logs.list,
            filter=filter_str,
            select="eventTimestamp,operationName,caller,resourceId,level",
        )

        for event in activity_logs:
            op_name = getattr(getattr(event, "operation_name", None), "value", "") or ""
            if op_name not in relevant_operations:
                continue
            events.append({
                "event_time": event.event_timestamp.isoformat() if event.event_timestamp else "",
                "operation": op_name,
                "caller": getattr(event, "caller", "Unknown"),
                "resource_id": getattr(event, "resource_id", ""),
                "level": getattr(getattr(event, "level", None), "value", ""),
            })
    except Exception as exc:
        logger.error("Azure Activity Log lookup failed: %s", exc)

    logger.info("Collected %d relevant Azure Activity Log events.", len(events))
    return events


def get_idle_vm_instances(cpu_threshold: float = 5.0, hours: int = 24) -> List[str]:
    """
    Return Azure VM resource IDs where average CPU over the last *hours* is below
    *cpu_threshold* percent.
    """
    if not all([_SUBSCRIPTION_ID, _TENANT_ID, _CLIENT_ID, _CLIENT_SECRET]):
        return []

    try:
        from azure.mgmt.compute import ComputeManagementClient  # type: ignore
    except ImportError:
        logger.error("azure-mgmt-compute not installed. Run: pip install azure-mgmt-compute")
        return []

    credential = _get_credential()
    compute_client = ComputeManagementClient(credential, _SUBSCRIPTION_ID)

    try:
        vms = list(_with_backoff(compute_client.virtual_machines.list_all))
    except Exception as exc:
        logger.error("Azure VM list failed: %s", exc)
        return []

    resource_ids = [vm.id for vm in vms if vm.id]
    if not resource_ids:
        return []

    metrics = collect_azure_monitor_metrics(resource_ids, metric_name="Percentage CPU", hours=hours)
    idle = []
    for resource_id, datapoints in metrics.items():
        if not datapoints:
            continue
        avg_cpu = sum(d["average"] for d in datapoints) / len(datapoints)
        if avg_cpu < cpu_threshold:
            idle.append(resource_id)

    logger.info("Found %d idle Azure VMs (CPU < %.1f%%).", len(idle), cpu_threshold)
    return idle
