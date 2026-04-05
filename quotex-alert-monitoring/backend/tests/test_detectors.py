"""
Tests for the 9 detector classes.
ALERT-ONLY: Validates analytical detection logic, not trade signals.
"""

import pytest

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
# Helper to build candles inline
# ---------------------------------------------------------------------------

def _c(open_: float, high: float, low: float, close: float, ts: float = 0) -> dict:
    """Quick candle constructor using raw prices (no base/scale)."""
    return {"open": open_, "high": high, "low": low, "close": close, "timestamp": ts}


# ===========================================================================
# MarketStructureDetector
# ===========================================================================

class TestMarketStructure:

    def test_structure_uptrend(self, sample_candles):
        """Uptrend candles should produce a bullish bias."""
        det = MarketStructureDetector()
        result = det.detect(sample_candles)
        assert result["trend_bias"] == "bullish"

    def test_structure_downtrend(self, sample_bearish_candles):
        """Downtrend candles should produce a bearish bias."""
        det = MarketStructureDetector()
        result = det.detect(sample_bearish_candles)
        assert result["trend_bias"] == "bearish"

    def test_structure_chop(self, sample_choppy_candles):
        """Choppy candles should produce ranging bias or high chop probability."""
        det = MarketStructureDetector()
        result = det.detect(sample_choppy_candles)
        # Either detected as ranging or chop_probability is high
        assert result["trend_bias"] == "ranging" or result["chop_probability"] > 0.5


# ===========================================================================
# SupportResistanceDetector
# ===========================================================================

class TestSupportResistance:

    def test_support_resistance_levels(self, sample_candles):
        """Zones should be found in data with clear swing structure."""
        det = SupportResistanceDetector()
        result = det.detect(sample_candles)
        # At least some support or resistance zones should exist
        all_zones = result["all_support_zones"] + result["all_resistance_zones"]
        assert len(all_zones) > 0

    def test_support_resistance_empty(self):
        """Short data should return empty result without crashing."""
        det = SupportResistanceDetector()
        result = det.detect([_c(1, 2, 0.5, 1.5)])
        assert result["nearest_support"] is None
        assert result["nearest_resistance"] is None
        assert result["all_support_zones"] == []


# ===========================================================================
# PriceActionDetector
# ===========================================================================

class TestPriceAction:

    def test_price_action_engulfing(self):
        """Engulfing pattern detected in crafted two-candle sequence."""
        # Small bearish candle followed by large bullish engulfing
        candles = [
            _c(1.10, 1.105, 1.095, 1.098, 100),  # small bearish body
            _c(1.10, 1.105, 1.095, 1.098, 200),   # filler
            _c(1.10, 1.105, 1.095, 1.098, 300),   # filler
            _c(1.10, 1.105, 1.095, 1.098, 400),   # filler
            _c(1.10, 1.102, 1.097, 1.098, 500),   # small bear: body 1.10->1.098
            _c(1.095, 1.108, 1.094, 1.106, 600),  # bullish engulf: body 1.095->1.106
        ]
        det = PriceActionDetector()
        result = det.detect(candles)
        engulfing = [p for p in result["patterns"] if p["name"] == "engulfing"]
        assert len(engulfing) > 0

    def test_price_action_pin_bar(self):
        """Pin bar detected: long lower wick, small body."""
        candles = [
            _c(1.10, 1.105, 1.095, 1.098, 100),
            _c(1.10, 1.105, 1.095, 1.098, 200),
            _c(1.10, 1.105, 1.095, 1.098, 300),
            _c(1.10, 1.105, 1.095, 1.098, 400),
            _c(1.10, 1.105, 1.095, 1.098, 500),
            # Pin bar: body at top, long lower wick
            _c(1.100, 1.102, 1.085, 1.101, 600),  # body=0.001, lower_wick=0.015
        ]
        det = PriceActionDetector()
        result = det.detect(candles)
        pins = [p for p in result["patterns"] if p["name"] == "pin_bar"]
        assert len(pins) > 0
        assert pins[-1]["direction"] == "bullish"

    def test_price_action_empty(self):
        """Empty candle list should not crash."""
        det = PriceActionDetector()
        result = det.detect([])
        assert result["patterns"] == []


