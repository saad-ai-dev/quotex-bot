"""
History routes - ALERT-ONLY monitoring system.
Provides filtered access to historical signal records.
No trade history -- only alert prediction records.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["history"])


def _build_history_query(
    market_type: Optional[str] = None,
    expiry_profile: Optional[str] = None,
    outcome: Optional[str] = None,
    min_confidence: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Build a MongoDB query dict from the supplied filter parameters."""
    query: dict = {}

    if market_type:
        query["market_type"] = market_type.upper()
    if expiry_profile:
        query["expiry_profile"] = expiry_profile
    if outcome:
        query["outcome"] = outcome.upper()
    if min_confidence is not None:
        query["confidence"] = {"$gte": min_confidence}

    # Date range filter on created_at (stored as ISO string, lexicographic ordering works)
    if date_from or date_to:
        date_filter: dict = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        query["created_at"] = date_filter

    return query


@router.get("/")
async def get_history(
    market_type: Optional[str] = Query(None, description="LIVE or OTC"),
    expiry_profile: Optional[str] = Query(None, description="e.g. 1m, 2m, 3m"),
    outcome: Optional[str] = Query(None, description="WIN, LOSS, NEUTRAL, UNKNOWN"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    date_from: Optional[str] = Query(None, description="ISO date string lower bound"),
    date_to: Optional[str] = Query(None, description="ISO date string upper bound"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return full signal history with filters.

    ALERT-ONLY: Returns alert prediction history, not trade P&L history.
    """
    query = _build_history_query(
        market_type=market_type,
        expiry_profile=expiry_profile,
        outcome=outcome,
        min_confidence=min_confidence,
        date_from=date_from,
        date_to=date_to,
    )

    collection = db["signals"]
    cursor = (
        collection.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    signals = await cursor.to_list(length=limit)
    total = await collection.count_documents(query)

    return {
        "signals": signals,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/wins")
async def get_wins(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return signals with WIN outcome.

    ALERT-ONLY: Signals where the alert prediction was correct.
    """
    collection = db["signals"]
    query = {"outcome": "WIN", "status": "EVALUATED"}
    cursor = (
        collection.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    signals = await cursor.to_list(length=limit)
    total = await collection.count_documents(query)

    return {"signals": signals, "total": total, "skip": skip, "limit": limit}


@router.get("/losses")
async def get_losses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return signals with LOSS outcome.

    ALERT-ONLY: Signals where the alert prediction was incorrect.
    """
    collection = db["signals"]
    query = {"outcome": "LOSS", "status": "EVALUATED"}
    cursor = (
        collection.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    signals = await cursor.to_list(length=limit)
    total = await collection.count_documents(query)

    return {"signals": signals, "total": total, "skip": skip, "limit": limit}


@router.get("/pending")
async def get_pending(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return signals that are still pending evaluation.

    ALERT-ONLY: Signals whose alert outcome has not yet been determined.
    """
    collection = db["signals"]
    query = {"status": "PENDING"}
    cursor = (
        collection.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    signals = await cursor.to_list(length=limit)
    total = await collection.count_documents(query)

    return {"signals": signals, "total": total, "skip": skip, "limit": limit}
