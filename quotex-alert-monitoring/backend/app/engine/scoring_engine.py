"""
Scoring Engine - ALERT-ONLY system.
Computes bullish/bearish scores, applies penalties, and determines signal direction.
No trade execution - produces numerical scores for alert generation only.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Default weight categories and their values
DEFAULT_WEIGHTS: Dict[str, float] = {
    "market_structure": 15,
    "support_resistance": 15,
    "price_action": 20,
    "liquidity": 10,
    "order_blocks": 10,
    "fvg": 8,
    "supply_demand": 10,
    "volume_proxy": 7,
    "otc_patterns": 5,
}


class ScoringEngine:
    """Computes directional scores and confidence from detector results.

    ALERT-ONLY: Scores are informational. They indicate analytical bias,
    not trade recommendations. No execution logic exists here.
    """

    def __init__(self, profile_config: Dict[str, Any]) -> None:
        self._config = profile_config
        self._weights = profile_config.get("weights", dict(DEFAULT_WEIGHTS))
        # Support both flat keys and nested thresholds dict from JSON configs
        thresholds = profile_config.get("thresholds", {})
        self._direction_threshold = thresholds.get(
            "min_bullish",
            profile_config.get("direction_threshold", 30.0),
        )
        self._direction_margin = thresholds.get(
            "direction_margin",
            profile_config.get("direction_margin", 8.0),
        )
        self._min_confidence = thresholds.get(
            "min_confidence",
            profile_config.get("min_confidence", 50.0),
        )

    def compute_scores(self, detector_results: Dict[str, Any]) -> Dict[str, Any]:
        """Compute bullish/bearish scores, apply penalties, determine direction.

        ALERT-ONLY: Output is analytical scoring data, not trade signals.

        Args:
            detector_results: Dict mapping detector names to their result dicts.
                Each result must have 'bullish_contribution' and 'bearish_contribution'
                on a 0-10 scale. Also expects '_meta' key with candle_count,
                parse_mode, and chart_read_confidence.

        Returns:
            Dict with bullish_score, bearish_score, confidence,
            prediction_direction, and penalties breakdown.
        """
        meta = detector_results.get("_meta", {})
        candle_count = meta.get("candle_count", 0)
        chart_read_confidence = meta.get("chart_read_confidence", 1.0)

        raw_bull, raw_bear, total_weight = self._compute_raw_scores(detector_results)

        # Normalize to 0-100 scale
        if total_weight > 0:
            bullish_score = round((raw_bull / total_weight) * 100.0, 2)
            bearish_score = round((raw_bear / total_weight) * 100.0, 2)
        else:
            bullish_score = 0.0
            bearish_score = 0.0

        # Clamp to 0-100
        bullish_score = max(0.0, min(100.0, bullish_score))
        bearish_score = max(0.0, min(100.0, bearish_score))

        # Compute penalties
        agreeing_count = self._count_agreeing_detectors(
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            detector_results=detector_results,
        )

        penalties = self._compute_penalties(
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            detector_results=detector_results,
            candle_count=candle_count,
            chart_read_confidence=chart_read_confidence,
            agreeing_count=agreeing_count,
        )

        total_penalty = sum(penalties.values())

        # Confidence = directional clarity + signal strength - penalties
        dominant_score = max(bullish_score, bearish_score)
        minor_score = min(bullish_score, bearish_score)
        abs_diff = abs(bullish_score - bearish_score)

        # Directional clarity: how clearly one side dominates
        clarity = min(abs_diff / 12.0, 1.0)

        # Confidence from dominant score strength and directional clarity
        confidence = (dominant_score * 0.6) + (clarity * 35.0) - total_penalty
        confidence = round(max(0.0, min(100.0, confidence)), 2)

        # Direction determination
        direction = self._determine_direction(bullish_score, bearish_score, confidence)

        return {
            "bullish_score": bullish_score,
            "bearish_score": bearish_score,
            "confidence": confidence,
            "prediction_direction": direction,
            "penalties": penalties,
            "agreeing_count": agreeing_count,
            "score_gap": round(abs_diff, 2),
        }

    def _compute_raw_scores(
        self, detector_results: Dict[str, Any]
    ) -> tuple:
        """Extract contributions from each detector and apply profile weights.

        Returns (raw_bullish, raw_bearish, total_weight_used).
        """
        raw_bull = 0.0
        raw_bear = 0.0
        total_weight = 0.0

        for category, weight in self._weights.items():
            result = detector_results.get(category)
            if result is None or not isinstance(result, dict):
                continue
            if "error" in result:
                continue

            bull_contrib = float(result.get("bullish_contribution", 0.0))
            bear_contrib = float(result.get("bearish_contribution", 0.0))

            # Contributions are 0-10 scale, weight is the category importance
            # Weighted contribution = (contribution / 10) * weight
            raw_bull += (bull_contrib / 10.0) * weight
            raw_bear += (bear_contrib / 10.0) * weight
            total_weight += weight

        return raw_bull, raw_bear, total_weight

    def _compute_penalties(
        self,
        bullish_score: float,
        bearish_score: float,
        detector_results: Dict[str, Any],
        candle_count: int,
        chart_read_confidence: float,
        agreeing_count: int,
    ) -> Dict[str, float]:
        """Compute all penalty values that reduce confidence.

        ALERT-ONLY: Penalties reflect analytical uncertainty,
        not risk management for trades.
        """
        penalties: Dict[str, float] = {}

        # Conflict penalty: bull and bear scores too close = ambiguous
        score_diff = abs(bullish_score - bearish_score)
        if score_diff < 10.0:
            conflict_penalty = (10.0 - score_diff) * 1.0
            penalties["conflict_penalty"] = round(conflict_penalty, 2)

        # Chop penalty: choppy market = unreliable signals
        structure = detector_results.get("market_structure", {})
        chop_prob = structure.get("chop_probability", 0.5)
        if chop_prob > 0.6:
            chop_penalty = (chop_prob - 0.6) * 20.0
            penalties["chop_penalty"] = round(chop_penalty, 2)

        # Low confluence penalty: need at least 2 detectors agreeing
        if agreeing_count < 2:
            penalties["low_confluence_penalty"] = round((2 - agreeing_count) * 8.0, 2)

        # Weak data penalty
        min_ideal_candles = self._config.get("min_ideal_candles", 12)
        if candle_count < min_ideal_candles:
            ratio = candle_count / min_ideal_candles if min_ideal_candles > 0 else 0
            weak_data_penalty = (1.0 - ratio) * 12.0
            penalties["weak_data_penalty"] = round(weak_data_penalty, 2)

        # Parsing quality penalty: low chart_read_confidence
        if chart_read_confidence < 0.9:
            parsing_penalty = (0.9 - chart_read_confidence) * 30.0  # up to ~27 points
            penalties["parsing_quality_penalty"] = round(parsing_penalty, 2)

        # Timing reliability penalty: based on market type / profile settings
        timing_reliability = self._config.get("timing_reliability", 1.0)
        if timing_reliability < 1.0:
            timing_penalty = (1.0 - timing_reliability) * 15.0
            penalties["timing_reliability_penalty"] = round(timing_penalty, 2)

        return penalties

    def _count_agreeing_detectors(
        self,
        bullish_score: float,
        bearish_score: float,
        detector_results: Dict[str, Any],
    ) -> int:
        """Count detectors that clearly support the dominant side."""
        dominant_dir = "bull" if bullish_score >= bearish_score else "bear"
        agreeing_count = 0

        for cat in self._weights:
            r = detector_results.get(cat, {})
            if not isinstance(r, dict) or "error" in r:
                continue

            bull_contrib = float(r.get("bullish_contribution", 0))
            bear_contrib = float(r.get("bearish_contribution", 0))

            if dominant_dir == "bull" and bull_contrib > bear_contrib + 0.5:
                agreeing_count += 1
            elif dominant_dir == "bear" and bear_contrib > bull_contrib + 0.5:
                agreeing_count += 1

        return agreeing_count

    def _determine_direction(
        self, bullish_score: float, bearish_score: float, confidence: float
    ) -> str:
        """Determine the predicted direction from scores.

        ALERT-ONLY: Direction is an analytical prediction, not a trade instruction.
        """
        threshold = self._direction_threshold
        margin = self._direction_margin
        min_conf = self._min_confidence

        # Must pass minimum confidence gate from profile config
        if confidence < min_conf:
            return "NO_TRADE"

        if bullish_score >= threshold and bullish_score > bearish_score + margin:
            return "UP"
        elif bearish_score >= threshold and bearish_score > bullish_score + margin:
            return "DOWN"
        return "NO_TRADE"
