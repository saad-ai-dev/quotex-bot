"""
Profile-specific scoring tests.

ALERT-ONLY system -- tests verify that Live and OTC profiles load correctly
and produce distinct scoring behavior for different market types and expiries.
"""

import pytest
from typing import Any, Dict

from app.engine.profiles.live import LiveProfile
from app.engine.profiles.otc import OTCProfile
from app.engine.scoring_engine import ScoringEngine


# ---------------------------------------------------------------------------
# Profile loading tests
# ---------------------------------------------------------------------------

def test_live_1m_profile_loads():
    """LiveProfile().get_config('1m') returns a dict with 'weights' and thresholds."""
    config = LiveProfile().get_config("1m")
    assert isinstance(config, dict)
    assert "weights" in config
    assert isinstance(config["weights"], dict)
    # Should have a direction threshold
    assert "direction_threshold" in config


def test_live_2m_profile_loads():
    """LiveProfile().get_config('2m') returns a dict with 'weights'."""
    config = LiveProfile().get_config("2m")
    assert isinstance(config, dict)
    assert "weights" in config


def test_live_3m_profile_loads():
    """LiveProfile().get_config('3m') returns a dict with 'weights'."""
    config = LiveProfile().get_config("3m")
    assert isinstance(config, dict)
    assert "weights" in config


def test_otc_1m_profile_loads():
    """OTCProfile().get_config('1m') returns a dict with 'weights'."""
    config = OTCProfile().get_config("1m")
    assert isinstance(config, dict)
    assert "weights" in config


def test_otc_2m_profile_loads():
    """OTCProfile().get_config('2m') returns a dict with 'weights'."""
    config = OTCProfile().get_config("2m")
    assert isinstance(config, dict)
    assert "weights" in config


def test_otc_3m_profile_loads():
    """OTCProfile().get_config('3m') returns a dict with 'weights'."""
    config = OTCProfile().get_config("3m")
    assert isinstance(config, dict)
    assert "weights" in config


# ---------------------------------------------------------------------------
# Weight-specific tests
# ---------------------------------------------------------------------------

def test_otc_has_nonzero_otc_pattern_weight():
    """OTC profile must have a nonzero otc_patterns weight."""
    config = OTCProfile().get_config("1m")
    assert config["weights"].get("otc_patterns", 0) > 0


def test_live_has_zero_otc_pattern_weight():
    """LIVE profile must have zero otc_patterns weight."""
    config = LiveProfile().get_config("1m")
    assert config["weights"].get("otc_patterns", 0) == 0


# ---------------------------------------------------------------------------
# Scoring engine integration with profiles
# ---------------------------------------------------------------------------

def _make_detector_results(bull: float, bear: float) -> Dict[str, Any]:
    """Build a minimal detector_results dict with given contributions."""
    return {
        "market_structure": {
            "bullish_contribution": bull,
            "bearish_contribution": bear,
            "chop_probability": 0.3,
        },
        "support_resistance": {
            "bullish_contribution": bull,
            "bearish_contribution": bear,
        },
        "price_action": {
            "bullish_contribution": bull,
            "bearish_contribution": bear,
        },
        "liquidity": {
            "bullish_contribution": bull * 0.5,
            "bearish_contribution": bear * 0.5,
        },
        "order_blocks": {
            "bullish_contribution": bull * 0.5,
            "bearish_contribution": bear * 0.5,
        },
        "fvg": {
            "bullish_contribution": bull * 0.3,
            "bearish_contribution": bear * 0.3,
        },
        "supply_demand": {
            "bullish_contribution": bull * 0.5,
            "bearish_contribution": bear * 0.5,
        },
        "volume_proxy": {
            "bullish_contribution": bull * 0.3,
            "bearish_contribution": bear * 0.3,
        },
        "otc_patterns": {
            "bullish_contribution": bull * 0.8,
            "bearish_contribution": bear * 0.8,
        },
        "_meta": {
            "candle_count": 30,
            "parse_mode": "dom",
            "chart_read_confidence": 0.95,
        },
    }


def test_scoring_uses_profile_weights():
    """ScoringEngine with different profiles should produce different scores.
    ALERT-ONLY: verifies that profile weights affect analytical scoring.
    """
    live_config = LiveProfile().get_config("1m")
    otc_config = OTCProfile().get_config("1m")

    results = _make_detector_results(bull=7.0, bear=3.0)

    live_scores = ScoringEngine(live_config).compute_scores(results)
    otc_scores = ScoringEngine(otc_config).compute_scores(results)

    # The scores should differ because the profiles have different weights
    # (especially otc_patterns weight differs: 0 vs 12)
    assert live_scores["bullish_score"] != otc_scores["bullish_score"] or \
           live_scores["bearish_score"] != otc_scores["bearish_score"], (
        "Live and OTC profiles should produce different scores given different weights"
    )


def test_1m_vs_3m_thresholds_differ():
    """1m and 3m profiles typically have different direction thresholds.
    ALERT-ONLY: threshold differences reflect differing analytical timeframes.
    """
    live_1m = LiveProfile().get_config("1m")
    live_3m = LiveProfile().get_config("3m")

    # The direction_threshold or direction_margin should differ
    threshold_1m = live_1m.get("direction_threshold", 0)
    threshold_3m = live_3m.get("direction_threshold", 0)
    margin_1m = live_1m.get("direction_margin", 0)
    margin_3m = live_3m.get("direction_margin", 0)

    differs = (threshold_1m != threshold_3m) or (margin_1m != margin_3m)
    assert differs, (
        "1m and 3m profiles should have different direction_threshold or direction_margin"
    )
