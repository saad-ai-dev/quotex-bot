"""
Observation-Only OTC Validation Runner
ALERT-ONLY - Does NOT place trades.

Same interface as LiveObservationRunner but configured for OTC markets.
Monitors the backend for new OTC signals, records them, and evaluates
outcomes after candle close. Purely observational.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from testing.live_observation_runner import (
    LiveObservationRunner,
    ObservationSession,
    ObservedSignal,
)

logger = logging.getLogger(__name__)


class OTCObservationRunner(LiveObservationRunner):
    """Observation-only runner that monitors OTC alert signals.

    ALERT-ONLY: This runner does NOT place any trades. It monitors
    the backend API for new OTC signals, records them, and evaluates
    their outcomes by checking actual price movements after the
    signal's expiry window closes.

    Inherits from LiveObservationRunner with OTC-specific defaults
    and loss cause analysis.

    OTC markets have different characteristics:
    - More pattern-driven behavior
    - Less volume transparency
    - Different timing reliability
    - Higher susceptibility to specific failure modes (otc_overfit)
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        expiry_profiles: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            backend_url=backend_url,
            expiry_profiles=expiry_profiles or ["1m", "2m", "3m"],
        )

    async def start_session(self, market_type: str = "OTC") -> ObservationSession:
        """Start a new observation session for OTC markets.

        ALERT-ONLY: Begins monitoring OTC alerts, not placing trades.

        Args:
            market_type: Market type to observe. Defaults to "OTC".

        Returns:
            The new ObservationSession object.
        """
        return await super().start_session(market_type="OTC")

    def _guess_loss_cause(
        self, observed: ObservedSignal, full_data: Dict[str, Any]
    ) -> str:
        """Categorize root cause of a loss for OTC signals.

        ALERT-ONLY: OTC-specific loss analysis for improving alert accuracy.

        OTC markets have specific failure modes:
        - otc_overfit: Pattern matching is too aggressive for OTC noise.
        - weak_sr: Support/resistance levels are less reliable in OTC.
        - false_liquidity: Liquidity signals are unreliable in OTC.
        - timing_late: OTC timing is inherently less reliable.
        """
        confidence = observed.confidence
        reasons = observed.reasons
        features = observed.detected_features

        # OTC-specific failure modes take priority
        if observed.parse_confidence < 0.6:
            return "parsing_error"

        # Check for OTC pattern over-reliance
        otc_pattern_count = features.get("otc_pattern_count", 0)
        price_action_count = features.get("price_action_pattern_count", 0)
        if otc_pattern_count > 0 and price_action_count == 0:
            return "otc_overfit"

        # Volume-based signals are unreliable in OTC
        if features.get("burst_detected") and features.get("proxy_volume_score", 0) > 0.5:
            return "false_liquidity"

        # Weak support/resistance in OTC
        if features.get("has_nearby_support") or features.get("has_nearby_resistance"):
            if confidence < 65:
                return "weak_sr"

        # General chop detection
        if any("chop" in r.lower() for r in reasons):
            return "chop_alert"

        if confidence < 55:
            return "threshold_loose"

        if confidence > 85:
            return "high_conf_false_positive"

        return "otc_overfit"

    async def generate_session_report(self) -> Dict[str, Any]:
        """Generate OTC-specific observation session report.

        ALERT-ONLY: Report includes OTC-specific analysis fields.

        Returns:
            Dict with session metadata, signal details, aggregate metrics,
            and OTC-specific breakdowns.
        """
        base_report = await super().generate_session_report()
        base_report["report_type"] = "otc_observation"

        # Add OTC-specific analysis
        if self._session:
            loss_signals = [
                obs for obs in self._session.observed_signals
                if obs.outcome == "LOSS"
            ]
            loss_causes = {}
            for obs in loss_signals:
                cause = obs.root_cause_if_loss or "unknown_cause"
                loss_causes[cause] = loss_causes.get(cause, 0) + 1

            base_report["otc_loss_breakdown"] = loss_causes

            # OTC-specific metrics
            otc_pattern_signals = [
                obs for obs in self._session.observed_signals
                if obs.detected_features.get("otc_pattern_count", 0) > 0
            ]
            base_report["otc_pattern_signal_count"] = len(otc_pattern_signals)

        return base_report
