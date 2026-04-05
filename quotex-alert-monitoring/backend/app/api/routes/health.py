"""
Health-check route - ALERT-ONLY monitoring system.
Reports service status, database connectivity, and uptime.
No trade execution health checks.
"""

import logging
import time
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

# Captured at module import time; lifespan may override via set_start_time().
_start_time: float = time.time()


def set_start_time(t: float) -> None:
    """Allow the lifespan handler to record the true start time."""
    global _start_time
    _start_time = t


@router.get("/health")
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return service health information.

    ALERT-ONLY: Reports monitoring system health, not trade engine health.
    """
    uptime_seconds = round(time.time() - _start_time, 2)

    # Probe MongoDB
    db_status = "connected"
    try:
        await db.command("ping")
    except Exception as exc:
        logger.warning("MongoDB health-check ping failed: %s", exc)
        db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "Quotex Alert Monitoring API",
        "description": "ALERT-ONLY monitoring system - no trade execution",
        "db_status": db_status,
        "uptime_seconds": uptime_seconds,
    }
