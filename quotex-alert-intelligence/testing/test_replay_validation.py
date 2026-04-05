"""
Pytest tests for the replay validation framework.
ALERT-ONLY system - validates the testing framework itself.

Tests:
    - test_candle_generator_produces_valid_candles
    - test_replay_runner_processes_batch
    - test_metrics_computation_correct
    - test_failure_analysis_categorizes
    - test_report_generation
    - test_no_trade_counted_correctly
"""
import asyncio
import sys
from pathlib import Path

import pytest

# Ensure backend is importable
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

_TESTING_DIR = str(Path(__file__).resolve().parent.parent)
if _TESTING_DIR not in sys.path:
    sys.path.insert(0, _TESTING_DIR)

from testing.fixtures.candle_generator import CandleGenerator
from testing.batch_analyzer import BatchAnalyzer, FailureAnalysis, FAILURE_CATEGORIES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def candle_generator():
    """Create a deterministic candle generator."""
    return CandleGenerator(seed=42)


@pytest.fixture
def sample_batch(candle_generator):
    """Generate a sample batch of candle sequences."""
    return candle_generator.generate_batch(count=14, seed_start=200)


@pytest.fixture
def sample_signal_results():
    """Create sample signal result dicts for testing metrics computation."""
    return [
        {
            "signal_id": "sig_001",
            "prediction_direction": "UP",
            "direction": "UP",
            "confidence": 72.5,
            "outcome": "WIN",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["Bullish trend", "Support bounce"],
            "detected_features": {"trend_bias": "bullish"},
        },
        {
            "signal_id": "sig_002",
            "prediction_direction": "DOWN",
            "direction": "DOWN",
            "confidence": 68.0,
            "outcome": "WIN",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["Bearish structure"],
            "detected_features": {"trend_bias": "bearish"},
        },
        {
            "signal_id": "sig_003",
            "prediction_direction": "UP",
            "direction": "UP",
            "confidence": 55.0,
            "outcome": "LOSS",
            "market_type": "OTC",
            "expiry_profile": "2m",
            "reasons": ["Weak support"],
            "detected_features": {
                "has_nearby_support": True,
                "has_nearby_resistance": True,
                "chop_probability": 0.3,
            },
        },
        {
            "signal_id": "sig_004",
            "prediction_direction": "DOWN",
            "direction": "DOWN",
            "confidence": 88.0,
            "outcome": "LOSS",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["Strong bearish signal"],
            "detected_features": {"trend_bias": "bearish"},
        },
        {
            "signal_id": "sig_005",
            "prediction_direction": "NO_TRADE",
            "direction": "NO_TRADE",
            "confidence": 40.0,
            "outcome": "NO_TRADE",
            "market_type": "LIVE",
            "expiry_profile": "3m",
            "reasons": ["No clear edge"],
            "detected_features": {"chop_probability": 0.8},
        },
        {
            "signal_id": "sig_006",
            "prediction_direction": "UP",
            "direction": "UP",
            "confidence": 61.0,
            "outcome": "NEUTRAL",
            "market_type": "OTC",
            "expiry_profile": "1m",
            "reasons": ["Doji candle"],
            "detected_features": {},
        },
        {
            "signal_id": "sig_007",
            "prediction_direction": "DOWN",
            "direction": "DOWN",
            "confidence": 75.0,
            "outcome": "WIN",
            "market_type": "OTC",
            "expiry_profile": "2m",
            "reasons": ["OTC pattern match"],
            "detected_features": {"otc_pattern_count": 2},
        },
        {
            "signal_id": "sig_008",
            "prediction_direction": "UP",
            "direction": "UP",
            "confidence": 50.0,
            "outcome": "LOSS",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["False liquidity sweep"],
            "detected_features": {
                "stop_hunt_detected": True,
                "liquidity_above": True,
                "chop_probability": 0.4,
            },
        },
        {
            "signal_id": "sig_009",
            "prediction_direction": "NO_TRADE",
            "direction": "NO_TRADE",
            "confidence": 30.0,
            "outcome": "NO_TRADE",
            "market_type": "OTC",
            "expiry_profile": "1m",
            "reasons": ["Insufficient data"],
            "detected_features": {},
        },
        {
            "signal_id": "sig_010",
            "prediction_direction": "UP",
            "direction": "UP",
            "confidence": 82.0,
            "outcome": "WIN",
            "market_type": "LIVE",
            "expiry_profile": "2m",
            "reasons": ["Strong bullish structure", "Order block retest"],
            "detected_features": {"active_order_block_count": 1},
        },
    ]


