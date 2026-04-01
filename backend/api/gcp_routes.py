"""
REST API routes for GCP billing, anomalies, forecasts, budgets, alerts, recommendations.
Mirrors the AWS routes but reads from gcp_* collections.
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

router = APIRouter(prefix="/api/gcp")


def _doc_id(doc: Dict) -> Dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _docs_id(docs: List[Dict]) -> List[Dict]:
    return [_doc_id(d) for d in docs]


@router.get("/health")
async def gcp_health() -> Dict[str, Any]:
    try:
        db = get_db()
        count = db["gcp_billing_raw"].count_documents({})
        return {"status": "ok", "cloud": "gcp", "records": count, "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return {"status": "error", "cloud": "gcp", "error": str(exc)}


@router.get("/billing/current")
async def gcp_current_billing() -> Dict[str, Any]:
    db = get_db()
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    pipeline = [
        {"$match": {"timestamp": {"$gte": month_start}}},
        {"$group": {"_id": None, "total_cost": {"$sum": "$cost"}}},
    ]
    result = list(db["gcp_billing_raw"].aggregate(pipeline))
    total = result[0]["total_cost"] if result else 0.0
    return {"month": now.strftime("%Y-%m"), "total_cost": round(total, 4), "currency": "USD"}


@router.get("/billing/history")
async def gcp_billing_history(days: int = Query(default=7, ge=1, le=90)) -> List[Dict[str, Any]]:
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%dT%H:00:00", "date": "$timestamp"}},
            "total_cost": {"$sum": "$cost"},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {"timestamp": "$_id", "total_cost": 1, "_id": 0}},
    ]
    return list(db["gcp_billing_raw"].aggregate(pipeline))


@router.get("/billing/services")
async def gcp_billing_by_service(days: int = Query(default=7, ge=1, le=90)) -> List[Dict[str, Any]]:
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$service", "total_cost": {"$sum": "$cost"}, "data_points": {"$sum": 1}}},
        {"$sort": {"total_cost": -1}},
        {"$project": {"service": "$_id", "total_cost": 1, "data_points": 1, "_id": 0}},
    ]
    return list(db["gcp_billing_raw"].aggregate(pipeline))


@router.get("/anomalies")
async def gcp_list_anomalies(
    severity: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    db = get_db()
    query: Dict[str, Any] = {}
    if severity:
        query["severity"] = severity
    total = db["gcp_anomalies_detected"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(db["gcp_anomalies_detected"].find(query).sort("timestamp", -1).skip(skip).limit(page_size))
    return {"total": total, "page": page, "page_size": page_size, "items": _docs_id(docs)}


@router.get("/forecasts/latest")
async def gcp_latest_forecast(service: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    db = get_db()
    query: Dict[str, Any] = {"service": service or "ALL"}
    forecast = db["gcp_forecasts"].find_one(query, sort=[("created_at", -1)])
    if not forecast:
        raise HTTPException(status_code=404, detail="No GCP forecast available.")
    return _doc_id(forecast)


class GcpBudgetPayload(BaseModel):
    budget_type: str = "monthly"
    name: str
    limit: float
    alert_thresholds: List[float] = [0.5, 0.8, 0.9, 1.0]
    service_filter: Optional[str] = None


@router.get("/budgets")
async def gcp_list_budgets() -> List[Dict[str, Any]]:
    db = get_db()
    return _docs_id(list(db["gcp_budgets"].find().sort("created_at", -1)))


@router.post("/budgets", status_code=201)
async def gcp_create_budget(payload: GcpBudgetPayload) -> Dict[str, Any]:
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {**payload.model_dump(), "cloud": "gcp", "created_at": now, "updated_at": now}
    result = db["gcp_budgets"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.get("/budgets/{budget_id}/forecast")
async def gcp_budget_forecast(budget_id: str) -> Dict[str, Any]:
    db = get_db()
    try:
        oid = ObjectId(budget_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid budget ID.")

    budget = db["gcp_budgets"].find_one({"_id": oid})
    if not budget:
        raise HTTPException(status_code=404, detail="GCP budget not found.")

    service = budget.get("service_filter")
    budget_limit = float(budget.get("limit", 0))

    forecast = db["gcp_forecasts"].find_one(
        {"service": service or "ALL"}, sort=[("created_at", -1)]
    )
    if not forecast:
        raise HTTPException(status_code=404, detail="No GCP forecast available.")

    predictions = forecast.get("predictions", [])
    daily_totals: Dict[str, float] = {}
    for pt in predictions:
        ds = pt["ds"][:10] if isinstance(pt["ds"], str) else pt["ds"].strftime("%Y-%m-%d")
        daily_totals[ds] = daily_totals.get(ds, 0) + pt["yhat"]

    cumulative = 0.0
    days_until_breach = None
    for i, day in enumerate(sorted(daily_totals.keys())):
        cumulative += daily_totals[day]
        if cumulative >= budget_limit and days_until_breach is None:
            days_until_breach = i + 1

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    agg = list(db["gcp_billing_raw"].aggregate([
        {"$match": {"timestamp": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$cost"}}},
    ]))
    current_spend = float(agg[0]["total"]) if agg else 0.0

    return {
        "budget_id": budget_id,
        "budget_name": budget.get("name", ""),
        "budget_limit": budget_limit,
        "current_spend": current_spend,
        "forecasted_spend": cumulative,
        "breach_probability": min(1.0, cumulative / budget_limit) if budget_limit > 0 else 0.0,
        "days_until_breach": days_until_breach,
    }


@router.get("/alerts")
async def gcp_list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    db = get_db()
    query = {"cloud": "gcp"}
    total = db["gcp_alerts_sent"].count_documents(query)
    skip = (page - 1) * page_size
    docs = list(db["gcp_alerts_sent"].find(query).sort("timestamp", -1).skip(skip).limit(page_size))
    return {"total": total, "page": page, "page_size": page_size, "items": _docs_id(docs)}


@router.post("/alerts/{alert_id}/acknowledge")
async def gcp_acknowledge_alert(alert_id: str) -> Dict[str, Any]:
    db = get_db()
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID.")
    result = db["gcp_alerts_sent"].update_one(
        {"_id": oid},
        {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/recommendations")
async def gcp_list_recommendations() -> List[Dict[str, Any]]:
    db = get_db()
    docs = list(db["gcp_recommendations"].find().sort("created_at", -1).limit(50))
    return _docs_id(docs)


@router.post("/trigger/collect")
async def gcp_trigger_collect() -> Dict[str, Any]:
    import asyncio
    from backend.agents.agent1_gcp_data_collector import collect_gcp_cost_data
    records = await asyncio.to_thread(collect_gcp_cost_data)
    return {"status": "done", "job": "gcp_data_collection", "records_collected": len(records)}


@router.post("/trigger/detect")
async def gcp_trigger_detect(background_tasks: BackgroundTasks) -> Dict[str, str]:
    def _run():
        from backend.agents.agent2_gcp_anomaly_detector import detect_gcp_anomalies
        detect_gcp_anomalies()
    background_tasks.add_task(_run)
    return {"status": "triggered", "job": "gcp_anomaly_detection"}
