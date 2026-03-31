"""
MongoDB connection and collection management for AnomalyIQ.
Supports multi-cloud: AWS, Azure, GCP — all in one database, filtered by `provider`.
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

# Collection names (provider-agnostic — all clouds share one DB)
COLLECTIONS = [
    "billing_raw",          # renamed from aws_billing_raw
    "anomalies_detected",
    "root_cause_analysis",
    "budgets",
    "forecasts",
    "alerts_sent",
    "recommendations",
    "user_feedback",
]


def connect_db() -> None:
    """Initialise MongoDB client, create collections and indexes."""
    global client, db

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)

    try:
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

    # --- billing_raw: TTL 90 days, provider-first compound lookup ---
    _safe_create_index(
        "billing_raw",
        [("created_at", ASCENDING)],
        name="ttl_billing_raw",
        expireAfterSeconds=_TTL_90_DAYS,
    )
    _safe_create_index(
        "billing_raw",
        [
            ("provider", ASCENDING),
            ("timestamp", ASCENDING),
            ("service", ASCENDING),
            ("region", ASCENDING),
        ],
        name="billing_lookup",
    )

    # --- anomalies_detected ---
    _safe_create_index(
        "anomalies_detected",
        [("provider", ASCENDING), ("timestamp", ASCENDING)],
        name="anomaly_provider_timestamp",
    )
    _safe_create_index(
        "anomalies_detected",
        [("provider", ASCENDING), ("severity", ASCENDING), ("status", ASCENDING)],
        name="anomaly_provider_severity_status",
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
        [("provider", ASCENDING), ("service", ASCENDING), ("forecast_date", ASCENDING)],
        name="forecast_provider_service_date",
    )

    # --- alerts_sent ---
    _safe_create_index(
        "alerts_sent",
        [("provider", ASCENDING), ("anomaly_id", ASCENDING), ("timestamp", ASCENDING)],
        name="alert_provider_dedup",
    )

    # --- recommendations ---
    _safe_create_index(
        "recommendations",
        [("provider", ASCENDING), ("anomaly_id", ASCENDING)],
        name="rec_provider_anomaly_id",
    )
    _safe_create_index(
        "recommendations",
        [("provider", ASCENDING), ("status", ASCENDING)],
        name="rec_provider_status",
    )

    # --- budgets ---
    _safe_create_index(
        "budgets",
        [("provider", ASCENDING), ("budget_type", ASCENDING), ("name", ASCENDING)],
        name="budget_provider_type_name",
        unique=True,
    )

    logger.info("MongoDB indexes verified / created.")


def _safe_create_index(collection_name: str, keys: list, **kwargs) -> None:
    """Create an index, ignoring 'already exists' errors."""
    try:
        db[collection_name].create_index(keys, **kwargs)
    except OperationFailure as exc:
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