@pytest.fixture
def batch_analyzer():
    """Create a BatchAnalyzer instance."""
    return BatchAnalyzer()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCandleGenerator:
    """Tests for the CandleGenerator class."""

    def test_candle_generator_produces_valid_candles(self, candle_generator):
        """ALERT-ONLY: Verify candle data has correct structure and OHLC constraints."""
        for gen_method in [
            candle_generator.generate_uptrend,
            candle_generator.generate_downtrend,
            candle_generator.generate_range,
            candle_generator.generate_reversal_up,
            candle_generator.generate_reversal_down,
            candle_generator.generate_otc_alternating,
            candle_generator.generate_otc_spike_reversal,
        ]:
            # Reset RNG for each generator
            candle_generator.rng = __import__("numpy").random.RandomState(42)
            candles = gen_method(n=20)

            assert len(candles) == 20, f"Expected 20 candles from {gen_method.__name__}"

            for i, candle in enumerate(candles):
                # Required keys
                assert "open" in candle, f"Missing 'open' in candle {i}"
                assert "high" in candle, f"Missing 'high' in candle {i}"
                assert "low" in candle, f"Missing 'low' in candle {i}"
                assert "close" in candle, f"Missing 'close' in candle {i}"
                assert "timestamp" in candle, f"Missing 'timestamp' in candle {i}"

                # OHLC constraints
                assert candle["high"] >= candle["open"], (
                    f"High < Open in candle {i}: {candle}"
                )
                assert candle["high"] >= candle["close"], (
                    f"High < Close in candle {i}: {candle}"
                )
                assert candle["low"] <= candle["open"], (
                    f"Low > Open in candle {i}: {candle}"
                )
                assert candle["low"] <= candle["close"], (
                    f"Low > Close in candle {i}: {candle}"
                )

                # Values are numeric
                for key in ("open", "high", "low", "close"):
                    assert isinstance(candle[key], float), (
                        f"candle['{key}'] is not float: {type(candle[key])}"
                    )

                # Timestamp is increasing
                if i > 0:
                    assert candle["timestamp"] > candles[i - 1]["timestamp"], (
                        f"Timestamp not increasing at candle {i}"
                    )

    def test_candle_generator_deterministic(self):
        """ALERT-ONLY: Same seed produces identical candle sequences."""
        gen1 = CandleGenerator(seed=123)
        gen2 = CandleGenerator(seed=123)

        candles1 = gen1.generate_uptrend(n=10)
        candles2 = gen2.generate_uptrend(n=10)

        assert len(candles1) == len(candles2)
        for c1, c2 in zip(candles1, candles2):
            assert c1 == c2, "Deterministic generation failed"

    def test_candle_generator_batch(self, candle_generator):
        """ALERT-ONLY: Batch generation produces correct count with metadata."""
        batch = candle_generator.generate_batch(count=7, seed_start=300)

        assert len(batch) == 7

        for item in batch:
            assert "sequence_id" in item
            assert "pattern_type" in item
            assert "market_type" in item
            assert "expected_direction" in item
            assert "actual_next_candle_direction" in item
            assert "candles" in item
            assert len(item["candles"]) == 30
            assert item["market_type"] in ("LIVE", "OTC")
            assert item["expected_direction"] in ("UP", "DOWN", "NO_TRADE")
            assert item["actual_next_candle_direction"] in ("bullish", "bearish", "neutral")

    def test_uptrend_has_rising_prices(self, candle_generator):
        """ALERT-ONLY: Uptrend candles should generally show rising prices."""
        candles = candle_generator.generate_uptrend(n=30)
        first_close = candles[0]["close"]
        last_close = candles[-1]["close"]
        assert last_close > first_close, "Uptrend should have rising prices"

    def test_downtrend_has_falling_prices(self, candle_generator):
        """ALERT-ONLY: Downtrend candles should generally show falling prices."""
        candle_generator.rng = __import__("numpy").random.RandomState(42)
        candles = candle_generator.generate_downtrend(n=30)
        first_close = candles[0]["close"]
        last_close = candles[-1]["close"]
        assert last_close < first_close, "Downtrend should have falling prices"


