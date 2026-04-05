"""Evaluation service for the Quotex Alert Intelligence system.

ALERT-ONLY system -- evaluation determines whether a signal's predicted
direction matched the actual candle outcome. No trades are placed or settled;
this is purely for tracking prediction accuracy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.constants import Status, Outcome, Direction
from app.core.logging import get_logger
from app.db.repositories import alerts_repo
from app.utils.datetime_utils import now_utc, format_timestamp

logger = get_logger(__name__)


class EvaluationService:
    """Service for evaluating alert signal outcomes.

    ALERT-ONLY: Evaluation compares predicted direction against actual candle
    movement. No money, trades, or positions are involved.
    """

    @staticmethod
    async def evaluate_signal(
        signal_id: str,
        outcome: str,
        candle_direction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually evaluate a signal by marking its outcome.

        Args:
            signal_id: The unique signal identifier.
            outcome: One of WIN, LOSS, NEUTRAL, UNKNOWN.
            candle_direction: Optional actual candle direction (e.g. "bullish", "bearish").

        Returns:
            The updated alert document.

        Raises:
            ValueError: If the signal is not found or is already evaluated.
        """
        # Fetch the signal
        doc = await alerts_repo.get_alert_by_signal_id(signal_id)
        if doc is None:
            raise ValueError(f"Signal not found: {signal_id}")

        # Validate status is still pending
        if doc.get("status") == Status.EVALUATED:
            raise ValueError(
                f"Signal {signal_id} is already evaluated with outcome={doc.get('outcome')}"
            )

        # Build the actual result payload
        evaluated_at = now_utc()
        actual_result: Dict[str, Any] = {}
        if candle_direction:
            actual_result["candle_direction"] = candle_direction

        # Persist the evaluation -- ALERT-ONLY outcome tracking
        await alerts_repo.update_alert_outcome(
            signal_id=signal_id,
            outcome=outcome,
            actual_result=actual_result if actual_result else None,
            evaluated_at=evaluated_at,
        )

        logger.info(
            f"Evaluated signal {signal_id}: outcome={outcome} "
            f"candle_direction={candle_direction}"
        )

        # Fetch updated document
        updated_doc = await alerts_repo.get_alert_by_signal_id(signal_id)

        # Broadcast evaluation update via WebSocket (best-effort)
        try:
            from app.services.alert_dispatcher import AlertDispatcher
            await AlertDispatcher.dispatch_evaluation_update(updated_doc)
        except Exception as exc:
            logger.warning(f"WebSocket broadcast failed for evaluation {signal_id}: {exc}")

        return updated_doc

    @staticmethod
    async def auto_evaluate_pending() -> List[Dict[str, Any]]:
        """Auto-evaluate all pending signals whose candle close time has passed.

        Since this is an ALERT-ONLY system without direct market data feeds,
        signals that expire without receiving follow-up candle data from the
        browser extension are marked as UNKNOWN.

        NOTE: Actual WIN/LOSS evaluation requires the extension to send
        follow-up candle data after the expiry period. This method handles
        the fallback case where no such data arrives.

        Returns:
            List of signals that were auto-evaluated as UNKNOWN.
        """
        pending = await alerts_repo.get_pending_alerts()
        evaluated: List[Dict[str, Any]] = []

        for doc in pending:
            signal_id = doc.get("signal_id")
            try:
                evaluated_at = now_utc()
                await alerts_repo.update_alert_outcome(
                    signal_id=signal_id,
                    outcome=Outcome.UNKNOWN,
                    actual_result={"reason": "Auto-evaluated: no follow-up candle data received"},
                    evaluated_at=evaluated_at,
                )

                updated = await alerts_repo.get_alert_by_signal_id(signal_id)
                evaluated.append(updated)

                logger.info(
                    f"Auto-evaluated signal {signal_id} as UNKNOWN "
                    f"(no candle data received after expiry)"
                )

                # Broadcast update (best-effort)
                try:
                    from app.services.alert_dispatcher import AlertDispatcher
                    await AlertDispatcher.dispatch_evaluation_update(updated)
                except Exception:
                    pass

            except Exception as exc:
                logger.error(f"Failed to auto-evaluate signal {signal_id}: {exc}")

        if evaluated:
            logger.info(f"Auto-evaluated {len(evaluated)} pending signals as UNKNOWN")

        return evaluated

    @staticmethod
    def determine_outcome(
        predicted_direction: str,
        actual_candle_direction: Optional[str],
    ) -> str:
        """Determine the outcome of a prediction based on actual candle direction.

        ALERT-ONLY: This is a pure comparison function for tracking prediction
        accuracy. No financial outcome is implied.

        Args:
            predicted_direction: The predicted direction (UP or DOWN).
            actual_candle_direction: The actual candle direction
                ("bullish", "bearish", "neutral", "doji", or None).

        Returns:
            One of: WIN, LOSS, NEUTRAL, UNKNOWN.
        """
        if actual_candle_direction is None:
            return Outcome.UNKNOWN

        actual_lower = actual_candle_direction.lower().strip()

        # Neutral / doji candles
        if actual_lower in ("neutral", "doji"):
            return Outcome.NEUTRAL

        # Determine if the prediction was correct
        if predicted_direction == Direction.UP:
            if actual_lower == "bullish":
                return Outcome.WIN
            elif actual_lower == "bearish":
                return Outcome.LOSS
        elif predicted_direction == Direction.DOWN:
            if actual_lower == "bearish":
                return Outcome.WIN
            elif actual_lower == "bullish":
                return Outcome.LOSS

        # Fallback for unrecognized directions
        return Outcome.UNKNOWN
