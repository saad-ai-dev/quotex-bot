"""Analytics and performance endpoints."""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db
from app.core.constants import ExpiryProfile, MarketType, Outcome
from app.schemas.analytics import AnalyticsSummary, PerformanceEntry

router = APIRouter(prefix="/analytics", tags=["analytics"])

SIGNALS_COLLECTION = "signals"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _count(db: AsyncIOMotorDatabase, query: dict) -> int:
    return await db[SIGNALS_COLLECTION].count_documents(query)


def _safe_rate(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total > 0 else 0.0


# ---------------------------------------------------------------------------
# GET /analytics/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return an aggregated analytics overview across all signals."""
    total_alerts = await _count(db, {})
    total_wins = await _count(db, {"outcome": Outcome.WIN})
    total_losses = await _count(db, {"outcome": Outcome.LOSS})
    total_neutral = await _count(db, {"outcome": Outcome.NEUTRAL})
    total_unknown = await _count(db, {"outcome": Outcome.UNKNOWN})
    win_rate = _safe_rate(total_wins, total_wins + total_losses)

    # Per-market stats
    per_market_stats: dict = {}
    for mt in MarketType.ALL:
        mt_total = await _count(db, {"market_type": mt, "status": "EVALUATED"})
        mt_wins = await _count(db, {"market_type": mt, "outcome": Outcome.WIN})
        mt_losses = await _count(db, {"market_type": mt, "outcome": Outcome.LOSS})
        per_market_stats[mt] = {
            "total": mt_total,
            "wins": mt_wins,
            "losses": mt_losses,
            "win_rate": _safe_rate(mt_wins, mt_wins + mt_losses),
        }

    # Per-expiry stats
    per_expiry_stats: dict = {}
    for ep in ExpiryProfile.ALL:
        ep_total = await _count(db, {"expiry_profile": ep, "status": "EVALUATED"})
        ep_wins = await _count(db, {"expiry_profile": ep, "outcome": Outcome.WIN})
        ep_losses = await _count(db, {"expiry_profile": ep, "outcome": Outcome.LOSS})
        per_expiry_stats[ep] = {
            "total": ep_total,
            "wins": ep_wins,
            "losses": ep_losses,
            "win_rate": _safe_rate(ep_wins, ep_wins + ep_losses),
        }

    # Confidence bucket stats
    confidence_bucket_stats: dict = {}
    buckets = [(0, 50), (50, 65), (65, 75), (75, 85), (85, 100)]
    for low, high in buckets:
        label = f"{low}-{high}"
        b_filter = {"confidence": {"$gte": low, "$lt": high}, "status": "EVALUATED"}
        b_total = await _count(db, b_filter)
        b_wins = await _count(db, {**b_filter, "outcome": Outcome.WIN})
        b_losses = await _count(db, {**b_filter, "outcome": Outcome.LOSS})
        confidence_bucket_stats[label] = {
            "total": b_total,
            "wins": b_wins,
            "losses": b_losses,
            "win_rate": _safe_rate(b_wins, b_wins + b_losses),
        }

    # Last 50 alerts
    cursor = (
        db[SIGNALS_COLLECTION]
        .find({})
        .sort("timestamps.created_at", -1)
        .limit(50)
    )
    last_50_docs = await cursor.to_list(length=50)
    last_50_alerts = []
    for d in last_50_docs:
        d["signal_id"] = str(d.pop("_id"))
        last_50_alerts.append(d)

    return AnalyticsSummary(
        total_alerts=total_alerts,
        total_wins=total_wins,
        total_losses=total_losses,
        total_neutral=total_neutral,
        total_unknown=total_unknown,
        win_rate=win_rate,
        per_market_stats=per_market_stats,
        per_expiry_stats=per_expiry_stats,
        confidence_bucket_stats=confidence_bucket_stats,
        last_50_alerts=last_50_alerts,
    )


# ---------------------------------------------------------------------------
# GET /analytics/performance
# ---------------------------------------------------------------------------

@router.get("/performance", response_model=list[PerformanceEntry])
async def get_performance_breakdown(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return per-market, per-expiry performance breakdown."""
    entries: list[PerformanceEntry] = []

    for mt in MarketType.ALL:
        for ep in ExpiryProfile.ALL:
            base_filter = {
                "market_type": mt,
                "expiry_profile": ep,
                "status": "EVALUATED",
            }
            total = await _count(db, base_filter)
            wins = await _count(db, {**base_filter, "outcome": Outcome.WIN})
            losses = await _count(db, {**base_filter, "outcome": Outcome.LOSS})
            entries.append(
                PerformanceEntry(
                    market_type=mt,
                    expiry_profile=ep,
                    total=total,
                    wins=wins,
                    losses=losses,
                    win_rate=_safe_rate(wins, wins + losses),
                )
            )

    return entries
