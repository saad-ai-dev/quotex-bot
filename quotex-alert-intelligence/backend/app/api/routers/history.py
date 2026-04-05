from fastapi import APIRouter, Query

from app.db.repositories import alerts_repo
from app.core.constants import Status
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("")
async def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    market_type: str | None = None,
    expiry_profile: str | None = None,
    outcome: str | None = None,
):
    """Get evaluated alert history with optional filters."""
    filters = {"status": Status.EVALUATED}
    if market_type:
        filters["market_type"] = market_type
    if expiry_profile:
        filters["expiry_profile"] = expiry_profile
    if outcome:
        filters["outcome"] = outcome

    alerts = await alerts_repo.get_alerts(filters=filters, skip=skip, limit=limit)
    total = await alerts_repo.get_alerts_count(filters=filters)
    return {"items": alerts, "total": total, "skip": skip, "limit": limit}


@router.get("/recent")
async def get_recent_history(limit: int = Query(50, ge=1, le=200)):
    """Get the most recent alerts regardless of status."""
    alerts = await alerts_repo.get_recent_alerts(limit=limit)
    return {"items": alerts, "count": len(alerts)}