class TestReplayRunner:
    """Tests for the ReplayRunner class."""

    @pytest.mark.asyncio
    async def test_replay_runner_processes_batch(self, sample_batch):
        """ALERT-ONLY: ReplayRunner should process a batch of sequences."""
        from testing.historical_replay_runner import ReplayRunner

        runner = ReplayRunner()
        results = await runner.run_batch(sample_batch[:3], expiry_profile="1m")

        assert len(results) == 3

        for r in results:
            assert "signal_id" in r
            assert "prediction_direction" in r
            assert "confidence" in r
            assert "outcome" in r
            assert "market_type" in r
            assert r["prediction_direction"] in ("UP", "DOWN", "NO_TRADE")
            assert isinstance(r["confidence"], (int, float))
            assert r["outcome"] in ("WIN", "LOSS", "NEUTRAL", "UNKNOWN", "NO_TRADE")

    @pytest.mark.asyncio
    async def test_replay_runner_single_sequence(self, sample_batch):
        """ALERT-ONLY: ReplayRunner should process a single sequence."""
        from testing.historical_replay_runner import ReplayRunner

        runner = ReplayRunner()
        result = await runner.run_single(sample_batch[0], expiry_profile="1m")

        assert result["sequence_id"] == sample_batch[0]["sequence_id"]
        assert result["market_type"] == sample_batch[0]["market_type"]
        assert "bullish_score" in result
        assert "bearish_score" in result
        assert "reasons" in result
        assert isinstance(result["reasons"], list)


class TestMetricsComputation:
    """Tests for metrics computation."""

    def test_metrics_computation_correct(self, batch_analyzer, sample_signal_results):
        """ALERT-ONLY: Verify all metrics are computed correctly."""
        metrics = batch_analyzer.compute_metrics(sample_signal_results)

        assert metrics["total"] == 10
        assert metrics["wins"] == 4  # sig_001, sig_002, sig_007, sig_010
        assert metrics["losses"] == 3  # sig_003, sig_004, sig_008
        assert metrics["neutral"] == 1  # sig_006
        assert metrics["no_trade"] == 2  # sig_005, sig_009

        # Win rate: 4 wins / (4 wins + 3 losses) = 57.14%
        evaluated = metrics["wins"] + metrics["losses"]
        assert evaluated == 7
        expected_wr = round(4 / 7 * 100, 2)
        assert metrics["win_rate"] == expected_wr

        # No-trade rate: 2/10 = 20%
        assert metrics["no_trade_rate"] == 20.0

        # Average confidence
        total_conf = 72.5 + 68.0 + 55.0 + 88.0 + 40.0 + 61.0 + 75.0 + 50.0 + 30.0 + 82.0
        expected_avg = round(total_conf / 10, 2)
        assert metrics["avg_confidence"] == expected_avg

    def test_metrics_empty_signals(self, batch_analyzer):
        """ALERT-ONLY: Empty signal list should return zero metrics."""
        metrics = batch_analyzer.compute_metrics([])
        assert metrics["total"] == 0
        assert metrics["win_rate"] == 0.0

    def test_metrics_all_wins(self, batch_analyzer):
        """ALERT-ONLY: All-win batch should have 100% win rate."""
        signals = [
            {"signal_id": f"w{i}", "direction": "UP", "confidence": 80,
             "outcome": "WIN", "market_type": "LIVE", "expiry_profile": "1m"}
            for i in range(5)
        ]
        metrics = batch_analyzer.compute_metrics(signals)
        assert metrics["win_rate"] == 100.0
        assert metrics["wins"] == 5
        assert metrics["losses"] == 0

    def test_metrics_market_breakdown(self, batch_analyzer, sample_signal_results):
        """ALERT-ONLY: Live and OTC metrics should be computed separately."""
        metrics = batch_analyzer.compute_metrics(sample_signal_results)

        live_m = metrics["live_metrics"]
        otc_m = metrics["otc_metrics"]

        # LIVE signals: sig_001(W), sig_002(W), sig_004(L), sig_005(NT),
        #               sig_008(L), sig_010(W) = 6 total
        assert live_m["total"] == 6

        # OTC signals: sig_003(L), sig_006(N), sig_007(W), sig_009(NT) = 4 total
        assert otc_m["total"] == 4

    def test_metrics_expiry_breakdown(self, batch_analyzer, sample_signal_results):
        """ALERT-ONLY: Expiry breakdown should cover all profiles."""
        metrics = batch_analyzer.compute_metrics(sample_signal_results)
        expiry_bd = metrics["expiry_breakdown"]

        assert "1m" in expiry_bd
        assert "2m" in expiry_bd
        assert "3m" in expiry_bd


