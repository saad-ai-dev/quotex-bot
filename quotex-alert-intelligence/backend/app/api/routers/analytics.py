from fastapi import APIRouter

from app.db.repositories import analytics_repo, alerts_repo
from app.core.constants import Status, Outcome
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/summary")
async def get_analytics_summary():
    """Get the cached analytics summary. Falls back to live computation."""
    cached = await analytics_repo.get_cached_summary()
    if cached:
        return cached

    # Compute live if no cache exists
    total = await alerts_repo.get_alerts_count()
    evaluated = await alerts_repo.get_alerts_count({"status": Status.EVALUATED})
    wins = await alerts_repo.get_alerts_count({"outcome": Outcome.WIN})
    losses = await alerts_repo.get_alerts_count({"outcome": Outcome.LOSS})

    win_rate = 0.0
    if (wins + losses) > 0:
        win_rate = round((wins / (wins + losses)) * 100, 2)

    return {
        "total_alerts": total,
        "evaluated_alerts": evaluated,
        "pending_alerts": total - evaluated,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
    }


@router.get("/performance")
async def get_performance_breakdown():
    """Get win/loss performance grouped by market type and expiry profile."""
    performance = await analytics_repo.get_performance_by_market_and_expiry()
    return {"groups": performance}
