"""
AnomalyIQ — Azure & GCP Mock Data Generator
Generates MongoDB-ready JSON files mirroring the AWS mock data structure.
Same cost patterns, same date range (Feb 25 – Mar 27 2026), same anomaly types.

Run: python generate_azure_gcp_mock.py
Import (from mock_data/ folder):
  mongoimport --db anomalyiq --collection billing_raw      --file azure_billing_raw.json  --jsonArray
  mongoimport --db anomalyiq --collection billing_raw      --file gcp_billing_raw.json    --jsonArray
  mongoimport --db anomalyiq --collection anomalies_detected --file azure_anomalies.json  --jsonArray
  ... (see full list at bottom)
"""

import json
import math
import random
from datetime import datetime, timedelta, timezone

random.seed(99)

OUTPUT_DIR = "."
NOW = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)

# ── Azure service mapping (mirrors AWS services 1-to-1) ───────────────────────
AZURE_SERVICES = {
    "Azure Virtual Machines":  {"base": 2.50, "region": "eastus"},
    "Azure SQL Database":      {"base": 1.00, "region": "eastus"},
    "Azure Blob Storage":      {"base": 0.40, "region": "eastus"},
    "Azure CDN":               {"base": 0.30, "region": "eastus"},
    "Azure Functions":         {"base": 0.25, "region": "westeurope"},
    "Azure Cosmos DB":         {"base": 0.17, "region": "eastus"},
    "Azure Cache for Redis":   {"base": 0.13, "region": "eastus"},
    "Azure Data Factory":      {"base": 0.08, "region": "eastasia"},
}

# ── GCP service mapping (mirrors AWS services 1-to-1) ─────────────────────────
GCP_SERVICES = {
    "Compute Engine":   {"base": 2.50, "region": "us-central1"},
    "Cloud SQL":        {"base": 1.00, "region": "us-central1"},
    "Cloud Storage":    {"base": 0.40, "region": "us-central1"},
    "Cloud CDN":        {"base": 0.30, "region": "us-central1"},
    "Cloud Functions":  {"base": 0.25, "region": "europe-west1"},
    "Firestore":        {"base": 0.17, "region": "us-central1"},
    "Memorystore":      {"base": 0.13, "region": "us-central1"},
    "Cloud Dataflow":   {"base": 0.08, "region": "asia-east1"},
}

# Spike definitions — same timing as AWS, mapped to equivalent services
# {(service, date_str, hour): multiplier}
AZURE_SPIKES = {
    ("Azure Virtual Machines", "2026-03-15", 14): 138.0,  # Critical — same as EC2
    ("Azure SQL Database",     "2026-03-20",  9): 127.0,  # High — same as RDS
    ("Azure Functions",        "2026-03-22", 16): 168.0,  # Medium — same as Lambda
    ("Azure CDN",              "2026-03-24", 20): 285.0,  # High — same as CloudFront
    ("Azure Blob Storage",     "2026-03-25", 10):  68.0,  # Low — same as S3
    ("Azure Virtual Machines", "2026-03-26",  8):  92.0,  # High — today
}

GCP_SPIKES = {
    ("Compute Engine",  "2026-03-15", 14): 138.0,
    ("Cloud SQL",       "2026-03-20",  9): 127.0,
    ("Cloud Functions", "2026-03-22", 16): 168.0,
    ("Cloud CDN",       "2026-03-24", 20): 285.0,
    ("Cloud Storage",   "2026-03-25", 10):  68.0,
    ("Compute Engine",  "2026-03-26",  8):  92.0,
}

# ObjectId hex strings
def make_ids(prefix, count):
    return [f"{prefix}{str(i).zfill(6)}" for i in range(count)]

AZ_A_IDS  = make_ids("65f2a2b3c4d5e6f789", 6)
AZ_B_IDS  = make_ids("65f2a2b3c4d5e6f799", 4)
AZ_R_IDS  = make_ids("65f2a2b3c4d5e6f7a9", 6)
AZ_AL_IDS = make_ids("65f2a2b3c4d5e6f7b9", 8)
AZ_FC_ID  = "65f2a2b3c4d5e6f7c90000"

