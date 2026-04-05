"""
Pydantic v2 models for analytics payloads.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class PerformanceEntry(BaseModel):
    """Win/loss breakdown for a specific market_type + expiry_profile combination.

    ALERT-ONLY: Reflects prediction accuracy, not trading P&L.
    """
    market_type: str
    expiry_profile: str
    total: int = 0
    wins: int = 0
    losses: int = 0
    neutral: int = 0
    win_rate: float = 0.0
    avg_confidence: float = 0.0


class AnalyticsSummary(BaseModel):
    """Aggregated analytics summary for the dashboard.

    ALERT-ONLY: All metrics are about signal prediction quality.
    """
    total_signals: int = 0
    total_evaluated: int = 0
    total_pending: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_neutral: int = 0
    total_unknown: int = 0
    overall_win_rate: float = 0.0
    avg_confidence: float = 0.0
    performance_by_market_expiry: List[PerformanceEntry] = Field(default_factory=list)
    today_total: int = 0
    today_wins: int = 0
    today_losses: int = 0
    today_win_rate: float = 0.0
    cache_updated_at: Optional[str] = None
