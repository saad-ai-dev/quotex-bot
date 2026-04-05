"""
Signal Service - orchestrates signal creation from ingested candle data.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.db.repositories import alerts_repo
from app.engine.orchestrator import SignalOrchestrator
from app.engine.timing_engine import TimingEngine
from app.services.alert_dispatcher import AlertDispatcher

logger = get_logger(__name__)

# Module-level orchestrator instance (stateless after init)
_orchestrator = SignalOrchestrator()


class SignalService:
    """Coordinates analysis, persistence, and dispatch of new signal alerts.

    ALERT-ONLY: Creates analytical alert records. Never executes trades.
    """

    @staticmethod
    async def create_signal(
        market_type: str,
        asset_name: str,
        expiry_profile: str,
        candles: List[Dict[str, Any]],
        parse_mode: str = "dom",
        chart_read_confidence: float = 1.0,
        chart_snapshot_meta: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Run the full analysis pipeline, store the alert, and broadcast it.

        ALERT-ONLY workflow:
        1. Generate a unique signal_id.
        2. Run the orchestrator analysis engine.
        3. Compute evaluation deadline via TimingEngine.
        4. Persist alert document to MongoDB.
        5. Broadcast to connected WebSocket clients.

        Args:
            market_type: 'live' or 'otc'.
            asset_name: Asset pair name.
            expiry_profile: '1m', '2m', or '3m'.
            candles: List of OHLC candle dicts.
            parse_mode: How candles were obtained.
            chart_read_confidence: Confidence in parsed data quality.
            chart_snapshot_meta: Optional metadata about the chart capture.

        Returns:
            The full alert document dict as stored in MongoDB.
        """
        signal_id = f"sig_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        logger.info(
            "Creating signal %s | %s | %s | %s | %d candles",
            signal_id, asset_name, market_type, expiry_profile, len(candles),
        )

        # -- 1. Run analysis engine --
        analysis = await _orchestrator.analyze(
            candles=candles,
            market_type=market_type,
            expiry_profile=expiry_profile,
            parse_mode=parse_mode,
            chart_read_confidence=chart_read_confidence,
        )

        # -- 2. Compute evaluation deadline --
        signal_for_close_at = TimingEngine.compute_evaluation_time(
            created_at=now,
            expiry_profile=expiry_profile,
        )

        # -- 3. Build document --
        doc = {
            "signal_id": signal_id,
            "market_type": market_type,
            "asset_name": asset_name,
            "expiry_profile": expiry_profile,
            "prediction_direction": analysis["prediction_direction"],
            "bullish_score": analysis["bullish_score"],
            "bearish_score": analysis["bearish_score"],
            "confidence": analysis["confidence"],
            "reasons": analysis["reasons"],
            "detected_features": analysis["detected_features"],
            "penalties": analysis["penalties"],
            "parse_mode": analysis["parse_mode"],
            "chart_read_confidence": analysis["chart_read_confidence"],
            "candle_count": analysis["candle_count"],
            "status": "pending",
            "outcome": None,
            "actual_result": None,
            "created_at": now,
            "signal_for_close_at": signal_for_close_at,
            "evaluated_at": None,
            "chart_snapshot_meta": chart_snapshot_meta,
        }

        # -- 4. Persist --
        await alerts_repo.insert_alert(doc)

        # -- 5. Broadcast via WebSocket --
        try:
            await AlertDispatcher.broadcast_new_signal(doc)
        except Exception as exc:
            logger.warning("WebSocket broadcast failed (non-fatal): %s", exc)

        logger.info(
            "Signal %s created | direction=%s | confidence=%.2f | eval_at=%s",
            signal_id,
            analysis["prediction_direction"],
            analysis["confidence"],
            signal_for_close_at.isoformat(),
        )

        return doc
