"""
Signal routes - ALERT-ONLY monitoring system.
Handles signal ingestion (from Chrome extension), listing, and evaluation.
No trade execution -- signals are analytical alerts stored for review.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

import json as _json
import numpy as _np

from app.api.deps import get_db
from app.engine.orchestrator import SignalOrchestrator
from app.utils.ids import generate_signal_id
from app.utils.datetime_utils import now_utc, format_timestamp


def _sanitize(obj):
    """Recursively convert numpy types to Python natives for MongoDB/JSON."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (_np.integer,)):
        return int(obj)
    if isinstance(obj, (_np.floating,)):
        return float(obj)
    if isinstance(obj, _np.ndarray):
        return obj.tolist()
    if isinstance(obj, (_np.bool_,)):
        return bool(obj)
    return obj

logger = logging.getLogger(__name__)
router = APIRouter(tags=["signals"])

# ------------------------------------------------------------------
# ALERT-ONLY orchestrator instance (singleton, no trade execution)
# ------------------------------------------------------------------
orchestrator = SignalOrchestrator()


# ------------------------------------------------------------------
# Pydantic models for request/response validation
# ------------------------------------------------------------------

class CandleData(BaseModel):
    """Single OHLC candle as received from the Chrome extension."""
    open: float
    high: float
    low: float
    close: float
    timestamp: Optional[float] = None


class IngestPayload(BaseModel):
    """Payload sent by the Chrome extension to request signal analysis.

    ALERT-ONLY: This triggers analysis, not trade execution.
    """
    candles: List[CandleData] = Field(..., min_length=1)
    market_type: str = Field(default="LIVE", description="'LIVE' or 'OTC'")
    expiry_profile: str = Field(default="1m", description="e.g. '1m', '2m', '3m'")
    parse_mode: str = Field(default="dom", description="How candle data was parsed")
    chart_read_confidence: float = Field(
        default=0.9, ge=0.0, le=1.0,
        description="Confidence in the parsed candle data quality (0-1)",
    )
    asset_name: Optional[str] = Field(default=None, description="Asset symbol, e.g. 'EUR/USD'")


