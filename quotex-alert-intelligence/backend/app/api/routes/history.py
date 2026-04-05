"""History endpoints for evaluated signals."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db
from app.schemas.alert import SignalRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/history", tags=["history"])

SIGNALS_COLLECTION = "signals"


def _doc_to_signal_read(doc: dict) -> SignalRead:
    doc["signal_id"] = str(doc.pop("_id"))
    return SignalRead(**doc)


async def _query_history(
    db: AsyncIOMotorDatabase,
    market_type: Optional[str] = None,
    expiry_profile: Optional[str] = None,
    outcome: Optional[str] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
) -> PaginatedResponse[SignalRead]:
    """Shared query builder for history endpoints."""
    query: dict = {}

    if status:
        query["status"] = status
    else:
        # Default: only evaluated signals in history
        query["status"] = "EVALUATED"

    if market_type:
        query["market_type"] = market_type
    if expiry_profile:
        query["expiry_profile"] = expiry_profile
    if outcome:
        query["outcome"] = outcome
    if min_confidence is not None:
        query["confidence"] = {"$gte": min_confidence}
    if date_from or date_to:
        ts_filter: dict = {}
        if date_from:
            ts_filter["$gte"] = date_from.isoformat()
        if date_to:
            ts_filter["$lte"] = date_to.isoformat()
        query["timestamps.created_at"] = ts_filter

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
# GET /history
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[SignalRead])
async def get_history(
    market_type: Optional[str] = Query(None, pattern=r"^(LIVE|OTC)$"),
    expiry_profile: Optional[str] = Query(None, pattern=r"^(1m|2m|3m)$"),
    outcome: Optional[str] = Query(None, pattern=r"^(WIN|LOSS|NEUTRAL|UNKNOWN)$"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=100.0),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return all evaluated signals with optional filters."""
    return await _query_history(
        db,
        market_type=market_type,
        expiry_profile=expiry_profile,
        outcome=outcome,
        min_confidence=min_confidence,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /history/wins
# ---------------------------------------------------------------------------

@router.get("/wins", response_model=PaginatedResponse[SignalRead])
async def get_wins(
    market_type: Optional[str] = Query(None, pattern=r"^(LIVE|OTC)$"),
    expiry_profile: Optional[str] = Query(None, pattern=r"^(1m|2m|3m)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return only winning signals."""
    return await _query_history(
        db,
        market_type=market_type,
        expiry_profile=expiry_profile,
        outcome="WIN",
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /history/losses
# ---------------------------------------------------------------------------

@router.get("/losses", response_model=PaginatedResponse[SignalRead])
async def get_losses(
    market_type: Optional[str] = Query(None, pattern=r"^(LIVE|OTC)$"),
    expiry_profile: Optional[str] = Query(None, pattern=r"^(1m|2m|3m)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return only losing signals."""
    return await _query_history(
        db,
        market_type=market_type,
        expiry_profile=expiry_profile,
        outcome="LOSS",
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /history/pending
# ---------------------------------------------------------------------------

@router.get("/pending", response_model=PaginatedResponse[SignalRead])
async def get_pending(
    market_type: Optional[str] = Query(None, pattern=r"^(LIVE|OTC)$"),
    expiry_profile: Optional[str] = Query(None, pattern=r"^(1m|2m|3m)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return signals still pending evaluation."""
    return await _query_history(
        db,
        market_type=market_type,
        expiry_profile=expiry_profile,
        status="PENDING",
        skip=skip,
        limit=limit,
    )
