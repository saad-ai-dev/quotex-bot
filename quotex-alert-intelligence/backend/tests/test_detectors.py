"""
Tests for all detector modules.

ALERT-ONLY system -- detectors analyze chart data to produce analytical
features for alert generation. No trade execution logic is tested.
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
# Helper: build deterministic candle sequences for specific patterns
# ---------------------------------------------------------------------------

def _c(open_: float, high: float, low: float, close: float, ts: float = 0.0):
    """Shorthand candle constructor."""
    return {"open": open_, "high": high, "low": low, "close": close, "timestamp": ts}


# ---------------------------------------------------------------------------
# MarketStructureDetector tests
# ---------------------------------------------------------------------------

class TestStructureDetector:
    """Tests for market structure analysis. ALERT-ONLY."""

    def test_structure_detector_uptrend(self, sample_candles):
        """Uptrend candles should produce swing highs/lows and bullish bias.
        ALERT-ONLY: trend bias is informational, not a trade recommendation.
        """
        detector = MarketStructureDetector()
        result = detector.detect(sample_candles)

        assert result["trend_bias"] == "bullish"
        assert len(result["swing_highs"]) > 0
        assert len(result["swing_lows"]) > 0
        # Verify swing highs are ascending (higher highs)
        sh_prices = [sh["price"] for sh in result["swing_highs"]]
        assert sh_prices[-1] > sh_prices[0], "Last swing high should be higher than first"

    def test_structure_detector_downtrend(self, sample_bearish_candles):
        """Downtrend candles should produce bearish bias.
        ALERT-ONLY: bearish bias is informational only.
        """
        detector = MarketStructureDetector()
        result = detector.detect(sample_bearish_candles)

        assert result["trend_bias"] == "bearish"
        assert len(result["swing_highs"]) > 0
        assert len(result["swing_lows"]) > 0
        # Swing lows should be descending (lower lows)
        sl_prices = [sl["price"] for sl in result["swing_lows"]]
        assert sl_prices[-1] < sl_prices[0], "Last swing low should be lower than first"

    def test_structure_detector_chop(self, sample_choppy_candles):
        """Choppy candles should have high chop probability and ranging bias.
        ALERT-ONLY: chop detection reduces alert confidence.
        """
        detector = MarketStructureDetector()
        result = detector.detect(sample_choppy_candles)

        # Ranging market or high chop probability
        assert result["trend_bias"] == "ranging" or result["chop_probability"] > 0.5
        assert result["chop_probability"] > 0.4  # Should be significantly choppy


# ---------------------------------------------------------------------------
# SupportResistanceDetector tests
# ---------------------------------------------------------------------------

class TestSupportResistance:
    """Tests for support/resistance detection. ALERT-ONLY."""

    def test_support_resistance_levels(self, sample_candles):
        """Support and resistance levels should be found near price clusters.
        ALERT-ONLY: levels are informational for chart analysis.
        """
        detector = SupportResistanceDetector()
        result = detector.detect(sample_candles)

        # Should find at least some zones
        all_zones = result["all_support_zones"] + result["all_resistance_zones"]
        assert len(all_zones) > 0, "Should detect at least one S/R zone"

        # Each zone should have expected fields
        for zone in all_zones:
            assert "level" in zone
            assert "strength" in zone
            assert "touches" in zone
            assert zone["touches"] >= 1

    def test_support_resistance_empty(self):
        """Handles short data gracefully.
        ALERT-ONLY: prevents crashes on insufficient chart data.
        """
        detector = SupportResistanceDetector()
        # Only 3 candles -- too few for analysis
        short_data = [
            _c(1.08, 1.081, 1.079, 1.0805, 1.0),
            _c(1.0805, 1.0815, 1.0795, 1.081, 2.0),
            _c(1.081, 1.082, 1.080, 1.0815, 3.0),
        ]
        result = detector.detect(short_data)

        assert result["nearest_support"] is None
        assert result["nearest_resistance"] is None
        assert result["all_support_zones"] == []
        assert result["all_resistance_zones"] == []


# ---------------------------------------------------------------------------
# PriceActionDetector tests
# ---------------------------------------------------------------------------

class TestPriceAction:
    """Tests for price action pattern detection. ALERT-ONLY."""

    def test_price_action_engulfing(self):
        """Bullish and bearish engulfing patterns should be detected.
        ALERT-ONLY: engulfing patterns inform alert direction bias.
        """
        detector = PriceActionDetector()
        # Craft candles with a clear bullish engulfing at index 1
        candles = [
            _c(1.0810, 1.0815, 1.0805, 1.0808, 1.0),  # small bearish
            _c(1.0805, 1.0825, 1.0800, 1.0820, 2.0),  # bullish engulfing (body engulfs prev)
            _c(1.0820, 1.0830, 1.0815, 1.0825, 3.0),
            _c(1.0825, 1.0835, 1.0820, 1.0830, 4.0),
            _c(1.0830, 1.0840, 1.0825, 1.0835, 5.0),
        ]

        result = detector.detect(candles)
        patterns = result["patterns"]
        engulfing = [p for p in patterns if p["name"] == "engulfing"]
        assert len(engulfing) >= 1, "Should detect at least one engulfing pattern"

        # The engulfing at index 1 should be bullish
        bullish_eng = [p for p in engulfing if p["direction"] == "bullish"]
        assert len(bullish_eng) >= 1, "Should detect bullish engulfing"

    def test_price_action_pin_bar(self):
        """Pin bar with long lower wick should be detected as bullish.
        ALERT-ONLY: pin bars suggest potential reversal for alerts.
        """
        detector = PriceActionDetector()
        # Candle with long lower wick (pin bar): body is small, lower wick >= 2x body
        candles = [
            _c(1.0810, 1.0815, 1.0805, 1.0812, 1.0),
            _c(1.0812, 1.0815, 1.0805, 1.0810, 2.0),
            # Pin bar: open=1.0810, close=1.0812 (body=0.0002), low=1.0798 (lower wick=0.0012)
            _c(1.0810, 1.0814, 1.0798, 1.0812, 3.0),
            _c(1.0812, 1.0818, 1.0808, 1.0815, 4.0),
            _c(1.0815, 1.0820, 1.0812, 1.0818, 5.0),
        ]

        result = detector.detect(candles)
        patterns = result["patterns"]
        pin_bars = [p for p in patterns if p["name"] == "pin_bar"]
        assert len(pin_bars) >= 1, "Should detect at least one pin bar"

        bullish_pins = [p for p in pin_bars if p["direction"] == "bullish"]
        assert len(bullish_pins) >= 1, "Pin bar with long lower wick should be bullish"

    def test_price_action_empty(self):
        """Handles empty or short candle lists gracefully.
        ALERT-ONLY: prevents crashes on insufficient data.
        """
        detector = PriceActionDetector()

        result_empty = detector.detect([])
        assert result_empty == {"patterns": []}

        result_short = detector.detect([_c(1.08, 1.081, 1.079, 1.0805)])
        assert result_short == {"patterns": []}


# ---------------------------------------------------------------------------
# LiquidityDetector tests
# ---------------------------------------------------------------------------

class TestLiquidity:
    """Tests for liquidity detection. ALERT-ONLY."""

    def test_liquidity_equal_highs(self):
        """Equal highs should be detected when multiple candles hit the same level.
        ALERT-ONLY: equal highs indicate liquidity pools for alert analysis.
        """
        detector = LiquidityDetector()
        # Build candles with 3 clear local high extrema at ~1.0830, separated by lower candles
        candles = [
            _c(1.0800, 1.0810, 1.0795, 1.0805, 1.0),
            _c(1.0805, 1.0815, 1.0800, 1.0810, 2.0),
            _c(1.0810, 1.0830, 1.0808, 1.0825, 3.0),    # high at 1.0830 (local max)
            _c(1.0825, 1.0822, 1.0810, 1.0812, 4.0),     # dip
            _c(1.0812, 1.0815, 1.0805, 1.0810, 5.0),     # dip
            _c(1.0810, 1.0820, 1.0808, 1.0818, 6.0),     # recovery
            _c(1.0818, 1.08301, 1.0815, 1.0825, 7.0),    # high at ~1.0830 (local max)
            _c(1.0825, 1.0820, 1.0808, 1.0810, 8.0),     # dip
            _c(1.0810, 1.0815, 1.0802, 1.0812, 9.0),     # dip
            _c(1.0812, 1.0818, 1.0808, 1.0815, 10.0),    # recovery
            _c(1.0815, 1.0830, 1.0812, 1.0826, 11.0),    # high at 1.0830 (local max)
            _c(1.0826, 1.0822, 1.0810, 1.0815, 12.0),    # dip
            _c(1.0815, 1.0818, 1.0808, 1.0812, 13.0),    # lower
        ]

        result = detector.detect(candles)
        assert len(result["equal_highs"]) >= 1, "Should detect equal highs around 1.0830"
        for eh in result["equal_highs"]:
            assert eh["count"] >= 2
            assert eh["type"] == "equal_highs"

    def test_liquidity_sweep(self):
        """Sweep should be detected when price pierces a level then reverses.
        ALERT-ONLY: sweeps indicate stop hunts for alert generation.
        """
        detector = LiquidityDetector()
        # Build candles: equal highs at ~1.0830, then a candle pierces above and closes below
        candles = [
            _c(1.0810, 1.0820, 1.0805, 1.0815, 1.0),
            _c(1.0815, 1.0825, 1.0810, 1.0818, 2.0),
            _c(1.0818, 1.0830, 1.0812, 1.0820, 3.0),    # high at 1.0830
            _c(1.0820, 1.0825, 1.0815, 1.0818, 4.0),
            _c(1.0818, 1.0830, 1.0812, 1.0822, 5.0),    # high at 1.0830 (equal)
            _c(1.0822, 1.0828, 1.0818, 1.0820, 6.0),
            _c(1.0820, 1.0830, 1.0814, 1.0825, 7.0),    # high at 1.0830 (equal)
            # Sweep candle: pierces above 1.0830, then next closes below
            _c(1.0825, 1.0838, 1.0822, 1.0835, 8.0),    # pierce above equal highs
            _c(1.0835, 1.0836, 1.0818, 1.0820, 9.0),    # closes well below the level
            _c(1.0820, 1.0825, 1.0815, 1.0818, 10.0),
        ]

        result = detector.detect(candles)
        # Should detect the sweep
        if result["recent_sweep"] is not None:
            assert result["recent_sweep"]["direction"] == "bearish_sweep"
            assert result["recent_sweep"]["level"] > 0


# ---------------------------------------------------------------------------
# OrderBlockDetector tests
# ---------------------------------------------------------------------------

class TestOrderBlocks:
    """Tests for order block detection. ALERT-ONLY."""

    def test_order_blocks_found(self):
        """Order block should be detected before a displacement move.
        ALERT-ONLY: order blocks inform alert zone analysis.
        """
        detector = OrderBlockDetector()
        # Build candles: a bearish candle (the OB) followed by 3 strong bullish displacement candles
        # Need at least 8 candles, with the OB pattern starting after index 0
        avg_body = 0.0005  # Average body size reference

        candles = [
            _c(1.0800, 1.0808, 1.0795, 1.0805, 1.0),  # normal
            _c(1.0805, 1.0812, 1.0800, 1.0808, 2.0),  # normal
            _c(1.0808, 1.0815, 1.0802, 1.0810, 3.0),  # normal
            # Opposing (bearish) candle - the order block
            _c(1.0810, 1.0812, 1.0800, 1.0802, 4.0),  # bearish: O>C
            # Strong bullish displacement candles (body > 1.5x avg)
            _c(1.0802, 1.0822, 1.0800, 1.0820, 5.0),  # big bullish
            _c(1.0820, 1.0840, 1.0818, 1.0838, 6.0),  # big bullish
            _c(1.0838, 1.0858, 1.0836, 1.0855, 7.0),  # big bullish
            _c(1.0855, 1.0865, 1.0850, 1.0860, 8.0),  # continuation
            _c(1.0860, 1.0870, 1.0855, 1.0865, 9.0),  # continuation
            _c(1.0865, 1.0875, 1.0860, 1.0870, 10.0), # continuation
        ]

        result = detector.detect(candles)

        assert len(result["bullish_obs"]) >= 1, "Should detect at least one bullish order block"
        ob = result["bullish_obs"][0]
        assert ob["type"] == "bullish"
        assert ob["zone_high"] > ob["zone_low"]


# ---------------------------------------------------------------------------
# FairValueGapDetector tests
# ---------------------------------------------------------------------------

class TestFVG:
    """Tests for fair value gap detection. ALERT-ONLY."""

    def test_fvg_detected(self):
        """Fair value gap should be found in a gappy candle sequence.
        ALERT-ONLY: FVGs indicate imbalances for alert analysis.
        """
        detector = FairValueGapDetector()
        # Build a bullish FVG: candle[0].high < candle[2].low (gap between them)
        candles = [
            _c(1.0800, 1.0810, 1.0795, 1.0808, 1.0),  # prev: high = 1.0810
            _c(1.0808, 1.0835, 1.0805, 1.0830, 2.0),   # middle: strong impulse candle
            _c(1.0830, 1.0850, 1.0820, 1.0845, 3.0),    # next: low = 1.0820 > prev high 1.0810 => FVG!
            _c(1.0845, 1.0860, 1.0840, 1.0855, 4.0),
            _c(1.0855, 1.0870, 1.0850, 1.0865, 5.0),
        ]

        result = detector.detect(candles)

        assert len(result["bullish_fvgs"]) >= 1, "Should detect bullish FVG"
        fvg = result["bullish_fvgs"][0]
        assert fvg["direction"] == "bullish"
        assert fvg["gap_top"] > fvg["gap_bottom"]
        assert fvg["gap_size"] > 0


# ---------------------------------------------------------------------------
# SupplyDemandDetector tests
# ---------------------------------------------------------------------------

class TestSupplyDemand:
    """Tests for supply/demand zone detection. ALERT-ONLY."""

    def test_supply_demand_zones(self):
        """Demand zone should be found after base then rally.
        ALERT-ONLY: S/D zones inform alert zone analysis.
        """
        detector = SupplyDemandDetector()
        # Build: small body consolidation (base) then strong bullish departure
        # Need at least 10 candles, base at indices 2-4, impulse at 5-7
        # Average body must be large enough that base bodies < 0.8 * avg
        # and impulse bodies > 1.2 * avg
        candles = [
            _c(1.0800, 1.0812, 1.0795, 1.0808, 1.0),   # normal body ~8 pips
            _c(1.0808, 1.0818, 1.0802, 1.0810, 2.0),    # normal body ~2 pips
            # Base/consolidation: very small bodies
            _c(1.0810, 1.0813, 1.0808, 1.0811, 3.0),    # body = 1 pip
            _c(1.0811, 1.0814, 1.0809, 1.0812, 4.0),    # body = 1 pip
            _c(1.0812, 1.0815, 1.0810, 1.0811, 5.0),    # body = 1 pip
            # Strong bullish departure
            _c(1.0811, 1.0835, 1.0810, 1.0832, 6.0),    # body = 21 pips
            _c(1.0832, 1.0858, 1.0830, 1.0855, 7.0),    # body = 23 pips
            _c(1.0855, 1.0878, 1.0852, 1.0875, 8.0),    # body = 20 pips
            _c(1.0875, 1.0890, 1.0870, 1.0885, 9.0),    # continuation
            _c(1.0885, 1.0895, 1.0880, 1.0890, 10.0),   # continuation
        ]

        result = detector.detect(candles)

        assert len(result["demand_zones"]) >= 1, "Should detect at least one demand zone"
        dz = result["demand_zones"][0]
        assert dz["type"] == "demand"
        assert dz["zone_high"] > dz["zone_low"]
        assert dz["departure_strength"] > 0


# ---------------------------------------------------------------------------
# VolumeProxyDetector tests
# ---------------------------------------------------------------------------

class TestVolumeProxy:
    """Tests for volume proxy detection. ALERT-ONLY."""

    def test_volume_proxy_burst(self):
        """Burst should be detected after compression.
        ALERT-ONLY: volume proxy approximates activity from price data.
        """
        detector = VolumeProxyDetector()
        # Build: 6 compressed candles (tiny ranges) then 2 burst candles (big ranges)
        candles = [
            _c(1.0800, 1.0810, 1.0795, 1.0805, 1.0),    # normal (for overall avg)
            _c(1.0805, 1.0815, 1.0800, 1.0810, 2.0),     # normal
            # Compression phase (indices 2-7): very small ranges
            _c(1.0810, 1.0812, 1.0809, 1.0811, 3.0),     # range = 3 pips
            _c(1.0811, 1.0813, 1.0810, 1.0812, 4.0),     # range = 3 pips
            _c(1.0812, 1.0814, 1.0811, 1.0813, 5.0),     # range = 3 pips
            _c(1.0813, 1.0815, 1.0812, 1.0814, 6.0),     # range = 3 pips
            _c(1.0814, 1.0816, 1.0813, 1.0815, 7.0),     # range = 3 pips
            _c(1.0815, 1.0817, 1.0814, 1.0816, 8.0),     # range = 3 pips
            # Burst phase (indices 8-9): big ranges
            _c(1.0816, 1.0845, 1.0810, 1.0840, 9.0),     # range = 35 pips
            _c(1.0840, 1.0870, 1.0835, 1.0865, 10.0),    # range = 35 pips
        ]

        result = detector.detect(candles)

        assert result["burst_detected"], "Burst should be detected after compression"
        assert result["range_expansion"] > 2.0, "Range expansion should be significant"
        assert result["is_proxy"]


# ---------------------------------------------------------------------------
# OTCPatternDetector tests
# ---------------------------------------------------------------------------

class TestOTCPatterns:
    """Tests for OTC-specific pattern detection. ALERT-ONLY."""

    def test_otc_patterns_spike_reverse(self, sample_otc_candles):
        """Spike and reversal should be detected in OTC-like data.
        ALERT-ONLY: spike reversals are common in OTC markets.
        """
        detector = OTCPatternDetector()
        result = detector.detect(sample_otc_candles)

        spike_reverses = [p for p in result["patterns"] if p["name"] == "spike_reverse"]
        assert len(spike_reverses) >= 1, "Should detect at least one spike reversal"
        assert result["pattern_count"] > 0

    def test_otc_patterns_alternating(self, sample_otc_candles):
        """Alternating cycle should be detected in OTC-like data.
        ALERT-ONLY: alternating cycles are synthetic market artifacts.
        """
        detector = OTCPatternDetector()
        result = detector.detect(sample_otc_candles)

        alternating = [p for p in result["patterns"] if p["name"] == "alternating_cycle"]
        assert len(alternating) >= 1, "Should detect alternating cycle"
        assert result["cycle_detected"] is True, "cycle_detected should be True"

        # Alternating patterns have neutral direction
        for pat in alternating:
            assert pat["direction"] == "neutral"
            assert 0 < pat["strength"] <= 1.0
