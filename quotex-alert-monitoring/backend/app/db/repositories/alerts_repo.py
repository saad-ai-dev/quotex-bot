"""
Alerts repository - async CRUD operations for signal alert documents.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pymongo

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION = "alerts"


def _col():
    return get_collection(COLLECTION)


async def insert_alert(doc: Dict[str, Any]) -> str:
    """Insert a new alert document.

    Args:
        doc: Full alert document including signal_id.

    Returns:
        The inserted document's signal_id.
    """
    result = await _col().insert_one(doc)
    logger.info("Inserted alert %s (mongo _id=%s)", doc.get("signal_id"), result.inserted_id)
    return doc["signal_id"]


async def get_alert_by_signal_id(signal_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single alert by its signal_id.

    Returns:
        The alert document or None if not found.
    """
    doc = await _col().find_one({"signal_id": signal_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_alerts(
    filters: Optional[Dict[str, Any]] = None,
    skip: int = 0,
    limit: int = 50,
    sort: Optional[List[tuple]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve alerts with optional filtering, pagination, and sorting.

    Args:
        filters: MongoDB query filter dict.
        skip: Number of documents to skip.
        limit: Maximum documents to return.
        sort: List of (field, direction) tuples. Defaults to created_at desc.

    Returns:
        List of alert documents.
    """
    query = filters or {}
    sort_spec = sort or [("created_at", pymongo.DESCENDING)]

    cursor = _col().find(query).sort(sort_spec).skip(skip).limit(limit)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results


async def get_pending_alerts() -> List[Dict[str, Any]]:
    """Get all pending alerts whose evaluation time has passed.

    ALERT-ONLY: These are alerts awaiting outcome evaluation,
    not pending trade orders.

    Returns:
        List of pending alert documents ready for evaluation.
    """
    now = datetime.now(timezone.utc)
    query = {
        "status": "pending",
        "signal_for_close_at": {"$lte": now},
    }
    cursor = _col().find(query).sort("signal_for_close_at", pymongo.ASCENDING)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results


async def update_alert_outcome(
    signal_id: str,
    outcome: str,
    actual_result: Optional[str] = None,
    evaluated_at: Optional[datetime] = None,
) -> bool:
    """Update the outcome and status of an evaluated alert.

    Args:
        signal_id: The unique signal identifier.
        outcome: WIN, LOSS, NEUTRAL, or UNKNOWN.
        actual_result: The actual candle direction observed.
        evaluated_at: Timestamp of evaluation. Defaults to now (UTC).

    Returns:
        True if the document was modified.
    """
    if evaluated_at is None:
        evaluated_at = datetime.now(timezone.utc)

    update_doc: Dict[str, Any] = {
        "$set": {
            "outcome": outcome,
            "status": "evaluated",
            "evaluated_at": evaluated_at,
        }
    }
    if actual_result is not None:
        update_doc["$set"]["actual_result"] = actual_result

    result = await _col().update_one({"signal_id": signal_id}, update_doc)
    if result.modified_count > 0:
        logger.info("Evaluated alert %s -> %s", signal_id, outcome)
        return True
    logger.warning("Alert %s not found or already evaluated", signal_id)
    return False


async def get_alerts_count(filters: Optional[Dict[str, Any]] = None) -> int:
    """Return the count of alerts matching the given filters.

    Args:
        filters: MongoDB query filter dict. Defaults to empty (count all).

    Returns:
        Integer count.
    """
    query = filters or {}
    return await _col().count_documents(query)


async def get_recent_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch the most recent alerts ordered by creation time descending.

    Args:
        limit: Maximum number of alerts to return.

    Returns:
        List of alert documents.
    """
    return await get_alerts(filters={}, skip=0, limit=limit)


async def get_today_alerts() -> List[Dict[str, Any]]:
    """Fetch all alerts created today (UTC midnight onwards).

    Returns:
        List of today's alert documents.
    """
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    query = {"created_at": {"$gte": midnight}}
    return await get_alerts(filters=query, skip=0, limit=10000)


async def get_today_stats() -> Dict[str, int]:
    """Compute aggregated stats for today's alerts.

    ALERT-ONLY: Stats reflect prediction accuracy, not trading P&L.

    Returns:
        Dict with total, wins, losses, neutral, unknown, pending counts.
    """
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    base_filter = {"created_at": {"$gte": midnight}}

    total = await _col().count_documents(base_filter)
    wins = await _col().count_documents({**base_filter, "outcome": "WIN"})
    losses = await _col().count_documents({**base_filter, "outcome": "LOSS"})
    neutral = await _col().count_documents({**base_filter, "outcome": "NEUTRAL"})
    unknown = await _col().count_documents({**base_filter, "outcome": "UNKNOWN"})
    pending = await _col().count_documents({**base_filter, "status": "pending"})

    win_rate = round((wins / (wins + losses) * 100), 2) if (wins + losses) > 0 else 0.0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "neutral": neutral,
        "unknown": unknown,
        "pending": pending,
        "win_rate": win_rate,
    }