class EvaluatePayload(BaseModel):
    """Payload to evaluate a pending signal outcome."""
    actual_close: float
    outcome: Optional[str] = Field(
        default=None,
        description="WIN, LOSS, NEUTRAL, or UNKNOWN. Auto-calculated if omitted.",
    )


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("/ingest", status_code=201)
async def ingest_signal(
    payload: IngestPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Ingest candle data, run the analysis orchestrator, and store the signal.

    ALERT-ONLY: The orchestrator analyses chart data and produces an alert
    signal with direction, confidence, and reasons. No trades are executed.

    Returns:
        The full signal document as stored in MongoDB.
    """
    try:
        candles = [c.model_dump() for c in payload.candles]

        # Run the ALERT-ONLY analysis pipeline
        result = await orchestrator.analyze(
            candles=candles,
            market_type=payload.market_type,
            expiry_profile=payload.expiry_profile,
            parse_mode=payload.parse_mode,
            chart_read_confidence=payload.chart_read_confidence,
        )
    except Exception as exc:
        # Graceful fallback -- still create a signal record with NO_TRADE
        logger.exception("Orchestrator error during ingestion: %s", exc)
        result = {
            "bullish_score": 0.0,
            "bearish_score": 0.0,
            "confidence": 0.0,
            "prediction_direction": "NO_TRADE",
            "reasons": [f"Orchestrator error: {str(exc)}"],
            "detected_features": {},
            "penalties": {},
            "market_type": payload.market_type,
            "expiry_profile": payload.expiry_profile,
            "parse_mode": payload.parse_mode,
            "chart_read_confidence": payload.chart_read_confidence,
            "candle_count": len(payload.candles),
            "detector_results_raw": {},
        }

    # Build the signal document for storage
    now = now_utc()

    # Compute when this signal should be evaluated (candle close time)
    expiry_seconds = {"1m": 60, "2m": 120, "3m": 180}.get(payload.expiry_profile, 60)
    from app.utils.datetime_utils import add_seconds
    eval_time = add_seconds(now, expiry_seconds)

    signal_doc = {
        "signal_id": generate_signal_id(),
        "created_at": format_timestamp(now),
        "signal_for_close_at": format_timestamp(eval_time),
        "asset_name": payload.asset_name,
        "market_type": payload.market_type.upper(),
        "expiry_profile": payload.expiry_profile,
        "parse_mode": payload.parse_mode,
        "chart_read_confidence": payload.chart_read_confidence,
        "candle_count": result.get("candle_count", len(payload.candles)),
        "bullish_score": round(result.get("bullish_score", 0.0), 2),
        "bearish_score": round(result.get("bearish_score", 0.0), 2),
        "confidence": round(result.get("confidence", 0.0), 2),
        "prediction_direction": result.get("prediction_direction", "NO_TRADE"),
        "reasons": result.get("reasons", []),
        "detected_features": result.get("detected_features", {}),
        "penalties": result.get("penalties", {}),
        "status": "PENDING",
        "outcome": None,
        "actual_close": None,
        "evaluated_at": None,
    }

    # Sanitize numpy types before MongoDB insertion
    signal_doc = _sanitize(signal_doc)

    # Only save directional signals (UP/DOWN) to DB — skip NO_TRADE noise
    collection = db["signals"]
    if signal_doc["prediction_direction"] in ("UP", "DOWN"):
        await collection.insert_one(signal_doc)
    else:
        # Still return the doc but don't persist NO_TRADE
        pass

    # Remove Mongo internal _id before returning
    signal_doc.pop("_id", None)

    logger.info(
        "Signal ingested: %s direction=%s confidence=%.2f",
        signal_doc["signal_id"],
        signal_doc["prediction_direction"],
        signal_doc["confidence"],
    )

    # Broadcast to WebSocket clients for live dashboard updates
    try:
        from app.api.routes.websocket import manager
        import json
        event = {"event_type": "new_alert", "signal": signal_doc}
        await manager.broadcast(json.dumps(event, default=str))
    except Exception:
        pass  # Non-critical: dashboard will poll anyway

    return signal_doc


@router.get("/")
async def list_signals(
    market_type: Optional[str] = Query(None, description="Filter by market type"),
    expiry_profile: Optional[str] = Query(None, description="Filter by expiry profile"),
    status: Optional[str] = Query(None, description="PENDING or EVALUATED"),
    outcome: Optional[str] = Query(None, description="WIN, LOSS"),
    directional_only: bool = Query(False, description="Only show UP/DOWN signals"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List signals with optional filters.

    ALERT-ONLY: Returns stored alert signal records for dashboard display.
    """
    query: dict = {}

    if market_type:
        query["market_type"] = market_type.upper()
    if expiry_profile:
        query["expiry_profile"] = expiry_profile
    if status:
        query["status"] = status.upper()
    if outcome:
        query["outcome"] = outcome.upper()
    if directional_only:
        query["prediction_direction"] = {"$in": ["UP", "DOWN"]}

    collection = db["signals"]
    cursor = collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    signals = await cursor.to_list(length=limit)

    total = await collection.count_documents(query)

    return {
        "signals": signals,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Retrieve a single signal by ID.

    ALERT-ONLY: Returns the full alert signal document.
    """
    collection = db["signals"]
    doc = await collection.find_one({"signal_id": signal_id}, {"_id": 0})

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    return doc


@router.post("/{signal_id}/evaluate")
async def evaluate_signal(
    signal_id: str,
    payload: EvaluatePayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Evaluate a pending signal's outcome after the candle closes.

    ALERT-ONLY: This records whether the alert's prediction was correct.
    It does NOT close a trade or calculate profit/loss.

    Raises:
        HTTPException 404: Signal not found.
        HTTPException 400: Signal already evaluated.
    """
    collection = db["signals"]
    doc = await collection.find_one({"signal_id": signal_id})

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    if doc.get("status") == "EVALUATED":
        raise HTTPException(
            status_code=400,
            detail=f"Signal {signal_id} has already been evaluated",
        )

    # Determine outcome
    if payload.outcome:
        outcome = payload.outcome.upper()
    else:
        # Auto-calculate based on direction vs actual close
        direction = doc.get("prediction_direction", "NO_TRADE")
        # Compare actual close against the last candle close (entry reference)
        entry_close = None
        if doc.get("detected_features", {}).get("candle_count", 0) > 0:
            # We don't store the raw entry price by default; use bullish/bearish logic
            pass

        if direction == "UP":
            outcome = "WIN" if payload.actual_close > 0 else "LOSS"
        elif direction == "DOWN":
            outcome = "WIN" if payload.actual_close < 0 else "LOSS"
        else:
            outcome = "NEUTRAL"

    now = now_utc()
    update_fields = {
        "status": "EVALUATED",
        "outcome": outcome,
        "actual_close": payload.actual_close,
        "evaluated_at": format_timestamp(now),
    }

    await collection.update_one(
        {"signal_id": signal_id},
        {"$set": update_fields},
    )

    logger.info("Signal %s evaluated: outcome=%s", signal_id, outcome)

    # Return the updated document
    updated = await collection.find_one({"signal_id": signal_id}, {"_id": 0})
    return updated
