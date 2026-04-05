"""
Integration tests for the POST /api/signals/ingest endpoint.

ALERT-ONLY system -- tests verify that the ingest endpoint correctly
receives chart data, runs analysis, and returns structured alert signals.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Valid payload helper
# ---------------------------------------------------------------------------

def _valid_payload():
    """Return a minimal valid ingest payload.
    ALERT-ONLY: chart_read_confidence is 0.0-1.0 scale; candles min_length=1.
    """
    return {
        "market_type": "LIVE",
        "asset_name": "EUR/USD",
        "expiry_profile": "1m",
        "candles": [
            {"open": 1.08100, "high": 1.08120, "low": 1.08090, "close": 1.08115, "timestamp": 1700000000.0},
            {"open": 1.08115, "high": 1.08130, "low": 1.08105, "close": 1.08125, "timestamp": 1700000060.0},
        ],
        "parse_mode": "dom",
        "chart_read_confidence": 0.925,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_valid_payload_returns_201(async_client, mock_db):
    """Full valid payload should return HTTP 201."""
    resp = await async_client.post("/api/signals/ingest", json=_valid_payload())
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_ingest_returns_signal_fields(async_client, mock_db):
    """Response should contain key signal fields."""
    resp = await async_client.post("/api/signals/ingest", json=_valid_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert "signal_id" in data
    # The endpoint returns the full alert_doc which uses "direction" key
    assert "direction" in data
    assert "confidence" in data
    assert "bullish_score" in data
    assert "bearish_score" in data
    assert "reasons" in data


@pytest.mark.asyncio
async def test_ingest_single_candle_works(async_client, mock_db):
    """A single candle (min_length=1) should still be accepted."""
    payload = _valid_payload()
    payload["candles"] = [
        {"open": 1.08100, "high": 1.08120, "low": 1.08090, "close": 1.08115, "timestamp": 1700000000.0},
    ]
    resp = await async_client.post("/api/signals/ingest", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_ingest_empty_candles_returns_422(async_client, mock_db):
    """Empty candles list violates min_length=1 and returns 422."""
    payload = _valid_payload()
    payload["candles"] = []
    resp = await async_client.post("/api/signals/ingest", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_missing_market_type_returns_422(async_client, mock_db):
    """Missing required market_type field should return 422."""
    payload = _valid_payload()
    del payload["market_type"]
    resp = await async_client.post("/api/signals/ingest", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_invalid_expiry_returns_400(async_client, mock_db):
    """Invalid expiry_profile '5m' should return 400 from handler validation."""
    payload = _valid_payload()
    payload["expiry_profile"] = "5m"
    resp = await async_client.post("/api/signals/ingest", json=payload)
    # The handler validates expiry_profile and raises 400
    assert resp.status_code == 400
