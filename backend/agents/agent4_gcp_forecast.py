"""
Agent 4 GCP — Cost Forecaster
Uses Prophet (with ARIMA fallback) to forecast GCP spending.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _load_gcp_history(service: Optional[str] = None, lookback_days: int = 90) -> pd.DataFrame:
    """Return a DataFrame with columns [ds, y] from gcp_billing_raw."""
    from backend.database.mongodb import get_db

    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    query: Dict[str, Any] = {"timestamp": {"$gte": cutoff}}
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

    records = list(db["gcp_billing_raw"].aggregate(pipeline))
    if not records:
        return pd.DataFrame(columns=["ds", "y"])

    df = pd.DataFrame(records)
    df.rename(columns={"_id": "ds"}, inplace=True)
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = df["y"].astype(float)
    return df


def generate_gcp_forecast(service: Optional[str] = None, days: int = 30) -> Optional[Dict[str, Any]]:
    """Train a forecasting model on GCP data and store predictions."""
    from backend.database.mongodb import get_db

    db = get_db()
    service_key = service or "ALL"

    df = _load_gcp_history(service=service, lookback_days=90)

    if df.empty or len(df) < 48:
        logger.warning("GCP: Insufficient data for forecast service=%s (rows=%d).", service_key, len(df))
        return None

    model_used = "prophet"
    forecast_df = None

    try:
        from prophet import Prophet
        model = Prophet(
            interval_width=0.95,
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=True,
            changepoint_prior_scale=0.05,
        )
        model.fit(df)
        future = model.make_future_dataframe(periods=days * 24, freq="H")
        forecast = model.predict(future)
        last_date = df["ds"].max()
        forecast_df = forecast[forecast["ds"] > last_date][["ds", "yhat", "yhat_lower", "yhat_upper"]]
    except Exception as exc:
        logger.warning("GCP Prophet failed (%s), falling back to ARIMA.", exc)
        model_used = "arima"
        try:
            from statsmodels.tsa.arima.model import ARIMA
            series = df.set_index("ds")["y"].resample("H").sum().fillna(0)
            fitted = ARIMA(series, order=(2, 1, 2)).fit()
            steps = days * 24
            fc = fitted.forecast(steps=steps)
            ci = fitted.get_forecast(steps=steps).conf_int(alpha=0.20)
            idx = pd.date_range(start=series.index[-1] + pd.Timedelta(hours=1), periods=steps, freq="H")
            forecast_df = pd.DataFrame({
                "ds": idx, "yhat": fc.values,
                "yhat_lower": ci.iloc[:, 0].values, "yhat_upper": ci.iloc[:, 1].values,
            })
        except Exception as exc2:
            logger.error("GCP ARIMA also failed: %s", exc2)
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

    forecast_doc: Dict[str, Any] = {
        "forecast_date": datetime.now(timezone.utc),
        "service": service_key,
        "cloud": "gcp",
        "horizon_days": days,
        "model_used": model_used,
        "predictions": predictions,
        "mape": None,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        db["gcp_forecasts"].insert_one(forecast_doc)
        logger.info("GCP forecast stored: service=%s, model=%s, points=%d.", service_key, model_used, len(predictions))
    except Exception as exc:
        logger.error("Failed to store GCP forecast: %s", exc)

    return forecast_doc
