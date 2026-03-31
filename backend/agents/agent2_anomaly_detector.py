"""
Agent 2 — Anomaly Detector
Uses multiple statistical and ML methods to detect cost anomalies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Severity classifier
# ---------------------------------------------------------------------------


def classify_severity(cost_delta: float, percentage_increase: float) -> str:
    """
    Classify anomaly severity based on absolute cost delta and relative increase.

    Rules:
        Critical  : >200 % increase OR >$500/hr delta
        High      : 100–200 % OR $200–$500/hr
        Medium    : 50–100 %  OR $100–$200/hr
        Low       : 25–50 %   OR <$100/hr
    """
    if percentage_increase > 200 or cost_delta > 500:
        return "Critical"
    if percentage_increase > 100 or cost_delta > 200:
        return "High"
    if percentage_increase > 50 or cost_delta > 100:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Detection methods
# ---------------------------------------------------------------------------


def z_score_detection(
    service_data: List[float],
    current_cost: float,
    threshold: float = 3.0,
) -> Tuple[bool, float]:
    """
    Return (is_anomaly, z_score).
    Flags if *current_cost* is more than *threshold* standard deviations from the mean.
    """
    if len(service_data) < 5:
        return False, 0.0

    arr = np.array(service_data, dtype=float)
    mean = arr.mean()
    std = arr.std()

    if std == 0:
        return False, 0.0

    z = (current_cost - mean) / std
    return abs(z) >= threshold, float(z)


def isolation_forest_detection(
    data: List[float],
    contamination: float = 0.05,
) -> Tuple[bool, float]:
    """
    Use IsolationForest to detect if the last value in *data* is an anomaly.
    Returns (is_anomaly, anomaly_score) where score < 0 indicates anomaly.
    """
    if len(data) < 10:
        return False, 0.0

    X = np.array(data, dtype=float).reshape(-1, 1)
    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(X)

    score = float(model.decision_function(X[-1].reshape(1, -1))[0])
    prediction = model.predict(X[-1].reshape(1, -1))[0]

    return prediction == -1, score


def stl_decomposition_detection(
    service_data: List[float],
    current_cost: float,
    threshold: float = 3.0,
    period: int = 24,
) -> Tuple[bool, float]:
    """
    STL (Seasonal-Trend decomposition using LOESS) detection.

    Decomposes the historical + current cost series into trend, seasonal, and
    residual components.  Flags if the current point's residual is more than
    *threshold* standard deviations from the residual distribution mean.

    Requires at least 2× the seasonal period of data.
    """
    min_points = period * 2
    if len(service_data) < min_points:
        return False, 0.0

    try:
        from statsmodels.tsa.seasonal import STL  # type: ignore

        full_series = pd.Series(service_data + [current_cost])
        stl = STL(full_series, period=period, robust=True)
        result = stl.fit()

        residuals = result.resid
        current_residual = float(residuals.iloc[-1])
        residual_std = float(residuals.std())

        if residual_std == 0:
            return False, 0.0

        z = (current_residual - float(residuals.mean())) / residual_std
        return abs(z) >= threshold, float(z)

    except Exception as exc:
        logger.debug("STL detection skipped: %s", exc)
        return False, 0.0


def rolling_window_comparison(
    service: str,
    region: str,
    current_cost: float,
    provider: str = "aws",
    threshold_multiplier: float = 2.0,
) -> Tuple[bool, float, float]:
    """
    Compare *current_cost* to the same hour one week ago.
    Returns (is_anomaly, baseline_cost, percentage_change).
    """
    from backend.database.mongodb import get_db

    db = get_db()
    now = datetime.now(timezone.utc)
    week_ago_start = now - timedelta(days=7, hours=1)
    week_ago_end = now - timedelta(days=7) + timedelta(hours=1)

    cursor = db["billing_raw"].find(
        {
            "provider": provider,
            "service": service,
            "region": region,
            "timestamp": {"$gte": week_ago_start, "$lte": week_ago_end},
        }
    )

    records = list(cursor)
    if not records:
        return False, 0.0, 0.0

    baseline = float(np.mean([r["cost"] for r in records]))

    if baseline == 0:
        if current_cost > 0:
            return True, baseline, 100.0
        return False, baseline, 0.0

    pct_change = ((current_cost - baseline) / baseline) * 100.0
    is_anomaly = current_cost > baseline * threshold_multiplier

    return is_anomaly, baseline, pct_change


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def detect_anomalies(provider: str = "aws") -> List[Dict[str, Any]]:
    """
    Run all detection methods over the most recent hour's billing data for the
    given cloud provider and store any anomalies in MongoDB.
    Returns the list of new anomaly documents.
    """
    from backend.database.mongodb import get_db
    from backend.api.websocket import broadcast_anomaly_sync  # thread-safe WS bridge

    db = get_db()
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Latest snapshot (last hour) for this provider
    current_records = list(
        db["billing_raw"].find(
            {"provider": provider, "timestamp": {"$gte": one_hour_ago}}
        )
    )

    if not current_records:
        logger.info("No billing records in the last hour for provider=%s — skipping detection.", provider)
        return []

    # Historical window (last 30 days) for this provider
    thirty_days_ago = now - timedelta(days=30)
    historical = list(
        db["billing_raw"].find(
            {"provider": provider, "timestamp": {"$gte": thirty_days_ago, "$lt": one_hour_ago}}
        )
    )

    # Build per-service cost history
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

        # --- Z-score ---
        z_anomaly, z_score = z_score_detection(hist_costs, current_cost)

        # --- Isolation Forest ---
        all_costs = hist_costs + [current_cost]
        iso_anomaly, iso_score = isolation_forest_detection(all_costs)

        # --- Rolling window ---
        rw_anomaly, baseline, pct_change = rolling_window_comparison(
            service, region, current_cost, provider=provider
        )

        # --- STL decomposition ---
        stl_anomaly, stl_z = stl_decomposition_detection(hist_costs, current_cost)

        triggered_methods = []
        if z_anomaly:
            triggered_methods.append("z_score")
        if iso_anomaly:
            triggered_methods.append("isolation_forest")
        if rw_anomaly:
            triggered_methods.append("rolling_window")
        if stl_anomaly:
            triggered_methods.append("stl_decomposition")

        # Require at least one method to flag
        if not triggered_methods:
            continue

        # If baseline not yet computed (no rolling window data), use hist mean
        if baseline == 0.0 and hist_costs:
            baseline = float(np.mean(hist_costs))

        cost_delta = current_cost - baseline
        if baseline > 0:
            percentage_increase = (cost_delta / baseline) * 100.0
        else:
            percentage_increase = pct_change if pct_change else 0.0

        severity = classify_severity(cost_delta, percentage_increase)

        anomaly_doc: Dict[str, Any] = {
            "provider": provider,
            "timestamp": rec["timestamp"],
            "severity": severity,
            "service": service,
            "region": region,
            "baseline_cost": baseline,
            "actual_cost": current_cost,
            "cost_delta": cost_delta,
            "percentage_increase": percentage_increase,
            "detection_methods": triggered_methods,
            "status": "open",
            "created_at": datetime.now(timezone.utc),
        }

        try:
            result = db["anomalies_detected"].insert_one(anomaly_doc)
            anomaly_doc["_id"] = str(result.inserted_id)
            new_anomalies.append(anomaly_doc)
            logger.info(
                "Anomaly detected [%s] %s / %s — delta $%.2f (%.1f%%)",
                severity,
                service,
                region,
                cost_delta,
                percentage_increase,
            )
        except Exception as exc:
            logger.error("Failed to store anomaly: %s", exc)
            continue

        # Push to dashboard via WebSocket (thread-safe)
        broadcast_anomaly_sync(anomaly_doc)

        # Trigger downstream agents asynchronously
        _trigger_downstream(str(result.inserted_id), severity)

    logger.info("Detection pass complete: %d new anomalies.", len(new_anomalies))
    return new_anomalies


def _trigger_downstream(anomaly_id: str, severity: str) -> None:
    """Fire-and-forget triggers for agent3, agent5, agent6."""
    import threading

    def _run():
        try:
            from backend.agents.agent3_root_cause import analyze_anomaly
            from backend.agents.agent5_alert_manager import send_alert
            from backend.agents.agent6_recommendations import generate_recommendations

            analyze_anomaly(anomaly_id)
            send_alert(anomaly_id, severity)
            generate_recommendations(anomaly_id)
        except Exception as exc:
            logger.error("Downstream agent error for anomaly %s: %s", anomaly_id, exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
