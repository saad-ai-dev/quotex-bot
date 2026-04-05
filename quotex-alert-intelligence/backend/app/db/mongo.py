from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level client singleton
_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect() -> None:
    """Initialize the MongoDB connection."""
    global _client, _database

    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URL}")
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _database = _client[settings.MONGODB_DB_NAME]

    # Verify connection
    await _client.admin.command("ping")
    logger.info(f"Connected to MongoDB database: {settings.MONGODB_DB_NAME}")


def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance. Must call connect() first."""
    if _database is None:
        raise RuntimeError("Database not initialized. Call connect() first.")
    return _database


def get_collection(name: str) -> AsyncIOMotorCollection:
    """Get a collection by name from the database."""
    db = get_database()
    return db[name]


async def close_connection() -> None:
    """Close the MongoDB connection."""
    global _client, _database

    if _client is not None:
        logger.info("Closing MongoDB connection")
        _client.close()
        _client = None
        _database = None
