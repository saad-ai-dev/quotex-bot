"""FastAPI dependency injection helpers."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_database


def get_db() -> AsyncIOMotorDatabase:
    """Return the active MongoDB database instance.

    This is intended to be used with ``Depends(get_db)`` in route handlers.
    The underlying connection must already be established via ``db.mongo.connect()``.
    """
    return get_database()
