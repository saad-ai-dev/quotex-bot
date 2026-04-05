"""
MongoDB index creation.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

import pymongo

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_indexes() -> None:
    """Create required indexes on all collections.

    ALERT-ONLY: Indexes are optimised for reading alert history,
    filtering by market/expiry/outcome, and evaluating pending signals.
    """
    alerts = get_collection("alerts")

    index_definitions = [
        # Unique constraint on signal_id
        {
            "keys": [("signal_id", pymongo.ASCENDING)],
            "kwargs": {"unique": True, "name": "idx_signal_id_unique"},
        },
        # Time-series queries (most recent first)
        {
            "keys": [("created_at", pymongo.DESCENDING)],
            "kwargs": {"name": "idx_created_at_desc"},
        },
        # Filter by market type
        {
            "keys": [("market_type", pymongo.ASCENDING)],
            "kwargs": {"name": "idx_market_type"},
        },
        # Filter by expiry profile
        {
            "keys": [("expiry_profile", pymongo.ASCENDING)],
            "kwargs": {"name": "idx_expiry_profile"},
        },
        # Filter by outcome
        {
            "keys": [("outcome", pymongo.ASCENDING)],
            "kwargs": {"name": "idx_outcome"},
        },
        # Filter by evaluation status
        {
            "keys": [("status", pymongo.ASCENDING)],
            "kwargs": {"name": "idx_status"},
        },
        # Filter / sort by confidence
        {
            "keys": [("confidence", pymongo.DESCENDING)],
            "kwargs": {"name": "idx_confidence_desc"},
        },
        # Compound index for the pending-evaluation worker query
        {
            "keys": [
                ("status", pymongo.ASCENDING),
                ("signal_for_close_at", pymongo.ASCENDING),
            ],
            "kwargs": {"name": "idx_status_close_at"},
        },
        # Compound index for dashboard filtering
        {
            "keys": [
                ("market_type", pymongo.ASCENDING),
                ("expiry_profile", pymongo.ASCENDING),
                ("outcome", pymongo.ASCENDING),
                ("created_at", pymongo.DESCENDING),
            ],
            "kwargs": {"name": "idx_dashboard_compound"},
        },
    ]

    for defn in index_definitions:
        try:
            await alerts.create_index(defn["keys"], **defn["kwargs"])
            logger.info("Ensured index: %s", defn["kwargs"]["name"])
        except Exception as exc:
            logger.warning(
                "Failed to create index %s: %s",
                defn["kwargs"].get("name", "unknown"),
                exc,
            )

    # Settings and sessions collections (lightweight)
    settings_col = get_collection("settings")
    await settings_col.create_index(
        [("key", pymongo.ASCENDING)],
        unique=True,
        name="idx_settings_key",
    )

    sessions_col = get_collection("sessions")
    await sessions_col.create_index(
        [("started_at", pymongo.DESCENDING)],
        name="idx_sessions_started_at",
    )

    analytics_col = get_collection("analytics_cache")
    await analytics_col.create_index(
        [("cache_key", pymongo.ASCENDING)],
        unique=True,
        name="idx_analytics_cache_key",
    )

    logger.info("All indexes ensured.")
