from app.api.routes.signals import _build_execution_decision
from app.engine.orchestrator import SignalOrchestrator


def _make_candle(open_price: float, close_price: float) -> dict:
    high = max(open_price, close_price) + 0.0002
    low = min(open_price, close_price) - 0.0002
    return {
        "open": round(open_price, 5),
        "high": round(high, 5),
        "low": round(low, 5),
        "close": round(close_price, 5),
        "timestamp": 0.0,
    }


def test_execution_decision_blocks_weak_signal():
    signal_doc = {
        "prediction_direction": "UP",
        "confidence": 55.0,
        "market_type": "LIVE",
        "candle_count": 12,
        "penalties": {
            "conflict_penalty": 5.0,
            "weak_data_penalty": 3.0,
        },
        "detected_features": {
            "chop_probability": 0.65,
            "agreeing_detector_count": 2,
            "score_gap": 8.0,
            "strategy_name": "mean_reversion",
            "regime": "TRENDING",
            "trend_strength": 0.22,
        },
    }

    ready, blockers = _build_execution_decision(signal_doc)

    assert ready is False
    assert "confidence_below_56" in blockers
    assert "market_too_choppy" in blockers
    assert "mean_reversion_against_trend" in blockers
    assert "weak_data_penalty" in blockers


def test_execution_decision_allows_strong_signal():
    signal_doc = {
        "prediction_direction": "DOWN",
        "confidence": 67.0,
        "market_type": "LIVE",
        "candle_count": 24,
        "penalties": {},
        "detected_features": {
            "chop_probability": 0.31,
            "agreeing_detector_count": 4,
            "score_gap": 18.0,
            "strategy_name": "pullback_trend",
            "regime": "TRENDING",
            "trend_strength": 0.24,
            "recent_range_position": 0.62,
            "consecutive_up": 1,
            "consecutive_down": 1,
        },
    }

    ready, blockers = _build_execution_decision(signal_doc)

    assert ready is True
    assert blockers == []


def test_execution_decision_blocks_late_trend_entry():
    signal_doc = {
        "prediction_direction": "UP",
        "confidence": 64.0,
        "market_type": "OTC",
        "expiry_profile": "2m",
        "candle_count": 25,
        "penalties": {},
        "detected_features": {
            "chop_probability": 0.4,
            "agreeing_detector_count": 5,
            "score_gap": 12.0,
            "strategy_name": "pullback_trend",
            "regime": "TRENDING",
            "trend_strength": 0.36,
            "recent_range_position": 0.94,
            "consecutive_up": 3,
            "consecutive_down": 0,
        },
    }

    ready, blockers = _build_execution_decision(signal_doc)

    assert ready is False
    assert "late_entry_overextended_uptrend" in blockers


def test_orchestrator_skips_mean_reversion_when_market_is_trending():
    candles = [
        _make_candle(1.1000, 1.1010),
        _make_candle(1.1010, 1.1020),
        _make_candle(1.1020, 1.1030),
        _make_candle(1.1030, 1.1040),
        _make_candle(1.1040, 1.1050),
        _make_candle(1.1050, 1.1060),
        _make_candle(1.1060, 1.1055),
        _make_candle(1.1055, 1.1065),
        _make_candle(1.1065, 1.1075),
        _make_candle(1.1075, 1.1085),
    ]

    scores = {
        "bullish_score": 54.0,
        "bearish_score": 21.0,
        "confidence": 58.0,
        "prediction_direction": "UP",
        "penalties": {},
        "agreeing_count": 4,
        "score_gap": 33.0,
    }

    updated = SignalOrchestrator()._apply_trend_analysis(candles, scores)

    assert updated["prediction_direction"] == "NO_TRADE"
    assert updated["execution_context"]["regime"] == "TRENDING"
    assert updated["execution_context"]["strategy_name"] == "none"


def test_execution_decision_allows_trend_continuation_when_not_extended():
    signal_doc = {
        "prediction_direction": "UP",
        "confidence": 61.0,
        "market_type": "OTC",
        "expiry_profile": "2m",
        "candle_count": 24,
        "penalties": {},
        "detected_features": {
            "chop_probability": 0.33,
            "agreeing_detector_count": 4,
            "score_gap": 11.0,
            "strategy_name": "trend_continuation",
            "regime": "TRENDING",
            "trend_strength": 0.28,
            "recent_range_position": 0.72,
            "consecutive_up": 2,
            "consecutive_down": 0,
        },
    }

    ready, blockers = _build_execution_decision(signal_doc)

    assert ready is True
    assert blockers == []
