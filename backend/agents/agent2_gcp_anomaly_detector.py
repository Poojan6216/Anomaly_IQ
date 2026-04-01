"""
Agent 2 GCP — Anomaly Detector
Reuses the same ML detection methods as AWS but reads from gcp_billing_raw.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import numpy as np

from backend.agents.agent2_anomaly_detector import (
    classify_severity,
    z_score_detection,
    isolation_forest_detection,
    stl_decomposition_detection,
)

logger = logging.getLogger(__name__)


def detect_gcp_anomalies() -> List[Dict[str, Any]]:
    """Run anomaly detection over gcp_billing_raw. Returns new anomaly docs."""
    from backend.database.mongodb import get_db
    from backend.api.websocket import broadcast_anomaly_sync

    db = get_db()
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    current_records = list(
        db["gcp_billing_raw"].find({"timestamp": {"$gte": one_hour_ago}})
    )

    if not current_records:
        logger.info("GCP: No billing records in the last hour — skipping detection.")
        return []

    thirty_days_ago = now - timedelta(days=30)
    historical = list(
        db["gcp_billing_raw"].find(
            {"timestamp": {"$gte": thirty_days_ago, "$lt": one_hour_ago}}
        )
    )

    history_by_service: Dict[str, List[float]] = {}
    for rec in historical:
        key = f"{rec['service']}|{rec['region']}"
        history_by_service.setdefault(key, []).append(float(rec["cost"]))

    new_anomalies: List[Dict[str, Any]] = []

    for rec in current_records:
        service = rec["service"]
        region = rec["region"]
        current_cost = float(rec["cost"])
        key = f"{service}|{region}"

        hist_costs = history_by_service.get(key, [])
        if len(hist_costs) < 5:
            continue

        z_anomaly, z_score = z_score_detection(hist_costs, current_cost)
        all_costs = hist_costs + [current_cost]
        iso_anomaly, iso_score = isolation_forest_detection(all_costs)
        stl_anomaly, stl_z = stl_decomposition_detection(hist_costs, current_cost)

        triggered_methods = []
        if z_anomaly:
            triggered_methods.append("z_score")
        if iso_anomaly:
            triggered_methods.append("isolation_forest")
        if stl_anomaly:
            triggered_methods.append("stl_decomposition")

        if not triggered_methods:
            continue

        baseline = float(np.mean(hist_costs))
        cost_delta = current_cost - baseline
        percentage_increase = (cost_delta / baseline) * 100.0 if baseline > 0 else 0.0

        severity = classify_severity(cost_delta, percentage_increase)

        anomaly_doc: Dict[str, Any] = {
            "timestamp": rec["timestamp"],
            "severity": severity,
            "service": service,
            "region": region,
            "cloud": "gcp",
            "baseline_cost": baseline,
            "actual_cost": current_cost,
            "cost_delta": cost_delta,
            "percentage_increase": percentage_increase,
            "detection_methods": triggered_methods,
            "status": "open",
            "created_at": datetime.now(timezone.utc),
        }

        try:
            result = db["gcp_anomalies_detected"].insert_one(anomaly_doc)
            anomaly_doc["_id"] = str(result.inserted_id)
            new_anomalies.append(anomaly_doc)
            logger.info(
                "GCP Anomaly [%s] %s / %s — delta $%.4f (%.1f%%)",
                severity, service, region, cost_delta, percentage_increase,
            )
        except Exception as exc:
            logger.error("Failed to store GCP anomaly: %s", exc)
            continue

        broadcast_anomaly_sync(anomaly_doc)
        _trigger_downstream(str(result.inserted_id), severity)

    logger.info("GCP detection complete: %d new anomalies.", len(new_anomalies))
    return new_anomalies


def _trigger_downstream(anomaly_id: str, severity: str) -> None:
    """Fire alerts and recommendations for GCP anomalies."""
    import threading

    def _run():
        try:
            from backend.agents.agent5_alert_manager import store_alert
            from backend.database.mongodb import get_db
            from bson import ObjectId

            db = get_db()
            anomaly = db["gcp_anomalies_detected"].find_one({"_id": ObjectId(anomaly_id)})
            if not anomaly:
                return

            service = anomaly.get("service", "Unknown")
            region = anomaly.get("region", "Unknown")
            cost_delta = anomaly.get("cost_delta", 0)
            pct = anomaly.get("percentage_increase", 0)

            message = (
                f"GCP {severity} cost anomaly: {service} ({region}) "
                f"+${cost_delta:.4f}/hr (+{pct:.1f}%)"
            )
            store_alert(anomaly_id, severity, "email", message)
        except Exception as exc:
            logger.error("GCP downstream error for %s: %s", anomaly_id, exc)

    threading.Thread(target=_run, daemon=True).start()
