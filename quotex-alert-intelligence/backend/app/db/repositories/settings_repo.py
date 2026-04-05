from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "settings"

DEFAULT_SETTINGS = {
    "confidence_threshold": 65.0,
    "parse_interval_ms": 2000,
    "enabled_market_types": ["LIVE", "OTC"],
    "enabled_expiry_profiles": ["1m", "2m", "3m"],
    "auto_evaluate": True,
    "notification_enabled": False,
}


def _collection():
    return get_collection(COLLECTION_NAME)


async def get_settings() -> Dict[str, Any]:
    """Get the current settings. Returns defaults if none exist."""
    collection = _collection()
    doc = await collection.find_one({"_type": "global_settings"})
    if doc is None:
        logger.info("No settings found, returning defaults")
        return {**DEFAULT_SETTINGS}
    doc["_id"] = str(doc["_id"])
    return doc


async def update_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update settings (upsert). Returns the updated settings document."""
    collection = _collection()
    data["updated_at"] = datetime.now(timezone.utc)

    result = await collection.find_one_and_update(
        {"_type": "global_settings"},
        {"$set": data, "$setOnInsert": {"_type": "global_settings"}},
        upsert=True,
        return_document=True,
    )
    if result:
        result["_id"] = str(result["_id"])
    logger.info("Settings updated successfully")
    return result
