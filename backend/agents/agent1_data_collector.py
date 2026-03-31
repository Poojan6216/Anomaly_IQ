"""
Agent 1 — AWS Data Collector
Fetches cost data from AWS Cost Explorer, CloudWatch metrics and CloudTrail events.
All credentials loaded from environment variables.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AWS client helpers
# ---------------------------------------------------------------------------

_AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
_AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
_AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")


def _boto_client(service: str, region: Optional[str] = None) -> Any:
    return boto3.client(
        service,
        aws_access_key_id=_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=_AWS_SECRET_ACCESS_KEY,
        region_name=region or _AWS_REGION,
    )


def _with_backoff(fn, *args, max_retries: int = 5, base_delay: float = 1.0, **kwargs):
    """Call *fn* with exponential back-off on throttling errors."""
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("Throttling", "ThrottlingException", "RequestLimitExceeded"):
                delay = base_delay * (2 ** attempt)
                logger.warning("Rate-limited by AWS (%s). Retrying in %.1fs…", code, delay)
                time.sleep(delay)
            else:
                raise
    raise RuntimeError(f"AWS call failed after {max_retries} retries.")


# ---------------------------------------------------------------------------
# Main collection functions
# ---------------------------------------------------------------------------


def collect_cost_data() -> List[Dict[str, Any]]:
    """
    Fetch the last 14 days of daily cost data from AWS Cost Explorer,
    grouped by SERVICE and REGION, and persist to MongoDB.

    Returns the list of stored billing records.
    """
    from backend.database.mongodb import get_db  # lazy import to avoid circular deps

    ce = _boto_client("ce", region="us-east-1")  # Cost Explorer is global

    now = datetime.now(timezone.utc)
    # Collect from the start of the current month so MTD matches the AWS console
    start = now.replace(day=1).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    logger.info("Collecting cost data from %s to %s", start, end)

    all_results: List[Any] = []
    next_page_token: Optional[str] = None

    try:
        while True:
            kwargs: Dict[str, Any] = dict(
                TimePeriod={"Start": start, "End": end},
                Granularity="DAILY",
                Metrics=["UnblendedCost", "UsageQuantity"],
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "DIMENSION", "Key": "REGION"},
                ],
            )
            if next_page_token:
                kwargs["NextPageToken"] = next_page_token

            response = _with_backoff(ce.get_cost_and_usage, **kwargs)
            all_results.extend(response.get("ResultsByTime", []))
            next_page_token = response.get("NextPageToken")
            if not next_page_token:
                break
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("Failed to fetch cost data: %s", exc)
        return []

    db = get_db()
    records: List[Dict[str, Any]] = []

    for result in all_results:
        period_start_str = result["TimePeriod"]["Start"]
        try:
            # Daily granularity returns "YYYY-MM-DD"; hourly returns full ISO
            if "T" in period_start_str:
                period_start = datetime.fromisoformat(period_start_str.replace("Z", "+00:00"))
            else:
                period_start = datetime.strptime(period_start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            period_start = datetime.now(timezone.utc)

        for group in result.get("Groups", []):
            keys = group.get("Keys", [])
            service = keys[0] if len(keys) > 0 else "Unknown"
            region = keys[1] if len(keys) > 1 else "global"

            metrics = group.get("Metrics", {})
            cost = float(metrics.get("UnblendedCost", {}).get("Amount", 0))
            usage = float(metrics.get("UsageQuantity", {}).get("Amount", 0))

            record: Dict[str, Any] = {
                "provider": "aws",
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
            from pymongo import UpdateOne
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
                "Upserted %d billing records (%d inserted, %d updated).",
                len(records), result.upserted_count, result.modified_count,
            )
        except Exception as exc:
            logger.error("Failed to store billing records: %s", exc)

    return records


def collect_cloudwatch_metrics(
    instance_ids: List[str],
    hours: int = 24,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch CPUUtilization for the given EC2 instance IDs over the last *hours* hours.

    Returns a dict mapping instance_id -> list of {Timestamp, Average} dicts.
    """
    cw = _boto_client("cloudwatch")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    metrics: Dict[str, List[Dict[str, Any]]] = {}

    for instance_id in instance_ids:
        try:
            response = _with_backoff(
                cw.get_metric_statistics,
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=now,
                Period=3600,  # 1-hour granularity
                Statistics=["Average", "Maximum"],
            )
            datapoints = sorted(
                response.get("Datapoints", []),
                key=lambda d: d["Timestamp"],
            )
            metrics[instance_id] = [
                {
                    "timestamp": dp["Timestamp"].isoformat(),
                    "average_cpu": dp.get("Average", 0),
                    "max_cpu": dp.get("Maximum", 0),
                }
                for dp in datapoints
            ]
        except (ClientError, EndpointConnectionError) as exc:
            logger.warning("CloudWatch error for %s: %s", instance_id, exc)
            metrics[instance_id] = []

    logger.info("Collected CloudWatch metrics for %d instances.", len(instance_ids))
    return metrics


