"""
Pending Evaluator Worker - periodically evaluates stale pending signals.
ALERT-ONLY monitoring dashboard - no trade execution.

Designed to be called by APScheduler at a regular interval.
"""

from app.core.logging import get_logger
from app.services.evaluation_service import EvaluationService

logger = get_logger(__name__)


async def evaluate_pending_signals() -> None:
    """Evaluate all pending signals whose evaluation deadline has passed.

    ALERT-ONLY: This marks stale predictions as UNKNOWN. It does not
    close trades, cancel orders, or interact with any broker API.

    Called periodically by APScheduler (interval defined in config).
    """
    try:
        count = await EvaluationService.auto_evaluate_pending()
        if count > 0:
            logger.info("Pending evaluator: marked %d signals as UNKNOWN", count)
    except Exception as exc:
        logger.error("Pending evaluator failed: %s", exc, exc_info=True)
