from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.repositories import settings_repo
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class SettingsUpdate(BaseModel):
    confidence_threshold: float | None = Field(None, ge=0, le=100)
    parse_interval_ms: int | None = Field(None, ge=500, le=30000)
    enabled_market_types: list[str] | None = None
    enabled_expiry_profiles: list[str] | None = None
    auto_evaluate: bool | None = None
    notification_enabled: bool | None = None


@router.get("")
async def get_settings():
    """Get current system settings."""
    return await settings_repo.get_settings()


@router.put("")
async def update_settings(body: SettingsUpdate):
    """Update system settings."""
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await settings_repo.update_settings(update_data)
    return result
