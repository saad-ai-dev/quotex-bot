from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "sessions"


def _collection():
    return get_collection(COLLECTION_NAME)


async def create_session(session_data: Dict[str, Any]) -> str:
    """Create a new parsing/monitoring session. Returns the session ID."""
    collection = _collection()
    session_data["created_at"] = datetime.now(timezone.utc)
    session_data["is_active"] = True
    result = await collection.insert_one(session_data)
    session_id = str(result.inserted_id)
    logger.info(f"Created session {session_id}")
    return session_id


async def update_session(session_id: str, data: Dict[str, Any]) -> bool:
    """Update a session by its ID."""
    collection = _collection()
    data["updated_at"] = datetime.now(timezone.utc)
    result = await collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": data},
    )
    if result.modified_count > 0:
        logger.info(f"Updated session {session_id}")
        return True
    logger.warning(f"No session found to update: {session_id}")
    return False


async def get_active_session() -> Optional[Dict[str, Any]]:
    """Get the currently active session, if any."""
    collection = _collection()
    doc = await collection.find_one(
        {"is_active": True},
        sort=[("created_at", -1)],
    )
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
