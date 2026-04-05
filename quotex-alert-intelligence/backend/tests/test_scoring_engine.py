"""
Tests for the ScoringEngine class.

ALERT-ONLY system -- the scoring engine produces analytical scores and
directional predictions for alerts. No trade execution logic is tested.
"""

import pytest

from app.engine.scoring_engine import ScoringEngine, DEFAULT_WEIGHTS
from app.engine.profiles.live import DEFAULT_LIVE_CONFIG
from app.engine.profiles.otc import DEFAULT_OTC_CONFIG


# ---------------------------------------------------------------------------
# Helper to build detector results dicts
# ---------------------------------------------------------------------------

def _make_detector_results(
    bull_contributions: dict,
    bear_contributions: dict,
    candle_count: int = 30,
    chart_read_confidence: float = 1.0,
    chop_probability: float = 0.3,
):
    """Build a detector_results dict from per-category bull/bear contribution maps (0-10 scale)."""
    results = {}
    all_keys = set(bull_contributions.keys()) | set(bear_contributions.keys())
    for key in all_keys:
        results[key] = {
            "bullish_contribution": bull_contributions.get(key, 0.0),
            "bearish_contribution": bear_contributions.get(key, 0.0),
        }
    # Inject chop_probability into market_structure if present
    if "market_structure" in results:
        results["market_structure"]["chop_probability"] = chop_probability
    results["_meta"] = {
        "candle_count": candle_count,
        "chart_read_confidence": chart_read_confidence,
    }
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScoringEngineBullish:
    """Tests for bullish signal production. ALERT-ONLY."""

    def test_compute_scores_bullish(self):
        """Strong bullish contributions should produce UP direction.
        ALERT-ONLY: UP is an analytical prediction, not a buy signal.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={
                "market_structure": 8.0,
                "support_resistance": 7.0,
                "price_action": 9.0,
                "liquidity": 6.0,
                "order_blocks": 7.0,
                "fvg": 6.0,
                "supply_demand": 7.0,
                "volume_proxy": 5.0,
            },
            bear_contributions={
                "market_structure": 2.0,
                "support_resistance": 2.0,
                "price_action": 1.0,
                "liquidity": 3.0,
                "order_blocks": 2.0,
                "fvg": 2.0,
                "supply_demand": 2.0,
                "volume_proxy": 3.0,
            },
            chop_probability=0.2,
        )

        result = engine.compute_scores(detector_results)

        assert result["prediction_direction"] == "UP"
        assert result["bullish_score"] > result["bearish_score"]
        assert result["confidence"] > 0
        assert result["bullish_score"] > 50.0


class TestScoringEngineBearish:
    """Tests for bearish signal production. ALERT-ONLY."""

    def test_compute_scores_bearish(self):
        """Strong bearish contributions should produce DOWN direction.
        ALERT-ONLY: DOWN is an analytical prediction, not a sell signal.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={
                "market_structure": 2.0,
                "support_resistance": 1.0,
                "price_action": 1.0,
                "liquidity": 2.0,
                "order_blocks": 2.0,
                "fvg": 1.0,
                "supply_demand": 2.0,
                "volume_proxy": 2.0,
            },
            bear_contributions={
                "market_structure": 8.0,
                "support_resistance": 8.0,
                "price_action": 9.0,
                "liquidity": 7.0,
                "order_blocks": 8.0,
                "fvg": 7.0,
                "supply_demand": 8.0,
                "volume_proxy": 6.0,
            },
            chop_probability=0.2,
        )

        result = engine.compute_scores(detector_results)

        assert result["prediction_direction"] == "DOWN"
        assert result["bearish_score"] > result["bullish_score"]
        assert result["confidence"] > 0
        assert result["bearish_score"] > 50.0


