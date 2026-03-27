"""
AnomalyIQ Mock Data Generator
Generates realistic MongoDB-ready JSON files for all 8 collections.
Today's date: 2026-03-26
Run: python generate_mock_data.py
Import: mongoimport --db anomalyiq --collection <name> --file <name>.json --jsonArray
"""

import json
import math
import random
from datetime import datetime, timedelta, timezone

random.seed(42)

OUTPUT_DIR = "."

# ── Fixed ObjectId strings (24-char hex) ──────────────────────────────────────
A_IDS = [
    "65f1a2b3c4d5e6f789012340",  # EC2 Critical  Mar-15
    "65f1a2b3c4d5e6f789012341",  # RDS High      Mar-20
    "65f1a2b3c4d5e6f789012342",  # Lambda Medium Mar-22
    "65f1a2b3c4d5e6f789012343",  # CloudFront Hi Mar-24
    "65f1a2b3c4d5e6f789012344",  # S3 Low        Mar-25
    "65f1a2b3c4d5e6f789012345",  # EC2 High      Mar-26
]
B_IDS = [
    "65f1a2b3c4d5e6f789012350",
    "65f1a2b3c4d5e6f789012351",
    "65f1a2b3c4d5e6f789012352",
    "65f1a2b3c4d5e6f789012353",
]
REC_IDS = [f"65f1a2b3c4d5e6f78901236{i}" for i in range(6)]
ALERT_IDS = [f"65f1a2b3c4d5e6f78901237{i}" for i in range(8)]
FORECAST_ID = "65f1a2b3c4d5e6f789012380"

NOW = datetime(2026, 3, 26, 12, 0, 0, tzinfo=timezone.utc)


def oid(hex_str):
    return {"$oid": hex_str}


def dt(d: datetime):
    return {"$date": d.strftime("%Y-%m-%dT%H:%M:%SZ")}


# ── Base hourly cost per service (USD) ────────────────────────────────────────
SERVICES = {
    "Amazon EC2":         {"base": 2.50, "region": "us-east-1"},
    "Amazon RDS":         {"base": 1.00, "region": "us-east-1"},
    "Amazon S3":          {"base": 0.40, "region": "us-east-1"},
    "Amazon CloudFront":  {"base": 0.30, "region": "us-east-1"},
    "AWS Lambda":         {"base": 0.25, "region": "us-west-2"},
    "Amazon DynamoDB":    {"base": 0.17, "region": "us-east-1"},
    "Amazon ElastiCache": {"base": 0.13, "region": "us-east-1"},
    "AWS Glue":           {"base": 0.08, "region": "us-east-2"},
}

# Anomaly spikes: {(service, date_str, hour): cost_multiplier}
SPIKES = {
    ("Amazon EC2",        "2026-03-15", 14): 138.0,
    ("Amazon RDS",        "2026-03-20",  9): 127.0,
    ("AWS Lambda",        "2026-03-22", 16): 168.0,
    ("Amazon CloudFront", "2026-03-24", 20): 285.0,
    ("Amazon S3",         "2026-03-25", 10):  68.0,
    ("Amazon EC2",        "2026-03-26",  8):  92.0,
}


def noisy(base, noise_pct=0.12):
    return round(base * (1 + random.uniform(-noise_pct, noise_pct)), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. aws_billing_raw
# ═══════════════════════════════════════════════════════════════════════════════
def gen_billing_raw():
    records = []

    # Feb 25 → Mar 23: one record per service per day (at 12:00 UTC)
    start = datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
    end_daily = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc)
    current = start
    while current < end_daily:
        date_str = current.strftime("%Y-%m-%d")
        for svc, cfg in SERVICES.items():
            cost = noisy(cfg["base"] * 24)
            records.append({
                "timestamp": dt(current),
                "service": svc,
                "region": cfg["region"],
                "cost": cost,
                "usage_quantity": round(cost / cfg["base"] * 0.8, 2),
                "currency": "USD",
                "created_at": dt(current + timedelta(minutes=5)),
            })
        current += timedelta(days=1)

    # Add spike records at exact hour for spike days in the daily range
    for (svc, date_str, hour), multiplier in SPIKES.items():
        spike_dt = datetime(
            int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10]),
            hour, 0, 0, tzinfo=timezone.utc
        )
        if spike_dt < end_daily:
            cfg = SERVICES[svc]
            spike_cost = round(cfg["base"] * multiplier, 4)
            records.append({
                "timestamp": dt(spike_dt),
                "service": svc,
                "region": cfg["region"],
                "cost": spike_cost,
                "usage_quantity": round(spike_cost / cfg["base"] * 0.8, 2),
                "currency": "USD",
                "created_at": dt(spike_dt + timedelta(minutes=3)),
            })

    # Mar 24 → Mar 26 12:00: hourly records (shows nicely on AnomalyTimeline)
    current = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc)
    while current <= NOW:
        date_str = current.strftime("%Y-%m-%d")
        hour = current.hour
        for svc, cfg in SERVICES.items():
            spike_key = (svc, date_str, hour)
            if spike_key in SPIKES:
                cost = round(cfg["base"] * SPIKES[spike_key], 4)
            else:
                time_factor = 1.0 + 0.15 * math.sin(math.pi * hour / 12)
                cost = noisy(cfg["base"] * time_factor)
            records.append({
                "timestamp": dt(current),
                "service": svc,
                "region": cfg["region"],
                "cost": cost,
                "usage_quantity": round(cost / cfg["base"] * 0.8, 2),
                "currency": "USD",
                "created_at": dt(current + timedelta(minutes=2)),
            })
        current += timedelta(hours=1)

    return records


