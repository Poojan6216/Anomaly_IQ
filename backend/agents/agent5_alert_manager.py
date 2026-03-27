"""
Agent 5 — Alert Manager
Sends notifications via email (SES) and Slack based on anomaly severity.
Deduplicates alerts to prevent spamming.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3
import httpx
from botocore.exceptions import ClientError
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_SES_FROM_EMAIL: str = os.environ.get("SES_FROM_EMAIL", "")
_SES_REGION: str = os.environ.get("SES_REGION", "us-east-2")
_SLACK_WEBHOOK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")
_ALERT_TO_EMAIL: str = os.environ.get("ALERT_TO_EMAIL", _SES_FROM_EMAIL)

# Twilio SMS (optional — only used for Critical alerts)
_TWILIO_ACCOUNT_SID: str = os.environ.get("TWILIO_ACCOUNT_SID", "")
_TWILIO_AUTH_TOKEN: str = os.environ.get("TWILIO_AUTH_TOKEN", "")
_TWILIO_FROM_NUMBER: str = os.environ.get("TWILIO_FROM_NUMBER", "")
_ALERT_TO_PHONE: str = os.environ.get("ALERT_TO_PHONE", "")

# Channels by severity
_SEVERITY_CHANNELS: Dict[str, List[str]] = {
    "Critical": ["email", "sms"],
    "High": ["email"],
    "Medium": ["email"],
    "Low": ["digest"],
}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _already_alerted(anomaly_id: str, window_hours: int = 1) -> bool:
    """Return True if an alert for this anomaly was sent within *window_hours*."""
    from backend.database.mongodb import get_db

    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    existing = db["alerts_sent"].find_one(
        {
            "anomaly_id": anomaly_id,
            "timestamp": {"$gte": cutoff},
        }
    )
    return existing is not None


def store_alert(
    anomaly_id: str,
    severity: str,
    channel: str,
    message: str,
) -> Optional[str]:
    """Persist an alert record; returns the inserted _id as string."""
    from backend.database.mongodb import get_db

    db = get_db()
    doc: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc),
        "channel": channel,
        "anomaly_id": anomaly_id,
        "severity": severity,
        "message": message,
        "acknowledged": False,
        "acknowledged_at": None,
    }
    try:
        result = db["alerts_sent"].insert_one(doc)
        return str(result.inserted_id)
    except Exception as exc:
        logger.error("Failed to store alert: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Delivery methods
# ---------------------------------------------------------------------------


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via AWS SES. Returns True on success."""
    if not _SES_FROM_EMAIL:
        logger.warning("SES_FROM_EMAIL not set — skipping email.")
        return False
    if not to:
        logger.warning("No recipient address — skipping email.")
        return False

    ses = boto3.client(
        "ses",
        region_name=_SES_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )

    try:
        ses.send_email(
            Source=_SES_FROM_EMAIL,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body, "Charset": "UTF-8"},
                    "Html": {
                        "Data": f"<pre>{body}</pre>",
                        "Charset": "UTF-8",
                    },
                },
            },
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except ClientError as exc:
        logger.error("SES send_email failed: %s", exc)
        return False


def send_slack(message: str, webhook_url: Optional[str] = None) -> bool:
    """POST a message to a Slack Incoming Webhook. Returns True on success."""
    url = webhook_url or _SLACK_WEBHOOK_URL
    if not url:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack notification.")
        return False

    payload = {"text": message}
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Slack notification sent.")
            return True
        logger.error("Slack webhook returned %d: %s", response.status_code, response.text)
        return False
    except httpx.RequestError as exc:
        logger.error("Slack HTTP error: %s", exc)
        return False


