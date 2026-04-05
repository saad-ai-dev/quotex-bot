"""
Observation-Only LIVE Validation Runner
ALERT-ONLY - Does NOT place trades.

Monitors the backend for new LIVE signals, records them,
and evaluates outcomes after candle close. This runner is purely
observational: it watches alerts come in and records whether
predictions were correct, without any trade execution.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ObservedSignal:
    """A single observed signal with its evaluation metadata."""

    signal_id: str
    created_at: Optional[str] = None
    market_type: str = "LIVE"
    expiry_profile: str = "1m"
    direction: str = "NO_TRADE"
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    detected_features: Dict[str, Any] = field(default_factory=dict)
    parse_mode: str = "unknown"
    parse_confidence: float = 0.0
    outcome: Optional[str] = None
    root_cause_if_loss: Optional[str] = None
    evaluated_at: Optional[str] = None


@dataclass
class ObservationSession:
    """An observation session tracking signals over a time window."""

    session_id: str = ""
    market_type: str = "LIVE"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    observed_signals: List[ObservedSignal] = field(default_factory=list)
    total_observed: int = 0
    evaluated_count: int = 0
    wins: int = 0
    losses: int = 0
    neutral: int = 0
    unknown: int = 0


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


class LiveObservationRunner:
    """Observation-only runner that monitors LIVE alert signals.

    ALERT-ONLY: This runner does NOT place any trades. It monitors
    the backend API for new signals, records them, and evaluates
    their outcomes by checking actual price movements after the
    signal's expiry window closes.

    Typical workflow:
        1. Start a session targeting LIVE markets.
        2. Poll /api/signals for new LIVE signals periodically.
        3. Record each new signal's details.
        4. After the expiry window, check outcome via /api/history.
        5. Generate a session report with win/loss statistics.
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        expiry_profiles: Optional[List[str]] = None,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.expiry_profiles = expiry_profiles or ["1m", "2m", "3m"]
        self._session: Optional[ObservationSession] = None
        self._seen_signal_ids: set = set()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.backend_url,
                timeout=30.0,
            )
        return self._http_client

    async def start_session(self, market_type: str = "LIVE") -> ObservationSession:
        """Start a new observation session.

        ALERT-ONLY: Begins monitoring alerts, not placing trades.

        Args:
            market_type: Market type to observe ("LIVE").

        Returns:
            The new ObservationSession object.
        """
        session_id = f"obs_{market_type.lower()}_{int(time.time())}"
        self._session = ObservationSession(
            session_id=session_id,
            market_type=market_type,
            started_at=datetime.now(timezone.utc),
        )
        self._seen_signal_ids.clear()
        logger.info(
            "Started LIVE observation session %s for market_type=%s",
            session_id,
            market_type,
        )
        return self._session

    async def monitor_signals(self, duration_minutes: int = 60) -> None:
        """Poll for new LIVE signals for the specified duration.

        ALERT-ONLY: Passively monitors alert generation, no trade actions.

        Args:
            duration_minutes: How long to monitor in minutes.
        """
        if self._session is None:
            raise RuntimeError("No active session. Call start_session() first.")

        client = await self._get_client()
        end_time = time.monotonic() + (duration_minutes * 60)
        poll_interval = 5  # seconds

        logger.info(
            "Monitoring LIVE signals for %d minutes (session %s)",
            duration_minutes,
            self._session.session_id,
        )

        while time.monotonic() < end_time:
            try:
                resp = await client.get(
                    "/api/signals",
                    params={
                        "market_type": self._session.market_type,
                        "status": "PENDING",
                        "limit": 100,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    for item in items:
                        sig_id = item.get("signal_id", "")
                        if sig_id and sig_id not in self._seen_signal_ids:
                            self._seen_signal_ids.add(sig_id)
                            observed = self._record_signal(item)
                            self._session.observed_signals.append(observed)
                            self._session.total_observed += 1
                            logger.info(
                                "Observed new signal: %s direction=%s confidence=%.1f",
                                sig_id,
                                observed.direction,
                                observed.confidence,
                            )
                else:
                    logger.warning("Poll returned status %d", resp.status_code)

            except httpx.RequestError as exc:
                logger.error("HTTP error during monitoring: %s", exc)

            await asyncio.sleep(poll_interval)

        logger.info(
            "Monitoring complete. Observed %d signals.",
            self._session.total_observed,
        )

    def _record_signal(self, item: Dict[str, Any]) -> ObservedSignal:
        """Extract and record signal details from an API response item.

        ALERT-ONLY: Records alert metadata for later evaluation.
        """
        return ObservedSignal(
            signal_id=item.get("signal_id", ""),
            created_at=str(item.get("created_at", "")),
            market_type=item.get("market_type", "LIVE"),
            expiry_profile=item.get("expiry_profile", "1m"),
            direction=item.get("direction", "NO_TRADE"),
            confidence=float(item.get("confidence", 0.0)),
            reasons=item.get("reasons", []),
            detected_features=item.get("detected_features", {}),
            parse_mode=item.get("parse_mode", item.get("metadata", {}).get("parse_mode", "unknown")),
            parse_confidence=float(item.get("chart_read_confidence", 0.0)),
            outcome=item.get("outcome"),
        )

    async def evaluate_pending(self) -> None:
        """Check pending signals and evaluate those whose expiry has passed.

        ALERT-ONLY: Evaluates alert prediction accuracy by checking
        actual market outcomes. No trades are placed or evaluated.
        """
        if self._session is None:
            raise RuntimeError("No active session.")

        client = await self._get_client()

        for observed in self._session.observed_signals:
            if observed.outcome and observed.outcome != "UNKNOWN":
                continue  # Already evaluated

            try:
                resp = await client.get(f"/api/signals/{observed.signal_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "PENDING")
                    outcome = data.get("outcome", "UNKNOWN")

                    if status == "EVALUATED" and outcome != "UNKNOWN":
                        observed.outcome = outcome
                        observed.evaluated_at = str(
                            data.get("evaluated_at", datetime.now(timezone.utc))
                        )
                        self._session.evaluated_count += 1

                        if outcome == "WIN":
                            self._session.wins += 1
                        elif outcome == "LOSS":
                            self._session.losses += 1
                            observed.root_cause_if_loss = self._guess_loss_cause(
                                observed, data
                            )
                        elif outcome == "NEUTRAL":
                            self._session.neutral += 1
                        else:
                            self._session.unknown += 1

            except httpx.RequestError as exc:
                logger.error(
                    "Error evaluating signal %s: %s",
                    observed.signal_id,
                    exc,
                )

    def _guess_loss_cause(
        self, observed: ObservedSignal, full_data: Dict[str, Any]
    ) -> str:
        """Attempt to categorize the root cause of a loss.

        ALERT-ONLY: Loss analysis for improving alert accuracy.
        """
        confidence = observed.confidence
        reasons = observed.reasons

        if confidence < 55:
            return "threshold_loose"
        if observed.parse_confidence < 0.7:
            return "parsing_error"
        if any("chop" in r.lower() for r in reasons):
            return "chop_alert"
        if any("indecision" in r.lower() for r in reasons):
            return "weak_sr"
        if observed.market_type == "OTC":
            return "otc_overfit"
        return "unknown_cause"

    async def generate_session_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report for the observation session.

        ALERT-ONLY: Report summarizes alert prediction performance.

        Returns:
            Dict with session metadata, signal details, and aggregate metrics.
        """
        if self._session is None:
            return {"error": "No active session"}

        self._session.ended_at = datetime.now(timezone.utc)
        evaluated = self._session.wins + self._session.losses
        win_rate = (
            round((self._session.wins / evaluated) * 100, 2)
            if evaluated > 0
            else 0.0
        )

        signal_records = []
        for obs in self._session.observed_signals:
            signal_records.append({
                "signal_id": obs.signal_id,
                "created_at": obs.created_at,
                "market_type": obs.market_type,
                "expiry_profile": obs.expiry_profile,
                "direction": obs.direction,
                "confidence": obs.confidence,
                "reasons": obs.reasons,
                "detected_features": obs.detected_features,
                "parse_mode": obs.parse_mode,
                "parse_confidence": obs.parse_confidence,
                "outcome": obs.outcome,
                "root_cause_if_loss": obs.root_cause_if_loss,
                "evaluated_at": obs.evaluated_at,
            })

        return {
            "report_type": "live_observation",
            "session_id": self._session.session_id,
            "market_type": self._session.market_type,
            "started_at": (
                self._session.started_at.isoformat()
                if self._session.started_at
                else None
            ),
            "ended_at": (
                self._session.ended_at.isoformat()
                if self._session.ended_at
                else None
            ),
            "total_observed": self._session.total_observed,
            "evaluated_count": self._session.evaluated_count,
            "wins": self._session.wins,
            "losses": self._session.losses,
            "neutral": self._session.neutral,
            "unknown": self._session.unknown,
            "win_rate": win_rate,
            "signals": signal_records,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
