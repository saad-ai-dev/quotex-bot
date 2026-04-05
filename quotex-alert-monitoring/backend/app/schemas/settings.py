"""
Pydantic v2 models for settings payloads.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    """Current settings values."""
    sound_enabled: bool = True
    sound_volume: int = Field(default=80, ge=0, le=100)
    auto_evaluate: bool = True
    min_confidence_display: float = Field(default=0.0, ge=0.0, le=100.0)
    default_market_type: str = "all"
    default_expiry_profile: str = "all"
    alert_retention_days: int = Field(default=30, ge=1)


class SettingsUpdate(BaseModel):
    """Partial settings update. Only provided fields are changed."""
    sound_enabled: Optional[bool] = None
    sound_volume: Optional[int] = Field(default=None, ge=0, le=100)
    auto_evaluate: Optional[bool] = None
    min_confidence_display: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    default_market_type: Optional[str] = None
    default_expiry_profile: Optional[str] = None
    alert_retention_days: Optional[int] = Field(default=None, ge=1)
