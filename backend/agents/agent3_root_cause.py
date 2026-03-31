"""
Agent 3 — Root Cause Analyser
Uses Claude (claude-opus-4-6) to explain why a cost anomaly occurred.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import anthropic
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
_MODEL = "claude-opus-4-6"

_SYSTEM_PROMPT = """You are an expert multi-cloud cost analyst and DevOps engineer with deep knowledge of AWS, Azure, and GCP.
You will be provided with details of a detected cloud cost anomaly, along with supporting evidence
such as audit log events and monitoring metrics.

Your task is to produce a structured root-cause analysis.  Return your answer
as valid JSON with the following keys:
  - explanation   : string — clear plain-English explanation of why the cost spike occurred
  - root_cause    : string — one-sentence summary of the root cause
  - who           : string — who or what triggered the change (username, automation, unknown)
  - what_changed  : string — description of the infrastructure change
  - is_legitimate : boolean — whether this is an expected/legitimate cost increase
  - confidence    : float (0–1) — how confident you are in this analysis
  - evidence_used : list of strings — which evidence items were most relevant

Be concise, precise, and actionable. Reference the specific cloud provider and its services correctly."""


def _get_client() -> anthropic.Anthropic:
    if not _ANTHROPIC_API_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in the environment.")
    return anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)


def analyze_anomaly(anomaly_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the anomaly from MongoDB, gather supporting evidence,
    call Claude for root-cause analysis, and persist the result.

    Returns the root_cause_analysis document or None on failure.
    """
    from backend.database.mongodb import get_db

    db = get_db()

    # ------------------------------------------------------------------ #
    # 1. Load anomaly
    # ------------------------------------------------------------------ #
    try:
        oid = ObjectId(anomaly_id)
    except Exception:
        logger.error("Invalid anomaly_id: %s", anomaly_id)
        return None

    anomaly = db["anomalies_detected"].find_one({"_id": oid})
    if not anomaly:
        logger.error("Anomaly not found: %s", anomaly_id)
        return None

    provider = anomaly.get("provider", "aws")

    # ------------------------------------------------------------------ #
    # 2. Gather evidence (provider-specific)
    # ------------------------------------------------------------------ #
    anomaly_time: datetime = anomaly.get("timestamp", datetime.now(timezone.utc))
    if anomaly_time.tzinfo is None:
        anomaly_time = anomaly_time.replace(tzinfo=timezone.utc)

    hours_lookback = max(
        1,
        int((datetime.now(timezone.utc) - anomaly_time).total_seconds() / 3600) + 2,
    )

    audit_events: list = []
    compute_data: Dict[str, Any] = {}

    if provider == "aws":
        try:
            from backend.agents.agent1_data_collector import collect_cloudtrail_events
            audit_events = collect_cloudtrail_events(hours=hours_lookback)[:20]
        except Exception as exc:
            logger.warning("CloudTrail fetch skipped: %s", exc)

        if "EC2" in anomaly.get("service", ""):
            try:
                from backend.agents.agent1_data_collector import get_idle_ec2_instances
                compute_data["idle_instances"] = get_idle_ec2_instances(hours=hours_lookback)
            except Exception as exc:
                logger.warning("CloudWatch fetch skipped: %s", exc)

    evidence = {
        "provider": provider,
        "audit_events": audit_events,
        "compute_metrics": compute_data,
        "historical_baseline": anomaly.get("baseline_cost"),
        "detection_methods": anomaly.get("detection_methods", []),
    }

    # ------------------------------------------------------------------ #
    # 3. Build Claude prompt
    # ------------------------------------------------------------------ #
    anomaly_summary = {
        "provider": provider,
        "service": anomaly.get("service"),
        "region": anomaly.get("region"),
        "severity": anomaly.get("severity"),
        "actual_cost_per_hour": anomaly.get("actual_cost"),
        "baseline_cost_per_hour": anomaly.get("baseline_cost"),
        "cost_delta": anomaly.get("cost_delta"),
        "percentage_increase": anomaly.get("percentage_increase"),
        "timestamp": anomaly_time.isoformat(),
    }

    user_message = (
        f"Anomaly details:\n{json.dumps(anomaly_summary, indent=2)}\n\n"
        f"Supporting evidence:\n{json.dumps(evidence, indent=2, default=str)}\n\n"
        "Please provide the root-cause analysis as JSON."
    )

    # ------------------------------------------------------------------ #
    # 4. Call Claude with streaming
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

        logger.debug("Claude RCA response:\n%s", full_response)
    except anthropic.APIError as exc:
        logger.error("Claude API error during RCA: %s", exc)
        return None

    # ------------------------------------------------------------------ #
    # 5. Parse and store result
    # ------------------------------------------------------------------ #
    try:
        # Strip markdown code fences if present
        cleaned = full_response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Claude did not return valid JSON; storing raw text.")
        parsed = {"explanation": full_response, "root_cause": "See explanation"}

    rca_doc: Dict[str, Any] = {
        "anomaly_id": anomaly_id,
        "explanation": parsed.get("explanation", ""),
        "root_cause": parsed.get("root_cause", ""),
        "who": parsed.get("who", "Unknown"),
        "what_changed": parsed.get("what_changed", ""),
        "evidence": evidence,
        "confidence": float(parsed.get("confidence", 0.5)),
        "is_legitimate": bool(parsed.get("is_legitimate", False)),
        "evidence_used": parsed.get("evidence_used", []),
        "raw_response": full_response,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        db["root_cause_analysis"].replace_one(
            {"anomaly_id": anomaly_id},
            rca_doc,
            upsert=True,
        )
        logger.info("RCA stored for anomaly %s (confidence=%.2f)", anomaly_id, rca_doc["confidence"])
    except Exception as exc:
        logger.error("Failed to store RCA: %s", exc)

    return rca_doc
