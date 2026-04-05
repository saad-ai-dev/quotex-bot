"""
Profile-specific scoring tests for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Tests that each scoring profile (live_1m, live_2m, live_3m, otc_1m,
otc_2m, otc_3m) produces expected behavior: sensitivity levels,
confluence requirements, OTC-vs-live differentiation, chop detection,
confidence calibration, and config loading.
"""

import os
import sys
import json
from typing import Any, Dict, List

import pytest

# Ensure backend is importable
backend_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "backend")
)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.engine.orchestrator import SignalOrchestrator
from app.engine.scoring_engine import ScoringEngine
from app.engine.profiles.live import LiveProfile, DEFAULT_LIVE_CONFIG, EXPIRY_OVERRIDES as LIVE_EXPIRY_OVERRIDES
from app.engine.profiles.otc import OTCProfile, DEFAULT_OTC_CONFIG, EXPIRY_OVERRIDES as OTC_EXPIRY_OVERRIDES

from testing.fixtures.candle_fixtures import (
    generate_uptrend,
    generate_downtrend,
    generate_range,
    generate_breakout,
    generate_reversal,
    generate_doji_heavy,
    generate_random_walk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_orchestrator(
    candles: List[Dict],
    market_type: str,
    expiry_profile: str,
) -> Dict[str, Any]:
    """Run the SignalOrchestrator synchronously and return the result.

    ALERT-ONLY: Produces analytical signal data, not trade instructions.
    """
    import asyncio

    orchestrator = SignalOrchestrator()
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            orchestrator.analyze(
                candles=candles,
                market_type=market_type,
                expiry_profile=expiry_profile,
                parse_mode="dom",
                chart_read_confidence=1.0,
            )
        )
    finally:
        loop.close()
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLive1mHighSensitivity:
    """1m profile should produce signals faster (lower candle requirement)."""

    def test_live_1m_high_sensitivity(self):
        """Verify that the live 1m profile has a lower min_ideal_candles.

        ALERT-ONLY: Profile sensitivity affects alert generation speed.
        """
        profile = LiveProfile()
        config_1m = profile.get_config("1m")
        config_3m = profile.get_config("3m")

        # 1m requires fewer candles than 3m
        assert config_1m["min_ideal_candles"] < config_3m["min_ideal_candles"]

        # 1m has a higher threshold (more aggressive filtering per candle)
        assert config_1m["direction_threshold"] >= config_3m["direction_threshold"]

    def test_live_1m_produces_signal_on_strong_trend(self):
        """Strong uptrend on 1m should produce a directional signal.

        ALERT-ONLY: Tests that clear trends generate alerts in the 1m profile.
        """
        candles = generate_uptrend(n=20, step=0.0008)
        result = _run_orchestrator(candles, "LIVE", "1m")
        # Strong uptrend should produce either UP or at least not be NO_TRADE
        # with high bullish score
        assert result["bullish_score"] >= result["bearish_score"]


class TestLive2mBalanced:
    """2m profile should be more balanced between speed and reliability."""

    def test_live_2m_balanced(self):
        """Verify 2m profile parameters are between 1m and 3m.

        ALERT-ONLY: Balanced profile for moderate alert generation.
        """
        profile = LiveProfile()
        config_1m = profile.get_config("1m")
        config_2m = profile.get_config("2m")
        config_3m = profile.get_config("3m")

        # min_ideal_candles: 1m < 2m < 3m
        assert config_1m["min_ideal_candles"] <= config_2m["min_ideal_candles"]
        assert config_2m["min_ideal_candles"] <= config_3m["min_ideal_candles"]


class TestLive3mSmoother:
    """3m profile requires stronger confluence for signal generation."""

    def test_live_3m_smoother(self):
        """Verify 3m profile has the most relaxed threshold but highest data req.

        ALERT-ONLY: Smoother profile reduces false alerts at the cost of speed.
        """
        profile = LiveProfile()
        config_3m = profile.get_config("3m")

        # 3m requires the most candles
        assert config_3m["min_ideal_candles"] >= 25

        # Lower direction_threshold = easier to call a direction once data is strong
        assert config_3m["direction_threshold"] <= 30.0

    def test_live_3m_needs_strong_data(self):
        """3m profile should penalize weak data more heavily.

        ALERT-ONLY: Ensures 3m alerts have stronger data backing.
        """
        candles = generate_uptrend(n=10)  # Only 10 candles (below min_ideal_candles)
        result = _run_orchestrator(candles, "LIVE", "3m")

        # Should have a weak_data_penalty
        penalties = result.get("penalties", {})
        assert "weak_data_penalty" in penalties or result["confidence"] < 50.0


