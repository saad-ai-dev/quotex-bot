from pymongo import ASCENDING, DESCENDING, IndexModel

from app.db.mongo import get_collection
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_indexes() -> None:
    """Create all required indexes on the alerts collection."""
    alerts = get_collection("alerts")

    indexes = [
        IndexModel([("signal_id", ASCENDING)], unique=True, name="idx_signal_id_unique"),
        IndexModel([("created_at", DESCENDING)], name="idx_created_at_desc"),
        IndexModel([("market_type", ASCENDING)], name="idx_market_type"),
        IndexModel([("expiry_profile", ASCENDING)], name="idx_expiry_profile"),
        IndexModel([("outcome", ASCENDING)], name="idx_outcome"),
        IndexModel([("status", ASCENDING)], name="idx_status"),
        IndexModel([("confidence", DESCENDING)], name="idx_confidence"),
        IndexModel(
            [
                ("market_type", ASCENDING),
                ("expiry_profile", ASCENDING),
                ("status", ASCENDING),
            ],
            name="idx_market_expiry_status",
        ),
    ]

    result = await alerts.create_indexes(indexes)
    logger.info(f"Created indexes on alerts collection: {result}")
