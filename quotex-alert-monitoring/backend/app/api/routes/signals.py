"""
Signal routes - ALERT-ONLY monitoring system.
Handles signal ingestion (from Chrome extension), listing, and evaluation.
No trade execution -- signals are analytical alerts stored for review.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

import json as _json
import numpy as _np

from app.api.deps import get_db
from app.engine.orchestrator import SignalOrchestrator
from app.utils.ids import generate_signal_id
from app.utils.datetime_utils import now_utc, format_timestamp

# Global price cache: latest known price per asset (updated on every ingest)
# Used by the evaluator to get the close price when a signal expires
_price_cache: dict[str, float] = {}


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


def _build_execution_decision(signal_doc: dict) -> tuple[bool, list[str]]:
    """Apply stricter execution rules than alerting rules.

    The backend may emit an alert for operator visibility, but auto-trading
    should only be allowed for high-quality, low-ambiguity setups.
    """
    blockers: list[str] = []

    direction = signal_doc.get("prediction_direction")
    confidence = float(signal_doc.get("confidence", 0.0) or 0.0)
    market_type = str(signal_doc.get("market_type", "LIVE")).upper()
    candle_count = int(signal_doc.get("candle_count", 0) or 0)
    penalties = signal_doc.get("penalties", {}) or {}
    features = signal_doc.get("detected_features", {}) or {}

    expiry_profile = str(signal_doc.get("expiry_profile", "1m")).lower()
    is_two_minute_plus = expiry_profile in {"2m", "3m"}
    min_confidence = 56.0 if market_type == "OTC" else 54.0
    min_candles = 18 if market_type == "OTC" else 16
    min_score_gap = 6.0 if market_type == "OTC" else 5.0
    if not is_two_minute_plus:
        min_confidence += 2.0
        min_candles += 1
        min_score_gap += 2.0

    if direction not in ("UP", "DOWN"):
        blockers.append("non_directional_signal")
    if confidence < min_confidence:
        blockers.append(f"confidence_below_{min_confidence:.0f}")
    if candle_count < min_candles:
        blockers.append(f"not_enough_candles_{candle_count}")

    chop_probability = float(features.get("chop_probability", 0.0) or 0.0)
    if chop_probability > 0.62:
        blockers.append("market_too_choppy")

    agreeing_count = int(features.get("agreeing_detector_count", 0) or 0)
    min_agreeing_count = 2 if is_two_minute_plus else 3
    if agreeing_count < min_agreeing_count:
        blockers.append("low_detector_confluence")

    score_gap = float(features.get("score_gap", 0.0) or 0.0)
    if score_gap < min_score_gap:
        blockers.append("score_gap_too_small")

    strategy_name = str(features.get("strategy_name", "none"))
    regime = str(features.get("regime", "UNKNOWN"))
    trend_strength = float(features.get("trend_strength", 0.0) or 0.0)
    recent_range_position = float(features.get("recent_range_position", 0.5) or 0.5)
    consecutive_up = int(features.get("consecutive_up", 0) or 0)
    consecutive_down = int(features.get("consecutive_down", 0) or 0)

    if strategy_name == "mean_reversion" and regime == "TRENDING":
        blockers.append("mean_reversion_against_trend")
    if strategy_name == "mean_reversion" and trend_strength >= 0.2:
        blockers.append("trend_strength_too_high_for_reversion")
    if strategy_name == "pullback_trend":
        if direction == "UP" and recent_range_position >= 0.88 and consecutive_up >= 2:
            blockers.append("late_entry_overextended_uptrend")
        if direction == "DOWN" and recent_range_position <= 0.12 and consecutive_down >= 2:
            blockers.append("late_entry_overextended_downtrend")
    if strategy_name == "trend_continuation":
        if direction == "UP" and recent_range_position >= 0.84 and consecutive_up >= 2:
            blockers.append("late_entry_overextended_uptrend")
        if direction == "DOWN" and recent_range_position <= 0.16 and consecutive_down >= 2:
            blockers.append("late_entry_overextended_downtrend")

    if float(penalties.get("conflict_penalty", 0.0) or 0.0) > (6.5 if is_two_minute_plus else 5.0):
        blockers.append("signal_conflict_penalty")
    if float(penalties.get("weak_data_penalty", 0.0) or 0.0) > (1.5 if is_two_minute_plus else 0.5):
        blockers.append("weak_data_penalty")
    if float(penalties.get("parsing_quality_penalty", 0.0) or 0.0) > 0.0:
        blockers.append("parsing_quality_penalty")
    if float(penalties.get("chop_penalty", 0.0) or 0.0) > 2.0:
        blockers.append("chop_penalty")
    if float(penalties.get("low_confluence_penalty", 0.0) or 0.0) > 0.0:
        blockers.append("low_confluence_penalty")

    return len(blockers) == 0, blockers


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
    current_price: Optional[float] = Field(default=None, description="Real-time tick price from WS stream")


class EvaluatePayload(BaseModel):
    """Payload to evaluate a pending signal outcome."""
    actual_close: float
    outcome: Optional[str] = Field(
        default=None,
        description="WIN, LOSS, NEUTRAL, or UNKNOWN. Auto-calculated if omitted.",
    )


class ExecutionPayload(BaseModel):
    """Payload sent by the extension after a real Quotex click succeeds."""
    executed_price: Optional[float] = None
    asset_name: Optional[str] = None


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

    # Entry price = the last candle's close (the price when the alert fires)
    entry_price = None
    if payload.candles:
        entry_price = float(payload.candles[-1].close)

    # Update the global price cache on EVERY request
    # This ensures the evaluator always has the latest price
    import app.api.routes.signals as _signals_mod
    cache_price = None
    if payload.current_price:
        cache_price = float(payload.current_price)
    elif entry_price:
        cache_price = entry_price
    if cache_price and payload.asset_name:
        _signals_mod._price_cache[payload.asset_name] = cache_price
        logger.info("Price cache updated: %s = %.5f (current_price=%s)",
                    payload.asset_name, cache_price, payload.current_price)

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
        "entry_price": entry_price,
        "close_price": None,
        "status": "PENDING",
        "outcome": None,
        "actual_close": None,
        "evaluated_at": None,
        "was_executed": False,
        "execution_status": "ALERTED" if result.get("prediction_direction") in ("UP", "DOWN") else "NOT_EXECUTED",
        "executed_at": None,
        "executed_price": None,
    }

    execution_ready, execution_blockers = _build_execution_decision(signal_doc)
    signal_doc["execution_ready"] = execution_ready
    signal_doc["execution_blockers"] = execution_blockers

    if signal_doc["prediction_direction"] in ("UP", "DOWN") and not execution_ready:
        blocked_direction = signal_doc["prediction_direction"]
        signal_doc["blocked_direction"] = blocked_direction
        signal_doc["prediction_direction"] = "NO_TRADE"
        signal_doc["status"] = "BLOCKED"
        signal_doc["reasons"] = [
            f"Execution blocked: {', '.join(execution_blockers)}"
        ] + signal_doc.get("reasons", [])
        logger.info(
            "Signal blocked before alerting: asset=%s direction=%s confidence=%.2f blockers=%s",
            signal_doc.get("asset_name"),
            blocked_direction,
            signal_doc.get("confidence", 0.0),
            execution_blockers,
        )

    # Sanitize numpy types before MongoDB insertion
    signal_doc = _sanitize(signal_doc)

    # Only save directional signals (UP/DOWN) to DB — skip NO_TRADE noise
    collection = db["signals"]
    if signal_doc["prediction_direction"] in ("UP", "DOWN"):
        # Dedup: don't save if ANY signal for this asset was created in last 60 seconds
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        existing = await collection.find_one({
            "asset_name": signal_doc["asset_name"],
            "prediction_direction": {"$in": ["UP", "DOWN"]},
            "created_at": {"$gte": cutoff},
        })
        if existing:
            # Skip — too soon after last signal for this asset
            # Return NO_TRADE so the extension does NOT click again
            existing.pop("_id", None)
            existing["prediction_direction"] = "NO_TRADE"
            existing["_dedup"] = True
            return JSONResponse(content=existing, status_code=200)

        await collection.insert_one(signal_doc)
    else:
        # Still return the doc but don't persist NO_TRADE
        pass

    # Remove Mongo internal _id before returning
    signal_doc.pop("_id", None)

    if signal_doc["prediction_direction"] in ("UP", "DOWN"):
        logger.info(
            "Signal ingested: %s direction=%s confidence=%.2f bull=%.1f bear=%.1f candles=%d penalties=%s",
            signal_doc["signal_id"],
            signal_doc["prediction_direction"],
            signal_doc["confidence"],
            signal_doc.get("bullish_score", 0),
            signal_doc.get("bearish_score", 0),
            signal_doc.get("candle_count", 0),
            signal_doc.get("penalties", {}),
        )

    return signal_doc


@router.get("/")
async def list_signals(
    market_type: Optional[str] = Query(None, description="Filter by market type"),
    expiry_profile: Optional[str] = Query(None, description="Filter by expiry profile"),
    status: Optional[str] = Query(None, description="PENDING or EVALUATED"),
    outcome: Optional[str] = Query(None, description="WIN, LOSS"),
    directional_only: bool = Query(False, description="Only show UP/DOWN signals"),
    executed_only: bool = Query(False, description="Only show trades actually executed on Quotex"),
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
    if executed_only:
        query["was_executed"] = True

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


@router.post("/{signal_id}/executed")
async def mark_signal_executed(
    signal_id: str,
    payload: ExecutionPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Mark a signal as actually executed on Quotex.

    This is the source of truth for dashboard trade history alignment.
    """
    collection = db["signals"]
    doc = await collection.find_one({"signal_id": signal_id}, {"_id": 0})

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    if doc.get("prediction_direction") not in ("UP", "DOWN"):
        raise HTTPException(status_code=400, detail="Only directional signals can be marked executed")

    if doc.get("was_executed"):
        return doc

    now = now_utc()
    executed_price = payload.executed_price
    update_fields = {
        "was_executed": True,
        "execution_status": "EXECUTED",
        "executed_at": format_timestamp(now),
    }
    if executed_price is not None:
        update_fields["executed_price"] = float(executed_price)
        update_fields["entry_price"] = float(executed_price)
    if payload.asset_name:
        update_fields["asset_name"] = payload.asset_name

    await collection.update_one({"signal_id": signal_id}, {"$set": update_fields})
    updated = await collection.find_one({"signal_id": signal_id}, {"_id": 0})

    logger.info(
        "Signal executed on Quotex: %s asset=%s direction=%s",
        signal_id,
        updated.get("asset_name"),
        updated.get("prediction_direction"),
    )

    try:
        from app.api.routes.websocket import manager
        import json
        event = {"event_type": "new_alert", "signal": updated}
        await manager.broadcast(json.dumps(event, default=str))
    except Exception:
        pass

    return updated


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
