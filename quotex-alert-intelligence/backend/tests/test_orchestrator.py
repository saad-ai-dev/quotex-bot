"""
Orchestrator integration tests.

ALERT-ONLY system -- tests verify the SignalOrchestrator correctly coordinates
detectors and scoring to produce well-structured alert signal data.
"""

import pytest
from typing import Any, Dict, List

from app.engine.orchestrator import SignalOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(open_: float, high: float, low: float, close: float, ts: float = 0.0) -> Dict[str, Any]:
    return {"open": open_, "high": high, "low": low, "close": close, "timestamp": ts}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_orchestrator_initializes():
    """SignalOrchestrator() creates without error."""
    orch = SignalOrchestrator()
    assert orch is not None
    assert orch._detectors is not None
    assert len(orch._detectors) > 0


@pytest.mark.asyncio
async def test_orchestrator_analyze_returns_dict(sample_candles):
    """orchestrator.analyze() returns a dict."""
    orch = SignalOrchestrator()
    result = await orch.analyze(sample_candles, "LIVE", "1m", "dom", 90.0)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_orchestrator_result_has_required_keys(sample_candles):
    """The result dict must contain all required signal fields."""
    orch = SignalOrchestrator()
    result = await orch.analyze(sample_candles, "LIVE", "1m", "dom", 90.0)
    required_keys = {
        "bullish_score", "bearish_score", "confidence",
        "prediction_direction", "reasons", "detected_features",
    }
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - result.keys()}"
    )


@pytest.mark.asyncio
async def test_orchestrator_live_vs_otc_differ(sample_candles):
    """Same candles with different market_type may produce different scores.
    ALERT-ONLY: different profiles weight detectors differently.
    """
    orch = SignalOrchestrator()
    live_result = await orch.analyze(sample_candles, "LIVE", "1m", "dom", 90.0)
    otc_result = await orch.analyze(sample_candles, "OTC", "1m", "dom", 90.0)

    # At minimum the results should both be valid dicts
    assert isinstance(live_result, dict)
    assert isinstance(otc_result, dict)

    # They could differ in scores because of different profile weights
    # (we do not assert they MUST differ because edge cases may yield identical scores)
    assert "bullish_score" in live_result
    assert "bullish_score" in otc_result


@pytest.mark.asyncio
async def test_orchestrator_handles_short_candles():
    """3 candles should still work without crash."""
    candles = [
        _c(1.0800, 1.0810, 1.0795, 1.0805, ts=0.0),
        _c(1.0805, 1.0815, 1.0800, 1.0812, ts=60.0),
        _c(1.0812, 1.0820, 1.0808, 1.0818, ts=120.0),
    ]
    orch = SignalOrchestrator()
    result = await orch.analyze(candles, "LIVE", "1m", "dom", 90.0)
    assert isinstance(result, dict)
    assert "prediction_direction" in result


@pytest.mark.asyncio
async def test_orchestrator_handles_empty_candles():
    """0 candles returns NO_TRADE direction."""
    orch = SignalOrchestrator()
    result = await orch.analyze([], "LIVE", "1m", "dom", 90.0)
    assert isinstance(result, dict)
    assert result["prediction_direction"] == "NO_TRADE"


@pytest.mark.asyncio
async def test_orchestrator_confidence_in_range(sample_candles):
    """Confidence should always be between 0 and 100."""
    orch = SignalOrchestrator()
    result = await orch.analyze(sample_candles, "LIVE", "1m", "dom", 90.0)
    assert 0.0 <= result["confidence"] <= 100.0


@pytest.mark.asyncio
async def test_orchestrator_direction_valid(sample_candles):
    """prediction_direction must be one of UP, DOWN, NO_TRADE."""
    orch = SignalOrchestrator()
    result = await orch.analyze(sample_candles, "LIVE", "1m", "dom", 90.0)
    assert result["prediction_direction"] in ("UP", "DOWN", "NO_TRADE")


@pytest.mark.asyncio
async def test_orchestrator_reasons_are_strings(sample_candles):
    """reasons should be a list of strings."""
    orch = SignalOrchestrator()
    result = await orch.analyze(sample_candles, "LIVE", "1m", "dom", 90.0)
    assert isinstance(result["reasons"], list)
    for reason in result["reasons"]:
        assert isinstance(reason, str)