GCP_A_IDS  = make_ids("65f3a2b3c4d5e6f789", 6)
GCP_B_IDS  = make_ids("65f3a2b3c4d5e6f799", 4)
GCP_R_IDS  = make_ids("65f3a2b3c4d5e6f7a9", 6)
GCP_AL_IDS = make_ids("65f3a2b3c4d5e6f7b9", 8)
GCP_FC_ID  = "65f3a2b3c4d5e6f7c90000"


def oid(hex_str):
    return {"$oid": hex_str}

def dt(d: datetime):
    return {"$date": d.strftime("%Y-%m-%dT%H:%M:%SZ")}

def noisy(base, noise_pct=0.12):
    return round(base * (1 + random.uniform(-noise_pct, noise_pct)), 4)


# ── Billing raw generator ──────────────────────────────────────────────────────
def gen_billing_raw(provider, services, spikes):
    records = []

    # Feb 25 → Mar 23: daily records
    start = datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
    end_daily = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc)
    current = start
    while current < end_daily:
        for svc, cfg in services.items():
            cost = noisy(cfg["base"] * 24)
            records.append({
                "provider": provider,
                "timestamp": dt(current),
                "service": svc,
                "region": cfg["region"],
                "cost": cost,
                "usage_quantity": round(cost / cfg["base"] * 0.8, 2),
                "currency": "USD",
                "created_at": dt(current + timedelta(minutes=5)),
            })
        current += timedelta(days=1)

    # Spike records for daily range
    for (svc, date_str, hour), multiplier in spikes.items():
        spike_dt = datetime(
            int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10]),
            hour, 0, 0, tzinfo=timezone.utc
        )
        if spike_dt < end_daily:
            cfg = services[svc]
            spike_cost = round(cfg["base"] * multiplier, 4)
            records.append({
                "provider": provider,
                "timestamp": dt(spike_dt),
                "service": svc,
                "region": cfg["region"],
                "cost": spike_cost,
                "usage_quantity": round(spike_cost / cfg["base"] * 0.8, 2),
                "currency": "USD",
                "created_at": dt(spike_dt + timedelta(minutes=3)),
            })

    # Mar 24 → Mar 27 12:00: hourly records
    current = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc)
    while current <= NOW:
        date_str = current.strftime("%Y-%m-%d")
        hour = current.hour
        for svc, cfg in services.items():
            spike_key = (svc, date_str, hour)
            if spike_key in spikes:
                cost = round(cfg["base"] * spikes[spike_key], 4)
            else:
                time_factor = 1.0 + 0.15 * math.sin(math.pi * hour / 12)
                cost = noisy(cfg["base"] * time_factor)
            records.append({
                "provider": provider,
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


# ── Anomaly definitions ────────────────────────────────────────────────────────
def make_anomalies(provider, a_ids, services_map):
    svc_keys = list(services_map.keys())
    # Same pattern as AWS: [Critical, High, Medium, High, Low, High]
    defs = [
        (svc_keys[0], "us-east-1" if provider=="aws" else ("eastus" if provider=="azure" else "us-central1"),
         datetime(2026,3,15,14,0,tzinfo=timezone.utc), "Critical", 2.52, 345.82, 343.30, 13623.0, ["isolation_forest","zscore"], "resolved"),
        (svc_keys[1], "us-east-1" if provider=="aws" else ("eastus" if provider=="azure" else "us-central1"),
         datetime(2026,3,20,9,0,tzinfo=timezone.utc), "High", 1.01, 128.47, 127.46, 12620.0, ["isolation_forest","zscore"], "resolved"),
        (svc_keys[4], "us-west-2" if provider=="aws" else ("westeurope" if provider=="azure" else "europe-west1"),
         datetime(2026,3,22,16,0,tzinfo=timezone.utc), "Medium", 0.25, 42.03, 41.78, 16712.0, ["zscore"], "acknowledged"),
        (svc_keys[3], "us-east-1" if provider=="aws" else ("eastus" if provider=="azure" else "us-central1"),
         datetime(2026,3,24,20,0,tzinfo=timezone.utc), "High", 0.30, 85.62, 85.32, 28440.0, ["isolation_forest","zscore","rolling_window"], "open"),
        (svc_keys[2], "us-east-1" if provider=="aws" else ("eastus" if provider=="azure" else "us-central1"),
         datetime(2026,3,25,10,0,tzinfo=timezone.utc), "Low", 0.41, 27.88, 27.47, 6699.0, ["rolling_window"], "open"),
        (svc_keys[0], "us-east-1" if provider=="aws" else ("eastus" if provider=="azure" else "us-central1"),
         datetime(2026,3,26,8,0,tzinfo=timezone.utc), "High", 2.49, 229.38, 226.89, 9112.0, ["isolation_forest","zscore"], "open"),
    ]
    result = []
    for i, (svc, region, ts, severity, baseline, actual, delta, pct, methods, status) in enumerate(defs):
        result.append({
            "_id": oid(a_ids[i]),
            "provider": provider,
            "timestamp": dt(ts),
            "severity": severity,
            "service": svc,
            "region": region,
            "baseline_cost": baseline,
            "actual_cost": actual,
            "cost_delta": delta,
            "percentage_increase": pct,
            "detection_methods": methods,
            "status": status,
            "created_at": dt(ts + timedelta(minutes=5)),
        })
    return result


# ── RCA definitions ────────────────────────────────────────────────────────────
AZURE_RCA = [
    ("Unauthorized GPU VM scale-out: 47 NC24s_v3 VMs launched via compromised service principal. "
     "GPU utilization 99.8%, no egress — consistent with crypto-mining. VMs terminated after alert.",
     {"vm_count": 47, "vm_size": "NC24s_v3", "launched_by": "service-principal: sp-deploy-prod", "gpu_utilization": "99.8%"}, 0.97, False),
    ("Unoptimized analytical query ran full scan on 'events' table (1.8 TB) in Azure SQL. "
     "Triggered 3x compute tier auto-scale. Query killed at 11:15 UTC, migration rescheduled.",
     {"query_type": "SELECT * full scan", "table": "events", "table_size_gb": 1800, "scale_events": 3, "cpu_peak": "97.4%"}, 0.94, True),
    ("Recursive Azure Functions invocation loop introduced by deploy at 16:02 UTC. "
     "Function triggered on its own output blob. 168,420 self-invocations in 14 min. Hotfix deployed 16:48.",
     {"function_name": "process-upload", "invocations": 168420, "avg_duration_ms": 3200, "trigger": "Blob storage (all)"}, 0.99, False),
    ("DDoS attack on /api/search caused Azure CDN to serve 2.4 TB between 20:00–22:45 UTC. "
     "8,400 unique IPs, 34 countries. WAF rate-limiting missing on unauthenticated endpoints.",
     {"traffic_tb": 2.4, "unique_ips": 8400, "countries": 34, "target": "/api/search", "waf_gap": "rate-limit unauthenticated"}, 0.91, False),
    ("Scheduled quarterly export job transferred 6.8 TB from Blob Storage eastus to partner in West Europe. "
     "LRS→GRS egress fees applied. Legitimate but budget not updated for increased data volume.",
     {"transfer_gb": 6800, "source": "eastus", "dest": "westeurope", "rate_per_gb": 0.02, "job": "quarterly-partner-export"}, 0.88, True),
    ("VMSS auto-scale misconfiguration: CPU alert threshold set to >5% (should be >70%). "
     "api-backend VMSS scaled from 3 to 92 instances. Terraform apply at 07:45 UTC introduced the bug.",
     {"vmss_name": "api-backend-vmss", "scale_from": 3, "scale_to": 92, "vm_size": "Standard_D8s_v3", "wrong_threshold": ">5%", "correct_threshold": ">70%"}, 0.98, False),
]

GCP_RCA = [
    ("Unauthorized Compute Engine GPU instance launch: 47 n1-standard-96 instances with A100 GPUs "
     "created via compromised service account. 99.8% GPU utilization, no egress — crypto-mining pattern.",
     {"instance_count": 47, "machine_type": "n1-standard-96+GPU", "principal": "sa-deploy-prod@project.iam.gserviceaccount.com", "gpu_util": "99.8%"}, 0.97, False),
    ("Full table scan on Cloud SQL PostgreSQL 'events' table (1.8 TB) by unoptimized migration query. "
     "3x read replica auto-scale. Query terminated at 11:15 UTC.",
     {"query_type": "SELECT * full scan", "table": "events", "size_gb": 1800, "replicas_added": 3, "cpu_peak": "97.4%"}, 0.94, True),
    ("Recursive Cloud Functions loop: process-upload triggered on its own GCS output. "
     "168,420 invocations in 14 min. GCS trigger corrected via hotfix at 16:48 UTC.",
     {"function": "process-upload", "invocations": 168420, "avg_duration_ms": 3200, "trigger": "GCS ObjectFinalized (all)"}, 0.99, False),
    ("DDoS on /api/search routed through Cloud CDN — 2.4 TB served 20:00–22:45 UTC. "
     "8,400 IPs, 34 countries. Cloud Armor rate-limiting not configured for public endpoints.",
     {"traffic_tb": 2.4, "unique_ips": 8400, "countries": 34, "endpoint": "/api/search", "armor_gap": "rate-limit unauthenticated"}, 0.91, False),
    ("Scheduled quarterly export: 6.8 TB transferred from Cloud Storage us-central1 to partner bucket in EU. "
     "Inter-region egress fees at $0.02/GB. Legitimate but budget not updated.",
     {"transfer_gb": 6800, "source": "us-central1", "dest": "europe-west1", "rate_per_gb": 0.02, "job": "quarterly-partner-export"}, 0.88, True),
    ("MIG (Managed Instance Group) autoscaler misconfigured: CPU target set to 5% instead of 70%. "
     "api-backend MIG scaled from 3 to 92 n2-standard-8 instances. Terraform apply at 07:45 UTC.",
     {"mig_name": "api-backend-mig", "scale_from": 3, "scale_to": 92, "machine_type": "n2-standard-8", "wrong_cpu_target": "5%", "correct": "70%"}, 0.98, False),
]

def make_rca(provider, a_ids, rca_defs):
    timestamps = [
        datetime(2026,3,15,14,12,tzinfo=timezone.utc),
        datetime(2026,3,20, 9,18,tzinfo=timezone.utc),
        datetime(2026,3,22,16,22,tzinfo=timezone.utc),
        datetime(2026,3,24,20,31,tzinfo=timezone.utc),
        datetime(2026,3,25,10,19,tzinfo=timezone.utc),
        datetime(2026,3,26, 8,17,tzinfo=timezone.utc),
    ]
    result = []
    for i, (explanation, evidence, confidence, is_legitimate) in enumerate(rca_defs):
        result.append({
            "provider": provider,
            "anomaly_id": a_ids[i],
            "explanation": explanation,
            "evidence": {**evidence, "provider": provider},
            "confidence": confidence,
            "is_legitimate": is_legitimate,
            "created_at": dt(timestamps[i]),
        })
    return result


# ── Budgets ────────────────────────────────────────────────────────────────────
def make_budgets(provider, b_ids, service_names):
    return [
        {
            "_id": oid(b_ids[0]),
            "provider": provider,
            "budget_type": "monthly",
            "name": f"Total {provider.upper()} Monthly Budget",
            "limit": 5000.0,
            "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
            "service_filter": None,
            "region_filter": None,
            "created_at": dt(datetime(2026,1,1,0,0,tzinfo=timezone.utc)),
            "updated_at": dt(datetime(2026,3,1,0,0,tzinfo=timezone.utc)),
        },
        {
            "_id": oid(b_ids[1]),
            "provider": provider,
            "budget_type": "monthly",
            "name": f"{service_names[0]} Budget",
            "limit": 2200.0,
            "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
            "service_filter": service_names[0],
            "region_filter": None,
            "created_at": dt(datetime(2026,1,1,0,0,tzinfo=timezone.utc)),
            "updated_at": dt(datetime(2026,3,1,0,0,tzinfo=timezone.utc)),
        },
        {
            "_id": oid(b_ids[2]),
            "provider": provider,
            "budget_type": "monthly",
            "name": f"{service_names[1]} Budget",
            "limit": 800.0,
            "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
            "service_filter": service_names[1],
            "region_filter": None,
            "created_at": dt(datetime(2026,1,1,0,0,tzinfo=timezone.utc)),
            "updated_at": dt(datetime(2026,3,1,0,0,tzinfo=timezone.utc)),
        },
        {
            "_id": oid(b_ids[3]),
            "provider": provider,
            "budget_type": "daily",
            "name": f"{service_names[4]} Daily Budget",
            "limit": 50.0,
            "alert_thresholds": [0.5, 0.8, 0.9, 1.0],
            "service_filter": service_names[4],
            "region_filter": None,
            "created_at": dt(datetime(2026,2,1,0,0,tzinfo=timezone.utc)),
            "updated_at": dt(datetime(2026,2,1,0,0,tzinfo=timezone.utc)),
        },
    ]


# ── Forecasts ──────────────────────────────────────────────────────────────────
def make_forecasts(provider, fc_id, services):
    base_daily = sum(cfg["base"] for cfg in services.values()) * 24
    predictions = []
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
        "_id": oid(fc_id),
        "provider": provider,
        "forecast_date": dt(NOW),
        "service": "ALL",
        "horizon_days": 30,
        "model_used": "prophet",
        "predictions": predictions,
        "mape": 4.82,
        "created_at": dt(NOW),
    }]