class TestScoringEngineNoTrade:
    """Tests for NO_TRADE scenarios. ALERT-ONLY."""

    def test_compute_scores_no_trade(self):
        """Conflicting signals (close bull/bear) should produce NO_TRADE.
        ALERT-ONLY: NO_TRADE means insufficient analytical edge for an alert.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={
                "market_structure": 5.0,
                "support_resistance": 5.0,
                "price_action": 5.0,
                "liquidity": 5.0,
                "order_blocks": 5.0,
                "fvg": 5.0,
                "supply_demand": 5.0,
                "volume_proxy": 5.0,
            },
            bear_contributions={
                "market_structure": 5.0,
                "support_resistance": 5.0,
                "price_action": 5.0,
                "liquidity": 5.0,
                "order_blocks": 5.0,
                "fvg": 5.0,
                "supply_demand": 5.0,
                "volume_proxy": 5.0,
            },
            chop_probability=0.3,
        )

        result = engine.compute_scores(detector_results)

        assert result["prediction_direction"] == "NO_TRADE"


class TestScoringEnginePenalties:
    """Tests for penalty calculations. ALERT-ONLY."""

    def test_conflict_penalty_applied(self):
        """When bullish and bearish scores are close, conflict penalty reduces confidence.
        ALERT-ONLY: penalty reflects analytical uncertainty.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        engine = ScoringEngine(config)

        # Scores will be close -> conflict penalty applies
        detector_results = _make_detector_results(
            bull_contributions={
                "market_structure": 6.0,
                "support_resistance": 5.0,
                "price_action": 6.0,
                "liquidity": 5.0,
                "order_blocks": 5.0,
                "fvg": 5.0,
                "supply_demand": 5.0,
                "volume_proxy": 5.0,
            },
            bear_contributions={
                "market_structure": 5.0,
                "support_resistance": 5.5,
                "price_action": 5.0,
                "liquidity": 5.0,
                "order_blocks": 5.5,
                "fvg": 5.0,
                "supply_demand": 5.5,
                "volume_proxy": 5.0,
            },
            chop_probability=0.3,
        )

        result = engine.compute_scores(detector_results)
        assert "conflict_penalty" in result["penalties"]
        assert result["penalties"]["conflict_penalty"] > 0

    def test_chop_penalty(self):
        """High chop probability reduces confidence via chop_penalty.
        ALERT-ONLY: reflects choppy market uncertainty.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={
                "market_structure": 7.0,
                "price_action": 7.0,
            },
            bear_contributions={
                "market_structure": 3.0,
                "price_action": 3.0,
            },
            chop_probability=0.85,  # Very high chop
        )

        result = engine.compute_scores(detector_results)
        assert "chop_penalty" in result["penalties"]
        assert result["penalties"]["chop_penalty"] > 0
        # Chop penalty = (0.85 - 0.5) * 40 = 14.0
        assert result["penalties"]["chop_penalty"] == 14.0

    def test_weak_data_penalty(self):
        """Few candles trigger a weak_data_penalty.
        ALERT-ONLY: insufficient data reduces analytical confidence.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        config["min_ideal_candles"] = 20
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={"market_structure": 7.0, "price_action": 7.0},
            bear_contributions={"market_structure": 3.0, "price_action": 3.0},
            candle_count=5,  # Way below min_ideal_candles=20
        )

        result = engine.compute_scores(detector_results)
        assert "weak_data_penalty" in result["penalties"]
        assert result["penalties"]["weak_data_penalty"] > 0
        # Expected: (1.0 - 5/20) * 25 = 0.75 * 25 = 18.75
        assert result["penalties"]["weak_data_penalty"] == 18.75

    def test_parsing_quality_penalty(self):
        """Low chart_read_confidence triggers parsing_quality_penalty.
        ALERT-ONLY: low parsing quality means unreliable chart reading.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={"market_structure": 7.0, "price_action": 7.0},
            bear_contributions={"market_structure": 3.0, "price_action": 3.0},
            chart_read_confidence=0.5,  # Below 0.9 threshold
        )

        result = engine.compute_scores(detector_results)
        assert "parsing_quality_penalty" in result["penalties"]
        assert result["penalties"]["parsing_quality_penalty"] > 0
        # Expected: (0.9 - 0.5) * 30 = 12.0
        assert result["penalties"]["parsing_quality_penalty"] == 12.0


class TestScoringEngineProfiles:
    """Tests for profile weight configurations. ALERT-ONLY."""

    def test_live_profile_weights(self):
        """LIVE profile should have otc_patterns weight of 0.
        ALERT-ONLY: LIVE markets don't use OTC-specific detection.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        assert config["weights"]["otc_patterns"] == 0
        assert config["weights"]["price_action"] == 20
        assert config["weights"]["market_structure"] == 15
        assert config["timing_reliability"] == 1.0

    def test_otc_profile_weights(self):
        """OTC profile should have non-zero otc_patterns weight.
        ALERT-ONLY: OTC markets use pattern-specific detection.
        """
        config = dict(DEFAULT_OTC_CONFIG)
        assert config["weights"]["otc_patterns"] == 12
        assert config["weights"]["otc_patterns"] > 0
        # OTC has lower liquidity weight
        assert config["weights"]["liquidity"] < DEFAULT_LIVE_CONFIG["weights"]["liquidity"]
        # OTC has lower timing reliability
        assert config["timing_reliability"] < 1.0
        assert config["timing_reliability"] == 0.85


class TestScoringEngineThresholds:
    """Tests for threshold and margin behavior. ALERT-ONLY."""

    def test_threshold_behavior(self):
        """Scores below direction_threshold produce NO_TRADE.
        ALERT-ONLY: threshold guards against low-confidence alerts.
        """
        # Set a high threshold that won't be met
        config = dict(DEFAULT_LIVE_CONFIG)
        config["direction_threshold"] = 90.0
        config["direction_margin"] = 5.0
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={"market_structure": 5.0, "price_action": 5.0},
            bear_contributions={"market_structure": 2.0, "price_action": 2.0},
        )

        result = engine.compute_scores(detector_results)
        # With moderate contributions, scores won't reach 90 threshold
        assert result["prediction_direction"] == "NO_TRADE"

    def test_direction_margin(self):
        """When scores are close (within margin), direction is NO_TRADE.
        ALERT-ONLY: margin prevents alerts when edge is too thin.
        """
        config = dict(DEFAULT_LIVE_CONFIG)
        config["direction_threshold"] = 30.0
        config["direction_margin"] = 50.0  # Extremely wide margin
        engine = ScoringEngine(config)

        detector_results = _make_detector_results(
            bull_contributions={
                "market_structure": 7.0,
                "price_action": 7.0,
                "support_resistance": 7.0,
                "liquidity": 6.0,
                "order_blocks": 6.0,
                "fvg": 6.0,
                "supply_demand": 6.0,
                "volume_proxy": 5.0,
            },
            bear_contributions={
                "market_structure": 3.0,
                "price_action": 3.0,
                "support_resistance": 3.0,
                "liquidity": 4.0,
                "order_blocks": 4.0,
                "fvg": 4.0,
                "supply_demand": 4.0,
                "volume_proxy": 5.0,
            },
        )

        result = engine.compute_scores(detector_results)
        # With margin of 50, bullish must exceed bearish by 50 points
        # That's virtually impossible, so direction should be NO_TRADE
        assert result["prediction_direction"] == "NO_TRADE"
