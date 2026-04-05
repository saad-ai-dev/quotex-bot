"""
Historical Replay Validation Runner
ALERT-ONLY system - replays candle sequences through the signal engine
and evaluates predictions against known outcomes.
No trade execution.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

import sys

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.engine.orchestrator import SignalOrchestrator
from app.services.evaluation_service import EvaluationService


class ReplayRunner:
    """Runs historical candle sequences through the orchestrator and evaluates outcomes.

    ALERT-ONLY: This runner replays candle data through the analysis pipeline
    to validate signal predictions. No trades are placed or simulated.
    """

    def __init__(self):
        self.orchestrator = SignalOrchestrator()
        self.results: List[Dict[str, Any]] = []

    async def run_single(
        self, sequence: Dict[str, Any], expiry_profile: str = "1m"
    ) -> Dict[str, Any]:
        """Run a single candle sequence through the engine.

        ALERT-ONLY: Produces a prediction and compares against known outcome.

        Args:
            sequence: Dict with 'candles', 'market_type',
                'actual_next_candle_direction', and optional metadata.
            expiry_profile: Expiry duration string, e.g. '1m', '2m', '3m'.

        Returns:
            Signal record dict with prediction, outcome, and all metadata.
        """
        candles = sequence["candles"]
        market_type = sequence.get("market_type", "LIVE")
        actual_direction = sequence.get("actual_next_candle_direction")

        # Run orchestrator -- ALERT-ONLY analysis
        result = await self.orchestrator.analyze(
            candles=candles,
            market_type=market_type,
            expiry_profile=expiry_profile,
            parse_mode="replay",
            chart_read_confidence=95.0,  # High confidence for replay data
        )

        predicted = result.get("prediction_direction", "NO_TRADE")
        confidence = result.get("confidence", 0.0)

        # Determine outcome using the evaluation service
        if predicted == "NO_TRADE":
            outcome = "NO_TRADE"
        else:
            outcome = EvaluationService.determine_outcome(predicted, actual_direction)

        signal_record = {
            "signal_id": f"replay_{uuid.uuid4().hex[:8]}",
            "sequence_id": sequence.get("sequence_id", "unknown"),
            "pattern_type": sequence.get("pattern_type", "unknown"),
            "market_type": market_type,
            "expiry_profile": expiry_profile,
            "prediction_direction": predicted,
            "confidence": confidence,
            "bullish_score": result.get("bullish_score", 0),
            "bearish_score": result.get("bearish_score", 0),
            "reasons": result.get("reasons", []),
            "detected_features": result.get("detected_features", {}),
            "penalties": result.get("penalties", {}),
            "actual_next_candle_direction": actual_direction,
            "expected_direction": sequence.get("expected_direction", "unknown"),
            "outcome": outcome,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return signal_record

    async def run_batch(
        self, sequences: List[Dict], expiry_profile: str = "1m"
    ) -> List[Dict]:
        """Run a batch of sequences through the engine.

        ALERT-ONLY: Batch replay for validation metrics collection.

        Args:
            sequences: List of sequence dicts.
            expiry_profile: Expiry duration string.

        Returns:
            List of signal record dicts.
        """
        results = []
        for seq in sequences:
            record = await self.run_single(seq, expiry_profile)
            results.append(record)
        self.results.extend(results)
        return results

    def compute_metrics(self, results: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Compute validation metrics from results.

        ALERT-ONLY: Metrics measure alert prediction accuracy across
        multiple dimensions including direction, confidence calibration,
        and market type breakdown.

        Args:
            results: List of signal records. Defaults to internal results.

        Returns:
            Dict with comprehensive metrics breakdown.
        """
        if results is None:
            results = self.results

        total = len(results)
        if total == 0:
            return {"total": 0, "error": "no results"}

        wins = sum(1 for r in results if r["outcome"] == "WIN")
        losses = sum(1 for r in results if r["outcome"] == "LOSS")
        neutral = sum(1 for r in results if r["outcome"] == "NEUTRAL")
        unknown = sum(1 for r in results if r["outcome"] == "UNKNOWN")
        no_trade = sum(1 for r in results if r["outcome"] == "NO_TRADE")

        traded = wins + losses
        win_rate = round((wins / traded * 100), 2) if traded > 0 else 0.0

        # Per-market breakdown
        live_results = [r for r in results if r["market_type"] == "LIVE"]
        otc_results = [r for r in results if r["market_type"] == "OTC"]

        def _market_metrics(subset: List[Dict]) -> Dict[str, Any]:
            t = len(subset)
            w = sum(1 for r in subset if r["outcome"] == "WIN")
            lo = sum(1 for r in subset if r["outcome"] == "LOSS")
            nt = sum(1 for r in subset if r["outcome"] == "NO_TRADE")
            traded_s = w + lo
            return {
                "total": t,
                "wins": w,
                "losses": lo,
                "no_trade": nt,
                "win_rate": round(w / traded_s * 100, 2) if traded_s > 0 else 0.0,
                "avg_confidence": round(
                    sum(r["confidence"] for r in subset) / t, 2
                ) if t > 0 else 0.0,
            }

        # Confidence calibration buckets
        calibration = {}
        for label, low, high in [
            ("50-60", 50, 60), ("60-70", 60, 70), ("70-80", 70, 80),
            ("80-90", 80, 90), ("90-100", 90, 100),
        ]:
            bucket = [
                r for r in results
                if low <= r["confidence"] < high and r["outcome"] != "NO_TRADE"
            ]
            bucket_wins = sum(1 for r in bucket if r["outcome"] == "WIN")
            bucket_evaluated = sum(
                1 for r in bucket if r["outcome"] in ("WIN", "LOSS")
            )
            if bucket_evaluated > 0:
                calibration[label] = round(bucket_wins / bucket_evaluated * 100, 2)

        # High-confidence signals (>=70)
        high_conf = [
            r for r in results
            if r["confidence"] >= 70 and r["outcome"] != "NO_TRADE"
        ]
        high_conf_wins = sum(1 for r in high_conf if r["outcome"] == "WIN")
        high_conf_losses = sum(1 for r in high_conf if r["outcome"] == "LOSS")

        # UP vs DOWN precision
        up_alerts = [
            r for r in results
            if r["prediction_direction"] == "UP" and r["outcome"] != "NO_TRADE"
        ]
        down_alerts = [
            r for r in results
            if r["prediction_direction"] == "DOWN" and r["outcome"] != "NO_TRADE"
        ]
        up_wins = sum(1 for r in up_alerts if r["outcome"] == "WIN")
        down_wins = sum(1 for r in down_alerts if r["outcome"] == "WIN")

        # Per-expiry breakdown
        expiry_breakdown = {}
        for expiry in set(r["expiry_profile"] for r in results):
            expiry_results = [r for r in results if r["expiry_profile"] == expiry]
            expiry_breakdown[expiry] = _market_metrics(expiry_results)

        return {
            "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
            "total_alerts": total,
            "wins": wins,
            "losses": losses,
            "neutral": neutral,
            "unknown": unknown,
            "no_trade": no_trade,
            "win_rate_excluding_neutral_unknown": win_rate,
            "avg_confidence": round(
                sum(r["confidence"] for r in results) / total, 2
            ),
            "confidence_calibration": calibration,
            "high_confidence_total": len(high_conf),
            "high_confidence_wins": high_conf_wins,
            "high_confidence_losses": high_conf_losses,
            "high_confidence_win_rate": round(
                high_conf_wins / len(high_conf) * 100, 2
            ) if high_conf else 0.0,
            "up_precision": round(
                up_wins / len(up_alerts) * 100, 2
            ) if up_alerts else 0.0,
            "down_precision": round(
                down_wins / len(down_alerts) * 100, 2
            ) if down_alerts else 0.0,
            "no_trade_rate": round(no_trade / total * 100, 2),
            "live_metrics": _market_metrics(live_results),
            "otc_metrics": _market_metrics(otc_results),
            "expiry_breakdown": expiry_breakdown,
        }

    def analyze_failures(self, results: Optional[List[Dict]] = None) -> List[Dict]:
        """Categorize and analyze losing signals.

        ALERT-ONLY: Identifies root causes for incorrect alert predictions.

        Args:
            results: List of signal records. Defaults to internal results.

        Returns:
            List of failure analysis dicts.
        """
        if results is None:
            results = self.results

        losses = [r for r in results if r["outcome"] == "LOSS"]
        analysis = []

        for loss in losses:
            root_cause = self._categorize_failure(loss)
            analysis.append({
                "signal_id": loss["signal_id"],
                "sequence_id": loss.get("sequence_id"),
                "pattern_type": loss.get("pattern_type"),
                "market_type": loss["market_type"],
                "expiry_profile": loss["expiry_profile"],
                "confidence": loss["confidence"],
                "predicted": loss["prediction_direction"],
                "actual": loss["actual_next_candle_direction"],
                "reasons": loss["reasons"],
                "detected_features": loss.get("detected_features", {}),
                "root_cause": root_cause,
            })

        return analysis

    def _categorize_failure(self, loss: Dict) -> str:
        """Assign a root cause category to a losing signal.

        ALERT-ONLY: Categories help identify systematic weaknesses in
        the alert prediction pipeline.

        Categories:
            - high_confidence_false_positive: High confidence but wrong prediction.
            - alert_in_chop_conditions: Signal generated during choppy market.
            - profile_mismatch: Wrong profile applied for market conditions.
            - missing_otc_analysis: OTC market not properly analyzed.
            - weak_sr_logic: Support/resistance detection was inaccurate.
            - false_price_action: Price action pattern was misleading.
            - false_liquidity_detection: Liquidity sweep detection was wrong.
            - weak_order_block: Order block was not respected by price.
            - incorrect_fvg_reaction: FVG fill prediction was incorrect.
            - weak_supply_demand: Supply/demand zone did not hold.
            - threshold_too_loose: Low confidence signal should have been filtered.
            - timing_issue: Signal arrived too late.
            - otc_overfit: OTC pattern matching was over-fitted.
            - parsing_quality: Chart data quality was insufficient.
            - conflicting_detectors: Detectors gave contradictory signals.
            - volume_proxy_misleading: Volume proxy gave false reading.
            - unclassified: No clear root cause identified.
        """
        confidence = loss["confidence"]
        reasons = " ".join(loss.get("reasons", []))
        pattern_type = loss.get("pattern_type", "")
        market = loss["market_type"]
        features = loss.get("detected_features", {})
        penalties = loss.get("penalties", {})

        # Check parsing quality first
        parse_conf = features.get("parse_mode", "")
        if parse_conf == "screenshot" or features.get("candle_count", 30) < 10:
            return "parsing_quality"

        # High-confidence false positive is the most critical
        if confidence >= 75:
            return "high_confidence_false_positive"

        # Chop conditions
        chop_prob = features.get("chop_probability", 0.5)
        if chop_prob > 0.7 or "chop" in reasons.lower() or "range" in pattern_type:
            return "alert_in_chop_conditions"

        # Profile mismatch
        if "otc" in pattern_type and market == "LIVE":
            return "profile_mismatch"

        # OTC-specific
        if market == "OTC" and "otc" not in reasons.lower():
            return "missing_otc_analysis"

        if market == "OTC" and features.get("otc_pattern_count", 0) > 2:
            return "otc_overfit"

        # Conflicting detectors
        bull_score = loss.get("bullish_score", 0)
        bear_score = loss.get("bearish_score", 0)
        if bull_score > 30 and bear_score > 30:
            return "conflicting_detectors"

        # Feature-specific failures
        if features.get("has_nearby_support") and features.get("has_nearby_resistance"):
            if "support" in reasons.lower() or "resistance" in reasons.lower():
                return "weak_sr_logic"

        if features.get("price_action_pattern_count", 0) > 0:
            if "engulfing" in reasons.lower() or "pin" in reasons.lower() or "hammer" in reasons.lower():
                return "false_price_action"

        if features.get("stop_hunt_detected") or (
            features.get("liquidity_above") and features.get("liquidity_below")
        ):
            if "liquidity" in reasons.lower() or "sweep" in reasons.lower():
                return "false_liquidity_detection"

        if features.get("active_order_block_count", 0) > 0:
            if "order block" in reasons.lower():
                return "weak_order_block"

        if features.get("active_fvg_count", 0) > 0:
            if "fvg" in reasons.lower() or "fair value" in reasons.lower():
                return "incorrect_fvg_reaction"

        if features.get("has_nearby_demand") or features.get("has_nearby_supply"):
            if "demand" in reasons.lower() or "supply" in reasons.lower():
                return "weak_supply_demand"

        if features.get("burst_detected"):
            return "volume_proxy_misleading"

        # Threshold issues
        if confidence < 55:
            return "threshold_too_loose"

        # Timing
        if any("timing" in r.lower() or "late" in r.lower() for r in loss.get("reasons", [])):
            return "timing_issue"

        return "unclassified"

    def generate_report(self, results: Optional[List[Dict]] = None) -> str:
        """Generate a markdown validation report.

        ALERT-ONLY: Report summarizes alert prediction performance
        and failure analysis for review by developers.

        Args:
            results: List of signal records. Defaults to internal results.

        Returns:
            Markdown-formatted report string.
        """
        if results is None:
            results = self.results

        metrics = self.compute_metrics(results)
        failures = self.analyze_failures(results)

        # Group failures by category
        failure_groups: Dict[str, List[Dict]] = {}
        for f in failures:
            cat = f["root_cause"]
            failure_groups.setdefault(cat, []).append(f)

        lines = [
            "# Historical Replay Validation Report",
            f"**Date:** {datetime.now(timezone.utc).isoformat()}",
            f"**Total Alerts:** {metrics.get('total_alerts', 0)}",
            "",
            "## Summary Metrics",
            f"- Wins: {metrics.get('wins', 0)}",
            f"- Losses: {metrics.get('losses', 0)}",
            f"- Neutral: {metrics.get('neutral', 0)}",
            f"- Unknown: {metrics.get('unknown', 0)}",
            f"- No-Trade: {metrics.get('no_trade', 0)}",
            f"- **Win Rate (excl. neutral/unknown):** {metrics.get('win_rate_excluding_neutral_unknown', 0)}%",
            f"- **Avg Confidence:** {metrics.get('avg_confidence', 0)}",
            f"- **No-Trade Rate:** {metrics.get('no_trade_rate', 0)}%",
            "",
            "## Directional Precision",
            f"- UP Precision: {metrics.get('up_precision', 0)}%",
            f"- DOWN Precision: {metrics.get('down_precision', 0)}%",
            "",
            "## Confidence Calibration",
        ]

        calibration = metrics.get("confidence_calibration", {})
        for bucket, rate in sorted(calibration.items()):
            lines.append(f"- {bucket}: {rate}% win rate")

        lines.extend([
            "",
            "## High-Confidence Signals (>=70)",
            f"- Total: {metrics.get('high_confidence_total', 0)}",
            f"- Wins: {metrics.get('high_confidence_wins', 0)}",
            f"- Losses: {metrics.get('high_confidence_losses', 0)}",
            f"- Win Rate: {metrics.get('high_confidence_win_rate', 0)}%",
            "",
            "## Market Breakdown",
        ])

        live_m = metrics.get("live_metrics", {})
        otc_m = metrics.get("otc_metrics", {})
        lines.append(
            f"### LIVE: total={live_m.get('total', 0)}, wins={live_m.get('wins', 0)}, "
            f"losses={live_m.get('losses', 0)}, win_rate={live_m.get('win_rate', 0)}%, "
            f"avg_conf={live_m.get('avg_confidence', 0)}"
        )
        lines.append(
            f"### OTC: total={otc_m.get('total', 0)}, wins={otc_m.get('wins', 0)}, "
            f"losses={otc_m.get('losses', 0)}, win_rate={otc_m.get('win_rate', 0)}%, "
            f"avg_conf={otc_m.get('avg_confidence', 0)}"
        )

        # Expiry breakdown
        expiry_bd = metrics.get("expiry_breakdown", {})
        if expiry_bd:
            lines.extend(["", "## Expiry Breakdown"])
            for expiry, em in sorted(expiry_bd.items()):
                lines.append(
                    f"### {expiry}: total={em.get('total', 0)}, wins={em.get('wins', 0)}, "
                    f"losses={em.get('losses', 0)}, win_rate={em.get('win_rate', 0)}%"
                )

        lines.extend(["", "## Failure Analysis"])

        for cat, items in sorted(failure_groups.items(), key=lambda x: -len(x[1])):
            lines.append(f"### {cat} ({len(items)} occurrences)")
            for item in items[:3]:  # Show top 3 examples per category
                lines.append(
                    f"  - {item['signal_id']}: conf={item['confidence']}, "
                    f"predicted={item['predicted']}, actual={item['actual']}"
                )
            lines.append("")

        return "\n".join(lines)

    def save_results(self, filepath: str, results: Optional[List[Dict]] = None):
        """Save results to JSON.

        ALERT-ONLY: Persists alert validation data for review.

        Args:
            filepath: Output file path.
            results: List of signal records. Defaults to internal results.
        """
        if results is None:
            results = self.results
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(
                {"results": results, "metrics": self.compute_metrics(results)},
                f,
                indent=2,
                default=str,
            )


