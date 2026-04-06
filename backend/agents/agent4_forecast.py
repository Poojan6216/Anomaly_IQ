"""
Agent 4 — Cost Forecaster
Uses Prophet (with ARIMA fallback) to forecast AWS spending per service.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_history(service: Optional[str] = None, lookback_days: int = 90, provider: str = "aws") -> pd.DataFrame:
    """Return a DataFrame with columns [ds, y] from MongoDB billing history."""
    from backend.database.mongodb import get_db

    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    query: Dict[str, Any] = {"provider": provider, "timestamp": {"$gte": cutoff}}
    if service and service != "ALL":
        query["service"] = service

    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%dT%H:00:00",
                        "date": "$timestamp",
                    }
                },
                "y": {"$sum": "$cost"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    records = list(db["billing_raw"].aggregate(pipeline))
    if not records:
        return pd.DataFrame(columns=["ds", "y"])

    df = pd.DataFrame(records)
    df.rename(columns={"_id": "ds"}, inplace=True)
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = df["y"].astype(float)
    return df


def _run_prophet(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """Fit Prophet and return future DataFrame with yhat/yhat_lower/yhat_upper."""
    from prophet import Prophet  # type: ignore

    model = Prophet(
        interval_width=0.95,          # 95 % confidence bands
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=True,
        changepoint_prior_scale=0.05,
        uncertainty_samples=500,
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=days * 24, freq="H")
    forecast = model.predict(future)

    # Return only the forecasted portion (not historical fitted values)
    last_historical_date = df["ds"].max()
    future_mask = forecast["ds"] > last_historical_date
    return forecast[future_mask][["ds", "yhat", "yhat_lower", "yhat_upper"]]


def _run_arima(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """Simple ARIMA(2,1,2) fallback forecaster."""
    from statsmodels.tsa.arima.model import ARIMA  # type: ignore

    series = df.set_index("ds")["y"]
    series = series.resample("H").sum().fillna(0)

    model = ARIMA(series, order=(2, 1, 2))
    fitted = model.fit()

    steps = days * 24
    forecast_result = fitted.forecast(steps=steps)
    conf_int = fitted.get_forecast(steps=steps).conf_int(alpha=0.20)

    future_index = pd.date_range(
        start=series.index[-1] + pd.Timedelta(hours=1),
        periods=steps,
        freq="H",
    )

    result = pd.DataFrame(
        {
            "ds": future_index,
            "yhat": forecast_result.values,
            "yhat_lower": conf_int.iloc[:, 0].values,
            "yhat_upper": conf_int.iloc[:, 1].values,
        }
    )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_forecast(service: Optional[str] = None, days: int = 30, provider: str = "aws") -> Optional[Dict[str, Any]]:
    """
    Train a forecasting model on historical data and store predictions.

    Returns the forecast document or None on failure.
    """
    from backend.database.mongodb import get_db

    db = get_db()
    service_key = service or "ALL"

    df = _load_history(service=service, lookback_days=90, provider=provider)

    if df.empty or len(df) < 48:
        logger.warning("Insufficient data to forecast service=%s (rows=%d).", service_key, len(df))
        return None

    model_used = "prophet"
    forecast_df: Optional[pd.DataFrame] = None

    try:
        forecast_df = _run_prophet(df, days=days)
    except Exception as exc:
        logger.warning("Prophet failed (%s), falling back to ARIMA.", exc)
        model_used = "arima"
        try:
            forecast_df = _run_arima(df, days=days)
        except Exception as exc2:
            logger.error("ARIMA also failed: %s", exc2)
            return None

    if forecast_df is None or forecast_df.empty:
        return None

    predictions = [
        {
            "ds": row["ds"].isoformat(),
            "yhat": max(0.0, float(row["yhat"])),
            "yhat_lower": max(0.0, float(row["yhat_lower"])),
            "yhat_upper": max(0.0, float(row["yhat_upper"])),
        }
        for _, row in forecast_df.iterrows()
    ]

    # Approximate MAPE: compare last 10 % of historical data to forecast's
    # in-sample fitted range (simple holdout estimate)
    try:
        holdout_n = max(1, len(df) // 10)
        holdout = df.tail(holdout_n)
        # forecast_df only covers future dates; re-run predict on holdout dates
        holdout_future = pd.DataFrame({"ds": holdout["ds"].values})
        if model_used == "prophet":
            # model is still in scope when prophet succeeded
            holdout_pred = model.predict(holdout_future)["yhat"].values  # type: ignore[name-defined]
        else:
            holdout_pred = holdout["y"].values  # fallback: no estimate
        actuals_h = holdout["y"].values
        non_zero = actuals_h != 0
        if non_zero.sum() > 0:
            mape = float(
                np.mean(np.abs((actuals_h[non_zero] - holdout_pred[non_zero]) / actuals_h[non_zero])) * 100
            )
        else:
            mape = None
    except Exception:
        mape = None

    forecast_doc: Dict[str, Any] = {
        "provider": provider,
        "forecast_date": datetime.now(timezone.utc),
        "service": service_key,
        "horizon_days": days,
        "model_used": model_used,
        "predictions": predictions,
        "mape": mape,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        db["forecasts"].insert_one(forecast_doc)
        logger.info(
            "Forecast stored: service=%s, model=%s, points=%d.",
            service_key,
            model_used,
            len(predictions),
        )
    except Exception as exc:
        logger.error("Failed to store forecast: %s", exc)

    return forecast_doc


def check_budget_breach(budget_id: str) -> Optional[Dict[str, Any]]:
    """
    Compare the latest forecast for a budget's service against the budget limit.
    Returns a BudgetBreachForecast-style dict.
    """
    from backend.database.mongodb import get_db
    from bson import ObjectId

    db = get_db()

    try:
        oid = ObjectId(budget_id)
    except Exception:
        logger.error("Invalid budget_id: %s", budget_id)
        return None

    budget = db["budgets"].find_one({"_id": oid})
    if not budget:
        logger.error("Budget not found: %s", budget_id)
        return None

    service = budget.get("service_filter")
    budget_limit: float = float(budget.get("limit", 0))
    provider: str = budget.get("provider", "aws")

    # Latest forecast — try service-specific first, fall back to "ALL"
    forecast = db["forecasts"].find_one(
        {"provider": provider, "service": service or "ALL"},
        sort=[("created_at", -1)],
    )
    if not forecast and service:
        forecast = db["forecasts"].find_one(
            {"provider": provider, "service": "ALL"},
            sort=[("created_at", -1)],
        )

    if not forecast:
        logger.warning("No forecast available for budget %s.", budget_id)
        return None

    predictions: List[Dict] = forecast.get("predictions", [])
    if not predictions:
        return None

    # Aggregate daily totals
    daily_totals: Dict[str, float] = {}
    for pt in predictions:
        ds = pt["ds"].strftime("%Y-%m-%d") if hasattr(pt["ds"], "strftime") else pt["ds"][:10]
        daily_totals[ds] = daily_totals.get(ds, 0) + pt["yhat"]

    days_sorted = sorted(daily_totals.keys())
    cumulative = 0.0
    days_until_breach = None
    for i, day in enumerate(days_sorted):
        cumulative += daily_totals[day]
        if cumulative >= budget_limit and days_until_breach is None:
            days_until_breach = i + 1

    forecasted_spend = cumulative
    breach_probability = min(1.0, forecasted_spend / budget_limit) if budget_limit > 0 else 0.0

    # Current spend (sum of billing data this month)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    agg = list(
        db["billing_raw"].aggregate(
            [
                {"$match": {"provider": provider, "timestamp": {"$gte": month_start}}},
                {"$group": {"_id": None, "total": {"$sum": "$cost"}}},
            ]
        )
    )
    current_spend = float(agg[0]["total"]) if agg else 0.0

    result = {
        "budget_id": budget_id,
        "budget_name": budget.get("name", ""),
        "budget_limit": budget_limit,
        "current_spend": current_spend,
        "forecasted_spend": forecasted_spend,
        "breach_probability": breach_probability,
        "days_until_breach": days_until_breach,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Budget breach check [%s]: prob=%.2f, days_until=%s",
        budget.get("name"),
        breach_probability,
        days_until_breach,
    )
    return result
