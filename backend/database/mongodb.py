"""
MongoDB connection and collection management for AnomalyIQ.
Loads MONGODB_URI and MONGODB_DB_NAME from environment variables.
"""

import os
import logging
from datetime import timedelta

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, OperationFailure

load_dotenv()

logger = logging.getLogger(__name__)

MONGODB_URI: str = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME: str = os.environ.get("MONGODB_DB_NAME", "anomalyiq")

# Module-level singletons — populated by connect_db()
client: MongoClient | None = None
db: Database | None = None

# TTL constants
_TTL_90_DAYS = int(timedelta(days=90).total_seconds())
_TTL_30_DAYS = int(timedelta(days=30).total_seconds())

# Collection names
COLLECTIONS = [
    "aws_billing_raw",
    "anomalies_detected",
    "root_cause_analysis",
    "budgets",
    "forecasts",
    "alerts_sent",
    "recommendations",
    "user_feedback",
    "gcp_billing_raw",
    "gcp_anomalies_detected",
    "gcp_forecasts",
    "gcp_budgets",
    "gcp_alerts_sent",
    "gcp_recommendations",
]


def connect_db() -> None:
    """Initialise MongoDB client, create collections and indexes."""
    global client, db

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)

    try:
        # Verify connectivity
        client.admin.command("ping")
        logger.info("MongoDB connection established: %s / %s", MONGODB_URI, MONGODB_DB_NAME)
    except ConnectionFailure as exc:
        logger.error("Cannot reach MongoDB at %s: %s", MONGODB_URI, exc)
        raise

    db = client[MONGODB_DB_NAME]
    _ensure_collections_and_indexes()


def disconnect_db() -> None:
    """Close the MongoDB client."""
    global client, db
    if client is not None:
        client.close()
        logger.info("MongoDB connection closed.")
        client = None
        db = None


def _ensure_collections_and_indexes() -> None:
    """Create collections (if absent) and apply index definitions."""
    existing = set(db.list_collection_names())

    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
            logger.debug("Created collection: %s", name)

    # --- aws_billing_raw: TTL 90 days ---
    _safe_create_index(
        "aws_billing_raw",
        [("created_at", ASCENDING)],
        name="ttl_aws_billing_raw",
        expireAfterSeconds=_TTL_90_DAYS,
    )
    _safe_create_index(
        "aws_billing_raw",
        [("timestamp", ASCENDING), ("service", ASCENDING), ("region", ASCENDING)],
        name="billing_lookup",
    )

    # --- anomalies_detected ---
    _safe_create_index(
        "anomalies_detected",
        [("timestamp", ASCENDING)],
        name="anomaly_timestamp",
    )
    _safe_create_index(
        "anomalies_detected",
        [("severity", ASCENDING), ("status", ASCENDING)],
        name="anomaly_severity_status",
    )

    # --- root_cause_analysis ---
    _safe_create_index(
        "root_cause_analysis",
        [("anomaly_id", ASCENDING)],
        name="rca_anomaly_id",
        unique=True,
    )

    # --- forecasts: TTL 30 days ---
    _safe_create_index(
        "forecasts",
        [("created_at", ASCENDING)],
        name="ttl_forecasts",
        expireAfterSeconds=_TTL_30_DAYS,
    )
    _safe_create_index(
        "forecasts",
        [("service", ASCENDING), ("forecast_date", ASCENDING)],
        name="forecast_service_date",
    )

    # --- alerts_sent ---
    _safe_create_index(
        "alerts_sent",
        [("anomaly_id", ASCENDING), ("timestamp", ASCENDING)],
        name="alert_dedup",
    )

    # --- recommendations ---
    _safe_create_index(
        "recommendations",
        [("anomaly_id", ASCENDING)],
        name="rec_anomaly_id",
    )
    _safe_create_index(
        "recommendations",
        [("status", ASCENDING)],
        name="rec_status",
    )

    # --- budgets ---
    _safe_create_index(
        "budgets",
        [("budget_type", ASCENDING), ("name", ASCENDING)],
        name="budget_type_name",
        unique=True,
    )

    # --- GCP collections ---
    _safe_create_index(
        "gcp_billing_raw",
        [("created_at", ASCENDING)],
        name="ttl_gcp_billing_raw",
        expireAfterSeconds=_TTL_90_DAYS,
    )
    _safe_create_index(
        "gcp_billing_raw",
        [("timestamp", ASCENDING), ("service", ASCENDING), ("region", ASCENDING)],
        name="gcp_billing_lookup",
    )
    _safe_create_index(
        "gcp_anomalies_detected",
        [("timestamp", ASCENDING)],
        name="gcp_anomaly_timestamp",
    )
    _safe_create_index(
        "gcp_forecasts",
        [("created_at", ASCENDING)],
        name="ttl_gcp_forecasts",
        expireAfterSeconds=_TTL_30_DAYS,
    )
    _safe_create_index(
        "gcp_alerts_sent",
        [("anomaly_id", ASCENDING), ("timestamp", ASCENDING)],
        name="gcp_alert_dedup",
    )

    logger.info("MongoDB indexes verified / created.")


def _safe_create_index(collection_name: str, keys: list, **kwargs) -> None:
    """Create an index, ignoring 'already exists' errors."""
    try:
        db[collection_name].create_index(keys, **kwargs)
    except OperationFailure as exc:
        # Index with different options already exists — log and continue.
        logger.warning(
            "Could not create index '%s' on '%s': %s",
            kwargs.get("name", "?"),
            collection_name,
            exc,
        )


def get_db() -> Database:
    """Return the active database, raising if not connected."""
    if db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db
