"""Metrics computation worker for the Quotex Alert Intelligence system.

ALERT-ONLY system -- computes and caches analytics summaries for the
dashboard. Designed to run on an APScheduler interval (e.g., every 60 seconds).
"""

from app.core.logging import get_logger
from app.services.analytics_service import AnalyticsService
from app.db.repositories import analytics_repo

logger = get_logger(__name__)


async def compute_metrics() -> None:
    """Compute and cache the analytics summary.

    ALERT-ONLY: Metrics reflect signal prediction accuracy and distribution,
    not trading profits or financial performance.

    This function is intended to be scheduled via APScheduler at a less
    frequent interval (e.g., every 60 seconds) since analytics computation
    involves multiple MongoDB aggregation pipelines.

    The computed summary is stored in the analytics_cache collection so
    that dashboard requests can be served quickly without re-running
    the full aggregation each time.
    """
    try:
        # Compute fresh analytics summary
        summary = await AnalyticsService.get_summary()

        # Cache the summary in MongoDB for fast retrieval
        await analytics_repo.update_cached_summary(summary)

        logger.info(
            f"Metrics worker completed: cached summary with "
            f"{summary.get('total_alerts', 0)} total alerts, "
            f"win_rate={summary.get('win_rate', 0.0):.1f}%"
        )

    except Exception as exc:
        logger.error(f"Metrics worker failed: {exc}", exc_info=True)
