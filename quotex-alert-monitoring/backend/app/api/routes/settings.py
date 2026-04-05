"""
Settings routes - ALERT-ONLY monitoring system.
Manages alert thresholds, UI preferences, and monitoring configuration.
No trade execution settings.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settings"])

# Default settings for the ALERT-ONLY system
DEFAULT_SETTINGS = {
    "min_confidence_threshold": 0.6,
    "alert_sound_enabled": True,
    "alert_sound_file": "alert.mp3",
    "websocket_broadcast_enabled": True,
    "auto_evaluate_pending": True,
    "evaluation_interval_seconds": 10,
    "metrics_interval_seconds": 60,
    "dashboard_refresh_ms": 5000,
    "market_types_enabled": ["LIVE", "OTC"],
    "expiry_profiles_enabled": ["1m", "2m", "3m"],
    "max_history_display": 200,
    "confidence_buckets": [0.0, 0.4, 0.6, 0.75, 0.9, 1.0],
}

SETTINGS_DOC_ID = "global_settings"


@router.get("/")
async def get_settings(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Retrieve current monitoring settings.

    ALERT-ONLY: These settings control alerting behaviour, not trade parameters.
    """
    collection = db["settings"]
    doc = await collection.find_one({"_id": SETTINGS_DOC_ID})

    if doc is None:
        logger.info("No settings found in DB, returning defaults")
        return DEFAULT_SETTINGS

    # Remove Mongo internal field before returning
    doc.pop("_id", None)
    return doc


@router.put("/")
async def update_settings(
    settings: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Update monitoring settings (partial or full).

    ALERT-ONLY: Only alert/monitoring settings are accepted.
    Any trade-execution keys will be silently ignored.

    Raises:
        HTTPException 400: If the payload is empty.
    """
    if not settings:
        raise HTTPException(status_code=400, detail="Settings payload cannot be empty")

    # Strip any trade-execution keys that should never exist
    trade_keys = {"lot_size", "max_trades", "risk_percent", "auto_trade", "broker_api_key"}
    for key in trade_keys:
        settings.pop(key, None)

    collection = db["settings"]

    # Merge with existing (or defaults) so partial updates work
    existing = await collection.find_one({"_id": SETTINGS_DOC_ID})
    if existing is None:
        merged = {**DEFAULT_SETTINGS, **settings}
    else:
        existing.pop("_id", None)
        merged = {**existing, **settings}

    await collection.replace_one(
        {"_id": SETTINGS_DOC_ID},
        merged,
        upsert=True,
    )

    logger.info("Settings updated successfully")
    return merged
