"""
REST API routes for AnomalyIQ — multi-cloud (AWS / Azure / GCP).
Every endpoint accepts ?provider=aws|azure|gcp (default: aws).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from backend.database.mongodb import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

VALID_PROVIDERS = {"aws", "azure", "gcp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_id(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _docs_id(docs: List[Dict]) -> List[Dict]:
    return [_doc_id(d) for d in docs]


def _validate_provider(provider: str) -> str:
    p = provider.lower()
    if p not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Invalid provider '{provider}'. Must be one of: aws, azure, gcp.")
    return p


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    try:
        db = get_db()
        db.command("ping")
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------


@router.get("/billing/current")
async def get_current_billing(
    provider: str = Query(default="aws"),
) -> Dict[str, Any]:
    """Return month-to-date total cost for a given cloud provider."""
    provider = _validate_provider(provider)
    db = get_db()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pipeline = [
        {"$match": {"provider": provider, "timestamp": {"$gte": month_start}}},
        {"$group": {"_id": None, "total_cost": {"$sum": "$cost"}}},
    ]
    result = list(db["billing_raw"].aggregate(pipeline))
    total = result[0]["total_cost"] if result else 0.0

    return {
        "provider": provider,
        "month": now.strftime("%Y-%m"),
        "total_cost": round(total, 4),
        "currency": "USD",
    }


@router.get("/billing/history")
async def get_billing_history(
    provider: str = Query(default="aws"),
    days: int = Query(default=7, ge=1, le=90),
) -> List[Dict[str, Any]]:
    """Return hourly cost totals for the last *days* days."""
    provider = _validate_provider(provider)
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"provider": provider, "timestamp": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%dT%H:00:00",
                        "date": "$timestamp",
                    }
                },
                "total_cost": {"$sum": "$cost"},
            }
        },
        {"$sort": {"_id": 1}},
        {"$project": {"timestamp": "$_id", "total_cost": 1, "_id": 0}},
    ]

    return list(db["billing_raw"].aggregate(pipeline))


@router.get("/billing/services")
async def get_billing_by_service(
    provider: str = Query(default="aws"),
    days: int = Query(default=7, ge=1, le=90),
) -> List[Dict[str, Any]]:
    """Return cost breakdown grouped by service for the last *days* days."""
    provider = _validate_provider(provider)
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"provider": provider, "timestamp": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": "$service",
                "total_cost": {"$sum": "$cost"},
                "data_points": {"$sum": 1},
            }
        },
        {"$sort": {"total_cost": -1}},
        {"$project": {"service": "$_id", "total_cost": 1, "data_points": 1, "_id": 0}},
    ]

    return list(db["billing_raw"].aggregate(pipeline))


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


@router.get("/anomalies")
async def list_anomalies(
    provider: str = Query(default="aws"),
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    provider = _validate_provider(provider)
    db = get_db()

    query: Dict[str, Any] = {"provider": provider}
    if severity:
        query["severity"] = severity
    if status:
        query["status"] = status

    total = db["anomalies_detected"].count_documents(query)
    skip = (page - 1) * page_size

    docs = list(
        db["anomalies_detected"]
        .find(query)
        .sort("timestamp", -1)
        .skip(skip)
        .limit(page_size)
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": _docs_id(docs),
    }


@router.get("/anomalies/{anomaly_id}")
async def get_anomaly(
    anomaly_id: str,
    provider: str = Query(default="aws"),
) -> Dict[str, Any]:
    provider = _validate_provider(provider)
    db = get_db()

    try:
        oid = ObjectId(anomaly_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid anomaly ID.")

    anomaly = db["anomalies_detected"].find_one({"_id": oid, "provider": provider})
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found.")

    rca = db["root_cause_analysis"].find_one({"anomaly_id": anomaly_id})

    result = _doc_id(anomaly)
    result["root_cause_analysis"] = _doc_id(rca) if rca else None
    return result


class FeedbackPayload(BaseModel):
    is_real: bool
    comment: Optional[str] = None


@router.post("/anomalies/{anomaly_id}/feedback")
async def submit_feedback(anomaly_id: str, payload: FeedbackPayload) -> Dict[str, Any]:
    db = get_db()

    try:
        oid = ObjectId(anomaly_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid anomaly ID.")

    if not db["anomalies_detected"].find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Anomaly not found.")

    feedback_doc = {
        "anomaly_id": anomaly_id,
        "is_real": payload.is_real,
        "comment": payload.comment,
        "submitted_at": datetime.now(timezone.utc),
    }

    result = db["user_feedback"].insert_one(feedback_doc)

    new_status = "false_positive" if not payload.is_real else "acknowledged"
    db["anomalies_detected"].update_one(
        {"_id": oid},
        {"$set": {"status": new_status}},
    )

    return {"feedback_id": str(result.inserted_id), "status": "recorded"}


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------


@router.get("/forecasts/latest")
async def get_latest_forecast(
    provider: str = Query(default="aws"),
    service: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    provider = _validate_provider(provider)
    db = get_db()
    query: Dict[str, Any] = {"provider": provider, "service": service or "ALL"}
    forecast = db["forecasts"].find_one(query, sort=[("created_at", -1)])
    if not forecast:
        raise HTTPException(status_code=404, detail="No forecast available.")
    return _doc_id(forecast)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


class BudgetPayload(BaseModel):
    provider: str = "aws"
    budget_type: str = "monthly"
    name: str
    limit: float
    alert_thresholds: List[float] = [0.5, 0.8, 0.9, 1.0]
    service_filter: Optional[str] = None
    region_filter: Optional[str] = None


@router.get("/budgets")
async def list_budgets(provider: str = Query(default="aws")) -> List[Dict[str, Any]]:
    provider = _validate_provider(provider)
    db = get_db()
    return _docs_id(list(db["budgets"].find({"provider": provider}).sort("created_at", -1)))


@router.post("/budgets", status_code=201)
async def create_budget(payload: BudgetPayload) -> Dict[str, Any]:
    _validate_provider(payload.provider)
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {**payload.model_dump(), "created_at": now, "updated_at": now}
    result = db["budgets"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.get("/budgets/{budget_id}/forecast")
async def get_budget_forecast(budget_id: str) -> Dict[str, Any]:
    from backend.agents.agent4_forecast import check_budget_breach

    result = check_budget_breach(budget_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Budget not found or no forecast available yet.",
        )
    return result


@router.put("/budgets/{budget_id}")
async def update_budget(budget_id: str, payload: BudgetPayload) -> Dict[str, Any]:
    db = get_db()

    try:
        oid = ObjectId(budget_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid budget ID.")

    update_data = {**payload.model_dump(), "updated_at": datetime.now(timezone.utc)}
    result = db["budgets"].update_one({"_id": oid}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Budget not found.")

    updated = db["budgets"].find_one({"_id": oid})
    return _doc_id(updated)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get("/alerts")
async def list_alerts(
    provider: str = Query(default="aws"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    provider = _validate_provider(provider)
    db = get_db()
    query = {"provider": provider}
    total = db["alerts_sent"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(
        db["alerts_sent"].find(query).sort("timestamp", -1).skip(skip).limit(page_size)
    )
    return {"total": total, "page": page, "page_size": page_size, "items": _docs_id(docs)}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    provider: str = Query(default="aws"),
) -> Dict[str, Any]:
    provider = _validate_provider(provider)
    db = get_db()

    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID.")

    result = db["alerts_sent"].update_one(
        {"_id": oid, "provider": provider},
        {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc)}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found.")

    return {"status": "acknowledged", "alert_id": alert_id}


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get("/recommendations")
async def list_recommendations(
    provider: str = Query(default="aws"),
    status: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    provider = _validate_provider(provider)
    db = get_db()
    query: Dict[str, Any] = {"provider": provider}
    if status:
        query["status"] = status
    docs = list(db["recommendations"].find(query).sort("created_at", -1).limit(50))
    return _docs_id(docs)


# ---------------------------------------------------------------------------
# Billing — Yearly Comparison & Service Month-over-Month
# ---------------------------------------------------------------------------

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_MOCK_YEARLY: Dict[str, Dict] = {
    "aws": {
        "year_2025": [950, 890, 1020, 1100, 980, 1150, 1200, 1180, 1090, 1250, 1380, 1450],
        "year_2026": [1380, 1420, 1510, None, None, None, None, None, None, None, None, None],
    },
    "azure": {
        "year_2025": [420, 380, 450, 490, 440, 510, 540, 530, 480, 560, 620, 680],
        "year_2026": [650, 680, 720, None, None, None, None, None, None, None, None, None],
    },
    "gcp": {
        "year_2025": [210, 190, 240, 260, 230, 280, 310, 290, 260, 320, 360, 390],
        "year_2026": [370, 390, 420, None, None, None, None, None, None, None, None, None],
    },
}

_MOCK_SERVICES: Dict[str, Dict] = {
    "aws": {
        "services": ["EC2", "S3", "RDS", "Lambda", "CloudFront", "EKS", "DynamoDB", "Redshift"],
        "current_month":  [420, 85, 180, 45, 62, 230, 95, 145],
        "previous_month": [380, 92, 165, 38, 58, 210, 88, 130],
    },
    "azure": {
        "services": ["Virtual Machines", "Storage Account", "SQL Database", "App Service", "Azure DevOps", "AKS"],
        "current_month":  [280, 65, 120, 85, 45, 95],
        "previous_month": [255, 72, 108, 78, 42, 88],
    },
    "gcp": {
        "services": ["Compute Engine", "Cloud Storage", "BigQuery", "Cloud Run", "Cloud SQL", "Kubernetes Engine"],
        "current_month":  [155, 38, 65, 48, 72, 95],
        "previous_month": [140, 42, 58, 45, 68, 88],
    },
}


@router.get("/billing/yearly-comparison")
async def get_yearly_comparison(
    provider: str = Query(default="aws"),
) -> Dict[str, Any]:
    """Monthly cost totals for 2025 and 2026 (Jan–Mar) for year-over-year comparison.
    Uses real data from billing_raw where available, fills gaps with mock data."""
    provider = _validate_provider(provider)
    db = get_db()
    mock = _MOCK_YEARLY[provider]

    pipeline = [
        {
            "$match": {
                "provider": provider,
                "timestamp": {
                    "$gte": datetime(2025, 1, 1, tzinfo=timezone.utc),
                    "$lt":  datetime(2027, 1, 1, tzinfo=timezone.utc),
                },
            }
        },
        {
            "$group": {
                "_id": {
                    "year":  {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                },
                "total_cost": {"$sum": "$cost"},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1}},
    ]

    real_lookup: Dict[tuple, float] = {
        (r["_id"]["year"], r["_id"]["month"]): round(r["total_cost"], 2)
        for r in db["billing_raw"].aggregate(pipeline)
    }

    year_2025, year_2026 = [], []
    for m in range(1, 13):
        year_2025.append(real_lookup.get((2025, m)) if (2025, m) in real_lookup else mock["year_2025"][m - 1])
        year_2026.append(real_lookup.get((2026, m)) if (2026, m) in real_lookup else mock["year_2026"][m - 1])

    return {
        "provider": provider,
        "months": MONTHS,
        "year_2025": year_2025,
        "year_2026": year_2026,
    }


@router.get("/billing/service-comparison")
async def get_service_comparison(
    provider: str = Query(default="aws"),
) -> Dict[str, Any]:
    """Current month vs previous month cost per service.
    Uses real data from billing_raw where available, falls back to mock."""
    provider = _validate_provider(provider)
    db = get_db()
    mock = _MOCK_SERVICES[provider]

    now = datetime.now(timezone.utc)
    current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_end      = current_start
    prev_start    = (current_start - timedelta(days=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    def _service_costs(start: datetime, end: datetime) -> Dict[str, float]:
        pipeline = [
            {"$match": {"provider": provider, "timestamp": {"$gte": start, "$lt": end}}},
            {"$group": {"_id": "$service", "total_cost": {"$sum": "$cost"}}},
            {"$sort": {"total_cost": -1}},
        ]
        return {r["_id"]: round(r["total_cost"], 2) for r in db["billing_raw"].aggregate(pipeline)}

    current_costs = _service_costs(current_start, now)
    prev_costs    = _service_costs(prev_start, prev_end)

    if current_costs or prev_costs:
        services = sorted(
            set(list(current_costs.keys()) + list(prev_costs.keys())),
            key=lambda s: current_costs.get(s, 0),
            reverse=True,
        )[:8]
        current_month  = [current_costs.get(s, 0) for s in services]
        previous_month = [prev_costs.get(s, 0) for s in services]
    else:
        services       = mock["services"][:8]
        current_month  = mock["current_month"][:8]
        previous_month = mock["previous_month"][:8]

    return {
        "provider": provider,
        "services": services,
        "current_month":  current_month,
        "previous_month": previous_month,
        "current_label":  now.strftime("%b %Y"),
        "previous_label": prev_start.strftime("%b %Y"),
    }


# ---------------------------------------------------------------------------
# Manual triggers
# ---------------------------------------------------------------------------


@router.post("/trigger/collect")
async def trigger_collect(provider: str = Query(default="aws")) -> Dict[str, Any]:
    """Manually trigger data collection for a given cloud provider."""
    import asyncio
    provider = _validate_provider(provider)

    if provider == "aws":
        from backend.agents.agent1_data_collector import collect_cost_data
        records = await asyncio.to_thread(collect_cost_data)
    elif provider == "azure":
        from backend.agents.agent1_azure_data_collector import collect_cost_data as collect_azure
        records = await asyncio.to_thread(collect_azure)
    else:  # gcp
        from backend.agents.agent1_gcp_data_collector import collect_cost_data as collect_gcp
        records = await asyncio.to_thread(collect_gcp)

    return {"status": "done", "provider": provider, "job": "data_collection", "records_collected": len(records)}


@router.post("/trigger/detect")
async def trigger_detect(
    provider: str = Query(default="aws"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> Dict[str, str]:
    """Manually trigger anomaly detection for a given cloud provider."""
    provider = _validate_provider(provider)

    def _run():
        from backend.agents.agent2_anomaly_detector import detect_anomalies
        detect_anomalies(provider=provider)

    background_tasks.add_task(_run)
    return {"status": "triggered", "provider": provider, "job": "anomaly_detection"}
