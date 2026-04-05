"""Analytics and performance schemas."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class PerformanceEntry(BaseModel):
    """Win-rate breakdown for a specific market / expiry slice."""

    market_type: str
    expiry_profile: str
    total: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0


class AnalyticsSummary(BaseModel):
    """Aggregated analytics overview."""

    total_alerts: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_neutral: int = 0
    total_unknown: int = 0
    win_rate: float = 0.0

    per_market_stats: Dict[str, Any] = Field(default_factory=dict)
    per_expiry_stats: Dict[str, Any] = Field(default_factory=dict)
    confidence_bucket_stats: Dict[str, Any] = Field(default_factory=dict)

    last_50_alerts: List[Dict[str, Any]] = Field(default_factory=list)
