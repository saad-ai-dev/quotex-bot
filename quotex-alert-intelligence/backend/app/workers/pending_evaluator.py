"""Pending signal evaluator worker for the Quotex Alert Intelligence system.

ALERT-ONLY system -- this worker auto-evaluates expired pending signals
that did not receive follow-up candle data from the browser extension.
Designed to run on an APScheduler interval (e.g., every 10 seconds).
"""

from app.core.logging import get_logger
from app.services.evaluation_service import EvaluationService

logger = get_logger(__name__)


async def evaluate_pending_signals() -> None:
    """Evaluate all pending signals past their evaluation time.

    ALERT-ONLY: Signals that expire without receiving actual candle data
    from the browser extension are marked as UNKNOWN. This ensures no
    signal remains in PENDING state indefinitely.

    This function is intended to be scheduled via APScheduler at a regular
    interval (e.g., every 10 seconds as configured in settings).

    The actual WIN/LOSS determination requires the extension to send
    follow-up candle data after the expiry period. Without that data,
    the best we can do is mark signals as UNKNOWN.
    """
    try:
        evaluated = await EvaluationService.auto_evaluate_pending()

        if evaluated:
            logger.info(
                f"Pending evaluator completed: {len(evaluated)} signals "
                f"auto-evaluated as UNKNOWN"
            )
        else:
            logger.debug("Pending evaluator: no expired signals to evaluate")

    except Exception as exc:
        logger.error(f"Pending evaluator failed: {exc}", exc_info=True)
