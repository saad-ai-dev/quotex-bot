"""Alert / Signal schemas for the Quotex Alert Intelligence system."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import PyObjectId


# ---------------------------------------------------------------------------
# Candle & chart snapshot helpers
# ---------------------------------------------------------------------------

class CandleData(BaseModel):
    """Single candle data point."""

    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    timestamp: Optional[float] = None


class ChartSnapshotMeta(BaseModel):
    """Metadata about the chart screenshot / parse region."""

    parse_mode: str = "full"
    region_x: Optional[int] = None
    region_y: Optional[int] = None
    region_width: Optional[int] = None
    region_height: Optional[int] = None
    raw_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Signal ingest (create)
# ---------------------------------------------------------------------------

class SignalCreate(BaseModel):
    """Payload sent by the extension / parser to create a new alert signal."""

    market_type: str = Field(
        ..., pattern=r"^(LIVE|OTC)$", description="LIVE or OTC"
    )
    asset_name: Optional[str] = None
    expiry_profile: str = Field(
        ..., pattern=r"^(1m|2m|3m)$", description="1m, 2m, or 3m"
    )
    chart_snapshot_meta: Optional[ChartSnapshotMeta] = None
    candles: List[CandleData] = Field(default_factory=list)
    parse_mode: str = "full"
    chart_read_confidence: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Confidence of the chart read / parse (0-100)",
    )


# ---------------------------------------------------------------------------
# Detected features (analysis output)
# ---------------------------------------------------------------------------

class DetectedFeatures(BaseModel):
    """Features detected by the analysis engine."""

    structure_bias: Optional[Dict[str, Any]] = None
    support_resistance: Optional[Dict[str, Any]] = None
    price_action_patterns: Optional[List[Dict[str, Any]]] = None
    liquidity: Optional[Dict[str, Any]] = None
    order_blocks: Optional[List[Dict[str, Any]]] = None
    fvg: Optional[List[Dict[str, Any]]] = None
    supply_demand: Optional[Dict[str, Any]] = None
    volume_proxy: Optional[Dict[str, Any]] = None
    otc_patterns: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# Signal read (response)
# ---------------------------------------------------------------------------

class SignalRead(BaseModel):
    """Full signal representation returned to clients."""

    signal_id: str
    market_type: str
    asset_name: Optional[str] = None
    expiry_profile: str

    prediction_direction: str
    confidence: float
    bullish_score: float = 0.0
    bearish_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    detected_features: DetectedFeatures = Field(default_factory=DetectedFeatures)

    chart_parse_mode: str = "full"
    chart_read_confidence: float = 0.0

    status: str = "PENDING"
    outcome: Optional[str] = None
    actual_result: Optional[Dict[str, Any]] = None

    timestamps: Dict[str, Any] = Field(default_factory=dict)
    snapshot_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Signal evaluation
# ---------------------------------------------------------------------------

class SignalEvaluate(BaseModel):
    """Payload to manually evaluate (mark) a signal outcome."""

    outcome: str = Field(
        ..., pattern=r"^(WIN|LOSS|NEUTRAL|UNKNOWN)$",
        description="WIN, LOSS, NEUTRAL, or UNKNOWN",
    )
    candle_direction: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# WebSocket push event
# ---------------------------------------------------------------------------

class AlertPushEvent(BaseModel):
    """Event pushed over WebSocket when a new alert is generated."""

    event_type: str = "new_alert"
    signal: SignalRead
