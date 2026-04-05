"""
Tests for the ScoringEngine.
ALERT-ONLY: Validates analytical scoring logic, not trade decision-making.
"""

import pytest

from app.engine.scoring_engine import ScoringEngine
from app.engine.profiles.live import LiveProfile
from app.engine.profiles.otc import OTCProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detector_results(
    bull_contribs: dict,
    bear_contribs: dict,
    candle_count: int = 30,
    chart_read_confidence: float = 1.0,
    chop_probability: float = 0.3,
) -> dict:
    """Build a detector_results dict compatible with ScoringEngine.compute_scores.

    bull_contribs / bear_contribs map category -> contribution (0-10 scale).
    """
    categories = [
        "market_structure", "support_resistance", "price_action",
        "liquidity", "order_blocks", "fvg", "supply_demand",
        "volume_proxy", "otc_patterns",
    ]
    results = {}
    for cat in categories:
        results[cat] = {
            "bullish_contribution": bull_contribs.get(cat, 0.0),
            "bearish_contribution": bear_contribs.get(cat, 0.0),
        }
    # Inject chop_probability into market_structure
    results["market_structure"]["chop_probability"] = chop_probability

    results["_meta"] = {
        "candle_count": candle_count,
        "chart_read_confidence": chart_read_confidence,
    }
    return results


def _live_engine(expiry: str = "1m") -> ScoringEngine:
    config = LiveProfile().get_config(expiry)
    return ScoringEngine(config)


def _otc_engine(expiry: str = "1m") -> ScoringEngine:
    config = OTCProfile().get_config(expiry)
    return ScoringEngine(config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compute_scores_bullish():
    """High bullish contributions across detectors produce an UP direction."""
    engine = _live_engine()
    results = _make_detector_results(
        bull_contribs={
            "market_structure": 9, "support_resistance": 8, "price_action": 9,
            "liquidity": 7, "order_blocks": 8, "fvg": 7, "supply_demand": 8,
            "volume_proxy": 7,
        },
        bear_contribs={
            "market_structure": 1, "support_resistance": 2, "price_action": 1,
            "liquidity": 2, "order_blocks": 1, "fvg": 2, "supply_demand": 1,
            "volume_proxy": 2,
        },
        chop_probability=0.2,
    )
    scores = engine.compute_scores(results)
    assert scores["prediction_direction"] == "UP"
    assert scores["bullish_score"] > scores["bearish_score"]


def test_compute_scores_bearish():
    """High bearish contributions produce a DOWN direction."""
    engine = _live_engine()
    results = _make_detector_results(
        bull_contribs={
            "market_structure": 1, "support_resistance": 2, "price_action": 1,
            "liquidity": 2, "order_blocks": 1, "fvg": 2, "supply_demand": 1,
            "volume_proxy": 2,
        },
        bear_contribs={
            "market_structure": 9, "support_resistance": 8, "price_action": 9,
            "liquidity": 7, "order_blocks": 8, "fvg": 7, "supply_demand": 8,
            "volume_proxy": 7,
        },
        chop_probability=0.2,
    )
    scores = engine.compute_scores(results)
    assert scores["prediction_direction"] == "DOWN"
    assert scores["bearish_score"] > scores["bullish_score"]


def test_compute_scores_no_trade():
    """Conflicting equal signals produce NO_TRADE."""
    engine = _live_engine()
    results = _make_detector_results(
        bull_contribs={cat: 5 for cat in [
            "market_structure", "support_resistance", "price_action",
            "liquidity", "order_blocks", "fvg", "supply_demand", "volume_proxy",
        ]},
        bear_contribs={cat: 5 for cat in [
            "market_structure", "support_resistance", "price_action",
            "liquidity", "order_blocks", "fvg", "supply_demand", "volume_proxy",
        ]},
        chop_probability=0.6,
    )
    scores = engine.compute_scores(results)
    assert scores["prediction_direction"] == "NO_TRADE"


def test_conflict_penalty():
    """Close bull/bear scores trigger a conflict penalty."""
    engine = _live_engine()
    results = _make_detector_results(
        bull_contribs={cat: 5 for cat in [
            "market_structure", "support_resistance", "price_action",
            "liquidity", "order_blocks", "fvg", "supply_demand", "volume_proxy",
        ]},
        bear_contribs={cat: 4 for cat in [
            "market_structure", "support_resistance", "price_action",
            "liquidity", "order_blocks", "fvg", "supply_demand", "volume_proxy",
        ]},
        chop_probability=0.3,
    )
    scores = engine.compute_scores(results)
    assert "conflict_penalty" in scores["penalties"]
    assert scores["penalties"]["conflict_penalty"] > 0


def test_chop_penalty():
    """High chop_probability triggers a chop penalty."""
    engine = _live_engine()
    results = _make_detector_results(
        bull_contribs={"market_structure": 8, "price_action": 8},
        bear_contribs={"market_structure": 2, "price_action": 2},
        chop_probability=0.85,
    )
    scores = engine.compute_scores(results)
    assert "chop_penalty" in scores["penalties"]
    assert scores["penalties"]["chop_penalty"] > 0


def test_weak_data_penalty():
    """Too few candles trigger a weak_data_penalty."""
    engine = _live_engine("1m")  # min_ideal_candles = 15 for 1m live
    results = _make_detector_results(
        bull_contribs={"price_action": 7},
        bear_contribs={"price_action": 2},
        candle_count=5,
    )
    scores = engine.compute_scores(results)
    assert "weak_data_penalty" in scores["penalties"]
    assert scores["penalties"]["weak_data_penalty"] > 0


def test_parsing_quality_penalty():
    """Low chart_read_confidence triggers a parsing_quality_penalty."""
    engine = _live_engine()
    results = _make_detector_results(
        bull_contribs={"price_action": 7},
        bear_contribs={"price_action": 2},
        chart_read_confidence=0.5,
    )
    scores = engine.compute_scores(results)
    assert "parsing_quality_penalty" in scores["penalties"]
    assert scores["penalties"]["parsing_quality_penalty"] > 0


def test_live_profile_weights():
    """LIVE profile sets otc_patterns weight to 0."""
    config = LiveProfile().get_config("1m")
    assert config["weights"]["otc_patterns"] == 0


def test_otc_profile_weights():
    """OTC profile gives otc_patterns a positive weight."""
    config = OTCProfile().get_config("1m")
    assert config["weights"]["otc_patterns"] > 0


def test_threshold_behavior():
    """Scores below the direction threshold produce NO_TRADE."""
    engine = _live_engine("1m")
    # Give only a tiny bullish edge -- not enough to pass threshold
    results = _make_detector_results(
        bull_contribs={"price_action": 3},
        bear_contribs={"price_action": 1},
        candle_count=30,
        chop_probability=0.3,
    )
    scores = engine.compute_scores(results)
    # With most categories at 0, the normalized scores will be very low
    assert scores["prediction_direction"] == "NO_TRADE"
