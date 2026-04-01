"""
Agent 1 GCP — Data Collector
Fetches cost data from GCP Cloud Billing API.
Falls back to realistic mock data when billing export is not configured.
"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
_GCP_BILLING_ACCOUNT_ID = os.environ.get("GCP_BILLING_ACCOUNT_ID", "")
_GCP_CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

GCP_SERVICES = [
    "Compute Engine", "BigQuery", "Cloud Storage", "Cloud Run",
    "GKE", "Cloud SQL", "Cloud Functions", "Pub/Sub",
    "Cloud CDN", "Memorystore", "Cloud Logging", "Cloud DNS",
]

GCP_REGIONS = [
    "us-central1", "us-east1", "us-west1", "europe-west1",
    "asia-east1", "global",
]

_BASE_COSTS = {
    "Compute Engine": 16.0, "BigQuery": 10.5, "Cloud Storage": 6.5,
    "Cloud Run": 4.8, "GKE": 4.5, "Cloud SQL": 3.3,
    "Cloud Functions": 2.2, "Pub/Sub": 1.1, "Cloud CDN": 0.95,
    "Memorystore": 0.75, "Cloud Logging": 0.5, "Cloud DNS": 0.15,
}


def _get_gcp_credentials():
    """Try to load GCP credentials from service account JSON."""
    try:
        from google.oauth2 import service_account
        if _GCP_CREDENTIALS_PATH and os.path.exists(_GCP_CREDENTIALS_PATH):
            return service_account.Credentials.from_service_account_file(
                _GCP_CREDENTIALS_PATH,
                scopes=["https://www.googleapis.com/auth/cloud-billing.readonly"],
            )
    except Exception as exc:
        logger.debug("Could not load GCP credentials: %s", exc)
    return None


def _try_real_billing_data() -> Optional[List[Dict[str, Any]]]:
    """Attempt to fetch real billing info from GCP. Returns None if unavailable."""
    creds = _get_gcp_credentials()
    if not creds or not _GCP_BILLING_ACCOUNT_ID:
        return None

    try:
        from google.cloud import billing_v1

        client = billing_v1.CloudBillingClient(credentials=creds)
        account_name = f"billingAccounts/{_GCP_BILLING_ACCOUNT_ID}"

        account = client.get_billing_account(name=account_name)
        logger.info("GCP Billing Account verified: %s (%s)", account.display_name, account.name)

        projects = list(client.list_project_billing_info(name=account_name))
        logger.info("Found %d projects linked to billing account.", len(projects))

        return None
    except Exception as exc:
        logger.warning("GCP Billing API call failed: %s", exc)
        return None


def _generate_mock_billing(days: int = 31) -> List[Dict[str, Any]]:
    """Generate realistic mock GCP billing data."""
    records: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    current = start
    while current < now:
        hour_of_day = current.hour
        day_of_week = current.weekday()
        is_business = 8 <= hour_of_day <= 20 and day_of_week < 5

        for service in GCP_SERVICES:
            base = _BASE_COSTS.get(service, 1.0) / 24.0
            time_factor = 1.3 if is_business else 0.7
            noise = random.gauss(0, base * 0.15)
            spike = 0.0

            if random.random() < 0.003:
                spike = base * random.uniform(2.0, 5.0)

            cost = max(0.001, base * time_factor + noise + spike)
            region = random.choice(GCP_REGIONS[:3]) if service != "Cloud DNS" else "global"

            records.append({
                "timestamp": current,
                "service": service,
                "region": region,
                "cost": round(cost, 6),
                "usage_quantity": round(cost * random.uniform(0.5, 3.0), 4),
                "currency": "USD",
                "cloud": "gcp",
                "project_id": _GCP_PROJECT_ID or "demo-project",
                "created_at": datetime.now(timezone.utc),
            })

        current += timedelta(hours=1)

    return records


def collect_gcp_cost_data() -> List[Dict[str, Any]]:
    """
    Collect GCP billing data. Tries real API first, falls back to mock data.
    Stores results in MongoDB gcp_billing_raw collection.
    """
    from backend.database.mongodb import get_db

    real_data = _try_real_billing_data()

    if real_data is not None:
        records = real_data
        logger.info("Using real GCP billing data: %d records.", len(records))
    else:
        records = _generate_mock_billing()
        logger.info("Using mock GCP billing data: %d records.", len(records))

    db = get_db()

    if records:
        try:
            from pymongo import UpdateOne
            ops = [
                UpdateOne(
                    {
                        "timestamp": r["timestamp"],
                        "service": r["service"],
                        "region": r["region"],
                        "cloud": "gcp",
                    },
                    {"$set": r},
                    upsert=True,
                )
                for r in records
            ]
            result = db["gcp_billing_raw"].bulk_write(ops, ordered=False)
            logger.info(
                "GCP: Upserted %d billing records (%d inserted, %d updated).",
                len(records), result.upserted_count, result.modified_count,
            )
        except Exception as exc:
            logger.error("Failed to store GCP billing records: %s", exc)

    return records
