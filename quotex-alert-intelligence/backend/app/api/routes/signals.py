"""Signal ingest, listing, and evaluation endpoints."""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db
from app.schemas.alert import SignalCreate, SignalEvaluate, SignalRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/signals", tags=["signals"])

SIGNALS_COLLECTION = "signals"


def _doc_to_signal_read(doc: dict) -> SignalRead:
    """Convert a MongoDB document into a SignalRead schema."""
    doc["signal_id"] = str(doc.pop("_id"))
    return SignalRead(**doc)


# ---------------------------------------------------------------------------
# POST /signals/ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=SignalRead, status_code=201)
async def ingest_signal(
    payload: SignalCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Receive raw chart data, run the analysis orchestrator, and return the alert signal."""
    now = datetime.now(timezone.utc)

    # Build the base document
    doc = {
        "market_type": payload.market_type,
        "asset_name": payload.asset_name,
        "expiry_profile": payload.expiry_profile,
        "candles": [c.model_dump() for c in payload.candles],
        "chart_parse_mode": payload.parse_mode,
        "chart_read_confidence": payload.chart_read_confidence,
        "chart_snapshot_meta": (
            payload.chart_snapshot_meta.model_dump()
            if payload.chart_snapshot_meta
            else None
        ),
        "status": "PENDING",
        "outcome": None,
        "actual_result": None,
        "snapshot_ref": None,
        "timestamps": {
            "created_at": now.isoformat(),
            "signal_for_close_at": None,
            "evaluated_at": None,
        },
    }

    # ------------------------------------------------------------------
    # Run the orchestrator (analysis engine) if available
    # ------------------------------------------------------------------
    try:
        from app.engine.orchestrator import run_orchestrator  # type: ignore[import-untyped]

        result = await run_orchestrator(payload, db)
        doc["prediction_direction"] = result.get("prediction_direction", "NO_TRADE")
        doc["confidence"] = result.get("confidence", 0.0)
        doc["bullish_score"] = result.get("bullish_score", 0.0)
        doc["bearish_score"] = result.get("bearish_score", 0.0)
        doc["reasons"] = result.get("reasons", [])
        doc["detected_features"] = result.get("detected_features", {})
    except ImportError:
        # Orchestrator not yet implemented -- fall back to defaults
        doc["prediction_direction"] = "NO_TRADE"
        doc["confidence"] = 0.0
        doc["bullish_score"] = 0.0
        doc["bearish_score"] = 0.0
        doc["reasons"] = ["Orchestrator not available"]
        doc["detected_features"] = {}

    insert_result = await db[SIGNALS_COLLECTION].insert_one(doc)
    doc["_id"] = insert_result.inserted_id

    signal_read = _doc_to_signal_read(doc)

    # Broadcast over WebSocket (best-effort)
    try:
        from app.api.routes.websocket import manager
        from app.schemas.alert import AlertPushEvent

        event = AlertPushEvent(event_type="new_alert", signal=signal_read)
        await manager.broadcast(event.model_dump_json())
    except Exception:
        pass  # Non-critical

    return signal_read


# ---------------------------------------------------------------------------
# GET /signals
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[SignalRead])
async def list_signals(
    market_type: Optional[str] = Query(None, pattern=r"^(LIVE|OTC)$"),
    expiry_profile: Optional[str] = Query(None, pattern=r"^(1m|2m|3m)$"),
    status: Optional[str] = Query(None, pattern=r"^(PENDING|EVALUATED)$"),
    outcome: Optional[str] = Query(None, pattern=r"^(WIN|LOSS|NEUTRAL|UNKNOWN)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List signals with optional filters and pagination."""
    query: dict = {}
    if market_type:
        query["market_type"] = market_type
    if expiry_profile:
        query["expiry_profile"] = expiry_profile
    if status:
        query["status"] = status
    if outcome:
        query["outcome"] = outcome

    total = await db[SIGNALS_COLLECTION].count_documents(query)
    cursor = (
        db[SIGNALS_COLLECTION]
        .find(query)
        .sort("timestamps.created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    items = [_doc_to_signal_read(d) for d in docs]

    return PaginatedResponse[SignalRead](
        items=items, total=total, skip=skip, limit=limit
    )


# ---------------------------------------------------------------------------
# GET /signals/{signal_id}
# ---------------------------------------------------------------------------

@router.get("/{signal_id}", response_model=SignalRead)
async def get_signal(
    signal_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Retrieve a single signal by its ID."""
    if not ObjectId.is_valid(signal_id):
        raise HTTPException(status_code=400, detail="Invalid signal_id format")

    doc = await db[SIGNALS_COLLECTION].find_one({"_id": ObjectId(signal_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    return _doc_to_signal_read(doc)


# ---------------------------------------------------------------------------
# POST /signals/{signal_id}/evaluate
# ---------------------------------------------------------------------------

@router.post("/{signal_id}/evaluate", response_model=SignalRead)
async def evaluate_signal(
    signal_id: str,
    payload: SignalEvaluate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Manually evaluate (mark) a signal outcome."""
    if not ObjectId.is_valid(signal_id):
        raise HTTPException(status_code=400, detail="Invalid signal_id format")

    doc = await db[SIGNALS_COLLECTION].find_one({"_id": ObjectId(signal_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    update_fields = {
        "outcome": payload.outcome,
        "status": "EVALUATED",
        "timestamps.evaluated_at": payload.evaluated_at.isoformat(),
    }
    if payload.candle_direction:
        update_fields["actual_result.candle_direction"] = payload.candle_direction

    await db[SIGNALS_COLLECTION].update_one(
        {"_id": ObjectId(signal_id)},
        {"$set": update_fields},
    )

    updated = await db[SIGNALS_COLLECTION].find_one({"_id": ObjectId(signal_id)})
    return _doc_to_signal_read(updated)