class TestFailureAnalysis:
    """Tests for failure analysis and categorization."""

    def test_failure_analysis_categorizes(self, batch_analyzer, sample_signal_results):
        """ALERT-ONLY: Loss signals should be categorized into known categories."""
        loss_signals = [
            s for s in sample_signal_results if s.get("outcome") == "LOSS"
        ]
        failures = batch_analyzer.analyze_failures(loss_signals)

        assert len(failures) == 3  # sig_003, sig_004, sig_008

        for fa in failures:
            assert isinstance(fa, FailureAnalysis)
            assert fa.category in FAILURE_CATEGORIES, (
                f"Unknown category: {fa.category}"
            )
            assert fa.signal_id != ""
            assert fa.explanation != ""

    def test_high_confidence_false_positive_detection(self, batch_analyzer):
        """ALERT-ONLY: High confidence losses should be categorized correctly."""
        signal = {
            "signal_id": "hc_loss",
            "direction": "DOWN",
            "confidence": 90.0,
            "outcome": "LOSS",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["Strong signal"],
            "detected_features": {"chop_probability": 0.2},
        }
        category = batch_analyzer.categorize_failure(signal)
        assert category == "high_conf_false_positive"

    def test_chop_alert_detection(self, batch_analyzer):
        """ALERT-ONLY: Choppy market losses should be categorized correctly."""
        signal = {
            "signal_id": "chop_loss",
            "direction": "UP",
            "confidence": 60.0,
            "outcome": "LOSS",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["High chop probability detected"],
            "detected_features": {"chop_probability": 0.85},
        }
        category = batch_analyzer.categorize_failure(signal)
        assert category == "chop_alert"

    def test_threshold_loose_detection(self, batch_analyzer):
        """ALERT-ONLY: Low confidence losses should be threshold_loose."""
        signal = {
            "signal_id": "low_conf",
            "direction": "UP",
            "confidence": 52.0,
            "outcome": "LOSS",
            "market_type": "LIVE",
            "expiry_profile": "1m",
            "reasons": ["Marginal signal"],
            "detected_features": {"chop_probability": 0.3},
        }
        category = batch_analyzer.categorize_failure(signal)
        assert category == "threshold_loose"

    def test_failure_grouping(self, batch_analyzer):
        """ALERT-ONLY: Failures should be grouped by category and ranked."""
        failures = [
            FailureAnalysis(signal_id="f1", category="weak_sr", confidence=65),
            FailureAnalysis(signal_id="f2", category="weak_sr", confidence=70),
            FailureAnalysis(signal_id="f3", category="chop_alert", confidence=55),
            FailureAnalysis(signal_id="f4", category="weak_sr", confidence=62),
            FailureAnalysis(signal_id="f5", category="false_price_action", confidence=68),
        ]
        groups = batch_analyzer.group_by_category(failures)

        # Most frequent first
        categories = list(groups.keys())
        assert categories[0] == "weak_sr"
        assert len(groups["weak_sr"]) == 3
        assert len(groups["chop_alert"]) == 1
        assert len(groups["false_price_action"]) == 1

    def test_all_17_categories_defined(self):
        """ALERT-ONLY: Verify all 17 failure categories are defined."""
        assert len(FAILURE_CATEGORIES) == 17
        expected = {
            "parsing_error", "wrong_market_detection", "weak_sr",
            "false_price_action", "false_liquidity", "weak_ob",
            "incorrect_fvg", "weak_sd", "otc_overfit", "live_overfit",
            "threshold_loose", "threshold_strict", "timing_late",
            "chop_alert", "high_conf_false_positive", "profile_mismatch",
            "eval_bug",
        }
        assert set(FAILURE_CATEGORIES) == expected


