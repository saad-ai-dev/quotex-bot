"""
Tests for chart_math utility functions.

ALERT-ONLY system -- these utilities support signal analysis computations.
No trade execution logic is involved.
"""

import pytest

from app.utils.chart_math import (
    is_bullish,
    is_bearish,
    is_doji,
    compute_candle_body,
    compute_candle_range,
    compute_upper_wick,
    compute_lower_wick,
    compute_atr,
    normalize_candles,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(open_: float, high: float, low: float, close: float, ts: float = 0.0):
    return {"open": open_, "high": high, "low": low, "close": close, "timestamp": ts}


# ---------------------------------------------------------------------------
# is_bullish / is_bearish / is_doji
# ---------------------------------------------------------------------------

def test_is_bullish():
    """A candle with close > open is bullish."""
    candle = _c(1.0800, 1.0820, 1.0790, 1.0815)
    assert is_bullish(candle) is True
    assert is_bearish(candle) is False


def test_is_bearish():
    """A candle with close < open is bearish."""
    candle = _c(1.0815, 1.0820, 1.0790, 1.0800)
    assert is_bearish(candle) is True
    assert is_bullish(candle) is False


def test_is_doji():
    """A candle with close approximately equal to open is a doji."""
    # body = 0.0001, range = 0.0030, ratio = 0.033 < 0.1 threshold
    candle = _c(1.0800, 1.0820, 1.0790, 1.0801)
    assert is_doji(candle) is True


def test_is_doji_flat():
    """A candle with zero range is considered a doji."""
    candle = _c(1.0800, 1.0800, 1.0800, 1.0800)
    assert is_doji(candle) is True


# ---------------------------------------------------------------------------
# compute_candle_body
# ---------------------------------------------------------------------------

def test_compute_candle_body():
    """Body should be abs(close - open)."""
    candle = _c(1.0800, 1.0820, 1.0790, 1.0815)
    body = compute_candle_body(candle)
    assert body == pytest.approx(0.0015, abs=1e-8)


def test_compute_candle_body_bearish():
    """Body of a bearish candle should also be positive."""
    candle = _c(1.0815, 1.0820, 1.0790, 1.0800)
    body = compute_candle_body(candle)
    assert body == pytest.approx(0.0015, abs=1e-8)


# ---------------------------------------------------------------------------
# compute_candle_range
# ---------------------------------------------------------------------------

def test_compute_candle_range():
    """Range should be high - low."""
    candle = _c(1.0800, 1.0820, 1.0790, 1.0815)
    r = compute_candle_range(candle)
    assert r == pytest.approx(0.0030, abs=1e-8)


# ---------------------------------------------------------------------------
# compute_upper_wick / compute_lower_wick
# ---------------------------------------------------------------------------

def test_compute_upper_wick():
    """Upper wick is high - max(open, close)."""
    candle = _c(1.0800, 1.0820, 1.0790, 1.0815)
    uw = compute_upper_wick(candle)
    assert uw == pytest.approx(1.0820 - 1.0815, abs=1e-8)


def test_compute_lower_wick():
    """Lower wick is min(open, close) - low."""
    candle = _c(1.0800, 1.0820, 1.0790, 1.0815)
    lw = compute_lower_wick(candle)
    assert lw == pytest.approx(1.0800 - 1.0790, abs=1e-8)


# ---------------------------------------------------------------------------
# compute_atr
# ---------------------------------------------------------------------------

def test_compute_atr():
    """ATR should return a float > 0 for valid candles with movement."""
    candles = [
        _c(1.0800, 1.0810, 1.0790, 1.0805, ts=0.0),
        _c(1.0805, 1.0820, 1.0795, 1.0815, ts=60.0),
        _c(1.0815, 1.0830, 1.0810, 1.0825, ts=120.0),
        _c(1.0825, 1.0835, 1.0800, 1.0810, ts=180.0),
    ]
    atr = compute_atr(candles)
    assert isinstance(atr, float)
    assert atr > 0.0


def test_compute_atr_single_candle():
    """ATR with a single candle should return 0.0 (insufficient data)."""
    candles = [_c(1.0800, 1.0810, 1.0790, 1.0805)]
    atr = compute_atr(candles)
    assert atr == 0.0


# ---------------------------------------------------------------------------
# normalize_candles
# ---------------------------------------------------------------------------

def test_normalize_candles():
    """normalize_candles fills missing fields with 0.0 and converts to float."""
    raw = [
        {"open": 1.08, "close": 1.09},  # missing high, low, timestamp
        {"high": 1.10, "low": 1.07},     # missing open, close, timestamp
        {},                               # entirely empty
    ]
    normalized = normalize_candles(raw)
    assert len(normalized) == 3

    # First candle: high/low/timestamp should be 0.0
    assert normalized[0]["high"] == 0.0
    assert normalized[0]["low"] == 0.0
    assert normalized[0]["timestamp"] == 0.0
    assert normalized[0]["open"] == pytest.approx(1.08)
    assert normalized[0]["close"] == pytest.approx(1.09)

    # Second candle: open/close/timestamp should be 0.0
    assert normalized[1]["open"] == 0.0
    assert normalized[1]["close"] == 0.0

    # Third candle: all fields should be 0.0
    for key in ("open", "high", "low", "close", "timestamp"):
        assert normalized[2][key] == 0.0


def test_normalize_candles_preserves_valid():
    """normalize_candles should preserve all fields when they are already present."""
    raw = [_c(1.0800, 1.0820, 1.0790, 1.0815, ts=100.0)]
    normalized = normalize_candles(raw)
    assert normalized[0]["open"] == pytest.approx(1.0800)
    assert normalized[0]["high"] == pytest.approx(1.0820)
    assert normalized[0]["low"] == pytest.approx(1.0790)
    assert normalized[0]["close"] == pytest.approx(1.0815)
    assert normalized[0]["timestamp"] == pytest.approx(100.0)
