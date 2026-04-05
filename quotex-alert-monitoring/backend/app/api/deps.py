"""
FastAPI dependency injection - ALERT-ONLY system.
Provides database connections and shared resources to route handlers.
No trade execution dependencies.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Module-level reference set during application lifespan startup.
_db: AsyncIOMotorDatabase | None = None


def set_db(db: AsyncIOMotorDatabase) -> None:
    """Called once at startup to store the Motor database reference."""
    global _db
    _db = db
    logger.info("Database reference configured for dependency injection")


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency: returns the shared Motor database instance.

    ALERT-ONLY: Used for reading/writing signal data, not trade state.

    Raises:
        RuntimeError: If called before the database has been initialised.
    """
    if _db is None:
        raise RuntimeError(
            "Database not initialised. Ensure the application lifespan handler "
            "has connected to MongoDB before serving requests."
        )
    return _db
