#!/usr/bin/env python3
"""
Quotex Alert Monitor - Seed Default Settings
ALERT-ONLY: Inserts default monitoring settings into MongoDB.
No trade execution settings are configured.

Usage:
    python scripts/seed_settings.py
"""

import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


DEFAULT_SETTINGS = {
    "key": "default",
    "backend_url": "http://localhost:8000",
    "ws_url": "ws://localhost:8000/ws/signals",
    "monitoring_enabled": False,
    "sound_enabled": True,
    "notifications_enabled": True,
    "min_confidence": 60,
    "alert_assets": [],
    "capture_interval_ms": 5000,
    "overlay_enabled": True,
    "overlay_position": "top-right",
    "theme": "dark",
    # Scoring engine weights - ALERT-ONLY scoring for confidence calculation
    "scoring_weights": {
        "trend": 25,
        "momentum": 25,
        "volatility": 20,
        "volume": 15,
        "pattern": 15,
    },
    # Confidence tier thresholds
    "confidence_tiers": {
        "high": 75,
        "medium": 50,
        "low": 0,
    },
    # Signal expiry defaults (seconds)
    "default_expiry_seconds": 300,
    # Assets to monitor (empty = all)
    "monitored_assets": [],
    # Metadata
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "version": "1.0.0",
    "description": "ALERT-ONLY monitoring settings. No trade execution.",
}


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


def seed_settings(db):
    """Insert or update default settings."""
    settings = db["settings"]

    result = settings.update_one(
        {"key": "default"},
        {"$setOnInsert": DEFAULT_SETTINGS},
        upsert=True,
    )

    if result.upserted_id:
        print("  Inserted default settings")
    else:
        print("  Default settings already exist (not overwritten)")


def seed_initial_stats(db):
    """Create initial daily stats entry."""
    daily_stats = db["daily_stats"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    result = daily_stats.update_one(
        {"date": today},
        {
            "$setOnInsert": {
                "date": today,
                "total_signals": 0,
                "signals_by_hour": {},
                "signals_by_direction": {"UP": 0, "DOWN": 0},
                "signals_by_confidence": {"high": 0, "medium": 0, "low": 0},
                "top_assets": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    if result.upserted_id:
        print(f"  Created daily stats entry for {today}")
    else:
        print(f"  Daily stats for {today} already exist")


def main():
    print("=" * 50)
    print("Quotex Alert Monitor - Seed Settings")
    print("ALERT-ONLY: No trade execution configuration")
    print("=" * 50)

    db = get_connection()
    print(f"\nDatabase: {db.name}")

    print("\nSeeding settings...")
    seed_settings(db)

    print("\nSeeding initial stats...")
    seed_initial_stats(db)

    print("\nSeeding complete.")
    print("=" * 50)


if __name__ == "__main__":
    main()