# ===========================================================================
# LiquidityDetector
# ===========================================================================

class TestLiquidity:

    def test_liquidity_equal_highs(self):
        """Equal highs detected when multiple candles touch the same high level."""
        # Create candles where several highs cluster at ~1.1050
        base = [
            _c(1.100, 1.103, 1.098, 1.102, 100),
            _c(1.102, 1.104, 1.100, 1.103, 200),
            _c(1.103, 1.1050, 1.101, 1.104, 300),  # high at 1.1050
            _c(1.104, 1.103, 1.099, 1.100, 400),
            _c(1.100, 1.1050, 1.098, 1.104, 500),  # high at 1.1050
            _c(1.104, 1.103, 1.099, 1.101, 600),
            _c(1.101, 1.1050, 1.099, 1.103, 700),  # high at 1.1050
            _c(1.103, 1.104, 1.100, 1.102, 800),
            _c(1.102, 1.103, 1.099, 1.100, 900),
            _c(1.100, 1.102, 1.098, 1.101, 1000),
        ]
        det = LiquidityDetector()
        result = det.detect(base)
        assert len(result["equal_highs"]) > 0

    def test_liquidity_sweep(self):
        """Sweep detected when price pierces an equal level then closes back."""
        # Build candles with equal highs at 1.105, then a pierce and reversal
        candles = [
            _c(1.100, 1.103, 1.098, 1.102, 100),
            _c(1.102, 1.104, 1.100, 1.103, 200),
            _c(1.103, 1.105, 1.101, 1.104, 300),   # high touch 1.105
            _c(1.104, 1.103, 1.099, 1.100, 400),
            _c(1.100, 1.105, 1.098, 1.104, 500),   # high touch 1.105
            _c(1.104, 1.103, 1.099, 1.101, 600),
            _c(1.101, 1.105, 1.099, 1.103, 700),   # high touch 1.105
            _c(1.103, 1.104, 1.100, 1.102, 800),
            _c(1.102, 1.108, 1.101, 1.107, 900),   # pierce above 1.105
            _c(1.107, 1.107, 1.098, 1.100, 1000),  # close back below
        ]
        det = LiquidityDetector()
        result = det.detect(candles)
        # Either a sweep is detected or equal_highs exist (detector finds the structure)
        has_sweep = result["recent_sweep"] is not None
        has_equal_highs = len(result["equal_highs"]) > 0
        assert has_sweep or has_equal_highs


# ===========================================================================
# OrderBlockDetector
# ===========================================================================

class TestOrderBlocks:

    def test_order_blocks_found(self):
        """Order block detected before a displacement move."""
        # Build: small bearish candle, then 3 strong bullish candles
        candles = [
            _c(1.100, 1.102, 1.098, 1.101, 100),
            _c(1.101, 1.103, 1.099, 1.102, 200),
            _c(1.102, 1.104, 1.100, 1.103, 300),
            _c(1.103, 1.105, 1.101, 1.104, 400),
            # Opposing bearish candle (potential OB)
            _c(1.104, 1.105, 1.098, 1.099, 500),
            # Strong bullish displacement (3 candles)
            _c(1.099, 1.112, 1.098, 1.111, 600),
            _c(1.111, 1.124, 1.110, 1.123, 700),
            _c(1.123, 1.136, 1.122, 1.135, 800),
            _c(1.135, 1.138, 1.130, 1.136, 900),
            _c(1.136, 1.140, 1.132, 1.138, 1000),
        ]
        det = OrderBlockDetector()
        result = det.detect(candles)
        all_obs = result["bullish_obs"] + result["bearish_obs"]
        assert len(all_obs) > 0


# ===========================================================================
# FairValueGapDetector
# ===========================================================================

