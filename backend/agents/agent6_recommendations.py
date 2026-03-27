"""
Agent 6 — Recommendation Engine
Uses Claude (claude-opus-4-6) to generate actionable cost-saving recommendations.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import anthropic
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
_MODEL = "claude-opus-4-6"

_SYSTEM_PROMPT = """You are a senior AWS cost optimisation engineer.
You will receive details of a detected cost anomaly, a root-cause analysis (if available),
and optional CloudWatch metrics for idle resources.

Generate a JSON array of actionable recommendations.  Each recommendation must follow this schema:
{
  "action": "<short imperative sentence — what to do>",
  "detail": "<paragraph explaining why and how>",
  "service": "<AWS service affected>",
  "region": "<AWS region>",
  "estimated_savings": <float — estimated USD saved per month>,
  "effort": "low|medium|high",
  "priority": 1–5  (1 = highest)
}

Return ONLY the JSON array, no extra prose.
Order recommendations by priority (1 first).
Be specific and realistic about savings estimates."""


def _get_client() -> anthropic.Anthropic:
    if not _ANTHROPIC_API_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in the environment.")
    return anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)


def estimate_savings(recommendation_doc: Dict[str, Any]) -> float:
    """Return the estimated monthly savings for a recommendation document."""
    return float(recommendation_doc.get("estimated_savings", 0.0))


def generate_recommendations(anomaly_id: str) -> List[Dict[str, Any]]:
    """
    Fetch anomaly + RCA data, gather CloudWatch idle-instance metrics,
    call Claude for recommendations, store and return the results.
    """
    from backend.database.mongodb import get_db
    from backend.agents.agent1_data_collector import get_idle_ec2_instances

    db = get_db()

    # ------------------------------------------------------------------ #
    # 1. Load anomaly
    # ------------------------------------------------------------------ #
    try:
        oid = ObjectId(anomaly_id)
    except Exception:
        logger.error("Invalid anomaly_id: %s", anomaly_id)
        return []

    anomaly = db["anomalies_detected"].find_one({"_id": oid})
    if not anomaly:
        logger.error("Anomaly not found: %s", anomaly_id)
        return []

    # ------------------------------------------------------------------ #
    # 2. Load root-cause analysis (may not exist yet)
    # ------------------------------------------------------------------ #
    rca = db["root_cause_analysis"].find_one({"anomaly_id": anomaly_id})

    # ------------------------------------------------------------------ #
    # 3. Gather idle EC2 instances (if relevant service)
    # ------------------------------------------------------------------ #
    idle_instances: List[str] = []
    if "EC2" in anomaly.get("service", ""):
        try:
            idle_instances = get_idle_ec2_instances(cpu_threshold=5.0, hours=24)
        except Exception as exc:
            logger.warning("Could not fetch idle instances: %s", exc)

    # ------------------------------------------------------------------ #
    # 4. Build prompt context
    # ------------------------------------------------------------------ #
    anomaly_ctx = {
        "service": anomaly.get("service"),
        "region": anomaly.get("region"),
        "severity": anomaly.get("severity"),
        "cost_delta_per_hour": anomaly.get("cost_delta"),
        "percentage_increase": anomaly.get("percentage_increase"),
        "actual_cost_per_hour": anomaly.get("actual_cost"),
        "baseline_cost_per_hour": anomaly.get("baseline_cost"),
    }

    rca_ctx = {}
    if rca:
        rca_ctx = {
            "root_cause": rca.get("root_cause", ""),
            "explanation": rca.get("explanation", ""),
            "who": rca.get("who", ""),
            "what_changed": rca.get("what_changed", ""),
            "is_legitimate": rca.get("is_legitimate", False),
            "confidence": rca.get("confidence", 0.5),
        }

    user_message = (
        f"Anomaly:\n{json.dumps(anomaly_ctx, indent=2)}\n\n"
        f"Root Cause Analysis:\n{json.dumps(rca_ctx, indent=2)}\n\n"
        f"Idle EC2 instances (CPU < 5%): {idle_instances}\n\n"
        "Please generate cost-optimisation recommendations as a JSON array."
    )

    # ------------------------------------------------------------------ #
    # 5. Call Claude with streaming
    # ------------------------------------------------------------------ #
    client = _get_client()
    full_response = ""

    try:
        with client.messages.stream(
            model=_MODEL,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                full_response += text
    except anthropic.APIError as exc:
        logger.error("Claude API error during recommendations: %s", exc)
        return []

    # ------------------------------------------------------------------ #
    # 6. Parse recommendations
    # ------------------------------------------------------------------ #
    try:
        cleaned = full_response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        parsed: List[Dict] = json.loads(cleaned)
        if not isinstance(parsed, list):
            parsed = [parsed]
    except json.JSONDecodeError:
        logger.warning("Claude returned non-JSON recommendations; wrapping as single item.")
        parsed = [{"action": full_response, "estimated_savings": 0.0}]

    # ------------------------------------------------------------------ #
    # 7. Persist to MongoDB
    # ------------------------------------------------------------------ #
    stored: List[Dict[str, Any]] = []
    for item in parsed:
        rec_doc: Dict[str, Any] = {
            "anomaly_id": anomaly_id,
            "action": item.get("action", ""),
            "detail": item.get("detail", ""),
            "estimated_savings": float(item.get("estimated_savings", 0.0)),
            "savings_period": "monthly",
            "service": item.get("service", anomaly.get("service", "")),
            "region": item.get("region", anomaly.get("region", "")),
            "effort": item.get("effort", "medium"),
            "priority": int(item.get("priority", 3)),
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }

        try:
            result = db["recommendations"].insert_one(rec_doc)
            rec_doc["_id"] = str(result.inserted_id)
            stored.append(rec_doc)
        except Exception as exc:
            logger.error("Failed to store recommendation: %s", exc)

    logger.info(
        "Generated %d recommendations for anomaly %s.",
        len(stored),
        anomaly_id,
    )

    # Send a single email summarising all new recommendations
    if stored:
        try:
            from backend.agents.agent5_alert_manager import send_email, _ALERT_TO_EMAIL
            subject = (
                f"[AnomalyIQ] {len(stored)} Cost-Saving Recommendation"
                f"{'s' if len(stored) > 1 else ''} — "
                f"{anomaly.get('service', '')} ({anomaly.get('region', '')})"
            )
            lines = [
                f"AnomalyIQ has generated {len(stored)} recommendation"
                f"{'s' if len(stored) > 1 else ''} for anomaly {anomaly_id}.\n"
            ]
            for idx, rec in enumerate(stored, 1):
                lines.append(
                    f"{idx}. {rec['action']}\n"
                    f"   Estimated savings: ${rec['estimated_savings']:.2f}/month\n"
                    f"   Effort: {rec.get('effort', 'medium')} | Priority: P{rec.get('priority', 3)}\n"
                )
            send_email(_ALERT_TO_EMAIL, subject, "\n".join(lines))
        except Exception as exc:
            logger.debug("Could not send recommendations notification: %s", exc)

    return stored


