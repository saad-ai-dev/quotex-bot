#!/usr/bin/env python3
"""
Seed default settings into the MongoDB settings collection.

This script inserts the default settings document if it does not already exist.
Safe to run multiple times - it will not overwrite existing settings.
"""

import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


DEFAULT_SETTINGS = {
    "_id": "default_settings",
    "active_profile": "live_1m",
    "market_type": "LIVE",
    "expiry_profile": "1m",
    "alerts_enabled": True,
    "sound_enabled": True,
    "notification_enabled": True,
    "auto_refresh_interval_ms": 5000,
    "max_signals_displayed": 50,
    "signal_retention_hours": 24,
    "filters": {
        "min_confidence": 60,
        "assets": [],
        "directions": ["CALL", "PUT"],
        "market_types": ["LIVE", "OTC"],
    },
    "display": {
        "theme": "dark",
        "compact_mode": False,
        "show_penalties": True,
        "show_component_scores": True,
        "show_parsing_metadata": False,
    },
    "scoring_overrides": {
        "custom_weights": None,
        "custom_thresholds": None,
        "custom_penalties": None,
    },
    "history": {
        "track_results": True,
        "max_history_entries": 1000,
        "export_format": "json",
    },
    "created_at": datetime.now(timezone.utc),
    "updated_at": datetime.now(timezone.utc),
}


def get_mongo_client():
    """Create and return a MongoDB client."""
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "quotex_alerts")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except ConnectionFailure:
        print("ERROR: Could not connect to MongoDB at", mongo_url)
        sys.exit(1)
    return client, client[db_name]


def seed_settings(db):
    """Insert default settings if they do not exist."""
    collection = db["settings"]

    existing = collection.find_one({"_id": "default_settings"})
    if existing:
        print("Default settings already exist. Skipping insertion.")
        print(f"  active_profile: {existing.get('active_profile')}")
        print(f"  market_type: {existing.get('market_type')}")
        print(f"  updated_at: {existing.get('updated_at')}")
        return False

    collection.insert_one(DEFAULT_SETTINGS)
    print("Default settings inserted successfully.")
    return True


def main():
    print("Quotex Alert Intelligence - Settings Seeder")
    print("=" * 50)

    client, db = get_mongo_client()
    db_name = os.getenv("MONGODB_DB_NAME", "quotex_alerts")
    print(f"Connected to MongoDB, database: {db_name}")
    print()

    seed_settings(db)
    client.close()


if __name__ == "__main__":
    main()