def collect_cloudtrail_events(hours: int = 1) -> List[Dict[str, Any]]:
    """
    Look up recent CloudTrail management events (write-only) filtered to
    relevant AWS actions that could cause cost spikes.

    Returns a list of simplified event dicts.
    """
    ct = _boto_client("cloudtrail")

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    relevant_actions = {
        "RunInstances",
        "TerminateInstances",
        "StopInstances",
        "StartInstances",
        "CreateBucket",
        "DeleteBucket",
        "PutBucketPolicy",
        "CreateDBInstance",
        "DeleteDBInstance",
        "CreateCluster",
        "DeleteCluster",
        "CreateLoadBalancer",
        "DeleteLoadBalancer",
        "CreateNatGateway",
        "DeleteNatGateway",
        "CreateVpnConnection",
        "AllocateAddress",
        "ReleaseAddress",
        "CreateVolume",
        "DeleteVolume",
        "PutScalingPolicy",
        "CreateAutoScalingGroup",
        "UpdateAutoScalingGroup",
    }

    events: List[Dict[str, Any]] = []

    try:
        paginator = ct.get_paginator("lookup_events")
        page_iterator = _with_backoff(
            paginator.paginate,
            StartTime=start_time,
            EndTime=now,
            LookupAttributes=[{"AttributeKey": "ReadOnly", "AttributeValue": "false"}],
        )

        for page in page_iterator:
            for event in page.get("Events", []):
                event_name = event.get("EventName", "")
                if event_name not in relevant_actions:
                    continue
                events.append(
                    {
                        "event_id": event.get("EventId", ""),
                        "event_name": event_name,
                        "event_time": event.get("EventTime", now).isoformat()
                        if hasattr(event.get("EventTime"), "isoformat")
                        else str(event.get("EventTime", "")),
                        "username": event.get("Username", "Unknown"),
                        "source_ip": event.get("SourceIPAddress", ""),
                        "resources": [
                            {
                                "type": r.get("ResourceType", ""),
                                "name": r.get("ResourceName", ""),
                            }
                            for r in event.get("Resources", []) or []
                        ],
                    }
                )
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("CloudTrail lookup failed: %s", exc)

    logger.info("Collected %d relevant CloudTrail events.", len(events))
    return events


def get_idle_ec2_instances(cpu_threshold: float = 5.0, hours: int = 24) -> List[str]:
    """
    Return instance IDs where average CPU over the last *hours* hours is below
    *cpu_threshold* percent.
    """
    ec2 = _boto_client("ec2")

    try:
        response = ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("EC2 describe_instances failed: %s", exc)
        return []

    instance_ids = [
        i["InstanceId"]
        for r in response.get("Reservations", [])
        for i in r.get("Instances", [])
    ]

    if not instance_ids:
        return []

    metrics = collect_cloudwatch_metrics(instance_ids, hours=hours)
    idle = []
    for iid, datapoints in metrics.items():
        if not datapoints:
            continue
        avg_cpu = sum(d["average_cpu"] for d in datapoints) / len(datapoints)
        if avg_cpu < cpu_threshold:
            idle.append(iid)

    logger.info("Found %d idle EC2 instances (CPU < %.1f%%).", len(idle), cpu_threshold)
    return idle
