"""
Settings repository - persistent key-value configuration store.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION = "settings"
SETTINGS_KEY = "global_settings"

# Default settings document
_DEFAULTS: Dict[str, Any] = {
    "sound_enabled": True,
    "sound_volume": 80,
    "auto_evaluate": True,
    "min_confidence_display": 0.0,
    "default_market_type": "all",
    "default_expiry_profile": "all",
    "alert_retention_days": 30,
}


def _col():
    return get_collection(COLLECTION)


async def get_settings() -> Dict[str, Any]:
    """Retrieve the current global settings.

    Returns a merged dict of defaults and any stored overrides.

    Returns:
        Settings dict.
    """
    doc = await _col().find_one({"key": SETTINGS_KEY})
    if doc is None:
        return dict(_DEFAULTS)

    merged = dict(_DEFAULTS)
    stored = doc.get("data", {})
    merged.update(stored)
    return merged


async def update_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update global settings (partial update / merge).

    Args:
        data: Dict of setting keys and their new values.

    Returns:
        The full settings dict after the update.
    """
    now = datetime.now(timezone.utc)

    # Upsert: merge provided data into the existing document
    await _col().update_one(
        {"key": SETTINGS_KEY},
        {
            "$set": {
                f"data.{k}": v for k, v in data.items()
            },
            "$setOnInsert": {"key": SETTINGS_KEY, "created_at": now},
            "$currentDate": {"updated_at": True},
        },
        upsert=True,
    )

    logger.info("Settings updated: %s", list(data.keys()))
    return await get_settings()