class TestReportGeneration:
    """Tests for report generation."""

    def test_report_generation(self, batch_analyzer, sample_signal_results):
        """ALERT-ONLY: Generate a full analysis and verify report structure."""
        analysis = batch_analyzer.analyze(sample_signal_results)

        assert analysis.total == 10
        assert analysis.wins == 4
        assert analysis.losses == 3
        assert analysis.win_rate > 0
        assert len(analysis.failure_analyses) == 3

        # Generate failure report
        report = batch_analyzer.generate_failure_report(analysis.failure_analyses)
        assert "total_failures" in report
        assert "categories" in report
        assert "ranked_categories" in report
        assert "details" in report
        assert report["total_failures"] == 3

    def test_improvement_recommendations(self, batch_analyzer):
        """ALERT-ONLY: Recommendations should be generated from failure groups."""
        failures = [
            FailureAnalysis(
                signal_id=f"f{i}", category="chop_alert",
                confidence=60, market_type="LIVE", expiry_profile="1m",
            )
            for i in range(5)
        ]
        groups = batch_analyzer.group_by_category(failures)
        recommendations = batch_analyzer.generate_improvement_recommendations(groups)

        assert len(recommendations) >= 1
        rec = recommendations[0]
        assert rec["category"] == "chop_alert"
        assert rec["failure_count"] == 5
        assert "action" in rec
        assert "priority" in rec
        assert "config_changes" in rec

    def test_batch_comparison(self, batch_analyzer):
        """ALERT-ONLY: Compare two batches and verify delta computation."""
        before = {
            "win_rate": 55.0,
            "precision_up": 50.0,
            "precision_down": 60.0,
            "no_trade_rate": 20.0,
            "avg_confidence": 65.0,
            "live_metrics": {"win_rate": 52.0},
            "otc_metrics": {"win_rate": 58.0},
            "expiry_breakdown": {"1m": {"win_rate": 55.0}},
        }
        after = {
            "win_rate": 62.0,
            "precision_up": 58.0,
            "precision_down": 65.0,
            "no_trade_rate": 25.0,
            "avg_confidence": 68.0,
            "live_metrics": {"win_rate": 60.0},
            "otc_metrics": {"win_rate": 64.0},
            "expiry_breakdown": {"1m": {"win_rate": 62.0}},
        }

        comparison = batch_analyzer.compare_batches(before, after)

        assert comparison["win_rate"]["delta"] == 7.0
        assert comparison["win_rate"]["assessment"] == "improved"
        assert comparison["precision_up"]["assessment"] == "improved"
        assert comparison["no_trade_rate"]["assessment"] == "more_cautious"
        assert comparison["overall"] == "improved"


class TestNoTradeCount:
    """Tests for NO_TRADE counting."""

    def test_no_trade_counted_correctly(self, batch_analyzer, sample_signal_results):
        """ALERT-ONLY: NO_TRADE signals should be counted separately from
        wins/losses and excluded from win rate calculation."""
        metrics = batch_analyzer.compute_metrics(sample_signal_results)

        # NO_TRADE signals: sig_005, sig_009
        assert metrics["no_trade"] == 2

        # Win rate should exclude NO_TRADE
        # Wins: 4, Losses: 3, evaluated = 7
        assert metrics["wins"] + metrics["losses"] == 7
        assert metrics["win_rate"] == round(4 / 7 * 100, 2)

        # NO_TRADE rate: 2/10 = 20%
        assert metrics["no_trade_rate"] == 20.0

    def test_all_no_trade_batch(self, batch_analyzer):
        """ALERT-ONLY: Batch with only NO_TRADE should have 0% win rate."""
        signals = [
            {
                "signal_id": f"nt{i}",
                "direction": "NO_TRADE",
                "confidence": 30,
                "outcome": "NO_TRADE",
                "market_type": "LIVE",
                "expiry_profile": "1m",
            }
            for i in range(5)
        ]
        metrics = batch_analyzer.compute_metrics(signals)

        assert metrics["no_trade"] == 5
        assert metrics["wins"] == 0
        assert metrics["losses"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["no_trade_rate"] == 100.0

    def test_no_trade_not_in_directional_precision(self, batch_analyzer):
        """ALERT-ONLY: NO_TRADE should not affect UP/DOWN precision."""
        signals = [
            {"signal_id": "u1", "direction": "UP", "confidence": 70,
             "outcome": "WIN", "market_type": "LIVE", "expiry_profile": "1m"},
            {"signal_id": "u2", "direction": "UP", "confidence": 65,
             "outcome": "LOSS", "market_type": "LIVE", "expiry_profile": "1m"},
            {"signal_id": "nt1", "direction": "NO_TRADE", "confidence": 30,
             "outcome": "NO_TRADE", "market_type": "LIVE", "expiry_profile": "1m"},
        ]
        metrics = batch_analyzer.compute_metrics(signals)

        # UP precision: 1 win / 2 UP signals = 50%
        assert metrics["precision_up"] == 50.0
        # DOWN precision: 0 signals = 0%
        assert metrics["precision_down"] == 0.0