# ── Alerts ─────────────────────────────────────────────────────────────────────
def make_alerts(provider, al_ids, a_ids, service_names):
    anomaly_configs = [
        (datetime(2026,3,15,14, 6,tzinfo=timezone.utc), "Critical", service_names[0], 345.82, 2.52, 13623, "email", True,  datetime(2026,3,15,14,38,tzinfo=timezone.utc)),
        (datetime(2026,3,15,14, 7,tzinfo=timezone.utc), "Critical", service_names[0], 345.82, 2.52, 13623, "slack", True,  datetime(2026,3,15,14,40,tzinfo=timezone.utc)),
        (datetime(2026,3,20, 9, 6,tzinfo=timezone.utc), "High",     service_names[1], 128.47, 1.01, 12620, "email", True,  datetime(2026,3,20,11,22,tzinfo=timezone.utc)),
        (datetime(2026,3,22,16, 6,tzinfo=timezone.utc), "Medium",   service_names[4],  42.03, 0.25, 16712, "slack", True,  datetime(2026,3,22,17, 5,tzinfo=timezone.utc)),
        (datetime(2026,3,24,20, 6,tzinfo=timezone.utc), "High",     service_names[3],  85.62, 0.30, 28440, "email", False, None),
        (datetime(2026,3,24,20, 7,tzinfo=timezone.utc), "High",     service_names[3],  85.62, 0.30, 28440, "slack", False, None),
        (datetime(2026,3,25,10, 6,tzinfo=timezone.utc), "Low",      service_names[2],  27.88, 0.41,  6699, "digest",False, None),
        (datetime(2026,3,26, 8, 6,tzinfo=timezone.utc), "High",     service_names[0], 229.38, 2.49,  9112, "email", False, None),
    ]
    anomaly_id_map = [a_ids[0], a_ids[0], a_ids[1], a_ids[2], a_ids[3], a_ids[3], a_ids[4], a_ids[5]]
    result = []
    for i, (ts, severity, svc, actual, baseline, pct, channel, acked, acked_at) in enumerate(anomaly_configs):
        doc = {
            "_id": oid(al_ids[i]),
            "provider": provider,
            "timestamp": dt(ts),
            "channel": channel,
            "anomaly_id": anomaly_id_map[i],
            "severity": severity,
            "message": (
                f"{severity.upper()}: {svc} cost spike detected. "
                f"Actual ${actual:.2f} vs baseline ${baseline:.2f} (+{pct:,}%). "
                f"[{provider.upper()}]"
            ),
            "acknowledged": acked,
        }
        if acked_at:
            doc["acknowledged_at"] = dt(acked_at)
        result.append(doc)
    return result


# ── Recommendations ────────────────────────────────────────────────────────────
AZURE_REC_ACTIONS = [
    ("Rotate service principal secrets and enforce MFA for all Azure AD app registrations",
     1240.00, "Azure Virtual Machines", "eastus", "low", 1, "approved"),
    ("Add EXPLAIN ANALYZE gate in ADO pipeline for Azure SQL migrations on tables > 100GB",
     380.00, "Azure SQL Database", "eastus", "medium", 2, "approved"),
    ("Enable Azure WAF rate-limiting policy: max 100 req/min per IP on unauthenticated endpoints",
     520.00, "Azure CDN", "eastus", "low", 1, "pending"),
    ("Switch 18 always-on dev/test VMs to Azure Reserved Instances (1-year, no-upfront)",
     680.00, "Azure Virtual Machines", "eastus", "low", 1, "pending"),
    ("Enable Azure Blob Storage lifecycle management to move cold blobs to Cool/Archive tier",
     142.00, "Azure Blob Storage", "eastus", "low", 3, "pending"),
    ("Add Azure Policy to block VMSS CPU alert thresholds below 20%",
     890.00, "Azure Virtual Machines", "eastus", "medium", 1, "pending"),
]

GCP_REC_ACTIONS = [
    ("Rotate service account keys and enforce Workload Identity Federation for GKE workloads",
     1240.00, "Compute Engine", "us-central1", "low", 1, "approved"),
    ("Add EXPLAIN ANALYZE gate in Cloud Build pipeline for Cloud SQL migrations on tables > 100GB",
     380.00, "Cloud SQL", "us-central1", "medium", 2, "approved"),
    ("Configure Cloud Armor rate-limiting rule: max 100 req/min per IP on unauthenticated endpoints",
     520.00, "Cloud CDN", "us-central1", "low", 1, "pending"),
    ("Switch 18 always-on dev/test Compute Engine instances to 1-year Committed Use Discounts",
     680.00, "Compute Engine", "us-central1", "low", 1, "pending"),
    ("Enable Cloud Storage Object Lifecycle Management to move infrequent objects to Nearline/Coldline",
     142.00, "Cloud Storage", "us-central1", "low", 3, "pending"),
    ("Add OPA constraint in Terraform CI to block MIG autoscaler CPU targets below 20%",
     890.00, "Compute Engine", "us-central1", "medium", 1, "pending"),
]

def make_recommendations(provider, r_ids, a_ids, rec_actions):
    timestamps = [
        datetime(2026,3,15,15,0,tzinfo=timezone.utc),
        datetime(2026,3,20,12,0,tzinfo=timezone.utc),
        datetime(2026,3,24,21,0,tzinfo=timezone.utc),
        datetime(2026,3,10, 9,0,tzinfo=timezone.utc),
        datetime(2026,3, 5, 9,0,tzinfo=timezone.utc),
        datetime(2026,3,26, 9,0,tzinfo=timezone.utc),
    ]
    anomaly_refs = [a_ids[0], a_ids[1], a_ids[3], None, None, a_ids[5]]
    result = []
    for i, (action, savings, service, region, effort, priority, status) in enumerate(rec_actions):
        result.append({
            "_id": oid(r_ids[i]),
            "provider": provider,
            "anomaly_id": anomaly_refs[i],
            "action": action,
            "estimated_savings": savings,
            "savings_period": "monthly",
            "service": service,
            "region": region,
            "effort": effort,
            "priority": priority,
            "status": status,
            "created_at": dt(timestamps[i]),
        })
    return result


# ── User feedback ──────────────────────────────────────────────────────────────
def make_feedback(provider, a_ids):
    return [
        {"provider": provider, "anomaly_id": a_ids[0], "is_real": True,
         "comment": "Confirmed — unauthorized VMs. Security team engaged, service principal revoked.",
         "submitted_at": dt(datetime(2026,3,15,15,10,tzinfo=timezone.utc))},
        {"provider": provider, "anomaly_id": a_ids[1], "is_real": True,
         "comment": "Legitimate but unplanned — bad query in migration job. Fixed.",
         "submitted_at": dt(datetime(2026,3,20,12,30,tzinfo=timezone.utc))},
        {"provider": provider, "anomaly_id": a_ids[2], "is_real": True,
         "comment": "Recursive function bug — hotfix deployed.",
         "submitted_at": dt(datetime(2026,3,22,18, 0,tzinfo=timezone.utc))},
    ]