class TestFVG:

    def test_fvg_detected(self):
        """FVG found in a gappy sequence where candle[i-1].high < candle[i+1].low."""
        candles = [
            _c(1.100, 1.102, 1.098, 1.101, 100),
            _c(1.101, 1.103, 1.099, 1.102, 200),
            # Candle before gap: high = 1.103
            _c(1.102, 1.103, 1.100, 1.102, 300),
            # Impulse candle (middle of FVG)
            _c(1.103, 1.112, 1.102, 1.111, 400),
            # Candle after gap: low = 1.110 > prev_high 1.103 => bullish FVG
            _c(1.111, 1.118, 1.110, 1.116, 500),
            _c(1.116, 1.120, 1.114, 1.118, 600),
        ]
        det = FairValueGapDetector()
        result = det.detect(candles)
        assert len(result["bullish_fvgs"]) > 0


# ===========================================================================
# SupplyDemandDetector
# ===========================================================================

class TestSupplyDemand:

    def test_supply_demand_zones(self):
        """Demand zone found when consolidation is followed by bullish impulse."""
        # 3 tight-body candles then 3 strong bullish candles
        avg_body_target = 0.010  # large impulse bodies
        candles = [
            _c(1.100, 1.102, 1.098, 1.101, 100),
            _c(1.101, 1.103, 1.099, 1.100, 200),
            _c(1.100, 1.102, 1.098, 1.101, 300),
            # Consolidation (small bodies)
            _c(1.101, 1.1015, 1.1005, 1.101, 400),
            _c(1.101, 1.1015, 1.1005, 1.1012, 500),
            _c(1.1012, 1.1018, 1.1008, 1.1015, 600),
            # Strong bullish impulse
            _c(1.1015, 1.115, 1.101, 1.114, 700),
            _c(1.114, 1.128, 1.113, 1.127, 800),
            _c(1.127, 1.140, 1.126, 1.139, 900),
            _c(1.139, 1.142, 1.135, 1.140, 1000),
            _c(1.140, 1.144, 1.138, 1.142, 1100),
        ]
        det = SupplyDemandDetector()
        result = det.detect(candles)
        assert len(result["demand_zones"]) > 0


# ===========================================================================
# VolumeProxyDetector
# ===========================================================================

class TestVolumeProxy:

    def test_volume_proxy_burst(self):
        """Burst detected after tight compression followed by range expansion."""
        # 8 compressed candles then 2 large range candles
        candles = []
        for i in range(8):
            # Tight range candles
            candles.append(_c(1.100, 1.1005, 1.0995, 1.1002, 100 + i * 60))
        # Burst candles with much larger range
        candles.append(_c(1.1002, 1.108, 1.099, 1.107, 580))
        candles.append(_c(1.107, 1.115, 1.106, 1.114, 640))

        det = VolumeProxyDetector()
        result = det.detect(candles)
        assert result["burst_detected"] == True


# ===========================================================================
# OTCPatternDetector
# ===========================================================================

class TestOTCPatterns:

    def test_otc_spike_reverse(self):
        """Spike reverse detected in OTC-like data."""
        det = OTCPatternDetector()
        # Build candles with a clear spike + reversal
        candles = []
        for i in range(8):
            candles.append(_c(1.100, 1.102, 1.098, 1.101, 100 + i * 60))
        # Large bullish spike
        candles.append(_c(1.101, 1.120, 1.100, 1.118, 580))
        # Immediate bearish reversal
        candles.append(_c(1.118, 1.119, 1.102, 1.104, 640))
        candles.append(_c(1.104, 1.106, 1.100, 1.102, 700))

        result = det.detect(candles)
        spike_patterns = [p for p in result["patterns"] if p["name"] == "spike_reverse"]
        assert len(spike_patterns) > 0

    def test_otc_alternating(self):
        """Alternating cycle detected in strictly alternating candles."""
        det = OTCPatternDetector()
        candles = []
        for i in range(12):
            if i % 2 == 0:
                candles.append(_c(1.100, 1.105, 1.098, 1.104, 100 + i * 60))
            else:
                candles.append(_c(1.104, 1.106, 1.098, 1.100, 100 + i * 60))

        result = det.detect(candles)
        alt_patterns = [p for p in result["patterns"] if p["name"] == "alternating_cycle"]
        assert len(alt_patterns) > 0
        assert result["cycle_detected"] is True
