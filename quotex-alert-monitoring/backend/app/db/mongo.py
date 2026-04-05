"""
Motor async MongoDB client singleton.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def connect() -> None:
    """Establish the MongoDB connection and store it in the module singleton.

    ALERT-ONLY: Database stores signal alerts and analytics only.
    """
    global _client, _database

    logger.info("Connecting to MongoDB at %s ...", settings.MONGODB_URL)
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _database = _client[settings.MONGODB_DB_NAME]

    # Verify connectivity
    try:
        await _client.admin.command("ping")
        logger.info(
            "MongoDB connected - database: %s", settings.MONGODB_DB_NAME
        )
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        raise


def get_database() -> AsyncIOMotorDatabase:
    """Return the active database handle.

    Raises:
        RuntimeError: If ``connect()`` has not been called.
    """
    if _database is None:
        raise RuntimeError(
            "MongoDB is not connected. Call connect() during application startup."
        )
    return _database


def get_collection(name: str) -> AsyncIOMotorCollection:
    """Return a collection from the active database.

    Args:
        name: Collection name.

    Raises:
        RuntimeError: If ``connect()`` has not been called.
    """
    db = get_database()
    return db[name]


async def close_connection() -> None:
    """Gracefully close the MongoDB connection."""
    global _client, _database
    if _client is not None:
        logger.info("Closing MongoDB connection ...")
        _client.close()
        _client = None
        _database = None
        logger.info("MongoDB connection closed.")
