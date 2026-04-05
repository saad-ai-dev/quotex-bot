"""Signal (alert) service for the Quotex Alert Intelligence system.

ALERT-ONLY system -- this service manages alert signal lifecycle,
NOT trade execution. Signals represent predicted candle directions
for informational / tracking purposes only.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.constants import Status, ExpiryProfile
from app.core.logging import get_logger
from app.db.repositories import alerts_repo
from app.utils.ids import generate_signal_id
from app.utils.datetime_utils import now_utc, add_seconds, format_timestamp

logger = get_logger(__name__)

# Mapping from expiry profile string to seconds until candle close
EXPIRY_SECONDS_MAP: Dict[str, int] = {
    ExpiryProfile.ONE_MINUTE: 60,
    ExpiryProfile.TWO_MINUTES: 120,
    ExpiryProfile.THREE_MINUTES: 180,
}


class SignalService:
    """Service layer for creating, retrieving, and listing alert signals.

    ALERT-ONLY: No trade execution is performed. Signals are informational
    predictions about upcoming candle directions on Quotex charts.
    """

    @staticmethod
    async def create_signal(
        signal_create: Dict[str, Any],
        orchestrator_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new alert signal from parsed chart data and orchestrator analysis.

        Args:
            signal_create: Raw signal input data (market_type, expiry_profile,
                           candles, parse_mode, chart_read_confidence, etc.).
            orchestrator_result: Output from the analysis engine containing
                                 prediction_direction, confidence, scores, reasons,
                                 and detected_features.

        Returns:
            The full alert document as inserted into MongoDB.
        """
        created_at = now_utc()
        signal_id = generate_signal_id()

        # Compute when the signal's target candle should close
        expiry_profile = signal_create.get("expiry_profile", "1m")
        expiry_seconds = EXPIRY_SECONDS_MAP.get(expiry_profile, 60)
        signal_for_close_at = add_seconds(created_at, expiry_seconds)

        # Build the full alert document -- ALERT-ONLY, no trade fields
        alert_doc: Dict[str, Any] = {
            "signal_id": signal_id,
            "market_type": signal_create.get("market_type", "LIVE"),
            "asset_name": signal_create.get("asset_name"),
            "expiry_profile": expiry_profile,

            # Orchestrator analysis results
            "prediction_direction": orchestrator_result.get("prediction_direction", "NO_TRADE"),
            "confidence": orchestrator_result.get("confidence", 0.0),
            "bullish_score": orchestrator_result.get("bullish_score", 0.0),
            "bearish_score": orchestrator_result.get("bearish_score", 0.0),
            "reasons": orchestrator_result.get("reasons", []),
            "detected_features": orchestrator_result.get("detected_features", {}),

            # Chart parsing metadata
            "chart_parse_mode": signal_create.get("parse_mode", "full"),
            "chart_read_confidence": signal_create.get("chart_read_confidence", 0.0),
            "chart_snapshot_meta": signal_create.get("chart_snapshot_meta"),
            "candles": signal_create.get("candles", []),

            # Lifecycle -- ALERT-ONLY status tracking
            "status": Status.PENDING,
            "outcome": None,
            "actual_result": None,
            "snapshot_ref": None,

            # Timestamps
            "created_at": created_at,
            "signal_for_close_at": signal_for_close_at,
            "evaluated_at": None,
            "timestamps": {
                "created_at": format_timestamp(created_at),
                "signal_for_close_at": format_timestamp(signal_for_close_at),
                "evaluated_at": None,
            },
        }

        # Persist to MongoDB
        await alerts_repo.insert_alert(alert_doc)
        logger.info(
            f"Created alert signal {signal_id} | "
            f"direction={alert_doc['prediction_direction']} "
            f"confidence={alert_doc['confidence']:.1f}% "
            f"market={alert_doc['market_type']} expiry={expiry_profile}"
        )

        # Broadcast new alert via WebSocket (best-effort, non-blocking)
        try:
            from app.services.alert_dispatcher import AlertDispatcher
            await AlertDispatcher.dispatch_new_alert(alert_doc)
        except Exception as exc:
            logger.warning(f"WebSocket broadcast failed for signal {signal_id}: {exc}")

        return alert_doc

    @staticmethod
    async def get_signal(signal_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single alert signal by its signal_id.

        Returns:
            The alert document dict, or None if not found.
        """
        doc = await alerts_repo.get_alert_by_signal_id(signal_id)
        if doc is None:
            logger.warning(f"Signal not found: {signal_id}")
        return doc

    @staticmethod
    async def list_signals(
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List alert signals with optional filters and pagination.

        Args:
            filters: MongoDB query filter dict (e.g. {"market_type": "LIVE"}).
            skip: Number of documents to skip.
            limit: Maximum documents to return.

        Returns:
            Tuple of (list of alert documents, total matching count).
        """
        query = filters or {}
        alerts = await alerts_repo.get_alerts(filters=query, skip=skip, limit=limit)
        total = await alerts_repo.get_alerts_count(filters=query)
        return alerts, total
