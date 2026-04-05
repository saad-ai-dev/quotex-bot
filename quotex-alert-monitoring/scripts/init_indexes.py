#!/usr/bin/env python3
"""
Quotex Alert Monitor - MongoDB Index Initialization
ALERT-ONLY: Creates indexes for the monitoring database.
No trade execution collections are created.

Usage:
    python scripts/init_indexes.py
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure


def get_connection():
    """Connect to MongoDB."""
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "quotex_monitoring")

    try:
        client = MongoClient(url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        print(f"Connected to MongoDB at {url}")
        return client[db_name]
    except ConnectionFailure as e:
        print(f"ERROR: Could not connect to MongoDB at {url}: {e}")
        sys.exit(1)


def create_indexes(db):
    """Create all required indexes for the monitoring system."""

    # ---- Signals Collection ----
    # ALERT-ONLY: Signals are for monitoring/alerting purposes
    signals = db["signals"]

    signals.create_index(
        [("timestamp", DESCENDING)],
        name="idx_signals_timestamp",
    )
    signals.create_index(
        [("asset", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_signals_asset_timestamp",
    )
    signals.create_index(
        [("status", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_signals_status_timestamp",
    )
    signals.create_index(
        [("direction", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_signals_direction_timestamp",
    )
    signals.create_index(
        [("confidence", DESCENDING)],
        name="idx_signals_confidence",
    )
    signals.create_index(
        [("confidence_tier", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_signals_tier_timestamp",
    )
    signals.create_index(
        [("expiry_time", ASCENDING)],
        name="idx_signals_expiry",
        expireAfterSeconds=86400,  # TTL: auto-delete after 24 hours
    )
    print(f"  Created {len(signals.index_information()) - 1} indexes on 'signals'")

    # ---- Alert Events Collection ----
    alert_events = db["alert_events"]

    alert_events.create_index(
        [("alerted_at", DESCENDING)],
        name="idx_alerts_alerted_at",
    )
    alert_events.create_index(
        [("signal_id", ASCENDING)],
        name="idx_alerts_signal_id",
    )
    alert_events.create_index(
        [("dismissed", ASCENDING), ("alerted_at", DESCENDING)],
        name="idx_alerts_dismissed",
    )
    print(f"  Created {len(alert_events.index_information()) - 1} indexes on 'alert_events'")

    # ---- Chart Data Collection ----
    chart_data = db["chart_data"]

    chart_data.create_index(
        [("asset", ASCENDING), ("timestamp", DESCENDING)],
        name="idx_chart_asset_timestamp",
    )
    chart_data.create_index(
        [("timestamp", ASCENDING)],
        name="idx_chart_timestamp_ttl",
        expireAfterSeconds=3600,  # TTL: auto-delete after 1 hour
    )
    print(f"  Created {len(chart_data.index_information()) - 1} indexes on 'chart_data'")

    # ---- Settings Collection ----
    settings = db["settings"]

    settings.create_index(
        [("key", ASCENDING)],
        name="idx_settings_key",
        unique=True,
    )
    print(f"  Created {len(settings.index_information()) - 1} indexes on 'settings'")

    # ---- Daily Stats Collection ----
    daily_stats = db["daily_stats"]

    daily_stats.create_index(
        [("date", DESCENDING)],
        name="idx_daily_stats_date",
        unique=True,
    )
    print(f"  Created {len(daily_stats.index_information()) - 1} indexes on 'daily_stats'")


def main():
    print("=" * 50)
    print("Quotex Alert Monitor - Index Initialization")
    print("ALERT-ONLY: No trade execution collections")
    print("=" * 50)

    db = get_connection()
    print(f"\nDatabase: {db.name}")
    print("\nCreating indexes...")
    create_indexes(db)

    print("\nAll indexes created successfully.")
    print("=" * 50)


if __name__ == "__main__":
    main()