# ── Write helpers ──────────────────────────────────────────────────────────────
def write_json(filename, data):
    path = f"{OUTPUT_DIR}/{filename}"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ {filename:50s} ({len(data):4d} documents)")


if __name__ == "__main__":
    print("\nGenerating Azure & GCP mock data...\n")

    az_svcs = list(AZURE_SERVICES.keys())
    gcp_svcs = list(GCP_SERVICES.keys())

    # Azure
    az_billing = gen_billing_raw("azure", AZURE_SERVICES, AZURE_SPIKES)
    write_json("azure_billing_raw.json",   az_billing)
    write_json("azure_anomalies.json",     make_anomalies("azure", AZ_A_IDS, AZURE_SERVICES))
    write_json("azure_rca.json",           make_rca("azure", AZ_A_IDS, AZURE_RCA))
    write_json("azure_budgets.json",       make_budgets("azure", AZ_B_IDS, az_svcs))
    write_json("azure_forecasts.json",     make_forecasts("azure", AZ_FC_ID, AZURE_SERVICES))
    write_json("azure_alerts.json",        make_alerts("azure", AZ_AL_IDS, AZ_A_IDS, az_svcs))
    write_json("azure_recommendations.json", make_recommendations("azure", AZ_R_IDS, AZ_A_IDS, AZURE_REC_ACTIONS))
    write_json("azure_feedback.json",      make_feedback("azure", AZ_A_IDS))

    # GCP
    gcp_billing = gen_billing_raw("gcp", GCP_SERVICES, GCP_SPIKES)
    write_json("gcp_billing_raw.json",   gcp_billing)
    write_json("gcp_anomalies.json",     make_anomalies("gcp", GCP_A_IDS, GCP_SERVICES))
    write_json("gcp_rca.json",           make_rca("gcp", GCP_A_IDS, GCP_RCA))
    write_json("gcp_budgets.json",       make_budgets("gcp", GCP_B_IDS, gcp_svcs))
    write_json("gcp_forecasts.json",     make_forecasts("gcp", GCP_FC_ID, GCP_SERVICES))
    write_json("gcp_alerts.json",        make_alerts("gcp", GCP_AL_IDS, GCP_A_IDS, gcp_svcs))
    write_json("gcp_recommendations.json", make_recommendations("gcp", GCP_R_IDS, GCP_A_IDS, GCP_REC_ACTIONS))
    write_json("gcp_feedback.json",      make_feedback("gcp", GCP_A_IDS))

    print("\nSanity check — March MTD totals:")
    march_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for label, billing in [("Azure", az_billing), ("GCP", gcp_billing)]:
        total = sum(
            r["cost"] for r in billing
            if datetime.fromisoformat(r["timestamp"]["$date"].replace("Z", "+00:00")) >= march_start
        )
        print(f"  {label}: ${total:,.2f}  (vs $5,000 budget)")

    print("\nAll files written to:", OUTPUT_DIR)
    print("\nImport commands (run from mock_data/ folder):")
    for prefix in ["azure", "gcp"]:
        for coll, suffix in [
            ("billing_raw",       f"{prefix}_billing_raw"),
            ("anomalies_detected",f"{prefix}_anomalies"),
            ("root_cause_analysis",f"{prefix}_rca"),
            ("budgets",           f"{prefix}_budgets"),
            ("forecasts",         f"{prefix}_forecasts"),
            ("alerts_sent",       f"{prefix}_alerts"),
            ("recommendations",   f"{prefix}_recommendations"),
            ("user_feedback",     f"{prefix}_feedback"),
        ]:
            print(f"  mongoimport --db anomalyiq --collection {coll} --file {suffix}.json --jsonArray")
    print()
