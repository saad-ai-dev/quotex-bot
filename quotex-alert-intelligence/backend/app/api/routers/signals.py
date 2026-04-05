import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.constants import MarketType, ExpiryProfile, Direction, Status, Outcome
from app.db.repositories import alerts_repo
from app.core.logging import get_logger
from app.engine.timing_engine import TimingEngine
from app.services.alert_dispatcher import AlertDispatcher

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SignalCreate(BaseModel):
    asset: str = Field(..., min_length=1, description="Trading pair, e.g. EUR/USD")
    market_type: str = Field(..., description="LIVE or OTC")
    expiry_profile: str = Field(..., description="1m, 2m, or 3m")
    direction: str = Field(..., description="UP, DOWN, or NO_TRADE")
    confidence: float = Field(..., ge=0, le=100)
    signal_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signal_for_close_at: datetime | None = None
    metadata: dict | None = None


class SignalResponse(BaseModel):
    signal_id: str
    message: str


class CandleData(BaseModel):
    open: float
    high: float
    low: float
    close: float
    timestamp: float | str | None = None


class IngestPayload(BaseModel):
    """Payload for the /ingest endpoint -- ALERT-ONLY chart data ingestion."""
    market_type: str = Field(..., description="LIVE or OTC")
    asset_name: str | None = Field(None, description="Trading pair, e.g. EUR/USD")
    expiry_profile: str = Field(..., description="1m, 2m, or 3m")
    candles: List[CandleData] = Field(..., min_length=1, description="Candle data from chart")
    parse_mode: str = Field("dom", description="How candles were obtained: dom, canvas, screenshot")
    chart_read_confidence: float = Field(1.0, ge=0.0, le=1.0)
    chart_snapshot_meta: dict | None = None


class EvaluatePayload(BaseModel):
    """Payload for manually evaluating a signal outcome -- ALERT-ONLY."""
    outcome: str = Field(..., description="WIN, LOSS, NEUTRAL, or UNKNOWN")
    candle_direction: str | None = Field(None, description="Actual candle direction, e.g. bullish, bearish")


# ---------------------------------------------------------------------------
# POST /signals  (simple create)
# ---------------------------------------------------------------------------

@router.post("", response_model=SignalResponse, status_code=201)
async def create_signal(body: SignalCreate):
    """Submit a new alert signal from chart analysis."""
    if body.market_type not in MarketType.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid market_type. Must be one of {MarketType.ALL}")
    if body.expiry_profile not in ExpiryProfile.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid expiry_profile. Must be one of {ExpiryProfile.ALL}")
    if body.direction not in Direction.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid direction. Must be one of {Direction.ALL}")

    signal_id = f"sig_{uuid.uuid4().hex[:12]}"

    alert_doc = {
        "signal_id": signal_id,
        "asset": body.asset,
        "market_type": body.market_type,
        "expiry_profile": body.expiry_profile,
        "direction": body.direction,
        "confidence": body.confidence,
        "signal_at": body.signal_at,
        "signal_for_close_at": body.signal_for_close_at,
        "status": Status.PENDING,
        "outcome": Outcome.UNKNOWN,
        "metadata": body.metadata or {},
        "created_at": datetime.now(timezone.utc),
    }

    await alerts_repo.insert_alert(alert_doc)
    return SignalResponse(signal_id=signal_id, message="Alert signal created")


