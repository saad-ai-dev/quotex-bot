from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.mongo import get_collection
from app.core.constants import Status, Outcome
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_COLLECTION = "analytics_cache"
ALERTS_COLLECTION = "alerts"


def _cache_collection():
    return get_collection(CACHE_COLLECTION)


def _alerts_collection():
    return get_collection(ALERTS_COLLECTION)


async def get_cached_summary() -> Optional[Dict[str, Any]]:
    """Get the cached analytics summary."""
    collection = _cache_collection()
    doc = await collection.find_one({"_type": "summary"})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_cached_summary(summary_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update the cached analytics summary (upsert)."""
    collection = _cache_collection()
    summary_data["updated_at"] = datetime.now(timezone.utc)

    result = await collection.find_one_and_update(
        {"_type": "summary"},
        {"$set": summary_data, "$setOnInsert": {"_type": "summary"}},
        upsert=True,
        return_document=True,
    )
    if result:
        result["_id"] = str(result["_id"])
    logger.info("Analytics summary cache updated")
    return result


async def get_performance_by_market_and_expiry() -> List[Dict[str, Any]]:
    """
    Aggregate alert performance grouped by market_type and expiry_profile.
    Returns win/loss/neutral counts and win rate for each group.
    """
    collection = _alerts_collection()

    pipeline = [
        {"$match": {"status": Status.EVALUATED}},
        {
            "$group": {
                "_id": {
                    "market_type": "$market_type",
                    "expiry_profile": "$expiry_profile",
                },
                "total": {"$sum": 1},
                "wins": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.WIN]}, 1, 0]}
                },
                "losses": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.LOSS]}, 1, 0]}
                },
                "neutrals": {
                    "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.NEUTRAL]}, 1, 0]}
                },
                "avg_confidence": {"$avg": "$confidence"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "market_type": "$_id.market_type",
                "expiry_profile": "$_id.expiry_profile",
                "total": 1,
                "wins": 1,
                "losses": 1,
                "neutrals": 1,
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
            }
        },
        {"$sort": {"market_type": 1, "expiry_profile": 1}},
    ]

    results = []
    async for doc in collection.aggregate(pipeline):
        results.append(doc)
    return results