class TestOTC1mPatternHeavy:
    """OTC 1m should weight patterns heavily."""

    def test_otc_1m_pattern_heavy(self):
        """Verify OTC 1m profile gives more weight to otc_patterns.

        ALERT-ONLY: OTC markets rely more on pattern-based analysis.
        """
        otc_profile = OTCProfile()
        config = otc_profile.get_config("1m")

        # OTC patterns should have non-zero weight
        assert config["weights"]["otc_patterns"] > 0

        # Volume proxy should have reduced weight in OTC
        live_profile = LiveProfile()
        live_config = live_profile.get_config("1m")
        assert config["weights"]["volume_proxy"] <= live_config["weights"]["volume_proxy"]


class TestOTCvsLiveSameData:
    """Same candles should produce different scores for OTC vs LIVE."""

    def test_otc_vs_live_same_data(self):
        """Feed identical candle data through OTC and LIVE profiles.

        ALERT-ONLY: Verifies that market type affects the analysis output,
        producing different alert characteristics for the same price data.
        """
        candles = generate_breakout(n=30)

        result_live = _run_orchestrator(candles, "LIVE", "1m")
        result_otc = _run_orchestrator(candles, "OTC", "1m")

        # Scores should differ because profiles weight detectors differently
        live_bull = result_live["bullish_score"]
        otc_bull = result_otc["bullish_score"]
        live_bear = result_live["bearish_score"]
        otc_bear = result_otc["bearish_score"]

        # They should not be exactly equal (different weights)
        scores_differ = (
            abs(live_bull - otc_bull) > 0.01
            or abs(live_bear - otc_bear) > 0.01
            or result_live["confidence"] != result_otc["confidence"]
        )
        assert scores_differ, "OTC and LIVE should produce different scores"


class TestNoTradeUnderChopAllProfiles:
    """Choppy data should produce NO_TRADE across all profiles."""

    def test_no_trade_under_chop_all_profiles(self):
        """Verify that highly choppy / ranging data produces NO_TRADE.

        ALERT-ONLY: Choppy markets should suppress alert generation.
        """
        # Doji-heavy candles = maximum indecision / chop
        candles = generate_doji_heavy(n=30)

        profiles = [
            ("LIVE", "1m"),
            ("LIVE", "2m"),
            ("LIVE", "3m"),
            ("OTC", "1m"),
            ("OTC", "2m"),
            ("OTC", "3m"),
        ]

        for market_type, expiry in profiles:
            result = _run_orchestrator(candles, market_type, expiry)
            # In choppy conditions, confidence should be low
            # The direction might be NO_TRADE or have very low confidence
            assert result["confidence"] < 60.0 or result["prediction_direction"] == "NO_TRADE", (
                f"{market_type}/{expiry}: Expected low confidence or NO_TRADE "
                f"on choppy data, got direction={result['prediction_direction']} "
                f"confidence={result['confidence']}"
            )


class TestConfidenceCalibration:
    """Higher-confidence signals should come from stronger setups."""

    def test_confidence_calibration(self):
        """Compare confidence between a strong trend and a weak/ranging setup.

        ALERT-ONLY: Confidence calibration ensures alert quality ranking.
        """
        strong_candles = generate_uptrend(n=30, step=0.0010)
        weak_candles = generate_range(n=30, amplitude=0.0005)

        result_strong = _run_orchestrator(strong_candles, "LIVE", "2m")
        result_weak = _run_orchestrator(weak_candles, "LIVE", "2m")

        # Strong trend should have higher confidence than ranging market
        assert result_strong["confidence"] > result_weak["confidence"], (
            f"Strong trend confidence ({result_strong['confidence']}) should "
            f"exceed weak/ranging confidence ({result_weak['confidence']})"
        )


class TestAllSixProfilesLoad:
    """Verify all 6 JSON configs (or defaults) load correctly."""

    def test_all_six_profiles_load(self):
        """Load all 6 profile configurations and verify they have required keys.

        ALERT-ONLY: Profile configs control alert generation parameters.
        """
        live_profile = LiveProfile()
        otc_profile = OTCProfile()

        required_keys = [
            "weights",
            "direction_threshold",
            "direction_margin",
            "min_ideal_candles",
        ]

        for expiry in ["1m", "2m", "3m"]:
            live_config = live_profile.get_config(expiry)
            otc_config = otc_profile.get_config(expiry)

            for key in required_keys:
                assert key in live_config, f"Missing '{key}' in live/{expiry}"
                assert key in otc_config, f"Missing '{key}' in otc/{expiry}"

            # Verify weights dict has expected detector keys
            expected_detectors = [
                "market_structure",
                "support_resistance",
                "price_action",
                "liquidity",
                "order_blocks",
                "fvg",
                "supply_demand",
                "volume_proxy",
                "otc_patterns",
            ]
            for det in expected_detectors:
                assert det in live_config["weights"], (
                    f"Missing detector '{det}' in live/{expiry} weights"
                )
                assert det in otc_config["weights"], (
                    f"Missing detector '{det}' in otc/{expiry} weights"
                )

            # OTC patterns should be active in OTC profiles
            assert otc_config["weights"]["otc_patterns"] > 0

            # OTC patterns should be inactive (0) in live profiles
            assert live_config["weights"]["otc_patterns"] == 0
