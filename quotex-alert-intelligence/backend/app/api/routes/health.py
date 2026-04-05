"""Health-check endpoint."""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db

router = APIRouter(tags=["health"])

APP_VERSION = "1.0.0"


@router.get("/health")
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return service health, version, and database connectivity."""
    db_ok = False
    try:
        # Ping the database to verify connectivity
        await db.command("ping")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": APP_VERSION,
        "database": "connected" if db_ok else "disconnected",
    }