@router.get("/{signal_id}")
async def get_signal(signal_id: str):
    """Get a single signal by its ID."""
    alert = await alerts_repo.get_alert_by_signal_id(signal_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Signal not found")
    return alert


@router.get("")
async def list_signals(
    skip: int = 0,
    limit: int = 50,
    market_type: str | None = None,
    expiry_profile: str | None = None,
    status: str | None = None,
    direction: str | None = None,
):
    """List signals with optional filters and pagination."""
    filters = {}
    if market_type:
        filters["market_type"] = market_type
    if expiry_profile:
        filters["expiry_profile"] = expiry_profile
    if status:
        filters["status"] = status
    if direction:
        filters["direction"] = direction

    alerts = await alerts_repo.get_alerts(filters=filters, skip=skip, limit=limit)
    total = await alerts_repo.get_alerts_count(filters=filters)
    return {"items": alerts, "total": total, "skip": skip, "limit": limit}


# ---------------------------------------------------------------------------
# POST /signals/ingest  -- ALERT-ONLY chart data ingestion & orchestrator
# ---------------------------------------------------------------------------

@router.post("/ingest", status_code=201)
async def ingest_signal(payload: IngestPayload):
    """Receive raw chart data, run the analysis orchestrator, and return the alert signal.

    ALERT-ONLY: This endpoint produces a prediction alert. No trades are placed.
    """
    if payload.market_type not in MarketType.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid market_type. Must be one of {MarketType.ALL}")
    if payload.expiry_profile not in ExpiryProfile.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid expiry_profile. Must be one of {ExpiryProfile.ALL}")

    now = datetime.now(timezone.utc)
    signal_id = f"sig_{uuid.uuid4().hex[:12]}"
    candles_raw = [c.model_dump() for c in payload.candles]

    # ------------------------------------------------------------------
    # Run the orchestrator (analysis engine) if available -- ALERT-ONLY
    # ------------------------------------------------------------------
    try:
        from app.engine.orchestrator import SignalOrchestrator

        orchestrator = SignalOrchestrator()
        result = await orchestrator.analyze(
            candles=candles_raw,
            market_type=payload.market_type,
            expiry_profile=payload.expiry_profile,
            parse_mode=payload.parse_mode,
            chart_read_confidence=payload.chart_read_confidence,
        )
    except Exception as exc:
        logger.warning("Orchestrator unavailable or failed, falling back to NO_TRADE defaults: %s", exc)
        result = {
            "prediction_direction": Direction.NO_TRADE,
            "confidence": 0.0,
            "bullish_score": 0.0,
            "bearish_score": 0.0,
            "reasons": [f"Orchestrator error: {str(exc)}"],
            "detected_features": {},
            "penalties": {},
        }

    # Compute the evaluation close time -- ALERT-ONLY timing
    signal_for_close_at = TimingEngine.compute_evaluation_time(now, payload.expiry_profile)

    # Build the full alert document
    alert_doc: Dict[str, Any] = {
        "signal_id": signal_id,
        "asset": payload.asset_name or "UNKNOWN",
        "market_type": payload.market_type,
        "expiry_profile": payload.expiry_profile,
        "direction": result.get("prediction_direction", Direction.NO_TRADE),
        "confidence": result.get("confidence", 0.0),
        "bullish_score": result.get("bullish_score", 0.0),
        "bearish_score": result.get("bearish_score", 0.0),
        "reasons": result.get("reasons", []),
        "detected_features": result.get("detected_features", {}),
        "penalties": result.get("penalties", {}),
        "parse_mode": payload.parse_mode,
        "chart_read_confidence": payload.chart_read_confidence,
        "chart_snapshot_meta": payload.chart_snapshot_meta,
        "candle_count": len(candles_raw),
        "signal_at": now,
        "signal_for_close_at": signal_for_close_at,
        "status": Status.PENDING,
        "outcome": Outcome.UNKNOWN,
        "created_at": now,
    }

    # Persist to MongoDB via the alerts repository
    await alerts_repo.insert_alert(alert_doc)

    # Broadcast new alert via WebSocket -- ALERT-ONLY notification
    try:
        await AlertDispatcher.dispatch_new_alert(alert_doc)
    except Exception as exc:
        logger.warning("WebSocket broadcast failed for signal %s: %s", signal_id, exc)

    return alert_doc


# ---------------------------------------------------------------------------
# POST /signals/{signal_id}/evaluate  -- ALERT-ONLY outcome evaluation
# ---------------------------------------------------------------------------

@router.post("/{signal_id}/evaluate")
async def evaluate_signal(signal_id: str, body: EvaluatePayload):
    """Manually evaluate a signal by marking its outcome.

    ALERT-ONLY: Evaluation tracks prediction accuracy. No trades are settled.
    """
    if body.outcome not in Outcome.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid outcome. Must be one of {Outcome.ALL}")

    try:
        from app.services.evaluation_service import EvaluationService

        updated_doc = await EvaluationService.evaluate_signal(
            signal_id=signal_id,
            outcome=body.outcome,
            candle_direction=body.candle_direction,
        )
        return updated_doc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Evaluation failed for signal %s: %s", signal_id, exc)
        raise HTTPException(status_code=500, detail="Evaluation failed")
