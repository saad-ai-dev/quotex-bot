"""
Timing engine edge case tests.

ALERT-ONLY system -- tests verify evaluation time computation and
candle-close timing checks for alert scheduling. No trade timing is involved.
"""

import pytest
from datetime import datetime, timedelta

from app.engine.timing_engine import TimingEngine


# ---------------------------------------------------------------------------
# compute_evaluation_time tests
# ---------------------------------------------------------------------------

def test_evaluation_time_1m():
    """1m expiry: evaluation time should be created_at + 60 seconds."""
    created_at = datetime(2025, 6, 15, 12, 0, 0)
    eval_time = TimingEngine.compute_evaluation_time(created_at, "1m")
    expected = created_at + timedelta(seconds=60)
    assert eval_time == expected


def test_evaluation_time_2m():
    """2m expiry: evaluation time should be created_at + 120 seconds."""
    created_at = datetime(2025, 6, 15, 12, 0, 0)
    eval_time = TimingEngine.compute_evaluation_time(created_at, "2m")
    expected = created_at + timedelta(seconds=120)
    assert eval_time == expected


def test_evaluation_time_3m():
    """3m expiry: evaluation time should be created_at + 180 seconds."""
    created_at = datetime(2025, 6, 15, 12, 0, 0)
    eval_time = TimingEngine.compute_evaluation_time(created_at, "3m")
    expected = created_at + timedelta(seconds=180)
    assert eval_time == expected


def test_evaluation_time_invalid_expiry():
    """Unknown expiry profile should raise ValueError."""
    created_at = datetime(2025, 6, 15, 12, 0, 0)
    with pytest.raises(ValueError, match="Unknown expiry profile"):
        TimingEngine.compute_evaluation_time(created_at, "5m")


# ---------------------------------------------------------------------------
# is_too_late_for_alert tests
# ---------------------------------------------------------------------------

def test_too_late_returns_true_when_1s_left():
    """With only 1 second remaining (< 5s default), it is too late."""
    candle_close = datetime(2025, 6, 15, 12, 1, 0)
    current = candle_close - timedelta(seconds=1)
    assert TimingEngine.is_too_late_for_alert(current, candle_close) is True


def test_too_late_returns_false_when_30s_left():
    """With 30 seconds remaining (> 5s default), it is not too late."""
    candle_close = datetime(2025, 6, 15, 12, 1, 0)
    current = candle_close - timedelta(seconds=30)
    assert TimingEngine.is_too_late_for_alert(current, candle_close) is False


def test_too_late_custom_threshold():
    """Custom min_seconds_before should be respected."""
    candle_close = datetime(2025, 6, 15, 12, 1, 0)
    current = candle_close - timedelta(seconds=8)
    # 8 seconds left, threshold = 10 => too late
    assert TimingEngine.is_too_late_for_alert(current, candle_close, min_seconds_before=10) is True
    # 8 seconds left, threshold = 5 => not too late
    assert TimingEngine.is_too_late_for_alert(current, candle_close, min_seconds_before=5) is False


# ---------------------------------------------------------------------------
# get_candle_countdown tests
# ---------------------------------------------------------------------------

def test_countdown_positive():
    """Countdown should return positive seconds when candle has not closed."""
    candle_close = datetime(2025, 6, 15, 12, 1, 0)
    current = datetime(2025, 6, 15, 12, 0, 30)
    countdown = TimingEngine.get_candle_countdown(candle_close, current)
    assert countdown == 30


def test_countdown_zero_at_close():
    """Countdown should be 0 exactly at close time."""
    candle_close = datetime(2025, 6, 15, 12, 1, 0)
    countdown = TimingEngine.get_candle_countdown(candle_close, candle_close)
    assert countdown == 0


def test_countdown_negative_after_close():
    """Countdown should be negative after candle has closed."""
    candle_close = datetime(2025, 6, 15, 12, 1, 0)
    current = datetime(2025, 6, 15, 12, 1, 5)
    countdown = TimingEngine.get_candle_countdown(candle_close, current)
    assert countdown == -5
