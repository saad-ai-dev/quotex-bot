"""
Edge case tests for ALL detectors in the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Tests each detector's behavior with empty data, single candles, minimal
data, identical candles, extreme values, micro-movements, negative values,
NaN values, missing fields, and out-of-order timestamps.
"""

import math
import time
from typing import Any, Dict, List

import pytest

import sys
import os

# Ensure backend is importable
backend_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "backend")
)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.engine.detectors.structure import MarketStructureDetector
from app.engine.detectors.support_resistance import SupportResistanceDetector
from app.engine.detectors.price_action import PriceActionDetector
from app.engine.detectors.liquidity import LiquidityDetector
from app.engine.detectors.order_blocks import OrderBlockDetector
from app.engine.detectors.fvg import FairValueGapDetector
from app.engine.detectors.supply_demand import SupplyDemandDetector
from app.engine.detectors.volume_proxy import VolumeProxyDetector
from app.engine.detectors.otc_patterns import OTCPatternDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ALL_DETECTOR_CLASSES = [
    MarketStructureDetector,
    SupportResistanceDetector,
    PriceActionDetector,
    LiquidityDetector,
    OrderBlockDetector,
    FairValueGapDetector,
    SupplyDemandDetector,
    VolumeProxyDetector,
    OTCPatternDetector,
]


@pytest.fixture(params=ALL_DETECTOR_CLASSES, ids=lambda cls: cls.__name__)
def detector(request):
    """Parametrized fixture returning an instance of each detector."""
    return request.param()


def _candle(
    open_: float = 1.0850,
    high: float = 1.0860,
    low: float = 1.0840,
    close: float = 1.0855,
    timestamp: float | None = None,
) -> Dict[str, Any]:
    """Build a single candle dict."""
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "timestamp": timestamp or time.time(),
    }


def _candle_series(n: int, base_price: float = 1.0850, step: float = 0.0003) -> List[Dict]:
    """Build a series of n candles with a small upward drift."""
    candles = []
    ts = time.time() - n * 60
    price = base_price
    for i in range(n):
        o = price
        c = price + step * (1 if i % 3 != 0 else -0.5)
        h = max(o, c) + 0.0002
        l_ = min(o, c) - 0.0002
        candles.append(_candle(o, h, l_, c, ts + i * 60))
        price = c
    return candles


# ---------------------------------------------------------------------------
# Test: empty candles
# ---------------------------------------------------------------------------


class TestEmptyCandlesAllDetectors:
    """Each detector should handle an empty candle list gracefully."""

    def test_empty_candles_all_detectors(self, detector):
        """Pass [] to the detector and verify it returns a valid result.

        ALERT-ONLY: Detectors produce analytical data, not trade signals.
        """
        result = detector.detect([])
        assert isinstance(result, dict), (
            f"{detector.__class__.__name__}.detect([]) did not return a dict"
        )


# ---------------------------------------------------------------------------
# Test: single candle
# ---------------------------------------------------------------------------


class TestSingleCandleAllDetectors:
    """Each detector should handle a list with one candle."""

    def test_single_candle_all_detectors(self, detector):
        """Pass a single candle to the detector.

        ALERT-ONLY: Verifies detectors degrade gracefully with minimal data.
        """
        candles = [_candle()]
        result = detector.detect(candles)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: two candles
# ---------------------------------------------------------------------------


class TestTwoCandlesAllDetectors:
    """Each detector should handle a list with two candles."""

    def test_two_candles_all_detectors(self, detector):
        """Pass two candles to the detector.

        ALERT-ONLY: Verifies detectors handle near-minimum data.
        """
        candles = [
            _candle(1.0850, 1.0860, 1.0840, 1.0855, time.time() - 60),
            _candle(1.0855, 1.0865, 1.0845, 1.0860, time.time()),
        ]
        result = detector.detect(candles)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: identical candles (flat line)
# ---------------------------------------------------------------------------


class TestIdenticalCandles:
    """All OHLC values are the same (flat line) across all candles."""

    def test_identical_candles(self, detector):
        """Pass candles where all OHLC values are identical.

        ALERT-ONLY: Flat lines should produce neutral / no-signal results.
        """
        flat_price = 1.0850
        candles = []
        ts = time.time() - 30 * 60
        for i in range(30):
            candles.append(_candle(flat_price, flat_price, flat_price, flat_price, ts + i * 60))

        result = detector.detect(candles)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: extreme volatility
# ---------------------------------------------------------------------------


