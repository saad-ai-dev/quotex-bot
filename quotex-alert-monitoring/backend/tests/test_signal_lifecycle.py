"""
Tests for signal lifecycle: EvaluationService.determine_outcome and TimingEngine.
ALERT-ONLY: Validates prediction outcome logic and timing calculations.
"""

from datetime import datetime, timedelta

import pytest

from app.services.evaluation_service import EvaluationService
from app.engine.timing_engine import TimingEngine
from app.core.constants import Outcome


# ===========================================================================
# EvaluationService.determine_outcome
# ===========================================================================

class TestDetermineOutcome:

    def test_determine_outcome_up_bullish_win(self):
        """Predicted UP, actual bullish => WIN."""
        result = EvaluationService.determine_outcome("UP", "bullish")
        assert result == Outcome.WIN

    def test_determine_outcome_up_bearish_loss(self):
        """Predicted UP, actual bearish => LOSS."""
        result = EvaluationService.determine_outcome("UP", "bearish")
        assert result == Outcome.LOSS

    def test_determine_outcome_down_bearish_win(self):
        """Predicted DOWN, actual bearish => WIN."""
        result = EvaluationService.determine_outcome("DOWN", "bearish")
        assert result == Outcome.WIN

    def test_determine_outcome_down_bullish_loss(self):
        """Predicted DOWN, actual bullish => LOSS."""
        result = EvaluationService.determine_outcome("DOWN", "bullish")
        assert result == Outcome.LOSS

    def test_determine_outcome_doji_neutral(self):
        """Actual neutral (doji) => NEUTRAL regardless of prediction."""
        result = EvaluationService.determine_outcome("UP", "neutral")
        assert result == Outcome.NEUTRAL

    def test_determine_outcome_none_unknown(self):
        """Unrecognised actual direction => UNKNOWN."""
        result = EvaluationService.determine_outcome("UP", "sideways")
        assert result == Outcome.UNKNOWN


# ===========================================================================
# TimingEngine
# ===========================================================================

class TestTimingEngine:

    def test_timing_engine_1m(self):
        """1m expiry adds 60 seconds to created_at."""
        now = datetime(2025, 1, 1, 12, 0, 0)
        eval_time = TimingEngine.compute_evaluation_time(now, "1m")
        assert eval_time == now + timedelta(seconds=60)

    def test_timing_engine_2m(self):
        """2m expiry adds 120 seconds."""
        now = datetime(2025, 1, 1, 12, 0, 0)
        eval_time = TimingEngine.compute_evaluation_time(now, "2m")
        assert eval_time == now + timedelta(seconds=120)

    def test_timing_engine_3m(self):
        """3m expiry adds 180 seconds."""
        now = datetime(2025, 1, 1, 12, 0, 0)
        eval_time = TimingEngine.compute_evaluation_time(now, "3m")
        assert eval_time == now + timedelta(seconds=180)

    def test_timing_engine_invalid(self):
        """Invalid expiry profile raises ValueError."""
        now = datetime(2025, 1, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="Unknown expiry profile"):
            TimingEngine.compute_evaluation_time(now, "5m")

    def test_too_late_for_alert(self):
        """Returns True when remaining time is less than min_seconds_before."""
        close_time = datetime(2025, 1, 1, 12, 1, 0)
        current = datetime(2025, 1, 1, 12, 0, 57)  # 3 seconds left
        assert TimingEngine.is_too_late_for_alert(current, close_time, min_seconds_before=5) is True
        # With enough time remaining
        current_early = datetime(2025, 1, 1, 12, 0, 50)  # 10 seconds left
        assert TimingEngine.is_too_late_for_alert(current_early, close_time, min_seconds_before=5) is False

    def test_countdown(self):
        """get_candle_countdown returns correct seconds remaining."""
        close_time = datetime(2025, 1, 1, 12, 1, 0)
        current = datetime(2025, 1, 1, 12, 0, 45)
        countdown = TimingEngine.get_candle_countdown(close_time, current_time=current)
        assert countdown == 15
