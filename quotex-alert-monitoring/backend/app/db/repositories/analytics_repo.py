"""
Analytics repository - cached summaries and performance aggregations.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_COLLECTION = "analytics_cache"
ALERTS_COLLECTION = "alerts"


def _cache_col():
    return get_collection(CACHE_COLLECTION)


def _alerts_col():
    return get_collection(ALERTS_COLLECTION)


async def get_cached_summary(cache_key: str = "global_summary") -> Optional[Dict[str, Any]]:
    """Retrieve a cached analytics summary.

    Args:
        cache_key: Identifier for the cached summary.

    Returns:
        The cached summary dict or None if not found / expired.
    """
    doc = await _cache_col().find_one({"cache_key": cache_key})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_cached_summary(
    cache_key: str, summary_data: Dict[str, Any]
) -> None:
    """Upsert a cached analytics summary.

    Args:
        cache_key: Identifier for the cached summary.
        summary_data: The summary data to cache.
    """
    now = datetime.now(timezone.utc)
    await _cache_col().update_one(
        {"cache_key": cache_key},
        {
            "$set": {
                "data": summary_data,
                "updated_at": now,
            },
            "$setOnInsert": {"cache_key": cache_key, "created_at": now},
        },
        upsert=True,
    )
    logger.debug("Analytics cache updated: %s", cache_key)


async def get_performance_by_market_and_expiry() -> List[Dict[str, Any]]:
    """Aggregate win/loss/neutral counts grouped by market_type and expiry_profile.

    ALERT-ONLY: Performance measures prediction accuracy, not trading P&L.

    Returns:
        List of dicts with market_type, expiry_profile, and outcome counts.
    """
    pipeline = [
        {
            "$match": {
                "status": "evaluated",
                "outcome": {"$in": ["WIN", "LOSS", "NEUTRAL"]},
            }
        },
        {
            "$group": {
                "_id": {
                    "market_type": "$market_type",
                    "expiry_profile": "$expiry_profile",
                },
                "total": {"$sum": 1},
                "wins": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", "WIN"]}, 1, 0]}
                },
                "losses": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", "LOSS"]}, 1, 0]}
                },
                "neutral": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", "NEUTRAL"]}, 1, 0]}
                },
                "avg_confidence": {"$avg": "$confidence"},
            },
        },
        {
            "$project": {
                "_id": 0,
                "market_type": "$_id.market_type",
                "expiry_profile": "$_id.expiry_profile",
                "total": 1,
                "wins": 1,
                "losses": 1,
                "neutral": 1,
                "avg_confidence": {"$round": ["$avg_confidence", 2]},
                "win_rate": {
                    "$cond": [
                        {"$gt": [{"$add": ["$wins", "$losses"]}, 0]},
                        {
                            "$round": [
                                {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                "$wins",
                                                {"$add": ["$wins", "$losses"]},
                                            ]
                                        },
                                        100,
                                    ]
                                },
                                2,
                            ]
                        },
                        0,
                    ]
                },
            },
        },
        {"$sort": {"market_type": 1, "expiry_profile": 1}},
    ]

    results = []
    async for doc in _alerts_col().aggregate(pipeline):
        results.append(doc)
    return results
