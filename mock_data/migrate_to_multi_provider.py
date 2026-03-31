"""
Migration: single-provider → multi-provider

Run ONCE after pulling this update.

What it does:
  1. Renames collection  aws_billing_raw  →  billing_raw
  2. Adds  provider: "aws"  to every document in all 8 collections
  3. Drops old single-provider indexes and lets the app recreate them on next start

Usage:
    python migrate_to_multi_provider.py
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(dotenv_path="../backend/.env")

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "anomalyiq")

COLLECTIONS_TO_TAG = [
    "billing_raw",           # after rename
    "anomalies_detected",
    "root_cause_analysis",
    "budgets",
    "forecasts",
    "alerts_sent",
    "recommendations",
    "user_feedback",
]

OLD_INDEXES_TO_DROP = {
    "billing_raw":         ["billing_lookup"],
    "anomalies_detected":  ["anomaly_timestamp", "anomaly_severity_status"],
    "forecasts":           ["forecast_service_date"],
    "alerts_sent":         ["alert_dedup"],
    "recommendations":     ["rec_anomaly_id", "rec_status"],
    "budgets":             ["budget_type_name"],
}


def main():
    print(f"\nConnecting to {MONGODB_URI} / {MONGODB_DB_NAME} ...\n")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
    db = client[MONGODB_DB_NAME]

    existing = set(db.list_collection_names())

    # ── Step 1: Rename aws_billing_raw → billing_raw ──────────────────────
    if "aws_billing_raw" in existing and "billing_raw" not in existing:
        db["aws_billing_raw"].rename("billing_raw")
        print("✓ Renamed  aws_billing_raw  →  billing_raw")
    elif "billing_raw" in existing:
        print("✓ billing_raw already exists — skipping rename")
    else:
        print("! aws_billing_raw not found — skipping rename")

    # ── Step 2: Add provider: "aws" to all existing documents ─────────────
    for coll_name in COLLECTIONS_TO_TAG:
        if coll_name not in db.list_collection_names():
            print(f"  Skipping {coll_name} (collection does not exist)")
            continue

        result = db[coll_name].update_many(
            {"provider": {"$exists": False}},
            {"$set": {"provider": "aws"}},
        )
        print(
            f"✓ {coll_name:30s}  tagged {result.modified_count:4d} docs with provider='aws'"
        )

    # ── Step 3: Drop stale indexes (app will recreate on next start) ──────
    for coll_name, index_names in OLD_INDEXES_TO_DROP.items():
        if coll_name not in db.list_collection_names():
            continue
        for idx_name in index_names:
            try:
                db[coll_name].drop_index(idx_name)
                print(f"✓ Dropped old index  {coll_name}.{idx_name}")
            except Exception:
                pass  # index may already not exist — that's fine

    print("\n✅ Migration complete. Restart the backend to rebuild indexes.\n")
    client.close()


if __name__ == "__main__":
    main()
