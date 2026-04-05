"""
Analytics routes - ALERT-ONLY monitoring system.
Provides aggregated statistics on signal prediction accuracy.
No trade P&L analytics -- only alert prediction performance.

Win rate is calculated ONLY from directional signals (UP/DOWN).
NO_TRADE signals are excluded from win rate calculations.
"""

import logging
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])

# Only directional signals count for win rate
DIRECTIONAL_FILTER = {"prediction_direction": {"$in": ["UP", "DOWN"]}}


async def _count(collection, query: dict) -> int:
    return await collection.count_documents(query)


@router.get("/summary")
async def get_summary(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return summary of signal prediction performance.

    ALERT-ONLY: Win rate is calculated only from directional signals (UP/DOWN).
    NO_TRADE signals are excluded from win rate calculation.
    """
    col = db["signals"]

    # Total directional signals (UP/DOWN only — these are the real alerts)
    total_directional = await _count(col, DIRECTIONAL_FILTER)
    wins = await _count(col, {"outcome": "WIN", **DIRECTIONAL_FILTER})
    losses = await _count(col, {"outcome": "LOSS", **DIRECTIONAL_FILTER})
    pending = await _count(col, {"status": "PENDING", **DIRECTIONAL_FILTER})

    traded = wins + losses
    win_rate = round((wins / traded * 100), 1) if traded > 0 else 0.0

    # Per-market breakdown (directional only)
    per_market: dict = {}
    for mt in ["LIVE", "OTC"]:
        mf = {**DIRECTIONAL_FILTER, "market_type": mt}
        mt_wins = await _count(col, {**mf, "outcome": "WIN"})
        mt_losses = await _count(col, {**mf, "outcome": "LOSS"})
        mt_traded = mt_wins + mt_losses
        per_market[mt] = {
            "total": mt_traded,
            "wins": mt_wins,
            "losses": mt_losses,
            "win_rate": round(mt_wins / mt_traded * 100, 1) if mt_traded > 0 else 0.0,
        }

    # Per-expiry breakdown (directional only)
    per_expiry: dict = {}
    for ep in ["1m", "2m", "3m"]:
        ef = {**DIRECTIONAL_FILTER, "expiry_profile": ep}
        ep_wins = await _count(col, {**ef, "outcome": "WIN"})
        ep_losses = await _count(col, {**ef, "outcome": "LOSS"})
        ep_traded = ep_wins + ep_losses
        per_expiry[ep] = {
            "total": ep_traded,
            "wins": ep_wins,
            "losses": ep_losses,
            "win_rate": round(ep_wins / ep_traded * 100, 1) if ep_traded > 0 else 0.0,
        }

    return {
        "total": total_directional,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "win_rate": win_rate,
        "per_market": per_market,
        "per_expiry": per_expiry,
    }


@router.get("/performance")
async def get_performance(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return performance grouped by market_type + expiry_profile.

    ALERT-ONLY: Only directional signals (UP/DOWN) are included.
    """
    col = db["signals"]
    results: list = []

    for mt in ["LIVE", "OTC"]:
        for ep in ["1m", "2m", "3m"]:
            mf = {**DIRECTIONAL_FILTER, "market_type": mt, "expiry_profile": ep}
            wins = await _count(col, {**mf, "outcome": "WIN"})
            losses = await _count(col, {**mf, "outcome": "LOSS"})
            traded = wins + losses
            if traded == 0:
                continue

            pipeline = [
                {"$match": mf},
                {"$group": {"_id": None, "avg_conf": {"$avg": "$confidence"}}},
            ]
            agg = await col.aggregate(pipeline).to_list(length=1)
            avg_conf = agg[0]["avg_conf"] if agg else 0.0

            results.append({
                "market_type": mt,
                "expiry_profile": ep,
                "total": traded,
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / traded * 100, 1),
                "avg_confidence": round(avg_conf, 1),
            })

    return {"performance": results}
