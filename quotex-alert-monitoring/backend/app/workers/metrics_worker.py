"""
Metrics Worker - periodically recomputes and caches analytics summaries.
ALERT-ONLY monitoring dashboard - no trade execution.

Designed to be called by APScheduler at a regular interval.
"""

from app.core.logging import get_logger
from app.services.analytics_service import AnalyticsService
from app.services.alert_dispatcher import AlertDispatcher

logger = get_logger(__name__)


async def compute_metrics() -> None:
    """Recompute analytics summary and broadcast updated metrics via WebSocket.

    ALERT-ONLY: Metrics reflect signal prediction accuracy and volume.
    No trading P&L, balance, or position data is involved.

    Called periodically by APScheduler (interval defined in config).
    """
    try:
        summary = await AnalyticsService.compute_and_cache_summary()
        await AlertDispatcher.broadcast_metrics(summary)
        logger.debug(
            "Metrics worker: summary recomputed (%d total signals)",
            summary.get("total_signals", 0),
        )
    except Exception as exc:
        logger.error("Metrics worker failed: %s", exc, exc_info=True)
