"""
Agent 1 — GCP Data Collector
Fetches cost data from GCP Cloud Billing API, Cloud Monitoring metrics,
and Cloud Audit Logs.
All credentials loaded from environment variables.

Required env vars:
    GCP_PROJECT_ID              — GCP project ID
    GCP_BILLING_ACCOUNT_ID      — Cloud Billing account ID (e.g. 01ABCD-123456-ABCDEF)
    GOOGLE_APPLICATION_CREDENTIALS — Path to service account JSON key file
                                     OR set GCP_SERVICE_ACCOUNT_JSON with the JSON content
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GCP credentials (loaded from environment)
# ---------------------------------------------------------------------------

_PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "")
_BILLING_ACCOUNT_ID: str = os.environ.get("GCP_BILLING_ACCOUNT_ID", "")

# Support inline JSON credentials as well as the standard file path
_SA_JSON_CONTENT: str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")


def _get_credentials():
    """Return GCP service account credentials."""
    from google.oauth2 import service_account  # type: ignore

    if _SA_JSON_CONTENT:
        info = json.loads(_SA_JSON_CONTENT)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    # Fall back to GOOGLE_APPLICATION_CREDENTIALS env var / ADC
    import google.auth  # type: ignore
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return credentials


def _with_backoff(fn, *args, max_retries: int = 5, base_delay: float = 1.0, **kwargs):
    """Call *fn* with exponential back-off on quota/rate errors."""
    from googleapiclient.errors import HttpError  # type: ignore

    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except HttpError as exc:
            if exc.resp.status in (429, 503):
                delay = base_delay * (2 ** attempt)
                logger.warning("GCP rate-limited (%d). Retrying in %.1fs…", exc.resp.status, delay)
                time.sleep(delay)
            else:
                raise
    raise RuntimeError(f"GCP call failed after {max_retries} retries.")


# ---------------------------------------------------------------------------
# Main collection functions
# ---------------------------------------------------------------------------


def collect_cost_data() -> List[Dict[str, Any]]:
    """
    Fetch the current month's daily cost data from GCP Cloud Billing API
    using BigQuery export (recommended) or the Billing Budgets API fallback.
    Groups by SKU description (service) and region, persists to MongoDB.

    Returns the list of stored billing records.
    """
    from backend.database.mongodb import get_db
    from pymongo import UpdateOne

    if not _PROJECT_ID:
        logger.warning(
            "GCP credentials not configured (GCP_PROJECT_ID required). "
            "Skipping GCP data collection."
        )
        return []

    try:
        from google.cloud import bigquery  # type: ignore
    except ImportError:
        logger.error(
            "google-cloud-bigquery not installed. "
            "Run: pip install google-cloud-bigquery google-cloud-monitoring google-auth"
        )
        return []

    credentials = _get_credentials()
    bq_client = bigquery.Client(project=_PROJECT_ID, credentials=credentials)

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    month_end = now.strftime("%Y-%m-%d")

    # Standard GCP billing export table naming: <project>.<dataset>.gcp_billing_export_v1_*
    # Users configure their billing export dataset — we use an environment variable as override.
    billing_dataset = os.environ.get("GCP_BILLING_DATASET", f"{_PROJECT_ID}.billing_export")

    logger.info("Collecting GCP cost data from %s to %s", month_start, month_end)

    query = f"""
        SELECT
            DATE(usage_start_time) AS usage_date,
            service.description    AS service_name,
            location.region        AS region,
            SUM(cost)              AS total_cost,
            SUM(usage.amount)      AS usage_quantity
        FROM `{billing_dataset}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) BETWEEN '{month_start}' AND '{month_end}'
        GROUP BY usage_date, service_name, region
        ORDER BY usage_date, total_cost DESC
    """

    all_rows: List[Any] = []
    try:
        job = bq_client.query(query)
        all_rows = list(_with_backoff(job.result))
    except Exception as exc:
        logger.error("Failed to fetch GCP billing data from BigQuery: %s", exc)
        return []

    db = get_db()
    records: List[Dict[str, Any]] = []

    for row in all_rows:
        try:
            period_start = datetime.combine(row.usage_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        except Exception:
            period_start = datetime.now(timezone.utc)

        service = str(row.service_name) if row.service_name else "Unknown"
        region = str(row.region) if row.region else "global"
        cost = float(row.total_cost) if row.total_cost else 0.0
        usage = float(row.usage_quantity) if row.usage_quantity else 0.0

        record: Dict[str, Any] = {
            "provider": "gcp",
            "timestamp": period_start,
            "service": service,
            "region": region,
            "cost": cost,
            "usage_quantity": usage,
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
                "GCP: upserted %d billing records (%d inserted, %d updated).",
                len(records), result.upserted_count, result.modified_count,
            )
        except Exception as exc:
            logger.error("Failed to store GCP billing records: %s", exc)

    return records


def collect_cloud_monitoring_metrics(
    resource_names: List[str],
    metric_type: str = "compute.googleapis.com/instance/cpu/utilization",
    hours: int = 24,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch a metric for the given GCP resource names over the last *hours* hours
    from Cloud Monitoring.

    Returns a dict mapping resource_name -> list of {timestamp, value} dicts.
    """
    if not _PROJECT_ID:
        return {}

    try:
        from google.cloud import monitoring_v3  # type: ignore
    except ImportError:
        logger.error("google-cloud-monitoring not installed. Run: pip install google-cloud-monitoring")
        return {}

    credentials = _get_credentials()
    monitoring_client = monitoring_v3.MetricServiceClient(credentials=credentials)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)
    project_name = f"projects/{_PROJECT_ID}"

    results: Dict[str, List[Dict[str, Any]]] = {}

    for resource_name in resource_names:
        try:
            interval = monitoring_v3.TimeInterval(
                end_time={"seconds": int(now.timestamp())},
                start_time={"seconds": int(start_time.timestamp())},
            )
            aggregation = monitoring_v3.Aggregation(
                alignment_period={"seconds": 3600},
                per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
            )
            filter_str = (
                f'metric.type = "{metric_type}" '
                f'AND resource.labels.instance_name = "{resource_name}"'
            )
            time_series = monitoring_client.list_time_series(
                request={
                    "name": project_name,
                    "filter": filter_str,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    "aggregation": aggregation,
                }
            )
            datapoints = []
            for series in time_series:
                for point in series.points:
                    datapoints.append({
                        "timestamp": datetime.fromtimestamp(
                            point.interval.end_time.timestamp(), tz=timezone.utc
                        ).isoformat(),
                        "value": point.value.double_value,
                    })
            results[resource_name] = sorted(datapoints, key=lambda d: d["timestamp"])
        except Exception as exc:
            logger.warning("Cloud Monitoring error for %s: %s", resource_name, exc)
            results[resource_name] = []

    logger.info("Collected GCP Cloud Monitoring metrics for %d resources.", len(resource_names))
    return results


def collect_audit_log_events(hours: int = 1) -> List[Dict[str, Any]]:
    """
    Fetch recent GCP Cloud Audit Log entries (admin activity) that could
    indicate infrastructure changes causing cost spikes.

    Returns a list of simplified event dicts.
    """
    if not _PROJECT_ID:
        logger.warning("GCP_PROJECT_ID not configured — skipping Audit Log.")
        return []

    try:
        from google.cloud import logging as gcp_logging  # type: ignore
    except ImportError:
        logger.error("google-cloud-logging not installed. Run: pip install google-cloud-logging")
        return []

    credentials = _get_credentials()
    log_client = gcp_logging.Client(project=_PROJECT_ID, credentials=credentials)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    relevant_methods = {
        "v1.compute.instances.insert",
        "v1.compute.instances.delete",
        "v1.compute.instances.start",
        "v1.compute.instances.stop",
        "v1.compute.autoscalers.insert",
        "v1.compute.autoscalers.update",
        "google.cloud.sql.v1.SqlInstancesService.Insert",
        "google.cloud.sql.v1.SqlInstancesService.Update",
        "storage.buckets.create",
        "storage.buckets.delete",
        "google.cloud.functions.v1.CloudFunctionsService.CreateFunction",
        "google.cloud.functions.v1.CloudFunctionsService.UpdateFunction",
        "google.dataflow.v1b3.Jobs.CreateJob",
    }

    events: List[Dict[str, Any]] = []

    try:
        filter_str = (
            f'logName="projects/{_PROJECT_ID}/logs/cloudaudit.googleapis.com%2Factivity" '
            f'timestamp>="{start_time.isoformat()}" '
            f'timestamp<="{now.isoformat()}" '
            f'severity>=DEFAULT'
        )
        entries = log_client.list_entries(
            filter_=filter_str,
            order_by=gcp_logging.DESCENDING,
            max_results=500,
        )

        for entry in entries:
            method_name = ""
            if hasattr(entry, "proto_payload") and entry.proto_payload:
                method_name = entry.proto_payload.get("methodName", "")
            elif isinstance(entry.payload, dict):
                method_name = entry.payload.get("methodName", "")

            if method_name not in relevant_methods:
                continue

            principal = ""
            if hasattr(entry, "proto_payload") and entry.proto_payload:
                auth_info = entry.proto_payload.get("authenticationInfo", {})
                principal = auth_info.get("principalEmail", "Unknown")

            events.append({
                "event_time": entry.timestamp.isoformat() if entry.timestamp else "",
                "method": method_name,
                "principal": principal,
                "resource": str(entry.resource) if entry.resource else "",
                "severity": str(entry.severity) if entry.severity else "DEFAULT",
            })
    except Exception as exc:
        logger.error("GCP Audit Log lookup failed: %s", exc)

    logger.info("Collected %d relevant GCP Audit Log events.", len(events))
    return events


def get_idle_compute_instances(cpu_threshold: float = 5.0, hours: int = 24) -> List[str]:
    """
    Return GCP Compute Engine instance names where average CPU over the last
    *hours* hours is below *cpu_threshold* percent.
    """
    if not _PROJECT_ID:
        return []

    try:
        from google.cloud import compute_v1  # type: ignore
    except ImportError:
        logger.error("google-cloud-compute not installed. Run: pip install google-cloud-compute")
        return []

    credentials = _get_credentials()
    instances_client = compute_v1.InstancesClient(credentials=credentials)

    try:
        all_instances = []
        request = compute_v1.AggregatedListInstancesRequest(project=_PROJECT_ID)
        for zone, response in instances_client.aggregated_list(request=request):
            if response.instances:
                all_instances.extend(
                    [i.name for i in response.instances if i.status == "RUNNING"]
                )
    except Exception as exc:
        logger.error("GCP instance list failed: %s", exc)
        return []

    if not all_instances:
        return []

    metrics = collect_cloud_monitoring_metrics(
        all_instances,
        metric_type="compute.googleapis.com/instance/cpu/utilization",
        hours=hours,
    )

    idle = []
    for instance_name, datapoints in metrics.items():
        if not datapoints:
            continue
        avg_cpu = sum(d["value"] * 100 for d in datapoints) / len(datapoints)  # 0–1 → 0–100
        if avg_cpu < cpu_threshold:
            idle.append(instance_name)

    logger.info("Found %d idle GCP instances (CPU < %.1f%%).", len(idle), cpu_threshold)
    return idle
