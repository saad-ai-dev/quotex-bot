"""
Evaluation Service - determines and records signal outcomes.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.logging import get_logger
from app.core.constants import Outcome
from app.db.repositories import alerts_repo
from app.services.alert_dispatcher import AlertDispatcher

logger = get_logger(__name__)


class EvaluationService:
    """Handles outcome evaluation of signal alerts.

    ALERT-ONLY: Evaluates whether predictions were correct.
    Does not close trades or manage positions.
    """

    @staticmethod
    async def evaluate_signal(
        signal_id: str,
        outcome: str,
        candle_direction: Optional[str] = None,
    ) -> bool:
        """Manually evaluate a signal with a given outcome.

        Args:
            signal_id: The unique signal identifier.
            outcome: WIN, LOSS, NEUTRAL, or UNKNOWN.
            candle_direction: Observed candle direction ('bullish', 'bearish', 'neutral').

        Returns:
            True if the alert was successfully updated.
        """
        now = datetime.now(timezone.utc)
        success = await alerts_repo.update_alert_outcome(
            signal_id=signal_id,
            outcome=outcome,
            actual_result=candle_direction,
            evaluated_at=now,
        )

        if success:
            logger.info("Signal %s evaluated -> %s (actual: %s)", signal_id, outcome, candle_direction)
            try:
                doc = await alerts_repo.get_alert_by_signal_id(signal_id)
                if doc:
                    await AlertDispatcher.broadcast_evaluation(doc)
            except Exception as exc:
                logger.warning("WebSocket broadcast for evaluation failed: %s", exc)

        return success

    @staticmethod
    async def auto_evaluate_pending() -> int:
        """Automatically evaluate all pending signals whose evaluation time has passed.

        Signals that have passed their ``signal_for_close_at`` deadline without
        receiving a manual evaluation are marked as UNKNOWN.

        ALERT-ONLY: This is a housekeeping operation for stale predictions,
        not an order management function.

        Returns:
            Number of signals marked as UNKNOWN.
        """
        pending = await alerts_repo.get_pending_alerts()
        if not pending:
            return 0

        count = 0
        now = datetime.now(timezone.utc)

        for alert in pending:
            signal_id = alert["signal_id"]
            try:
                success = await alerts_repo.update_alert_outcome(
                    signal_id=signal_id,
                    outcome=Outcome.UNKNOWN,
                    actual_result=None,
                    evaluated_at=now,
                )
                if success:
                    count += 1
                    logger.info("Auto-evaluated stale signal %s -> UNKNOWN", signal_id)
                    try:
                        doc = await alerts_repo.get_alert_by_signal_id(signal_id)
                        if doc:
                            await AlertDispatcher.broadcast_evaluation(doc)
                    except Exception:
                        pass
            except Exception as exc:
                logger.error("Failed to auto-evaluate %s: %s", signal_id, exc)

        if count > 0:
            logger.info("Auto-evaluated %d stale pending signals as UNKNOWN", count)

        return count

    @staticmethod
    def determine_outcome(predicted_direction: str, actual_direction: str) -> str:
        """Determine the outcome by comparing predicted vs actual candle direction.

        ALERT-ONLY: This is a pure comparison function for prediction accuracy.

        Args:
            predicted_direction: 'UP' or 'DOWN' from the signal.
            actual_direction: 'bullish', 'bearish', or 'neutral' observed.

        Returns:
            WIN, LOSS, or NEUTRAL.
        """
        if actual_direction == "neutral":
            return Outcome.NEUTRAL

        if predicted_direction == "UP" and actual_direction == "bullish":
            return Outcome.WIN
        if predicted_direction == "DOWN" and actual_direction == "bearish":
            return Outcome.WIN
        if predicted_direction == "UP" and actual_direction == "bearish":
            return Outcome.LOSS
        if predicted_direction == "DOWN" and actual_direction == "bullish":
            return Outcome.LOSS

        # NO_TRADE or unrecognised
        if predicted_direction == "NO_TRADE":
            return Outcome.NEUTRAL

        return Outcome.UNKNOWN
