"""
Pydantic models for cost forecasting.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    """A single predicted data point from Prophet / ARIMA."""

    ds: datetime          # datestamp
    yhat: float           # predicted value
    yhat_lower: float     # lower confidence bound
    yhat_upper: float     # upper confidence bound

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ForecastResult(BaseModel):
    """Full forecast output for a service (or aggregate) over a horizon."""

    forecast_date: datetime = Field(default_factory=datetime.utcnow)
    service: str = "ALL"
    horizon_days: int = 30
    model_used: str = "prophet"  # "prophet" | "arima"
    predictions: List[ForecastPoint] = Field(default_factory=list)
    mape: Optional[float] = None          # mean absolute percentage error
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BudgetConfig(BaseModel):
    """Budget definition with alert thresholds."""

    budget_type: str = "monthly"  # "monthly" | "daily" | "service"
    name: str
    limit: float
    alert_thresholds: List[float] = Field(
        default_factory=lambda: [0.5, 0.8, 0.9, 1.0]
    )
    service_filter: Optional[str] = None   # e.g. "Amazon EC2"
    region_filter: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BudgetBreachForecast(BaseModel):
    """Result of checking whether a budget is forecasted to be breached."""

    budget_id: str
    budget_name: str
    budget_limit: float
    current_spend: float
    forecasted_spend: float
    breach_probability: float = Field(ge=0.0, le=1.0)
    days_until_breach: Optional[int] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