# ═══════════════════════════════════════════════════════════════════════════════
# 2. anomalies_detected
# ═══════════════════════════════════════════════════════════════════════════════
ANOMALY_DEFS = [
    {
        "_id": oid(A_IDS[0]),
        "timestamp": dt(datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)),
        "severity": "Critical",
        "service": "Amazon EC2",
        "region": "us-east-1",
        "baseline_cost": 2.52,
        "actual_cost": 345.82,
        "cost_delta": 343.30,
        "percentage_increase": 13623.0,
        "detection_methods": ["isolation_forest", "zscore"],
        "status": "resolved",
        "created_at": dt(datetime(2026, 3, 15, 14, 5, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(A_IDS[1]),
        "timestamp": dt(datetime(2026, 3, 20, 9, 0, tzinfo=timezone.utc)),
        "severity": "High",
        "service": "Amazon RDS",
        "region": "us-east-1",
        "baseline_cost": 1.01,
        "actual_cost": 128.47,
        "cost_delta": 127.46,
        "percentage_increase": 12620.0,
        "detection_methods": ["isolation_forest", "zscore"],
        "status": "resolved",
        "created_at": dt(datetime(2026, 3, 20, 9, 5, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(A_IDS[2]),
        "timestamp": dt(datetime(2026, 3, 22, 16, 0, tzinfo=timezone.utc)),
        "severity": "Medium",
        "service": "AWS Lambda",
        "region": "us-west-2",
        "baseline_cost": 0.25,
        "actual_cost": 42.03,
        "cost_delta": 41.78,
        "percentage_increase": 16712.0,
        "detection_methods": ["zscore"],
        "status": "acknowledged",
        "created_at": dt(datetime(2026, 3, 22, 16, 5, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(A_IDS[3]),
        "timestamp": dt(datetime(2026, 3, 24, 20, 0, tzinfo=timezone.utc)),
        "severity": "High",
        "service": "Amazon CloudFront",
        "region": "us-east-1",
        "baseline_cost": 0.30,
        "actual_cost": 85.62,
        "cost_delta": 85.32,
        "percentage_increase": 28440.0,
        "detection_methods": ["isolation_forest", "zscore", "rolling_window"],
        "status": "open",
        "created_at": dt(datetime(2026, 3, 24, 20, 5, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(A_IDS[4]),
        "timestamp": dt(datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)),
        "severity": "Low",
        "service": "Amazon S3",
        "region": "us-east-1",
        "baseline_cost": 0.41,
        "actual_cost": 27.88,
        "cost_delta": 27.47,
        "percentage_increase": 6699.0,
        "detection_methods": ["rolling_window"],
        "status": "open",
        "created_at": dt(datetime(2026, 3, 25, 10, 5, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(A_IDS[5]),
        "timestamp": dt(datetime(2026, 3, 26, 8, 0, tzinfo=timezone.utc)),
        "severity": "High",
        "service": "Amazon EC2",
        "region": "us-east-1",
        "baseline_cost": 2.49,
        "actual_cost": 229.38,
        "cost_delta": 226.89,
        "percentage_increase": 9112.0,
        "detection_methods": ["isolation_forest", "zscore"],
        "status": "open",
        "created_at": dt(datetime(2026, 3, 26, 8, 5, tzinfo=timezone.utc)),
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. root_cause_analysis
# ═══════════════════════════════════════════════════════════════════════════════
RCA_DEFS = [
    {
        "anomaly_id": A_IDS[0],
        "explanation": (
            "A fleet of 47 unauthorized g4dn.12xlarge GPU instances was launched in us-east-1 at "
            "14:02 UTC on March 15. These instances were not provisioned by any known CI/CD pipeline "
            "or infrastructure-as-code change. CloudTrail logs reveal the instances were created via "
            "the root account using an API key last rotated 8 months ago. The workload pattern "
            "(100% GPU utilization, no VPC egress) is consistent with cryptocurrency mining. "
            "The instances were terminated at 17:34 UTC after the alert was acknowledged."
        ),
        "evidence": {
            "instance_count": 47,
            "instance_type": "g4dn.12xlarge",
            "launched_by": "root (AccessKeyId: AKIAIOSFODNN7EXAMPLE)",
            "cloudtrail_event": "RunInstances",
            "gpu_utilization_avg": "99.8%",
            "vpc_egress_gb": 0.0,
        },
        "confidence": 0.97,
        "is_legitimate": False,
        "created_at": dt(datetime(2026, 3, 15, 14, 12, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[1],
        "explanation": (
            "An unoptimized analytical query was deployed to the production RDS PostgreSQL cluster "
            "(db.r6g.2xlarge) at 08:47 UTC on March 20 as part of a data migration job. The query "
            "performed a full sequential scan on the 'events' table (1.8 TB) without using available "
            "indexes, triggering 127 IOPS bursts and sustained high CPU. The database auto-scaled "
            "read replicas three times, each adding ~$42/hr. The query was killed at 11:15 UTC and "
            "the migration was rescheduled with proper index hints."
        ),
        "evidence": {
            "query_type": "SELECT * full scan",
            "table": "events",
            "table_size_gb": 1800,
            "replicas_spawned": 3,
            "cpu_peak_pct": 97.4,
            "iops_burst_count": 127,
        },
        "confidence": 0.94,
        "is_legitimate": True,
        "created_at": dt(datetime(2026, 3, 20, 9, 18, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[2],
        "explanation": (
            "A recursive Lambda invocation loop was introduced by a deploy at 16:02 UTC on March 22. "
            "The image-processing function 'process-upload' was incorrectly configured to trigger on "
            "all S3 PUT events in the output bucket — including events it generated itself. Within "
            "14 minutes the function had self-invoked 168,420 times at an average duration of 3.2s. "
            "AWS service limits eventually throttled the invocations. The S3 trigger was corrected "
            "via a hotfix deploy at 16:48 UTC."
        ),
        "evidence": {
            "function_name": "process-upload",
            "total_invocations": 168420,
            "avg_duration_ms": 3200,
            "trigger": "S3 ObjectCreated (all)",
            "throttled_at": "2026-03-22T16:16:00Z",
        },
        "confidence": 0.99,
        "is_legitimate": False,
        "created_at": dt(datetime(2026, 3, 22, 16, 22, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[3],
        "explanation": (
            "A sustained DDoS attack targeting the /api/search endpoint caused CloudFront to serve "
            "2.4 TB of content between 20:00–22:45 UTC on March 24. The attack originated from "
            "8,400 unique IPs across 34 countries. CloudFront WAF rules were not configured to "
            "rate-limit unauthenticated search requests. AWS Shield Standard mitigated the volumetric "
            "component at 22:48 UTC. WAF rate-limiting rules have been deployed as an immediate fix."
        ),
        "evidence": {
            "traffic_tb": 2.4,
            "unique_ips": 8400,
            "countries": 34,
            "target_endpoint": "/api/search",
            "waf_rules_missing": "rate-limit unauthenticated",
            "shield_mitigation_utc": "2026-03-24T22:48:00Z",
        },
        "confidence": 0.91,
        "is_legitimate": False,
        "created_at": dt(datetime(2026, 3, 24, 20, 31, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[4],
        "explanation": (
            "A scheduled data export job transferred 6.8 TB of analytics data from S3 us-east-1 to "
            "a partner S3 bucket in eu-west-1 at 10:00 UTC on March 25. Cross-region data transfer "
            "fees of $0.02/GB applied. This is a legitimate quarterly export but the associated "
            "budget allocation was not updated to reflect the increased data volume. Recommend "
            "updating the S3 budget and notifying finance of the recurring quarterly charge."
        ),
        "evidence": {
            "transfer_gb": 6800,
            "source_region": "us-east-1",
            "dest_region": "eu-west-1",
            "transfer_rate_per_gb": 0.02,
            "job_name": "quarterly-partner-export",
        },
        "confidence": 0.88,
        "is_legitimate": True,
        "created_at": dt(datetime(2026, 3, 25, 10, 19, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[5],
        "explanation": (
            "A misconfigured Auto Scaling Group for the 'api-backend' service triggered a runaway "
            "scale-out event at 07:58 UTC on March 26. The CloudWatch alarm threshold was set to "
            "CPU > 5% (should be 70%), causing ASG to scale from 3 to 92 c6i.4xlarge instances "
            "within 6 minutes. The misconfiguration was introduced in a Terraform plan applied at "
            "07:45 UTC. The ASG was manually scaled back to 3 instances at 08:34 UTC and the "
            "Terraform state was corrected."
        ),
        "evidence": {
            "asg_name": "api-backend-asg",
            "scale_from": 3,
            "scale_to": 92,
            "instance_type": "c6i.4xlarge",
            "alarm_threshold_wrong": "CPU > 5%",
            "alarm_threshold_correct": "CPU > 70%",
            "terraform_apply_utc": "2026-03-26T07:45:00Z",
        },
        "confidence": 0.98,
        "is_legitimate": False,
        "created_at": dt(datetime(2026, 3, 26, 8, 17, tzinfo=timezone.utc)),
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. budgets
# ═══════════════════════════════════════════════════════════════════════════════
BUDGETS = [
    {
        "_id": oid(B_IDS[0]),
        "budget_type": "monthly",
        "name": "Total AWS Monthly Budget",
        "limit": 5000.0,
        "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
        "service_filter": None,
        "region_filter": None,
        "created_at": dt(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)),
        "updated_at": dt(datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(B_IDS[1]),
        "budget_type": "monthly",
        "name": "EC2 Compute Budget",
        "limit": 2200.0,
        "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
        "service_filter": "Amazon EC2",
        "region_filter": None,
        "created_at": dt(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)),
        "updated_at": dt(datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(B_IDS[2]),
        "budget_type": "monthly",
        "name": "RDS Database Budget",
        "limit": 800.0,
        "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
        "service_filter": "Amazon RDS",
        "region_filter": None,
        "created_at": dt(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)),
        "updated_at": dt(datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(B_IDS[3]),
        "budget_type": "daily",
        "name": "Lambda Daily Budget",
        "limit": 50.0,
        "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
        "service_filter": "AWS Lambda",
        "region_filter": None,
        "created_at": dt(datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)),
        "updated_at": dt(datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)),
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. forecasts
# ═══════════════════════════════════════════════════════════════════════════════
def gen_forecasts():
    predictions = []
    base_daily = sum(cfg["base"] for cfg in SERVICES.values()) * 24  # ~$116/day
    for i in range(31):
        day = NOW.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=i)
        trend = 1.0 + (i * 0.008)
        weekend_factor = 0.85 if day.weekday() >= 5 else 1.0
        yhat = round(base_daily * trend * weekend_factor, 2)
        margin = round(yhat * 0.12, 2)
        predictions.append({
            "ds": dt(day),
            "yhat": yhat,
            "yhat_lower": round(yhat - margin, 2),
            "yhat_upper": round(yhat + margin, 2),
        })
    return [{
        "_id": oid(FORECAST_ID),
        "forecast_date": dt(NOW),
        "service": "ALL",
        "horizon_days": 30,
        "model_used": "prophet",
        "predictions": predictions,
        "mape": 4.82,
        "created_at": dt(NOW),
    }]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. alerts_sent
# ═══════════════════════════════════════════════════════════════════════════════
ALERTS = [
    {
        "_id": oid(ALERT_IDS[0]),
        "timestamp": dt(datetime(2026, 3, 15, 14, 6, tzinfo=timezone.utc)),
        "channel": "email",
        "anomaly_id": A_IDS[0],
        "severity": "Critical",
        "message": "CRITICAL: Amazon EC2 cost spike detected in us-east-1. Actual cost $345.82 vs baseline $2.52 (+13,623%). Possible unauthorized GPU instances. Immediate investigation required.",
        "acknowledged": True,
        "acknowledged_at": dt(datetime(2026, 3, 15, 14, 38, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(ALERT_IDS[1]),
        "timestamp": dt(datetime(2026, 3, 15, 14, 7, tzinfo=timezone.utc)),
        "channel": "slack",
        "anomaly_id": A_IDS[0],
        "severity": "Critical",
        "message": "CRITICAL: Amazon EC2 cost spike in us-east-1. Actual $345.82 vs baseline $2.52 (+13,623%). Possible unauthorized GPU instances running.",
        "acknowledged": True,
        "acknowledged_at": dt(datetime(2026, 3, 15, 14, 40, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(ALERT_IDS[2]),
        "timestamp": dt(datetime(2026, 3, 20, 9, 6, tzinfo=timezone.utc)),
        "channel": "email",
        "anomaly_id": A_IDS[1],
        "severity": "High",
        "message": "HIGH: Amazon RDS cost spike in us-east-1. Actual $128.47 vs baseline $1.01 (+12,620%). Full table scan may be causing excessive read replica scaling.",
        "acknowledged": True,
        "acknowledged_at": dt(datetime(2026, 3, 20, 11, 22, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(ALERT_IDS[3]),
        "timestamp": dt(datetime(2026, 3, 22, 16, 6, tzinfo=timezone.utc)),
        "channel": "slack",
        "anomaly_id": A_IDS[2],
        "severity": "Medium",
        "message": "MEDIUM: AWS Lambda cost spike in us-west-2. Actual $42.03 vs baseline $0.25 (+16,712%). Possible recursive Lambda invocation loop detected.",
        "acknowledged": True,
        "acknowledged_at": dt(datetime(2026, 3, 22, 17, 5, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(ALERT_IDS[4]),
        "timestamp": dt(datetime(2026, 3, 24, 20, 6, tzinfo=timezone.utc)),
        "channel": "email",
        "anomaly_id": A_IDS[3],
        "severity": "High",
        "message": "HIGH: Amazon CloudFront cost spike in us-east-1. Actual $85.62 vs baseline $0.30 (+28,440%). DDoS-like traffic pattern detected. Review WAF rules immediately.",
        "acknowledged": False,
    },
    {
        "_id": oid(ALERT_IDS[5]),
        "timestamp": dt(datetime(2026, 3, 24, 20, 7, tzinfo=timezone.utc)),
        "channel": "slack",
        "anomaly_id": A_IDS[3],
        "severity": "High",
        "message": "HIGH: Amazon CloudFront spike detected. Actual $85.62 vs baseline $0.30 (+28,440%). Possible DDoS on /api/search.",
        "acknowledged": False,
    },
    {
        "_id": oid(ALERT_IDS[6]),
        "timestamp": dt(datetime(2026, 3, 25, 10, 6, tzinfo=timezone.utc)),
        "channel": "digest",
        "anomaly_id": A_IDS[4],
        "severity": "Low",
        "message": "LOW: Amazon S3 cost spike in us-east-1. Actual $27.88 vs baseline $0.41. Large cross-region transfer — may be legitimate quarterly export job.",
        "acknowledged": False,
    },
    {
        "_id": oid(ALERT_IDS[7]),
        "timestamp": dt(datetime(2026, 3, 26, 8, 6, tzinfo=timezone.utc)),
        "channel": "email",
        "anomaly_id": A_IDS[5],
        "severity": "High",
        "message": "HIGH: Amazon EC2 runaway Auto Scaling in us-east-1. ASG scaled to 92 instances. Actual $229.38 vs baseline $2.49. Check Terraform changes — ASG alarm threshold misconfigured.",
        "acknowledged": False,
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 7. recommendations
# ═══════════════════════════════════════════════════════════════════════════════
RECOMMENDATIONS = [
    {
        "_id": oid(REC_IDS[0]),
        "anomaly_id": A_IDS[0],
        "action": "Rotate all AWS root account and IAM access keys; enforce MFA via SCP",
        "detail": "The March 15 crypto-mining incident used a root account API key rotated 8+ months ago. Enforce 90-day key rotation policy and disable root account programmatic access entirely.",
        "estimated_savings": 1240.00,
        "savings_period": "monthly",
        "service": "Amazon EC2",
        "region": "us-east-1",
        "effort": "low",
        "priority": 1,
        "status": "approved",
        "created_at": dt(datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(REC_IDS[1]),
        "anomaly_id": A_IDS[1],
        "action": "Add EXPLAIN ANALYZE gate in CI/CD for queries on tables larger than 100 GB",
        "detail": "Require query plan review before merging migrations that touch large tables. Estimated to prevent 2-3 similar incidents per quarter saving ~$380/month.",
        "estimated_savings": 380.00,
        "savings_period": "monthly",
        "service": "Amazon RDS",
        "region": "us-east-1",
        "effort": "medium",
        "priority": 2,
        "status": "approved",
        "created_at": dt(datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(REC_IDS[2]),
        "anomaly_id": A_IDS[3],
        "action": "Deploy WAF rate-limiting: max 100 req/min per IP on unauthenticated endpoints",
        "detail": "CloudFront WAF lacks rate-limiting for public endpoints. Add rate-based rules for /api/search and other unauthenticated routes to prevent DDoS-driven cost spikes.",
        "estimated_savings": 520.00,
        "savings_period": "monthly",
        "service": "Amazon CloudFront",
        "region": "us-east-1",
        "effort": "low",
        "priority": 1,
        "status": "pending",
        "created_at": dt(datetime(2026, 3, 24, 21, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(REC_IDS[3]),
        "anomaly_id": None,
        "action": "Switch 18 always-on dev/test EC2 instances to 1-year Savings Plans (no-upfront)",
        "detail": "18 EC2 instances in dev/staging show >95% uptime over last 90 days. Switching to 1-year Savings Plans reduces their on-demand rate by 37%.",
        "estimated_savings": 680.00,
        "savings_period": "monthly",
        "service": "Amazon EC2",
        "region": "us-east-1",
        "effort": "low",
        "priority": 1,
        "status": "pending",
        "created_at": dt(datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(REC_IDS[4]),
        "anomaly_id": None,
        "action": "Enable S3 Intelligent-Tiering on the analytics-archive bucket (4.2 TB)",
        "detail": "analytics-archive has 4.2 TB with irregular access patterns. Intelligent-Tiering auto-moves infrequent objects to cheaper tiers with no retrieval fees.",
        "estimated_savings": 142.00,
        "savings_period": "monthly",
        "service": "Amazon S3",
        "region": "us-east-1",
        "effort": "low",
        "priority": 3,
        "status": "pending",
        "created_at": dt(datetime(2026, 3, 5, 9, 0, tzinfo=timezone.utc)),
    },
    {
        "_id": oid(REC_IDS[5]),
        "anomaly_id": A_IDS[5],
        "action": "Add OPA policy in Terraform CI to block ASG alarm thresholds below 20% CPU",
        "detail": "The March 26 runaway ASG was caused by a CloudWatch alarm set to CPU > 5%. Implement an OPA rule to reject alarm configs with thresholds below 20% before apply.",
        "estimated_savings": 890.00,
        "savings_period": "monthly",
        "service": "Amazon EC2",
        "region": "us-east-1",
        "effort": "medium",
        "priority": 1,
        "status": "pending",
        "created_at": dt(datetime(2026, 3, 26, 9, 0, tzinfo=timezone.utc)),
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 8. user_feedback
# ═══════════════════════════════════════════════════════════════════════════════
USER_FEEDBACK = [
    {
        "anomaly_id": A_IDS[0],
        "is_real": True,
        "comment": "Confirmed - unauthorized instances, security team engaged. Terminated and access keys revoked.",
        "submitted_at": dt(datetime(2026, 3, 15, 15, 10, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[1],
        "is_real": True,
        "comment": "Legitimate but unplanned - bad query in migration job. Engineering fixed it.",
        "submitted_at": dt(datetime(2026, 3, 20, 12, 30, tzinfo=timezone.utc)),
    },
    {
        "anomaly_id": A_IDS[2],
        "is_real": True,
        "comment": "Recursive Lambda bug - hotfix deployed. Not a security issue.",
        "submitted_at": dt(datetime(2026, 3, 22, 18, 0, tzinfo=timezone.utc)),
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Write JSON files
# ═══════════════════════════════════════════════════════════════════════════════
def write_json(filename, data):
    path = f"{OUTPUT_DIR}/{filename}"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ {filename:45s} ({len(data):4d} documents)")


if __name__ == "__main__":
    print("\nGenerating AnomalyIQ mock data...\n")

    billing = gen_billing_raw()
    write_json("aws_billing_raw.json", billing)
    write_json("anomalies_detected.json", ANOMALY_DEFS)
    write_json("root_cause_analysis.json", RCA_DEFS)
    write_json("budgets.json", BUDGETS)
    write_json("forecasts.json", gen_forecasts())
    write_json("alerts_sent.json", ALERTS)
    write_json("recommendations.json", RECOMMENDATIONS)
    write_json("user_feedback.json", USER_FEEDBACK)

    # Sanity check: March MTD total
    march_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    march_total = sum(
        r["cost"]
        for r in billing
        if datetime.fromisoformat(r["timestamp"]["$date"].replace("Z", "+00:00")) >= march_start
    )
    print(f"\nSanity check — March MTD total in aws_billing_raw: ${march_total:,.2f}")
    print("  CostMeter will show this vs $5,000 monthly budget\n")

    print("All files written to:", OUTPUT_DIR)
    print("\nImport commands (run from mock_data/ folder):")
    for coll in [
        "aws_billing_raw", "anomalies_detected", "root_cause_analysis",
        "budgets", "forecasts", "alerts_sent", "recommendations", "user_feedback",
    ]:
        print(f"  mongoimport --db anomalyiq --collection {coll} --file {coll}.json --jsonArray")
    print()