def send_sms(to: str, message: str) -> bool:
    """Send an SMS via Twilio. Returns True on success."""
    if not all([_TWILIO_ACCOUNT_SID, _TWILIO_AUTH_TOKEN, _TWILIO_FROM_NUMBER, to]):
        logger.warning("Twilio not fully configured — skipping SMS.")
        return False

    try:
        from twilio.rest import Client  # type: ignore  # optional dependency

        client = Client(_TWILIO_ACCOUNT_SID, _TWILIO_AUTH_TOKEN)
        client.messages.create(body=message[:1600], from_=_TWILIO_FROM_NUMBER, to=to)
        logger.info("SMS sent to %s", to)
        return True
    except ImportError:
        logger.warning("twilio package not installed — skipping SMS. Run: pip install twilio")
        return False
    except Exception as exc:
        logger.error("Twilio SMS failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def send_alert(anomaly_id: str, severity: str) -> List[str]:
    """
    Determine channels for *severity*, check deduplication, and dispatch.
    Returns list of channels that were actually notified.
    """
    from backend.database.mongodb import get_db

    db = get_db()

    if _already_alerted(anomaly_id):
        logger.info("Alert for anomaly %s already sent recently — skipped.", anomaly_id)
        return []

    try:
        anomaly = db["anomalies_detected"].find_one({"_id": ObjectId(anomaly_id)})
    except Exception:
        anomaly = None

    if not anomaly:
        logger.error("Cannot send alert — anomaly not found: %s", anomaly_id)
        return []

    service = anomaly.get("service", "Unknown")
    region = anomaly.get("region", "Unknown")
    cost_delta = anomaly.get("cost_delta", 0)
    pct = anomaly.get("percentage_increase", 0)
    actual = anomaly.get("actual_cost", 0)

    subject = f"[AnomalyIQ] {severity} Cost Anomaly — {service} ({region})"
    body = (
        f"AnomalyIQ has detected a {severity.upper()} cost anomaly.\n\n"
        f"  Service   : {service}\n"
        f"  Region    : {region}\n"
        f"  Severity  : {severity}\n"
        f"  Current   : ${actual:.2f}/hr\n"
        f"  Delta     : +${cost_delta:.2f}/hr (+{pct:.1f}%)\n"
        f"  Anomaly ID: {anomaly_id}\n\n"
        f"Please review at http://localhost:3000 and investigate the cause.\n"
    )

    channels = _SEVERITY_CHANNELS.get(severity, ["email"])
    notified: List[str] = []

    for channel in channels:
        if channel == "email":
            ok = send_email(_ALERT_TO_EMAIL, subject, body)
            if ok:
                store_alert(anomaly_id, severity, "email", subject)
                notified.append("email")
        elif channel == "slack":
            slack_msg = (
                f":rotating_light: *{severity} Cost Anomaly* — {service} ({region})\n"
                f"> Delta: +${cost_delta:.2f}/hr (+{pct:.1f}%)\n"
                f"> ID: `{anomaly_id}`"
            )
            ok = send_slack(slack_msg)
            if ok:
                store_alert(anomaly_id, severity, "slack", slack_msg)
                notified.append("slack")
        elif channel == "sms":
            sms_msg = (
                f"[AnomalyIQ] {severity} AWS Cost Anomaly\n"
                f"{service} ({region}): +${cost_delta:.2f}/hr (+{pct:.1f}%)\n"
                f"ID: {anomaly_id[-8:]}"
            )
            ok = send_sms(_ALERT_TO_PHONE, sms_msg)
            if ok:
                store_alert(anomaly_id, severity, "sms", sms_msg)
                notified.append("sms")
        elif channel == "digest":
            # Queue for daily digest — store with channel="digest"
            store_alert(anomaly_id, severity, "digest", body)
            notified.append("digest")
            logger.info("Alert queued for daily digest: anomaly %s", anomaly_id)

    # Push all fired alerts to connected dashboard clients via WebSocket
    if notified:
        try:
            from backend.api.websocket import broadcast_alert_sync

            alert_ws_payload = {
                "anomaly_id": anomaly_id,
                "severity": severity,
                "service": service,
                "region": region,
                "cost_delta": cost_delta,
                "percentage_increase": pct,
                "channels": notified,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            broadcast_alert_sync(alert_ws_payload)
        except Exception as exc:
            logger.debug("WebSocket broadcast skipped: %s", exc)

    logger.info(
        "Alerts sent for anomaly %s via: %s",
        anomaly_id,
        ", ".join(notified) if notified else "none",
    )
    return notified


def send_daily_digest() -> bool:
    """
    Collect all digest-queued alerts from the last 24 hours and send a summary email.
    """
    from backend.database.mongodb import get_db

    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    pending = list(
        db["alerts_sent"].find(
            {"channel": "digest", "timestamp": {"$gte": cutoff}, "acknowledged": False}
        )
    )

    if not pending:
        logger.info("No pending digest alerts.")
        return True

    lines = [f"AnomalyIQ Daily Digest — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"]
    for alert in pending:
        lines.append(
            f"  [{alert.get('severity', '?')}] Anomaly {alert.get('anomaly_id', '?')}"
        )

    body = "\n".join(lines)
    subject = f"[AnomalyIQ] Daily Digest — {len(pending)} anomalies"

    ok = send_email(_ALERT_TO_EMAIL, subject, body)

    if ok:
        ids = [a["_id"] for a in pending]
        db["alerts_sent"].update_many(
            {"_id": {"$in": ids}},
            {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc)}},
        )

    return ok
