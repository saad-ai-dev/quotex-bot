"""
Historical Replay Validation Runner
ALERT-ONLY - No trade execution.

Replays stored candle sequences through the signal engine and evaluates
predictions against known outcomes. This enables offline validation of
the analysis pipeline without connecting to live markets or placing trades.
"""

import asyncio
import json
import logging
import os
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
class ReplaySignal:
    """A single signal produced during replay."""

    sequence_index: int
    signal_data: Dict[str, Any]
    actual_direction: Optional[str] = None
    outcome: Optional[str] = None
    evaluation_notes: str = ""


@dataclass
class BatchResult:
    """Result of replaying a batch of candle sequences."""

    market_type: str
    expiry_profile: str
    total_sequences: int = 0
    signals: List[ReplaySignal] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    neutral: int = 0
    unknown: int = 0
    no_trade_count: int = 0
    total_latency_ms: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


class HistoryReplayRunner:
    """Replays historical candle sequences through the alert analysis engine.

    ALERT-ONLY: This runner produces analytical predictions and compares
    them against known outcomes. No trades are placed or simulated.

    Typical workflow:
        1. Load candle sequences from JSON files or MongoDB.
        2. For each sequence, feed candles to the orchestrator.
        3. Capture the predicted direction and confidence.
        4. Compare against the actual next candle(s) to evaluate correctness.
        5. Aggregate results into a BatchResult for reporting.
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        db_name: str = "quotex_alerts_test",
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.db_name = db_name

    async def load_candle_sequences(self, source: str) -> List[Dict[str, Any]]:
        """Load candle sequences from a JSON file or MongoDB collection.

        Each sequence is a dict with:
            - "candles": list of candle dicts
            - "actual_direction": the known outcome direction ("UP"/"DOWN")
            - "market_type": optional override
            - "expiry_profile": optional override

        ALERT-ONLY: Sequences contain historical market data for analysis.

        Args:
            source: Path to a JSON file, or a MongoDB collection name
                    prefixed with "mongodb://".

        Returns:
            List of sequence dicts.
        """
        if source.startswith("mongodb://"):
            return await self._load_from_mongodb(source)
        return self._load_from_json(source)

    def _load_from_json(self, filepath: str) -> List[Dict[str, Any]]:
        """Load sequences from a JSON file."""
        if not os.path.isfile(filepath):
            logger.warning("Sequence file not found: %s", filepath)
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "sequences" in data:
            return data["sequences"]

        logger.warning("Unexpected JSON structure in %s", filepath)
        return []

    async def _load_from_mongodb(self, source: str) -> List[Dict[str, Any]]:
        """Load sequences from a MongoDB collection.

        Expected source format: "mongodb://collection_name"
        """
        from motor.motor_asyncio import AsyncIOMotorClient

        collection_name = source.replace("mongodb://", "")
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client[self.db_name]
        col = db[collection_name]

        sequences = []
        async for doc in col.find():
            doc.pop("_id", None)
            sequences.append(doc)

        client.close()
        return sequences

    async def run_replay(
        self,
        sequences: List[Dict[str, Any]],
        market_type: str = "LIVE",
        expiry_profile: str = "1m",
    ) -> BatchResult:
        """Replay all sequences through the analysis engine.

        ALERT-ONLY: Produces predictions for comparison, no trades executed.

        For each sequence:
            1. Extract candle data.
            2. Send to the orchestrator (via direct import or HTTP).
            3. Record the prediction.
            4. Compare against actual outcome.

        Args:
            sequences: List of sequence dicts from load_candle_sequences.
            market_type: Default market type if not specified in sequence.
            expiry_profile: Default expiry if not specified in sequence.

        Returns:
            BatchResult with all signals and aggregate metrics.
        """
        batch = BatchResult(
            market_type=market_type,
            expiry_profile=expiry_profile,
            total_sequences=len(sequences),
            started_at=datetime.now(timezone.utc),
        )

        # Import orchestrator for direct replay (faster than HTTP)
        import sys

        backend_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from app.engine.orchestrator import SignalOrchestrator

        orchestrator = SignalOrchestrator()

        for idx, seq in enumerate(sequences):
            candles = seq.get("candles", [])
            actual_dir = seq.get("actual_direction")
            mt = seq.get("market_type", market_type)
            ep = seq.get("expiry_profile", expiry_profile)

            if not candles:
                logger.warning("Sequence %d has no candles, skipping", idx)
                continue

            start_time = time.monotonic()
            try:
                signal_data = await orchestrator.analyze(
                    candles=candles,
                    market_type=mt,
                    expiry_profile=ep,
                    parse_mode="replay",
                    chart_read_confidence=1.0,
                )
            except Exception as exc:
                logger.error("Replay error on sequence %d: %s", idx, exc)
                signal_data = {
                    "prediction_direction": "NO_TRADE",
                    "confidence": 0.0,
                    "bullish_score": 0.0,
                    "bearish_score": 0.0,
                    "reasons": [f"Replay error: {exc}"],
                }
            elapsed_ms = (time.monotonic() - start_time) * 1000
            batch.total_latency_ms += elapsed_ms

            predicted_dir = signal_data.get("prediction_direction", "NO_TRADE")

            # Evaluate outcome
            outcome, notes = self._evaluate_single(predicted_dir, actual_dir)
            replay_signal = ReplaySignal(
                sequence_index=idx,
                signal_data=signal_data,
                actual_direction=actual_dir,
                outcome=outcome,
                evaluation_notes=notes,
            )
            batch.signals.append(replay_signal)

            # Tally
            if predicted_dir == "NO_TRADE":
                batch.no_trade_count += 1
            elif outcome == "WIN":
                batch.wins += 1
            elif outcome == "LOSS":
                batch.losses += 1
            elif outcome == "NEUTRAL":
                batch.neutral += 1
            else:
                batch.unknown += 1

        batch.finished_at = datetime.now(timezone.utc)
        return batch

    def _evaluate_single(
        self, predicted: str, actual: Optional[str]
    ) -> tuple:
        """Compare a single prediction against the actual direction.

        ALERT-ONLY: Evaluates alert prediction accuracy.

        Returns:
            (outcome, notes) tuple.
        """
        if actual is None:
            return "UNKNOWN", "No actual direction provided"

        if predicted == "NO_TRADE":
            return "NEUTRAL", "No trade signal generated"

        actual_upper = actual.upper()
        if predicted == actual_upper:
            return "WIN", f"Predicted {predicted}, actual was {actual_upper}"
        elif actual_upper in ("UP", "DOWN"):
            return "LOSS", f"Predicted {predicted}, actual was {actual_upper}"
        else:
            return "NEUTRAL", f"Actual direction unclear: {actual}"

    async def evaluate_batch(
        self,
        signals: List[Dict[str, Any]],
        actuals: List[Optional[str]],
    ) -> Dict[str, Any]:
        """Evaluate a batch of signals against actual outcomes.

        ALERT-ONLY: Batch evaluation of alert predictions.

        Args:
            signals: List of signal data dicts from the orchestrator.
            actuals: List of actual directions (same length as signals).

        Returns:
            Dict with wins, losses, neutral, unknown counts and rates.
        """
        wins = losses = neutral = unknown = 0

        for sig, actual in zip(signals, actuals):
            predicted = sig.get("prediction_direction", "NO_TRADE")
            outcome, _ = self._evaluate_single(predicted, actual)
            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            elif outcome == "NEUTRAL":
                neutral += 1
            else:
                unknown += 1

        total = len(signals)
        evaluated = wins + losses
        win_rate = round((wins / evaluated) * 100, 2) if evaluated > 0 else 0.0

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "neutral": neutral,
            "unknown": unknown,
            "win_rate": win_rate,
        }

    def generate_report(self, batch_result: BatchResult) -> Dict[str, Any]:
        """Generate a structured report from a batch replay result.

        ALERT-ONLY: Report summarizes alert prediction performance.

        Args:
            batch_result: The BatchResult from run_replay.

        Returns:
            Dict matching the standard reporting format.
        """
        evaluated = batch_result.wins + batch_result.losses
        win_rate = (
            round((batch_result.wins / evaluated) * 100, 2) if evaluated > 0 else 0.0
        )
        avg_latency = (
            round(batch_result.total_latency_ms / batch_result.total_sequences, 2)
            if batch_result.total_sequences > 0
            else 0.0
        )

        # Per-signal details
        signal_details = []
        for sig in batch_result.signals:
            detail = {
                "sequence_index": sig.sequence_index,
                "predicted_direction": sig.signal_data.get("prediction_direction"),
                "confidence": sig.signal_data.get("confidence"),
                "bullish_score": sig.signal_data.get("bullish_score"),
                "bearish_score": sig.signal_data.get("bearish_score"),
                "actual_direction": sig.actual_direction,
                "outcome": sig.outcome,
                "notes": sig.evaluation_notes,
            }
            signal_details.append(detail)

        return {
            "report_type": "historical_replay",
            "market_type": batch_result.market_type,
            "expiry_profile": batch_result.expiry_profile,
            "total_sequences": batch_result.total_sequences,
            "wins": batch_result.wins,
            "losses": batch_result.losses,
            "neutral": batch_result.neutral,
            "unknown": batch_result.unknown,
            "no_trade_count": batch_result.no_trade_count,
            "win_rate": win_rate,
            "avg_latency_ms": avg_latency,
            "started_at": (
                batch_result.started_at.isoformat()
                if batch_result.started_at
                else None
            ),
            "finished_at": (
                batch_result.finished_at.isoformat()
                if batch_result.finished_at
                else None
            ),
            "signal_details": signal_details,
        }

    def save_report(self, report: Dict[str, Any], filepath: str) -> None:
        """Save a report to a JSON file.

        ALERT-ONLY: Persists alert performance reports for review.

        Args:
            report: Report dict from generate_report.
            filepath: Output file path.
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("Report saved to %s", filepath)
