from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING

from app.db.mongo import get_collection
from app.core.constants import Status
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "alerts"


def _collection():
    return get_collection(COLLECTION_NAME)


async def insert_alert(alert_doc: Dict[str, Any]) -> str:
    """Insert a new alert document. Returns the inserted signal_id."""
    collection = _collection()
    result = await collection.insert_one(alert_doc)
    logger.info(f"Inserted alert with _id={result.inserted_id}, signal_id={alert_doc.get('signal_id')}")
    return str(result.inserted_id)


async def get_alert_by_signal_id(signal_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single alert by its signal_id."""
    collection = _collection()
    doc = await collection.find_one({"signal_id": signal_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_alerts(
    filters: Optional[Dict[str, Any]] = None,
    skip: int = 0,
    limit: int = 50,
    sort: Optional[List[tuple]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve alerts with optional filters, pagination, and sorting."""
    collection = _collection()
    query = filters or {}
    sort_order = sort or [("created_at", DESCENDING)]

    cursor = collection.find(query).sort(sort_order).skip(skip).limit(limit)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results


async def get_pending_alerts() -> List[Dict[str, Any]]:
    """Get all pending alerts whose signal_for_close_at time has passed."""
    collection = _collection()
    now = datetime.now(timezone.utc)
    query = {
        "status": Status.PENDING,
        "signal_for_close_at": {"$lte": now},
    }
    cursor = collection.find(query).sort("signal_for_close_at", 1)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results


async def update_alert_outcome(
    signal_id: str,
    outcome: str,
    actual_result: Optional[Dict[str, Any]] = None,
    evaluated_at: Optional[datetime] = None,
) -> bool:
    """Update the outcome of an alert after evaluation."""
    collection = _collection()
    update_data = {
        "outcome": outcome,
        "status": Status.EVALUATED,
        "evaluated_at": evaluated_at or datetime.now(timezone.utc),
    }
    if actual_result is not None:
        update_data["actual_result"] = actual_result

    result = await collection.update_one(
        {"signal_id": signal_id},
        {"$set": update_data},
    )
    if result.modified_count > 0:
        logger.info(f"Updated alert {signal_id} outcome={outcome}")
        return True
    logger.warning(f"No alert found to update for signal_id={signal_id}")
    return False


async def get_alerts_count(filters: Optional[Dict[str, Any]] = None) -> int:
    """Count alerts matching the given filters."""
    collection = _collection()
    query = filters or {}
    return await collection.count_documents(query)


async def get_recent_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    """Get the most recent alerts, sorted by created_at descending."""
    collection = _collection()
    cursor = collection.find().sort("created_at", DESCENDING).limit(limit)
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results
