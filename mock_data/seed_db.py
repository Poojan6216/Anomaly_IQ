"""
Seed MongoDB with all mock data (AWS + Azure + GCP).
Maps all JSON files into the correct collection names used by the backend.
"""

import os
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / ".env")

MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "anomalyiq")

MOCK_DIR = Path(__file__).parent

# Each tuple: (json_file, target_collection)
# Multiple files can map to the same collection — they get merged in
SEED_MAP = [
    # billing_raw
    ("aws_billing_raw.json",        "billing_raw"),
    ("azure_billing_raw.json",      "billing_raw"),
    ("gcp_billing_raw.json",        "billing_raw"),
    # anomalies_detected
    ("anomalies_detected.json",     "anomalies_detected"),
    ("azure_anomalies.json",        "anomalies_detected"),
    ("gcp_anomalies.json",          "anomalies_detected"),
    # root_cause_analysis
    ("root_cause_analysis.json",    "root_cause_analysis"),
    ("azure_rca.json",              "root_cause_analysis"),
    ("gcp_rca.json",                "root_cause_analysis"),
    # budgets
    ("budgets.json",                "budgets"),
    ("azure_budgets.json",          "budgets"),
    ("gcp_budgets.json",            "budgets"),
    # forecasts
    ("forecasts.json",              "forecasts"),
    ("azure_forecasts.json",        "forecasts"),
    ("gcp_forecasts.json",          "forecasts"),
    # alerts_sent
    ("alerts_sent.json",            "alerts_sent"),
    ("azure_alerts.json",           "alerts_sent"),
    ("gcp_alerts.json",             "alerts_sent"),
    # recommendations
    ("recommendations.json",        "recommendations"),
    ("azure_recommendations.json",  "recommendations"),
    ("gcp_recommendations.json",    "recommendations"),
    # user_feedback
    ("user_feedback.json",          "user_feedback"),
    ("azure_feedback.json",         "user_feedback"),
    ("gcp_feedback.json",           "user_feedback"),
]


def seed():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")
    db = client[MONGODB_DB_NAME]

    # Drop existing data so we start fresh
    for coll_name in db.list_collection_names():
        db[coll_name].drop()
        print(f"  Dropped: {coll_name}")

    totals: dict[str, int] = {}

    for filename, collection in SEED_MAP:
        filepath = MOCK_DIR / filename
        if not filepath.exists():
            print(f"  [SKIP] {filename} — file not found")
            continue

        with open(filepath) as f:
            docs = json_util.loads(f.read())

        if not docs:
            print(f"  [SKIP] {filename} — empty")
            continue

        db[collection].insert_many(docs, ordered=False)
        totals[collection] = totals.get(collection, 0) + len(docs)
        print(f"  {filename:40s} → {collection}  ({len(docs)} docs)")

    print("\n--- Summary ---")
    for coll, count in sorted(totals.items()):
        print(f"  {coll:30s} {count} docs")
    print("\nDone!")
    client.close()


if __name__ == "__main__":
    seed()
