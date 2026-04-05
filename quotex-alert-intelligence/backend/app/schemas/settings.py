"""Settings schemas for runtime configuration."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    """Current runtime settings returned to clients."""

    backend_url: str = "http://localhost:8000"
    monitoring_enabled: bool = True
    market_mode: str = Field(
        default="auto", pattern=r"^(auto|live|otc)$",
        description="auto, live, or otc",
    )
    expiry_profile: str = Field(
        default="1m", pattern=r"^(1m|2m|3m)$",
    )
    min_confidence_threshold: float = Field(default=65.0, ge=0.0, le=100.0)
    sound_alerts_enabled: bool = True
    browser_notifications_enabled: bool = True
    screenshot_logging_enabled: bool = False
    parse_interval_ms: int = Field(default=2000, ge=500)
    use_websocket: bool = True
    auto_detect_market: bool = True
    live_profile_weights: Dict[str, float] = Field(default_factory=dict)
    otc_profile_weights: Dict[str, float] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    """Partial update payload for runtime settings."""

    backend_url: Optional[str] = None
    monitoring_enabled: Optional[bool] = None
    market_mode: Optional[str] = Field(
        default=None, pattern=r"^(auto|live|otc)$",
    )
    expiry_profile: Optional[str] = Field(
        default=None, pattern=r"^(1m|2m|3m)$",
    )
    min_confidence_threshold: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
    )
    sound_alerts_enabled: Optional[bool] = None
    browser_notifications_enabled: Optional[bool] = None
    screenshot_logging_enabled: Optional[bool] = None
    parse_interval_ms: Optional[int] = Field(default=None, ge=500)
    use_websocket: Optional[bool] = None
    auto_detect_market: Optional[bool] = None
    live_profile_weights: Optional[Dict[str, float]] = None
    otc_profile_weights: Optional[Dict[str, float]] = None
