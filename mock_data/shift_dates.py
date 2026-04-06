"""
Shift all dates in mock data JSON files forward by a given number of days.
Handles both plain ISO strings and MongoDB Extended JSON {"$date": "..."} format.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHIFT_DAYS = 7  # shift everything forward 7 days so data ends ~today (2026-04-02)

MOCK_DIR = Path(__file__).parent

FILES = [
    "aws_billing_raw.json",
    "azure_billing_raw.json",
    "gcp_billing_raw.json",
    "anomalies_detected.json",
    "azure_anomalies.json",
    "gcp_anomalies.json",
    "root_cause_analysis.json",
    "azure_rca.json",
    "gcp_rca.json",
    "budgets.json",
    "azure_budgets.json",
    "gcp_budgets.json",
    "forecasts.json",
    "azure_forecasts.json",
    "gcp_forecasts.json",
    "alerts_sent.json",
    "azure_alerts.json",
    "gcp_alerts.json",
    "recommendations.json",
    "azure_recommendations.json",
    "gcp_recommendations.json",
    "user_feedback.json",
    "azure_feedback.json",
    "gcp_feedback.json",
]

# Matches ISO datetime strings like 2026-03-15T14:00:00Z or 2026-03-15T14:00:00+00:00
ISO_RE = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))')


def shift_iso(match: re.Match) -> str:
    raw = match.group(1)
    # normalise Z → +00:00
    normalised = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalised)
        shifted = dt + timedelta(days=SHIFT_DAYS)
        # keep same format (Z suffix)
        return shifted.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return raw


def process_file(filepath: Path) -> None:
    with open(filepath) as f:
        content = f.read()

    shifted = ISO_RE.sub(shift_iso, content)

    with open(filepath, "w") as f:
        f.write(shifted)


if __name__ == "__main__":
    for name in FILES:
        path = MOCK_DIR / name
        if not path.exists():
            print(f"  [SKIP] {name}")
            continue
        process_file(path)
        print(f"  Shifted +{SHIFT_DAYS}d: {name}")

    print("\nDone. Re-run seed_db.py to reload MongoDB.")
