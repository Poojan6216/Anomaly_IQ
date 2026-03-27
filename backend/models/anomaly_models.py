"""
Pydantic models for anomaly detection pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BillingData(BaseModel):
    """Raw billing record fetched from AWS Cost Explorer."""

    timestamp: datetime
    service: str
    region: str
    cost: float
    usage_quantity: float = 0.0
    currency: str = "USD"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AnomalyDetected(BaseModel):
    """A cost anomaly identified by the detection pipeline."""

    timestamp: datetime
    severity: str  # "Critical" | "High" | "Medium" | "Low"
    service: str
    region: str
    baseline_cost: float
    actual_cost: float
    cost_delta: float
    percentage_increase: float
    detection_methods: List[str] = Field(default_factory=list)
    status: str = "open"  # "open" | "acknowledged" | "resolved" | "false_positive"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class RootCauseAnalysis(BaseModel):
    """Result of Claude-powered root-cause analysis for an anomaly."""

    anomaly_id: str
    explanation: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    is_legitimate: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Recommendation(BaseModel):
    """An actionable cost-saving recommendation."""

    anomaly_id: str
    action: str
    estimated_savings: float = 0.0
    savings_period: str = "monthly"
    service: str = ""
    region: str = ""
    status: str = "pending"  # "pending" | "approved" | "rejected" | "executed"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserFeedback(BaseModel):
    """User feedback on whether an anomaly was real."""

    anomaly_id: str
    is_real: bool
    comment: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Alert(BaseModel):
    """An alert dispatched to an external channel."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    channel: str  # "email" | "slack" | "digest"
    anomaly_id: str
    severity: str
    message: str
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
