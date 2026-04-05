"""
Pydantic v2 models for alert-related request/response payloads.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CandleData(BaseModel):
    """Single candle (OHLC + timestamp)."""
    open: float
    high: float
    low: float
    close: float
    timestamp: Optional[float] = None


class IngestPayload(BaseModel):
    """Payload sent by the browser extension to request signal analysis.

    ALERT-ONLY: This triggers analysis and alert generation, not trade execution.
    """
    market_type: str = Field(..., description="'live' or 'otc'")
    asset_name: str = Field(..., description="e.g. 'EUR/USD', 'AUD/CAD (OTC)'")
    expiry_profile: str = Field(..., description="'1m', '2m', or '3m'")
    candles: List[CandleData] = Field(..., min_length=1, description="OHLC candle data")
    parse_mode: str = Field(default="dom", description="'dom', 'canvas', or 'screenshot'")
    chart_read_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    chart_snapshot_meta: Optional[Dict[str, Any]] = Field(default=None)


class SignalResponse(BaseModel):
    """Full signal/alert document returned after analysis.

    ALERT-ONLY: All fields describe analytical predictions, not trade positions.
    """
    signal_id: str
    market_type: str
    asset_name: str
    expiry_profile: str
    prediction_direction: str
    bullish_score: float
    bearish_score: float
    confidence: float
    reasons: List[str] = Field(default_factory=list)
    detected_features: Dict[str, Any] = Field(default_factory=dict)
    penalties: Dict[str, float] = Field(default_factory=dict)
    parse_mode: str = "dom"
    chart_read_confidence: float = 1.0
    candle_count: int = 0
    status: str = "pending"
    outcome: Optional[str] = None
    actual_result: Optional[str] = None
    created_at: Optional[datetime] = None
    signal_for_close_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    chart_snapshot_meta: Optional[Dict[str, Any]] = None


class EvaluatePayload(BaseModel):
    """Payload for manually evaluating a signal outcome.

    ALERT-ONLY: Records whether the prediction was correct, not trade result.
    """
    outcome: str = Field(..., description="WIN, LOSS, NEUTRAL, or UNKNOWN")
    candle_direction: Optional[str] = Field(
        default=None,
        description="Actual observed candle direction: 'bullish', 'bearish', or 'neutral'",
    )
