"""
Sessions repository - monitoring session tracking.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pymongo

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION = "sessions"


def _col():
    return get_collection(COLLECTION)


async def create_session(session_data: Optional[Dict[str, Any]] = None) -> str:
    """Create a new monitoring session.

    ALERT-ONLY: Sessions track monitoring activity periods,
    not trading sessions.

    Args:
        session_data: Optional extra metadata for the session.

    Returns:
        The string ID of the inserted session document.
    """
    now = datetime.now(timezone.utc)
    doc = {
        "started_at": now,
        "ended_at": None,
        "is_active": True,
        "alerts_generated": 0,
        "metadata": session_data or {},
    }
    result = await _col().insert_one(doc)
    session_id = str(result.inserted_id)
    logger.info("Monitoring session started: %s", session_id)
    return session_id


async def update_session(
    session_id: str, update_data: Dict[str, Any]
) -> bool:
    """Update fields on an existing session.

    Args:
        session_id: The session's string ObjectId.
        update_data: Dict of fields to set.

    Returns:
        True if the document was modified.
    """
    from bson import ObjectId

    result = await _col().update_one(
        {"_id": ObjectId(session_id)},
        {"$set": update_data},
    )
    return result.modified_count > 0


async def get_active_session() -> Optional[Dict[str, Any]]:
    """Retrieve the currently active monitoring session, if any.

    Returns:
        The active session document, or None.
    """
    doc = await _col().find_one(
        {"is_active": True},
        sort=[("started_at", pymongo.DESCENDING)],
    )
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def end_session(session_id: str) -> bool:
    """Mark a monitoring session as ended.

    Args:
        session_id: The session's string ObjectId.

    Returns:
        True if the document was modified.
    """
    from bson import ObjectId

    now = datetime.now(timezone.utc)
    result = await _col().update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"is_active": False, "ended_at": now}},
    )
    if result.modified_count > 0:
        logger.info("Monitoring session ended: %s", session_id)
        return True
    return False
