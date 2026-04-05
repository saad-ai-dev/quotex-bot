"""
Edge case tests for all detector modules.

ALERT-ONLY system -- tests verify detectors handle degenerate inputs
without crashing and return correctly structured output dicts.
"""

import pytest
from typing import Any, Dict, List

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
# Helpers
# ---------------------------------------------------------------------------

def _c(open_: float, high: float, low: float, close: float, ts: float = 0.0) -> Dict[str, Any]:
    """Create a single candle dict."""
    return {"open": open_, "high": high, "low": low, "close": close, "timestamp": ts}


ALL_DETECTORS = [
    MarketStructureDetector(),
    SupportResistanceDetector(),
    PriceActionDetector(),
    LiquidityDetector(),
    OrderBlockDetector(),
    FairValueGapDetector(),
    SupplyDemandDetector(),
    VolumeProxyDetector(),
    OTCPatternDetector(),
]

DETECTOR_IDS = [
    "MarketStructure",
    "SupportResistance",
    "PriceAction",
    "Liquidity",
    "OrderBlock",
    "FVG",
    "SupplyDemand",
    "VolumeProxy",
    "OTCPatterns",
]


# ---------------------------------------------------------------------------
# Edge case tests for ALL detectors (parametrized)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=DETECTOR_IDS)
def test_all_detectors_handle_empty_list(detector):
    """Each detector.detect([]) should not crash and should return a dict."""
    result = detector.detect([])
    assert isinstance(result, dict)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=DETECTOR_IDS)
def test_all_detectors_handle_single_candle(detector):
    """detect([one_candle]) should not crash."""
    candles = [_c(1.0800, 1.0810, 1.0795, 1.0805, ts=1.0)]
    result = detector.detect(candles)
    assert isinstance(result, dict)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=DETECTOR_IDS)
def test_all_detectors_handle_two_candles(detector):
    """detect([c1, c2]) should not crash."""
    candles = [
        _c(1.0800, 1.0810, 1.0795, 1.0805, ts=1.0),
        _c(1.0805, 1.0815, 1.0800, 1.0812, ts=2.0),
    ]
    result = detector.detect(candles)
    assert isinstance(result, dict)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=DETECTOR_IDS)
def test_all_detectors_handle_flat_line(detector):
    """All candles with identical OHLC values should not crash."""
    candles = [_c(1.0800, 1.0800, 1.0800, 1.0800, ts=float(i)) for i in range(30)]
    result = detector.detect(candles)
    assert isinstance(result, dict)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=DETECTOR_IDS)
def test_all_detectors_handle_extreme_volatility(detector):
    """Candles with huge ranges (high - low = 100x normal) should not crash."""
    candles = []
    for i in range(30):
        base = 1.0 + i * 0.5  # large jumps
        candles.append(_c(base, base + 5.0, base - 5.0, base + 2.0, ts=float(i * 60)))
    result = detector.detect(candles)
    assert isinstance(result, dict)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=DETECTOR_IDS)
def test_all_detectors_handle_micro_movements(detector):
    """Very tiny price changes (0.00001 difference) should not crash."""
    candles = []
    base = 1.08000
    for i in range(30):
        offset = i * 0.00001
        candles.append(_c(
            base + offset,
            base + offset + 0.00001,
            base + offset - 0.00001,
            base + offset + 0.000005,
            ts=float(i * 60),
        ))
    result = detector.detect(candles)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Output structure tests for individual detectors
# ---------------------------------------------------------------------------

def _build_30_candles() -> List[Dict[str, Any]]:
    """Build 30 candles with some movement for structure testing."""
    base = 1.08000
    candles = []
    for i in range(30):
        o = base + (i % 5) * 0.0003
        h = o + 0.0005
        l = o - 0.0003
        c = o + 0.0002 if i % 2 == 0 else o - 0.0001
        candles.append(_c(o, h, l, c, ts=float(i * 60)))
    return candles


def test_structure_detector_returns_all_keys():
    """Verify MarketStructureDetector output dict has all expected keys."""
    detector = MarketStructureDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "trend_bias", "recent_bos", "recent_choch", "chop_probability",
        "swing_highs", "swing_lows", "momentum_state",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_support_resistance_returns_all_keys():
    """Verify SupportResistanceDetector output dict has all expected keys."""
    detector = SupportResistanceDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "nearest_support", "nearest_resistance",
        "all_support_zones", "all_resistance_zones",
        "support_strength", "resistance_strength",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_price_action_returns_patterns_list():
    """Verify PriceActionDetector output has 'patterns' key with a list."""
    detector = PriceActionDetector()
    result = detector.detect(_build_30_candles())
    assert "patterns" in result
    assert isinstance(result["patterns"], list)


def test_liquidity_returns_all_keys():
    """Verify LiquidityDetector output dict has all expected keys."""
    detector = LiquidityDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "liquidity_above", "liquidity_below",
        "equal_highs", "equal_lows",
        "recent_sweep", "reclaim_detected", "stop_hunt_detected",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_order_blocks_returns_all_keys():
    """Verify OrderBlockDetector output dict has all expected keys."""
    detector = OrderBlockDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "bullish_obs", "bearish_obs", "active_obs",
        "retested_obs", "invalidated_obs",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_fvg_returns_all_keys():
    """Verify FairValueGapDetector output dict has all expected keys."""
    detector = FairValueGapDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "bullish_fvgs", "bearish_fvgs", "active_fvgs",
        "current_reaction_in_fvg", "fvg_ob_overlap",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_supply_demand_returns_all_keys():
    """Verify SupplyDemandDetector output dict has all expected keys."""
    detector = SupplyDemandDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "demand_zones", "supply_zones",
        "nearest_demand", "nearest_supply",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_volume_proxy_returns_all_keys():
    """Verify VolumeProxyDetector output dict has all expected keys."""
    detector = VolumeProxyDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "proxy_volume_score", "range_expansion",
        "wick_imbalance", "velocity",
        "burst_detected", "is_proxy", "volatility_state",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_otc_patterns_returns_all_keys():
    """Verify OTCPatternDetector output dict has all expected keys."""
    detector = OTCPatternDetector()
    result = detector.detect(_build_30_candles())
    expected_keys = {
        "patterns", "pattern_count", "dominant_pattern",
        "cycle_detected", "template_match_score",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )
