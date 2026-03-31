"""
APScheduler-based task scheduler for AnomalyIQ.
Runs data collection and anomaly detection on a schedule,
and triggers downstream agents when anomalies are found.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


# ---------------------------------------------------------------------------
# Job wrappers
# ---------------------------------------------------------------------------


def _job_collect_data() -> None:
    """Collect cost data for all three cloud providers."""
    for provider, module_path in [
        ("aws",   "backend.agents.agent1_data_collector"),
        ("azure", "backend.agents.agent1_azure_data_collector"),
        ("gcp",   "backend.agents.agent1_gcp_data_collector"),
    ]:
        logger.info("[Scheduler] Starting Agent 1 — %s data collection.", provider.upper())
        try:
            import importlib
            mod = importlib.import_module(module_path)
            records = mod.collect_cost_data()
            logger.info("[Scheduler] Agent 1 (%s) collected %d records.", provider.upper(), len(records))
        except Exception as exc:
            logger.error("[Scheduler] Agent 1 (%s) error: %s", provider.upper(), exc)


def _job_detect_anomalies() -> None:
    """Run anomaly detection for all three cloud providers."""
    from backend.agents.agent2_anomaly_detector import detect_anomalies
    for provider in ("aws", "azure", "gcp"):
        logger.info("[Scheduler] Starting Agent 2 — anomaly detection (%s).", provider.upper())
        try:
            anomalies = detect_anomalies(provider=provider)
            logger.info("[Scheduler] Agent 2 (%s) found %d new anomalies.", provider.upper(), len(anomalies))
        except Exception as exc:
            logger.error("[Scheduler] Agent 2 (%s) error: %s", provider.upper(), exc)


def _job_forecast() -> None:
    logger.info("[Scheduler] Starting Agent 4 — daily forecasting.")
    try:
        from backend.agents.agent4_forecast import generate_forecast
        from backend.database.mongodb import get_db

        db = get_db()

        for provider in ("aws", "azure", "gcp"):
            top_services = db["billing_raw"].distinct("service", {"provider": provider})
            for days in (7, 30):
                generate_forecast(service=None, days=days, provider=provider)
                for service in top_services[:10]:
                    try:
                        generate_forecast(service=service, days=days, provider=provider)
                    except Exception as exc:
                        logger.warning(
                            "Forecast failed for provider=%s service=%s days=%d: %s",
                            provider, service, days, exc
                        )

        logger.info("[Scheduler] Agent 4 forecasting complete.")
    except Exception as exc:
        logger.error("[Scheduler] Agent 4 error: %s", exc)


def _job_budget_breach_check() -> None:
    """
    Check all configured budgets against the latest forecasts.
    If breach probability >= 80 %, send a warning email and push a WS event.
    """
    logger.info("[Scheduler] Starting budget breach check.")
    try:
        from backend.agents.agent4_forecast import check_budget_breach
        from backend.agents.agent5_alert_manager import send_email, _ALERT_TO_EMAIL
        from backend.api.websocket import broadcast_budget_warning_sync
        from backend.database.mongodb import get_db

        db = get_db()
        budgets = list(db["budgets"].find())

        if not budgets:
            logger.info("[Scheduler] No budgets configured — skipping breach check.")
            return

        for budget in budgets:
            result = check_budget_breach(str(budget["_id"]))
            if result is None:
                continue

            prob = result.get("breach_probability", 0.0)
            name = result.get("budget_name", "Unknown")

            if prob >= 0.8:
                days_left = result.get("days_until_breach")
                days_str = f"{days_left} days" if days_left else "soon"
                subject = f"[AnomalyIQ] Budget Breach Warning — {name}"
                body = (
                    f"Budget Breach Warning: {name}\n\n"
                    f"  Current spend   : ${result['current_spend']:.2f}\n"
                    f"  Budget limit    : ${result['budget_limit']:.2f}\n"
                    f"  Forecasted spend: ${result['forecasted_spend']:.2f}\n"
                    f"  Breach prob.    : {prob * 100:.0f}%\n"
                    f"  Breach in       : {days_str}\n\n"
                    f"Please review your AWS spending to avoid exceeding the budget."
                )
                send_email(_ALERT_TO_EMAIL, subject, body)
                broadcast_budget_warning_sync(result)
                logger.warning(
                    "[Scheduler] Budget breach warning sent for '%s' (prob=%.0f%%)",
                    name,
                    prob * 100,
                )

        logger.info("[Scheduler] Budget breach check complete (%d budgets).", len(budgets))
    except Exception as exc:
        logger.error("[Scheduler] Budget breach check error: %s", exc)


def _job_daily_digest() -> None:
    logger.info("[Scheduler] Sending daily alert digest.")
    try:
        from backend.agents.agent5_alert_manager import send_daily_digest
        send_daily_digest()
    except Exception as exc:
        logger.error("[Scheduler] Daily digest error: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_scheduler() -> BackgroundScheduler:
    """
    Create and start the APScheduler BackgroundScheduler with all jobs.
    Returns the scheduler instance.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running — skipping start.")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")

    # Agent 1: collect cost data every 15 minutes — run immediately on startup
    _scheduler.add_job(
        _job_collect_data,
        trigger=IntervalTrigger(minutes=15),
        id="agent1_collect",
        name="AWS Cost Data Collection",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
        next_run_time=datetime.now(timezone.utc),
    )

    # Agent 2: detect anomalies every 15 minutes (offset by 2 min to run after agent 1)
    _scheduler.add_job(
        _job_detect_anomalies,
        trigger=IntervalTrigger(minutes=15, start_date=_start_offset(minutes=2)),
        id="agent2_detect",
        name="Anomaly Detection",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )

    # Agent 4: daily forecast at 06:00 UTC
    _scheduler.add_job(
        _job_forecast,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="agent4_forecast",
        name="Daily Cost Forecast",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    # Agent 5: daily digest at 08:00 UTC
    _scheduler.add_job(
        _job_daily_digest,
        trigger=CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="agent5_daily_digest",
        name="Daily Alert Digest",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Agent 4: budget breach check every 6 hours
    _scheduler.add_job(
        _job_budget_breach_check,
        trigger=IntervalTrigger(hours=6),
        id="agent4_budget_breach",
        name="Budget Breach Check",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=600,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started with %d jobs: %s",
        len(_scheduler.get_jobs()),
        [j.id for j in _scheduler.get_jobs()],
    )
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the running scheduler instance, or None if not started."""
    return _scheduler


def _start_offset(minutes: int = 2) -> str:
    """Return an ISO datetime string *minutes* from now for interval offset."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    offset = now + timedelta(minutes=minutes)
    return offset.strftime("%Y-%m-%d %H:%M:%S")
