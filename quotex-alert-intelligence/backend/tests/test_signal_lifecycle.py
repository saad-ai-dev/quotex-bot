"""
Tests for the full signal lifecycle: creation, evaluation, and timing.

ALERT-ONLY system -- signals represent analytical predictions about candle
directions. No trade execution, no money, no positions. Evaluation tracks
prediction accuracy only.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.constants import Status, Outcome, Direction
from app.engine.timing_engine import TimingEngine
from app.services.evaluation_service import EvaluationService
from app.services.signal_service import SignalService


# ---------------------------------------------------------------------------
# Signal creation tests
# ---------------------------------------------------------------------------

class TestCreateSignal:
    """Tests for signal creation. ALERT-ONLY."""

    @pytest.mark.asyncio
    async def test_create_signal(self, mock_db, sample_signal_create):
        """Signal should be created with all fields and status=PENDING.
        ALERT-ONLY: signal is a prediction record, not a trade order.
        """
        orchestrator_result = {
            "prediction_direction": "UP",
            "confidence": 72.5,
            "bullish_score": 68.0,
            "bearish_score": 22.0,
            "reasons": ["Bullish market structure", "Strong price action"],
            "detected_features": {
                "structure_bias": {"trend_bias": "bullish"},
            },
        }

        # Patch the websocket dispatcher to avoid import issues
        with patch("app.services.signal_service.AlertDispatcher", create=True) as mock_disp:
            mock_disp.dispatch_new_alert = AsyncMock()

            result = await SignalService.create_signal(
                signal_create=sample_signal_create,
                orchestrator_result=orchestrator_result,
            )

        # Verify the created signal document
        assert result["status"] == Status.PENDING
        assert result["prediction_direction"] == "UP"
        assert result["confidence"] == 72.5
        assert result["bullish_score"] == 68.0
        assert result["bearish_score"] == 22.0
        assert result["market_type"] == "LIVE"
        assert result["expiry_profile"] == "1m"
        assert result["outcome"] is None
        assert result["signal_id"] is not None
        assert len(result["signal_id"]) > 0
        assert result["created_at"] is not None
        assert result["signal_for_close_at"] is not None

        # Verify timing: signal_for_close_at = created_at + 60s for 1m expiry
        delta = (result["signal_for_close_at"] - result["created_at"]).total_seconds()
        assert delta == 60.0

        # Verify DB insert was called
        mock_db["insert_alert"].assert_called_once()


# ---------------------------------------------------------------------------
# Signal evaluation tests
# ---------------------------------------------------------------------------

class TestEvaluateSignal:
    """Tests for signal evaluation (outcome determination). ALERT-ONLY."""

    @pytest.mark.asyncio
    async def test_evaluate_signal_win(self, mock_db):
        """UP prediction + bullish actual = WIN.
        ALERT-ONLY: WIN means the prediction matched the candle direction.
        """
        # Setup: pending signal predicting UP
        pending_doc = {
            "signal_id": "sig_test_001",
            "status": Status.PENDING,
            "prediction_direction": Direction.UP,
            "outcome": None,
        }
        mock_db["get_alert_by_signal_id"].side_effect = [
            pending_doc,  # First call: fetch for validation
            {**pending_doc, "status": Status.EVALUATED, "outcome": Outcome.WIN},  # After update
        ]

        with patch("app.services.evaluation_service.AlertDispatcher", create=True) as mock_disp:
            mock_disp.dispatch_evaluation_update = AsyncMock()

            result = await EvaluationService.evaluate_signal(
                signal_id="sig_test_001",
                outcome=Outcome.WIN,
                candle_direction="bullish",
            )

        assert result["outcome"] == Outcome.WIN
        assert result["status"] == Status.EVALUATED
        mock_db["update_alert_outcome"].assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_signal_loss(self, mock_db):
        """UP prediction + bearish actual = LOSS.
        ALERT-ONLY: LOSS means the prediction did not match.
        """
        pending_doc = {
            "signal_id": "sig_test_002",
            "status": Status.PENDING,
            "prediction_direction": Direction.UP,
            "outcome": None,
        }
        mock_db["get_alert_by_signal_id"].side_effect = [
            pending_doc,
            {**pending_doc, "status": Status.EVALUATED, "outcome": Outcome.LOSS},
        ]

        with patch("app.services.evaluation_service.AlertDispatcher", create=True) as mock_disp:
            mock_disp.dispatch_evaluation_update = AsyncMock()

            result = await EvaluationService.evaluate_signal(
                signal_id="sig_test_002",
                outcome=Outcome.LOSS,
                candle_direction="bearish",
            )

        assert result["outcome"] == Outcome.LOSS
        assert result["status"] == Status.EVALUATED

    @pytest.mark.asyncio
    async def test_evaluate_signal_neutral(self, mock_db):
        """Doji actual candle = NEUTRAL outcome.
        ALERT-ONLY: NEUTRAL means inconclusive candle.
        """
        pending_doc = {
            "signal_id": "sig_test_003",
            "status": Status.PENDING,
            "prediction_direction": Direction.UP,
            "outcome": None,
        }
        mock_db["get_alert_by_signal_id"].side_effect = [
            pending_doc,
            {**pending_doc, "status": Status.EVALUATED, "outcome": Outcome.NEUTRAL},
        ]

        with patch("app.services.evaluation_service.AlertDispatcher", create=True) as mock_disp:
            mock_disp.dispatch_evaluation_update = AsyncMock()

            result = await EvaluationService.evaluate_signal(
                signal_id="sig_test_003",
                outcome=Outcome.NEUTRAL,
                candle_direction="doji",
            )

        assert result["outcome"] == Outcome.NEUTRAL

    @pytest.mark.asyncio
    async def test_evaluate_signal_unknown(self, mock_db):
        """Missing candle data = UNKNOWN outcome.
        ALERT-ONLY: UNKNOWN means no follow-up data was available.
        """
        pending_doc = {
            "signal_id": "sig_test_004",
            "status": Status.PENDING,
            "prediction_direction": Direction.UP,
            "outcome": None,
        }
        mock_db["get_alert_by_signal_id"].side_effect = [
            pending_doc,
            {**pending_doc, "status": Status.EVALUATED, "outcome": Outcome.UNKNOWN},
        ]

        with patch("app.services.evaluation_service.AlertDispatcher", create=True) as mock_disp:
            mock_disp.dispatch_evaluation_update = AsyncMock()

            result = await EvaluationService.evaluate_signal(
                signal_id="sig_test_004",
                outcome=Outcome.UNKNOWN,
                candle_direction=None,
            )

        assert result["outcome"] == Outcome.UNKNOWN

    @pytest.mark.asyncio
    async def test_double_evaluation_rejected(self, mock_db):
        """Cannot evaluate an already-evaluated signal.
        ALERT-ONLY: prevents double-counting in accuracy tracking.
        """
        already_evaluated = {
            "signal_id": "sig_test_005",
            "status": Status.EVALUATED,
            "prediction_direction": Direction.UP,
            "outcome": Outcome.WIN,
        }
        mock_db["get_alert_by_signal_id"].return_value = already_evaluated

        with pytest.raises(ValueError, match="already evaluated"):
            await EvaluationService.evaluate_signal(
                signal_id="sig_test_005",
                outcome=Outcome.LOSS,
                candle_direction="bearish",
            )

        # DB update should NOT have been called
        mock_db["update_alert_outcome"].assert_not_called()


# ---------------------------------------------------------------------------
# Determine outcome unit tests (pure function, no DB)
# ---------------------------------------------------------------------------

class TestDetermineOutcome:
    """Tests for the static outcome determination function. ALERT-ONLY."""

    def test_up_bullish_is_win(self):
        assert EvaluationService.determine_outcome("UP", "bullish") == Outcome.WIN

    def test_up_bearish_is_loss(self):
        assert EvaluationService.determine_outcome("UP", "bearish") == Outcome.LOSS

    def test_down_bearish_is_win(self):
        assert EvaluationService.determine_outcome("DOWN", "bearish") == Outcome.WIN

    def test_down_bullish_is_loss(self):
        assert EvaluationService.determine_outcome("DOWN", "bullish") == Outcome.LOSS

    def test_doji_is_neutral(self):
        assert EvaluationService.determine_outcome("UP", "doji") == Outcome.NEUTRAL

    def test_neutral_is_neutral(self):
        assert EvaluationService.determine_outcome("DOWN", "neutral") == Outcome.NEUTRAL

    def test_none_is_unknown(self):
        assert EvaluationService.determine_outcome("UP", None) == Outcome.UNKNOWN


# ---------------------------------------------------------------------------
# TimingEngine tests
# ---------------------------------------------------------------------------

class TestTimingEngine:
    """Tests for the timing engine. ALERT-ONLY."""

    def test_timing_engine_1m(self):
        """1m expiry: evaluation time = created + 60 seconds.
        ALERT-ONLY: timing determines when to check prediction accuracy.
        """
        created = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        eval_time = TimingEngine.compute_evaluation_time(created, "1m")

        assert eval_time == created + timedelta(seconds=60)
        assert (eval_time - created).total_seconds() == 60

    def test_timing_engine_2m(self):
        """2m expiry: evaluation time = created + 120 seconds.
        ALERT-ONLY: 2-minute prediction window.
        """
        created = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        eval_time = TimingEngine.compute_evaluation_time(created, "2m")

        assert eval_time == created + timedelta(seconds=120)
        assert (eval_time - created).total_seconds() == 120

    def test_timing_engine_3m(self):
        """3m expiry: evaluation time = created + 180 seconds.
        ALERT-ONLY: 3-minute prediction window.
        """
        created = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        eval_time = TimingEngine.compute_evaluation_time(created, "3m")

        assert eval_time == created + timedelta(seconds=180)
        assert (eval_time - created).total_seconds() == 180

    def test_timing_engine_invalid_expiry(self):
        """Invalid expiry profile should raise ValueError.
        ALERT-ONLY: only 1m/2m/3m are supported.
        """
        created = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Unknown expiry profile"):
            TimingEngine.compute_evaluation_time(created, "5m")

    def test_is_too_late_for_alert(self):
        """Alert should not be generated too close to candle close.
        ALERT-ONLY: ensures timely alert delivery.
        """
        close_time = datetime(2024, 6, 15, 12, 1, 0, tzinfo=timezone.utc)

        # 3 seconds before close -- too late
        current_late = datetime(2024, 6, 15, 12, 0, 57, tzinfo=timezone.utc)
        assert TimingEngine.is_too_late_for_alert(current_late, close_time) is True

        # 10 seconds before close -- OK
        current_ok = datetime(2024, 6, 15, 12, 0, 50, tzinfo=timezone.utc)
        assert TimingEngine.is_too_late_for_alert(current_ok, close_time) is False
