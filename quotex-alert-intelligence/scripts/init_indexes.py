#!/usr/bin/env python3
"""
Initialize MongoDB indexes for the Quotex Alert Intelligence system.

This script creates all required indexes for optimal query performance.
Run this once during initial setup or after database recreation.
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure


def get_mongo_client():
    """Create and return a MongoDB client."""
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "quotex_alerts")
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    # Verify connection
    try:
        client.admin.command("ping")
    except ConnectionFailure:
        print("ERROR: Could not connect to MongoDB at", mongo_url)
        sys.exit(1)
    return client, client[db_name]


def create_signals_indexes(db):
    """Create indexes for the signals collection."""
    collection = db["signals"]
    indexes = [
        # Primary query: recent signals by timestamp
        ([("timestamp", DESCENDING)], {"name": "idx_timestamp_desc"}),
        # Filter by asset and market type
        ([("asset", ASCENDING), ("market_type", ASCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_asset_market_timestamp"}),
        # Filter by status
        ([("status", ASCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_status_timestamp"}),
        # Filter by direction and confidence
        ([("direction", ASCENDING), ("confidence", DESCENDING)],
         {"name": "idx_direction_confidence"}),
        # Expiry lookup for resolution
        ([("expiry_at", ASCENDING), ("status", ASCENDING)],
         {"name": "idx_expiry_status"}),
        # Market type + expiry profile compound
        ([("market_type", ASCENDING), ("expiry_profile", ASCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_market_expiry_timestamp"}),
        # Confidence threshold queries
        ([("confidence", DESCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_confidence_timestamp"}),
        # TTL index: auto-delete signals older than 7 days
        ([("created_at", ASCENDING)],
         {"name": "idx_ttl_created", "expireAfterSeconds": 604800}),
    ]
    for keys, opts in indexes:
        collection.create_index(keys, **opts)
        print(f"  Created index: {opts['name']}")


def create_history_indexes(db):
    """Create indexes for the signal_history collection."""
    collection = db["signal_history"]
    indexes = [
        ([("timestamp", DESCENDING)], {"name": "idx_history_timestamp"}),
        ([("asset", ASCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_history_asset_timestamp"}),
        ([("result.outcome", ASCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_history_outcome_timestamp"}),
        ([("market_type", ASCENDING), ("expiry_profile", ASCENDING), ("timestamp", DESCENDING)],
         {"name": "idx_history_market_expiry_timestamp"}),
        ([("confidence", DESCENDING)],
         {"name": "idx_history_confidence"}),
    ]
    for keys, opts in indexes:
        collection.create_index(keys, **opts)
        print(f"  Created index: {opts['name']}")


def create_settings_indexes(db):
    """Create indexes for the settings collection."""
    collection = db["settings"]
    indexes = [
        ([("_id", ASCENDING)], {"name": "idx_settings_id", "unique": True}),
    ]
    for keys, opts in indexes:
        collection.create_index(keys, **opts)
        print(f"  Created index: {opts['name']}")


def create_analytics_indexes(db):
    """Create indexes for the analytics collection."""
    collection = db["analytics"]
    indexes = [
        ([("period", ASCENDING), ("market_type", ASCENDING)],
         {"name": "idx_analytics_period_market"}),
        ([("asset", ASCENDING), ("period", ASCENDING)],
         {"name": "idx_analytics_asset_period"}),
        ([("calculated_at", DESCENDING)],
         {"name": "idx_analytics_calculated_at"}),
    ]
    for keys, opts in indexes:
        collection.create_index(keys, **opts)
        print(f"  Created index: {opts['name']}")


def main():
    print("Quotex Alert Intelligence - MongoDB Index Initialization")
    print("=" * 60)

    client, db = get_mongo_client()
    db_name = os.getenv("MONGODB_DB_NAME", "quotex_alerts")
    print(f"Connected to MongoDB, database: {db_name}")
    print()

    print("Creating signals indexes...")
    create_signals_indexes(db)
    print()

    print("Creating signal_history indexes...")
    create_history_indexes(db)
    print()

    print("Creating settings indexes...")
    create_settings_indexes(db)
    print()

    print("Creating analytics indexes...")
    create_analytics_indexes(db)
    print()

    print("All indexes created successfully.")
    client.close()


if __name__ == "__main__":
    main()