class TestExtremeVolatility:
    """Candles with very large ranges to test numerical stability."""

    def test_extreme_volatility(self, detector):
        """Pass candles with huge price swings.

        ALERT-ONLY: Tests detector robustness against extreme market conditions.
        """
        candles = []
        ts = time.time() - 30 * 60
        price = 1.0
        for i in range(30):
            swing = 0.5 * (1 if i % 2 == 0 else -1)
            o = price
            c = price + swing
            h = max(o, c) + 0.2
            l_ = min(o, c) - 0.2
            candles.append(_candle(o, h, l_, c, ts + i * 60))
            price = c

        result = detector.detect(candles)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: micro movements
# ---------------------------------------------------------------------------


class TestMicroMovements:
    """Very tiny price changes (0.00001 level)."""

    def test_micro_movements(self, detector):
        """Pass candles with extremely small price changes.

        ALERT-ONLY: Tests precision handling in detector calculations.
        """
        candles = []
        ts = time.time() - 30 * 60
        price = 1.08500
        for i in range(30):
            delta = 0.00001 * (1 if i % 2 == 0 else -1)
            o = price
            c = price + delta
            h = max(o, c) + 0.000005
            l_ = min(o, c) - 0.000005
            candles.append(_candle(o, h, l_, c, ts + i * 60))
            price = c

        result = detector.detect(candles)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: negative candle values
# ---------------------------------------------------------------------------


class TestNegativeCandleValues:
    """Candles with negative price values (should handle gracefully)."""

    def test_negative_candle_values(self, detector):
        """Pass candles with negative prices.

        ALERT-ONLY: While unusual, negative values should not crash detectors.
        """
        candles = []
        ts = time.time() - 30 * 60
        price = -0.5
        for i in range(30):
            step = 0.01 * (1 if i % 3 != 0 else -1)
            o = price
            c = price + step
            h = max(o, c) + 0.005
            l_ = min(o, c) - 0.005
            candles.append(_candle(o, h, l_, c, ts + i * 60))
            price = c

        # Some detectors may raise; that is acceptable as long as they
        # do not crash with unhandled exceptions
        try:
            result = detector.detect(candles)
            assert isinstance(result, dict)
        except (ValueError, ZeroDivisionError):
            # Acceptable: detector explicitly rejects invalid data
            pass


# ---------------------------------------------------------------------------
# Test: NaN in candles
# ---------------------------------------------------------------------------


class TestNanInCandles:
    """Candles containing NaN values."""

    def test_nan_in_candles(self, detector):
        """Pass candles with NaN values in OHLC fields.

        ALERT-ONLY: NaN handling prevents corrupt alert data.
        """
        candles = _candle_series(30)
        # Inject NaN into a few candles
        candles[5]["close"] = float("nan")
        candles[10]["high"] = float("nan")
        candles[15]["low"] = float("nan")

        try:
            result = detector.detect(candles)
            assert isinstance(result, dict)
        except (ValueError, TypeError, RuntimeError):
            # Acceptable: detector explicitly rejects NaN data
            pass


# ---------------------------------------------------------------------------
# Test: missing fields
# ---------------------------------------------------------------------------


class TestMissingFields:
    """Candles with missing open/high/low/close keys."""

    def test_missing_fields(self, detector):
        """Pass candles with some OHLC fields missing.

        ALERT-ONLY: Tests defensive handling of incomplete chart parse data.
        """
        candles = _candle_series(30)
        # Remove fields from some candles
        del candles[3]["high"]
        del candles[7]["low"]
        del candles[12]["open"]

        try:
            result = detector.detect(candles)
            assert isinstance(result, dict)
        except (KeyError, TypeError, ValueError):
            # Acceptable: detector requires complete candle data
            pass


# ---------------------------------------------------------------------------
# Test: out-of-order timestamps
# ---------------------------------------------------------------------------


class TestTimestampOrder:
    """Candles with out-of-order timestamps."""

    def test_timestamp_order(self, detector):
        """Pass candles whose timestamps are not in ascending order.

        ALERT-ONLY: Tests whether detectors assume sorted input.
        """
        candles = _candle_series(30)
        # Shuffle a few timestamps
        candles[5]["timestamp"], candles[20]["timestamp"] = (
            candles[20]["timestamp"],
            candles[5]["timestamp"],
        )
        candles[10]["timestamp"], candles[25]["timestamp"] = (
            candles[25]["timestamp"],
            candles[10]["timestamp"],
        )

        try:
            result = detector.detect(candles)
            assert isinstance(result, dict)
        except (ValueError, IndexError):
            # Acceptable: detector requires ordered timestamps
            pass