async def main():
    """Run a full historical replay validation cycle.

    ALERT-ONLY: Generates synthetic candle data, runs it through the
    signal engine, and evaluates prediction accuracy.
    """
    from testing.fixtures.candle_generator import CandleGenerator

    print("=" * 60)
    print("HISTORICAL REPLAY VALIDATION - ALERT ONLY")
    print("=" * 60)

    gen = CandleGenerator(seed=42)
    runner = ReplayRunner()

    # Generate test batches for each profile
    for expiry in ["1m", "2m", "3m"]:
        print(f"\n--- Running {expiry} profile ---")
        batch = gen.generate_batch(
            count=50, seed_start=100 + hash(expiry) % 1000
        )
        results = await runner.run_batch(batch, expiry_profile=expiry)
        metrics = runner.compute_metrics(results)
        print(
            f"  Total: {metrics['total_alerts']}, "
            f"Wins: {metrics['wins']}, "
            f"Losses: {metrics['losses']}, "
            f"No-Trade: {metrics['no_trade']}"
        )
        print(
            f"  Win Rate: {metrics['win_rate_excluding_neutral_unknown']}%, "
            f"Avg Confidence: {metrics['avg_confidence']}"
        )

    # Full report
    report = runner.generate_report()
    print("\n" + report)

    # Save
    output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(exist_ok=True)
    runner.save_results(str(output_dir / "replay_results.json"))
    with open(str(output_dir / "replay_report.md"), "w") as f:
        f.write(report)

    print(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
