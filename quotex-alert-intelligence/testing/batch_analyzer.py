"""
Batch analysis and failure analysis for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Provides tools to compute aggregate metrics over batches of alert signals,
categorize failures into 17 categories, group by failure category, rank by
frequency, generate improvement recommendations, compare before/after batches,
and export results as JSON and Markdown.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Failure categories (17 total)
# ---------------------------------------------------------------------------

FAILURE_CATEGORIES = [
    "parsing_error",
    "wrong_market_detection",
    "weak_sr",
    "false_price_action",
    "false_liquidity",
    "weak_ob",
    "incorrect_fvg",
    "weak_sd",
    "otc_overfit",
    "live_overfit",
    "threshold_loose",
    "threshold_strict",
    "timing_late",
    "chop_alert",
    "high_conf_false_positive",
    "profile_mismatch",
    "eval_bug",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FailureAnalysis:
    """Analysis of a single failed (LOSS) signal.

    ALERT-ONLY: Describes why an alert prediction was incorrect.
    """

    signal_id: str
    category: str
    direction: str = ""
    confidence: float = 0.0
    market_type: str = ""
    expiry_profile: str = ""
    reasons: List[str] = field(default_factory=list)
    detected_features: Dict[str, Any] = field(default_factory=dict)
    explanation: str = ""


@dataclass
class BatchAnalysis:
    """Complete analysis of a batch of signals.

    ALERT-ONLY: Aggregated metrics for a batch of alert predictions.
    """

    total: int = 0
    wins: int = 0
    losses: int = 0
    neutral: int = 0
    unknown: int = 0
    no_trade: int = 0
    win_rate: float = 0.0
    precision_up: float = 0.0
    precision_down: float = 0.0
    no_trade_rate: float = 0.0
    avg_confidence: float = 0.0
    confidence_calibration: Dict[str, float] = field(default_factory=dict)
    live_metrics: Dict[str, Any] = field(default_factory=dict)
    otc_metrics: Dict[str, Any] = field(default_factory=dict)
    expiry_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    failure_analyses: List[FailureAnalysis] = field(default_factory=list)
    failure_groups: Dict[str, List[FailureAnalysis]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------


class BatchAnalyzer:
    """Analyzes batches of alert signals for performance and failure patterns.

    ALERT-ONLY: All analysis is about alert prediction accuracy,
    not trade profitability. No trade execution or simulation occurs.

    Capabilities:
        - Compute all core metrics (win_rate, up/down precision, no_trade_rate,
          avg_confidence, confidence_calibration, live_vs_otc, expiry breakdown)
        - Categorize failures into 17 defined categories
        - Group failures and rank by frequency
        - Generate improvement recommendations from failure analysis
        - Compare two batches (before/after) to measure improvement
        - Export results as JSON and Markdown
    """

    def analyze(self, signals: List[Dict[str, Any]]) -> BatchAnalysis:
        """Run full batch analysis on a list of signal records.

        ALERT-ONLY: Evaluates alert quality metrics.

        Args:
            signals: List of signal dicts, each containing at minimum:
                signal_id, direction (or prediction_direction), confidence,
                outcome, market_type, expiry_profile.

        Returns:
            BatchAnalysis with all computed metrics and failure analyses.
        """
        analysis = BatchAnalysis()
        metrics = self.compute_metrics(signals)

        analysis.total = metrics["total"]
        analysis.wins = metrics["wins"]
        analysis.losses = metrics["losses"]
        analysis.neutral = metrics["neutral"]
        analysis.unknown = metrics["unknown"]
        analysis.no_trade = metrics["no_trade"]
        analysis.win_rate = metrics["win_rate"]
        analysis.precision_up = metrics["precision_up"]
        analysis.precision_down = metrics["precision_down"]
        analysis.no_trade_rate = metrics["no_trade_rate"]
        analysis.avg_confidence = metrics["avg_confidence"]
        analysis.confidence_calibration = metrics["confidence_calibration"]
        analysis.live_metrics = metrics["live_metrics"]
        analysis.otc_metrics = metrics["otc_metrics"]
        analysis.expiry_breakdown = metrics["expiry_breakdown"]

        # Analyze failures
        loss_signals = [s for s in signals if s.get("outcome") == "LOSS"]
        analysis.failure_analyses = self.analyze_failures(loss_signals)
        analysis.failure_groups = self.group_by_category(analysis.failure_analyses)

        return analysis

    def compute_metrics(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute aggregate performance metrics over a batch of signals.

        ALERT-ONLY: Metrics measure alert prediction accuracy across
        all dimensions: direction, confidence calibration, market type,
        and expiry profile breakdown.

        Args:
            signals: List of signal dicts.

        Returns:
            Dict with total, wins, losses, neutral, unknown, no_trade,
            win_rate, precision_up, precision_down, no_trade_rate,
            avg_confidence, confidence_calibration, live_metrics,
            otc_metrics, and expiry_breakdown.
        """
        total = len(signals)
        if total == 0:
            return {
                "total": 0, "wins": 0, "losses": 0, "neutral": 0,
                "unknown": 0, "no_trade": 0, "win_rate": 0.0,
                "precision_up": 0.0, "precision_down": 0.0,
                "no_trade_rate": 0.0, "avg_confidence": 0.0,
                "confidence_calibration": {},
                "live_metrics": {}, "otc_metrics": {},
                "expiry_breakdown": {},
            }

        wins = sum(1 for s in signals if s.get("outcome") == "WIN")
        losses = sum(1 for s in signals if s.get("outcome") == "LOSS")
        neutral = sum(1 for s in signals if s.get("outcome") == "NEUTRAL")
        unknown = sum(
            1 for s in signals if s.get("outcome") in ("UNKNOWN", None)
        )
        # Use both "direction" and "prediction_direction" keys for compatibility
        no_trade = sum(
            1 for s in signals
            if self._get_direction(s) == "NO_TRADE"
        )

        evaluated = wins + losses
        win_rate = round((wins / evaluated) * 100, 2) if evaluated > 0 else 0.0

        # Precision per direction
        up_signals = [s for s in signals if self._get_direction(s) == "UP"]
        up_wins = sum(1 for s in up_signals if s.get("outcome") == "WIN")
        precision_up = (
            round((up_wins / len(up_signals)) * 100, 2) if up_signals else 0.0
        )

        down_signals = [s for s in signals if self._get_direction(s) == "DOWN"]
        down_wins = sum(1 for s in down_signals if s.get("outcome") == "WIN")
        precision_down = (
            round((down_wins / len(down_signals)) * 100, 2) if down_signals else 0.0
        )

        no_trade_rate = round((no_trade / total) * 100, 2)

        # Average confidence
        confidences = [
            float(s.get("confidence", 0))
            for s in signals
            if s.get("confidence") is not None
        ]
        avg_confidence = (
            round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        )

        # Confidence calibration
        confidence_calibration = self._compute_calibration(signals)

        # Market type breakdown
        live_signals = [s for s in signals if s.get("market_type") == "LIVE"]
        otc_signals = [s for s in signals if s.get("market_type") == "OTC"]
        live_metrics = self._compute_subset_metrics(live_signals)
        otc_metrics = self._compute_subset_metrics(otc_signals)

        # Expiry profile breakdown
        expiry_breakdown = {}
        expiry_profiles = set(
            s.get("expiry_profile", "unknown") for s in signals
        )
        for ep in expiry_profiles:
            ep_signals = [
                s for s in signals if s.get("expiry_profile") == ep
            ]
            expiry_breakdown[ep] = self._compute_subset_metrics(ep_signals)

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "neutral": neutral,
            "unknown": unknown,
            "no_trade": no_trade,
            "win_rate": win_rate,
            "precision_up": precision_up,
            "precision_down": precision_down,
            "no_trade_rate": no_trade_rate,
            "avg_confidence": avg_confidence,
            "confidence_calibration": confidence_calibration,
            "live_metrics": live_metrics,
            "otc_metrics": otc_metrics,
            "expiry_breakdown": expiry_breakdown,
        }

    def _get_direction(self, signal: Dict[str, Any]) -> str:
        """Extract direction from a signal dict, supporting both key names."""
        return signal.get("direction", signal.get("prediction_direction", "NO_TRADE"))

    def _compute_subset_metrics(
        self, signals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute metrics for a subset of signals (market type or expiry)."""
        total = len(signals)
        if total == 0:
            return {
                "total": 0, "wins": 0, "losses": 0, "no_trade": 0,
                "win_rate": 0.0, "avg_confidence": 0.0,
            }
        wins = sum(1 for s in signals if s.get("outcome") == "WIN")
        losses = sum(1 for s in signals if s.get("outcome") == "LOSS")
        no_trade = sum(
            1 for s in signals if self._get_direction(s) == "NO_TRADE"
        )
        evaluated = wins + losses
        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "no_trade": no_trade,
            "win_rate": round(wins / evaluated * 100, 2) if evaluated > 0 else 0.0,
            "avg_confidence": round(
                sum(float(s.get("confidence", 0)) for s in signals) / total, 2
            ),
        }

    def _compute_calibration(
        self, signals: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute calibration: actual win rate per confidence bucket.

        ALERT-ONLY: Calibration checks if 80% confidence signals win ~80%.

        Returns dict mapping bucket labels to actual win rates.
        """
        buckets = {
            "50-60": (50, 60),
            "60-70": (60, 70),
            "70-80": (70, 80),
            "80-90": (80, 90),
            "90-100": (90, 100),
        }

        calibration = {}
        for label, (low, high) in buckets.items():
            bucket_signals = [
                s for s in signals
                if low <= float(s.get("confidence", 0)) < high
                and self._get_direction(s) != "NO_TRADE"
            ]
            if not bucket_signals:
                continue
            bucket_wins = sum(
                1 for s in bucket_signals if s.get("outcome") == "WIN"
            )
            bucket_evaluated = sum(
                1 for s in bucket_signals
                if s.get("outcome") in ("WIN", "LOSS")
            )
            if bucket_evaluated > 0:
                calibration[label] = round(
                    (bucket_wins / bucket_evaluated) * 100, 2
                )

        return calibration

    def analyze_failures(
        self, losses: List[Dict[str, Any]]
    ) -> List[FailureAnalysis]:
        """Categorize each loss signal into one of 17 failure categories.

        ALERT-ONLY: Failure analysis identifies why alerts were incorrect.

        Args:
            losses: List of signal dicts with outcome == "LOSS".

        Returns:
            List of FailureAnalysis objects.
        """
        analyses = []
        for sig in losses:
            category = self.categorize_failure(sig)
            fa = FailureAnalysis(
                signal_id=sig.get("signal_id", "unknown"),
                category=category,
                direction=self._get_direction(sig),
                confidence=float(sig.get("confidence", 0)),
                market_type=sig.get("market_type", ""),
                expiry_profile=sig.get("expiry_profile", ""),
                reasons=sig.get("reasons", []),
                detected_features=sig.get("detected_features", {}),
                explanation=self._explain_failure(category, sig),
            )
            analyses.append(fa)
        return analyses

    def categorize_failure(self, signal: Dict[str, Any]) -> str:
        """Determine the failure category for a single loss signal.

        ALERT-ONLY: Categorizes why the alert prediction was wrong.
        Uses the 17 defined failure categories.

        Args:
            signal: Signal dict with all metadata.

        Returns:
            Category string from FAILURE_CATEGORIES.
        """
        confidence = float(signal.get("confidence", 0))
        market_type = signal.get("market_type", "")
        reasons = signal.get("reasons", [])
        reasons_text = " ".join(reasons).lower()
        features = signal.get("detected_features", {})
        parse_confidence = float(
            signal.get(
                "chart_read_confidence",
                signal.get("parse_confidence", 1.0),
            )
        )

        # 1. Parsing issues
        if parse_confidence < 0.6:
            return "parsing_error"

        # 2. Chop detection
        chop_prob = features.get("chop_probability", 0.5)
        if chop_prob > 0.7 or "chop" in reasons_text:
            return "chop_alert"

        # 3. High-confidence false positive
        if confidence > 85:
            return "high_conf_false_positive"

        # 4. Evaluation logic error (outcome contradicts clear data)
        if signal.get("outcome") == "LOSS" and confidence == 0:
            return "eval_bug"

        # 5. Market-specific failures
        if market_type == "OTC":
            otc_count = features.get("otc_pattern_count", 0)
            pa_count = features.get("price_action_pattern_count", 0)
            if otc_count > 0 and pa_count == 0:
                return "otc_overfit"

        # 6. Wrong market detection
        direction = self._get_direction(signal)
        if market_type == "OTC" and "otc" not in reasons_text:
            return "wrong_market_detection"

        # 7. Feature-specific failures
        if features.get("has_nearby_support") and features.get("has_nearby_resistance"):
            return "weak_sr"

        if features.get("price_action_pattern_count", 0) > 2:
            return "false_price_action"

        if (
            features.get("stop_hunt_detected")
            or features.get("liquidity_above")
            or features.get("liquidity_below")
        ):
            return "false_liquidity"

        if features.get("active_order_block_count", 0) > 0:
            return "weak_ob"

        if features.get("active_fvg_count", 0) > 0:
            return "incorrect_fvg"

        if features.get("has_nearby_demand") or features.get("has_nearby_supply"):
            return "weak_sd"

        # 8. Threshold issues
        if confidence < 55:
            return "threshold_loose"

        # 9. Threshold too strict (borderline confidence, wrong direction)
        if 55 <= confidence <= 65:
            return "threshold_strict"

        # 10. Timing
        if "timing" in reasons_text or "late" in reasons_text:
            return "timing_late"

        # 11. Profile mismatch
        if market_type == "LIVE" and "otc" in reasons_text:
            return "profile_mismatch"

        # 12. Fallback
        if market_type == "LIVE":
            return "live_overfit"
        return "profile_mismatch"

    def _explain_failure(
        self, category: str, signal: Dict[str, Any]
    ) -> str:
        """Generate a human-readable explanation for the failure category."""
        explanations = {
            "parsing_error": "Chart data parsing was unreliable, leading to incorrect candle data.",
            "wrong_market_detection": "The market type was not correctly identified.",
            "weak_sr": "Support/resistance levels were too weak or contested to provide directional edge.",
            "false_price_action": "Detected price action pattern was a false signal.",
            "false_liquidity": "Liquidity detection was misleading; sweep did not lead to expected reversal.",
            "weak_ob": "Order block was not respected by price action.",
            "incorrect_fvg": "Fair value gap was filled before the predicted move occurred.",
            "weak_sd": "Supply/demand zone did not hold as expected.",
            "otc_overfit": "OTC-specific pattern matching was over-fitted to historical patterns.",
            "live_overfit": "Live market model assumptions did not hold.",
            "threshold_loose": "Low confidence signal was generated when threshold should have filtered it.",
            "threshold_strict": "Threshold classification led to incorrect direction assignment.",
            "timing_late": "Signal was generated too late relative to the actual price move.",
            "chop_alert": "Signal was generated during choppy/ranging conditions.",
            "high_conf_false_positive": "High confidence signal was incorrect; model was overconfident.",
            "profile_mismatch": "The applied profile did not match market conditions.",
            "eval_bug": "The evaluation logic produced an incorrect outcome classification.",
        }
        base = explanations.get(category, "Unknown failure category.")
        return (
            f"{base} (confidence: {signal.get('confidence', 'N/A')}, "
            f"market: {signal.get('market_type', 'N/A')})"
        )

    def group_by_category(
        self, failures: List[FailureAnalysis]
    ) -> Dict[str, List[FailureAnalysis]]:
        """Group failure analyses by their category, sorted by frequency.

        ALERT-ONLY: Groups alert failures for pattern identification.

        Args:
            failures: List of FailureAnalysis objects.

        Returns:
            Dict mapping category strings to lists of FailureAnalysis,
            ordered by frequency (most frequent first).
        """
        groups: Dict[str, List[FailureAnalysis]] = {}
        for fa in failures:
            groups.setdefault(fa.category, []).append(fa)
        # Sort by frequency (most common first)
        return dict(sorted(groups.items(), key=lambda kv: -len(kv[1])))

    def rank_failure_categories(
        self, failure_groups: Dict[str, List[FailureAnalysis]]
    ) -> List[Dict[str, Any]]:
        """Rank failure categories by frequency and impact.

        ALERT-ONLY: Identifies the most impactful failure modes.

        Args:
            failure_groups: Dict from group_by_category.

        Returns:
            List of dicts with category, count, percentage, and avg_confidence,
            sorted by count descending.
        """
        total_failures = sum(len(v) for v in failure_groups.values())
        ranked = []
        for cat, items in sorted(
            failure_groups.items(), key=lambda kv: -len(kv[1])
        ):
            ranked.append({
                "category": cat,
                "count": len(items),
                "percentage": round(
                    len(items) / total_failures * 100, 2
                ) if total_failures > 0 else 0.0,
                "avg_confidence": round(
                    sum(fa.confidence for fa in items) / len(items), 2
                ) if items else 0.0,
                "affected_markets": list(set(fa.market_type for fa in items)),
                "affected_expiries": list(set(fa.expiry_profile for fa in items)),
            })
        return ranked

    def generate_failure_report(
        self, failures: List[FailureAnalysis]
    ) -> Dict[str, Any]:
        """Generate a structured failure report.

        ALERT-ONLY: Report details why alerts were incorrect.

        Args:
            failures: List of FailureAnalysis objects.

        Returns:
            Dict with category counts, details, and summary statistics.
        """
        groups = self.group_by_category(failures)

        category_summary = {}
        for cat, items in groups.items():
            category_summary[cat] = {
                "count": len(items),
                "avg_confidence": round(
                    sum(fa.confidence for fa in items) / len(items), 2
                ) if items else 0.0,
                "market_types": list(set(fa.market_type for fa in items)),
                "expiry_profiles": list(set(fa.expiry_profile for fa in items)),
            }

        return {
            "total_failures": len(failures),
            "category_count": len(groups),
            "categories": category_summary,
            "top_failure_category": (
                max(groups, key=lambda k: len(groups[k])) if groups else "none"
            ),
            "ranked_categories": self.rank_failure_categories(groups),
            "details": [
                {
                    "signal_id": fa.signal_id,
                    "category": fa.category,
                    "direction": fa.direction,
                    "confidence": fa.confidence,
                    "market_type": fa.market_type,
                    "expiry_profile": fa.expiry_profile,
                    "explanation": fa.explanation,
                }
                for fa in failures
            ],
        }

    def generate_improvement_recommendations(
        self, failure_groups: Dict[str, List[FailureAnalysis]]
    ) -> List[Dict[str, Any]]:
        """Generate actionable improvement recommendations based on failures.

        ALERT-ONLY: Recommendations improve alert accuracy, not trade outcomes.

        Args:
            failure_groups: Dict from group_by_category.

        Returns:
            List of recommendation dicts with category, action, priority,
            details, config_changes, and affected information.
        """
        recommendations = []

        recommendation_map = {
            "parsing_error": {
                "action": "Improve chart parsing reliability",
                "details": (
                    "Review DOM/canvas/screenshot parsing confidence thresholds. "
                    "Consider adding validation layers before feeding data to detectors."
                ),
                "priority": "HIGH",
                "config_changes": [
                    {"key": "penalties.parsing_quality_weight", "change": "increase", "value": 0.2},
                ],
            },
            "chop_alert": {
                "action": "Increase chop detection sensitivity",
                "details": (
                    "Raise the chop_probability threshold for NO_TRADE filtering. "
                    "Consider adding additional choppy market indicators."
                ),
                "priority": "HIGH",
                "config_changes": [
                    {"key": "penalties.chop_weight", "change": "increase", "value": 0.3},
                ],
            },
            "high_conf_false_positive": {
                "action": "Recalibrate confidence scoring",
                "details": (
                    "Review the confidence calculation formula. High-confidence signals "
                    "should not be wrong frequently. Add additional validation layers."
                ),
                "priority": "CRITICAL",
                "config_changes": [
                    {"key": "penalties.conflict_weight", "change": "increase", "value": 0.3},
                    {"key": "thresholds.min_confidence", "change": "increase", "value": 2},
                ],
            },
            "weak_sr": {
                "action": "Strengthen support/resistance validation",
                "details": (
                    "Require more touch points for S/R zones. Increase minimum "
                    "zone strength before contributing to directional score."
                ),
                "priority": "MEDIUM",
                "config_changes": [
                    {"key": "weights.support_resistance", "change": "decrease", "value": 2},
                ],
            },
            "false_price_action": {
                "action": "Tighten price action pattern thresholds",
                "details": (
                    "Increase minimum strength requirement for candlestick patterns. "
                    "Add context validation (trend alignment, volume confirmation)."
                ),
                "priority": "MEDIUM",
                "config_changes": [
                    {"key": "weights.price_action", "change": "decrease", "value": 3},
                ],
            },
            "false_liquidity": {
                "action": "Refine liquidity detection logic",
                "details": (
                    "Add validation for liquidity sweeps: require reclaim confirmation "
                    "and momentum shift before scoring."
                ),
                "priority": "MEDIUM",
                "config_changes": [
                    {"key": "weights.liquidity", "change": "decrease", "value": 2},
                ],
            },
            "weak_ob": {
                "action": "Improve order block validation",
                "details": (
                    "Require stronger displacement after the OB candle. "
                    "Add invalidation check for price trading through the OB zone."
                ),
                "priority": "LOW",
                "config_changes": [
                    {"key": "weights.order_blocks", "change": "decrease", "value": 1},
                ],
            },
            "incorrect_fvg": {
                "action": "Refine FVG fill and reaction detection",
                "details": (
                    "Track FVG fill status more accurately. Only score FVGs "
                    "that are recently formed and have not been partially filled."
                ),
                "priority": "LOW",
                "config_changes": [
                    {"key": "weights.fvg", "change": "decrease", "value": 1},
                ],
            },
            "weak_sd": {
                "action": "Strengthen supply/demand zone scoring",
                "details": (
                    "Increase the minimum zone score required for contribution. "
                    "Add freshness decay for older zones."
                ),
                "priority": "LOW",
                "config_changes": [
                    {"key": "weights.supply_demand", "change": "decrease", "value": 1},
                ],
            },
            "otc_overfit": {
                "action": "Reduce OTC pattern weight or add diversification",
                "details": (
                    "OTC patterns may be over-fitted. Reduce otc_patterns weight "
                    "or require confluence with other detectors."
                ),
                "priority": "HIGH",
                "config_changes": [
                    {"key": "weights.otc_patterns", "change": "decrease", "value": 2},
                ],
            },
            "live_overfit": {
                "action": "Review live market model assumptions",
                "details": (
                    "Check whether live market profile weights and thresholds "
                    "match current market conditions."
                ),
                "priority": "MEDIUM",
                "config_changes": [],
            },
            "threshold_loose": {
                "action": "Raise minimum confidence threshold",
                "details": (
                    "Too many low-confidence signals are being generated. "
                    "Increase the min_confidence or min_bullish/min_bearish."
                ),
                "priority": "HIGH",
                "config_changes": [
                    {"key": "thresholds.min_confidence", "change": "increase", "value": 3},
                    {"key": "thresholds.direction_margin", "change": "increase", "value": 2},
                ],
            },
            "threshold_strict": {
                "action": "Review threshold classification logic",
                "details": (
                    "The threshold may be incorrectly classifying directions. "
                    "Check the direction_margin parameter."
                ),
                "priority": "MEDIUM",
                "config_changes": [
                    {"key": "thresholds.direction_margin", "change": "decrease", "value": 1},
                ],
            },
            "timing_late": {
                "action": "Improve signal timing",
                "details": (
                    "Signals are arriving too late. Reduce analysis latency "
                    "or optimize the analysis pipeline."
                ),
                "priority": "HIGH",
                "config_changes": [],
            },
            "profile_mismatch": {
                "action": "Review profile selection logic",
                "details": (
                    "Ensure the correct profile is applied for the detected "
                    "market conditions."
                ),
                "priority": "MEDIUM",
                "config_changes": [],
            },
            "wrong_market_detection": {
                "action": "Improve market type detection",
                "details": (
                    "The system is not correctly identifying OTC vs LIVE markets. "
                    "Review market detection logic."
                ),
                "priority": "HIGH",
                "config_changes": [],
            },
            "eval_bug": {
                "action": "Fix evaluation logic",
                "details": (
                    "The outcome evaluation logic has a bug. "
                    "Review evaluation_service code."
                ),
                "priority": "CRITICAL",
                "config_changes": [],
            },
        }

        # Sort by count of failures (most frequent first)
        sorted_groups = sorted(
            failure_groups.items(), key=lambda kv: len(kv[1]), reverse=True
        )

        for category, failures in sorted_groups:
            rec = recommendation_map.get(category, {
                "action": f"Investigate {category} failures",
                "details": f"Review the {category} failure pattern.",
                "priority": "MEDIUM",
                "config_changes": [],
            })
            recommendations.append({
                "category": category,
                "failure_count": len(failures),
                "action": rec["action"],
                "details": rec["details"],
                "priority": rec["priority"],
                "config_changes": rec.get("config_changes", []),
                "affected_markets": list(set(fa.market_type for fa in failures)),
                "affected_expiries": list(set(fa.expiry_profile for fa in failures)),
                "avg_confidence": round(
                    sum(fa.confidence for fa in failures) / len(failures), 2
                ),
            })

        return recommendations

    def compare_batches(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare metrics between two batches (before/after improvement).

        ALERT-ONLY: Measures whether changes improved alert accuracy.

        Args:
            before: Metrics dict from compute_metrics (baseline).
            after: Metrics dict from compute_metrics (after changes).

        Returns:
            Dict with deltas and assessment for each metric.
        """
        comparison = {}
        metrics_to_compare = [
            "win_rate",
            "precision_up",
            "precision_down",
            "no_trade_rate",
            "avg_confidence",
        ]

        for metric in metrics_to_compare:
            before_val = before.get(metric, 0.0)
            after_val = after.get(metric, 0.0)
            delta = round(after_val - before_val, 2)

            if metric in ("win_rate", "precision_up", "precision_down"):
                assessment = (
                    "improved" if delta > 0
                    else "degraded" if delta < 0
                    else "unchanged"
                )
            elif metric == "no_trade_rate":
                # Higher no_trade_rate is acceptable if it reduces losses
                assessment = (
                    "more_cautious" if delta > 0
                    else "more_aggressive" if delta < 0
                    else "unchanged"
                )
            else:
                assessment = "changed" if delta != 0 else "unchanged"

            comparison[metric] = {
                "before": before_val,
                "after": after_val,
                "delta": delta,
                "assessment": assessment,
            }

        # Market-specific comparison
        for market_key in ("live_metrics", "otc_metrics"):
            bm = before.get(market_key, {})
            am = after.get(market_key, {})
            if bm and am:
                bwr = bm.get("win_rate", 0.0)
                awr = am.get("win_rate", 0.0)
                comparison[market_key] = {
                    "before_win_rate": bwr,
                    "after_win_rate": awr,
                    "delta": round(awr - bwr, 2),
                }

        # Expiry-specific comparison
        for ep in set(
            list(before.get("expiry_breakdown", {}).keys())
            + list(after.get("expiry_breakdown", {}).keys())
        ):
            bep = before.get("expiry_breakdown", {}).get(ep, {})
            aep = after.get("expiry_breakdown", {}).get(ep, {})
            if bep and aep:
                comparison[f"expiry_{ep}"] = {
                    "before_win_rate": bep.get("win_rate", 0.0),
                    "after_win_rate": aep.get("win_rate", 0.0),
                    "delta": round(
                        aep.get("win_rate", 0.0) - bep.get("win_rate", 0.0), 2
                    ),
                }

        # Overall assessment
        wr_improved = comparison.get("win_rate", {}).get("assessment") == "improved"
        no_regression = all(
            comparison.get(m, {}).get("assessment") != "degraded"
            for m in ("precision_up", "precision_down")
        )
        comparison["overall"] = (
            "improved" if wr_improved and no_regression else "needs_review"
        )

        return comparison

    def export_json(
        self,
        analysis: BatchAnalysis,
        filepath: str,
    ) -> None:
        """Export batch analysis results to a JSON file.

        ALERT-ONLY: Persists alert analysis data for review.

        Args:
            analysis: BatchAnalysis from self.analyze().
            filepath: Output file path.
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "total": analysis.total,
                "wins": analysis.wins,
                "losses": analysis.losses,
                "neutral": analysis.neutral,
                "unknown": analysis.unknown,
                "no_trade": analysis.no_trade,
                "win_rate": analysis.win_rate,
                "precision_up": analysis.precision_up,
                "precision_down": analysis.precision_down,
                "no_trade_rate": analysis.no_trade_rate,
                "avg_confidence": analysis.avg_confidence,
                "confidence_calibration": analysis.confidence_calibration,
                "live_metrics": analysis.live_metrics,
                "otc_metrics": analysis.otc_metrics,
                "expiry_breakdown": analysis.expiry_breakdown,
            },
            "failure_report": self.generate_failure_report(analysis.failure_analyses),
            "recommendations": self.generate_improvement_recommendations(
                analysis.failure_groups
            ),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("JSON report exported to %s", filepath)

    def export_markdown(
        self,
        analysis: BatchAnalysis,
        filepath: str,
    ) -> str:
        """Export batch analysis results to a Markdown file.

        ALERT-ONLY: Generates human-readable alert analysis report.

        Args:
            analysis: BatchAnalysis from self.analyze().
            filepath: Output file path.

        Returns:
            The Markdown content string.
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Batch Analysis Report",
            f"**Date:** {datetime.now(timezone.utc).isoformat()}",
            f"**Total Signals:** {analysis.total}",
            "",
            "## Summary Metrics",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Wins | {analysis.wins} |",
            f"| Losses | {analysis.losses} |",
            f"| Neutral | {analysis.neutral} |",
            f"| Unknown | {analysis.unknown} |",
            f"| No-Trade | {analysis.no_trade} |",
            f"| **Win Rate** | **{analysis.win_rate}%** |",
            f"| UP Precision | {analysis.precision_up}% |",
            f"| DOWN Precision | {analysis.precision_down}% |",
            f"| No-Trade Rate | {analysis.no_trade_rate}% |",
            f"| Avg Confidence | {analysis.avg_confidence} |",
            "",
            "## Confidence Calibration",
        ]

        for bucket, rate in sorted(analysis.confidence_calibration.items()):
            lines.append(f"- {bucket}: {rate}% actual win rate")

        lines.extend([
            "",
            "## Market Breakdown",
            f"- **LIVE:** {analysis.live_metrics}",
            f"- **OTC:** {analysis.otc_metrics}",
            "",
            "## Expiry Breakdown",
        ])
        for ep, metrics in sorted(analysis.expiry_breakdown.items()):
            lines.append(f"- **{ep}:** {metrics}")

        lines.extend(["", "## Failure Analysis"])

        ranked = self.rank_failure_categories(analysis.failure_groups)
        for item in ranked:
            lines.append(
                f"### {item['category']} ({item['count']} failures, "
                f"{item['percentage']}%, avg_conf={item['avg_confidence']})"
            )

        recommendations = self.generate_improvement_recommendations(
            analysis.failure_groups
        )
        if recommendations:
            lines.extend(["", "## Improvement Recommendations"])
            for rec in recommendations:
                lines.append(
                    f"### [{rec['priority']}] {rec['action']} "
                    f"({rec['failure_count']} failures)"
                )
                lines.append(f"  {rec['details']}")
                if rec.get("config_changes"):
                    for cc in rec["config_changes"]:
                        lines.append(
                            f"  - Config: {cc['key']} -> {cc['change']} by {cc['value']}"
                        )
                lines.append("")

        content = "\n".join(lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Markdown report exported to %s", filepath)

        return content
