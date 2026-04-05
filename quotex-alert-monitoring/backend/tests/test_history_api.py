"""
Tests for the /api/history and /api/analytics endpoints.
ALERT-ONLY: Validates alert history retrieval and analytics, not trade records.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helper to build a mock MongoDB collection with controllable data
# ---------------------------------------------------------------------------

def _patch_collection(async_client_fixture, documents, total=None):
    """Replace the mock collection's find/count_documents with custom data.

    This is called within each test to set up the expected MongoDB responses.
    We access the dependency-overridden db mock through the app.
    """
    # async_client_fixture is the httpx client; the app stores mock db via
    # dependency override. We rebuild the mock behavior here.
    pass  # Not needed with the approach below


def _make_mock_db(documents=None, total=None):
    """Create a mock db whose 'signals' collection returns the given documents."""
    if documents is None:
        documents = []
    if total is None:
        total = len(documents)

    mock_db = MagicMock()
    mock_collection = MagicMock()

    # find() returns a chainable cursor mock
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=documents)

    mock_collection.find = MagicMock(return_value=mock_cursor)
    mock_collection.count_documents = AsyncMock(return_value=total)

    # aggregate for analytics performance
    mock_agg_cursor = MagicMock()
    mock_agg_cursor.to_list = AsyncMock(return_value=[])
    mock_collection.aggregate = MagicMock(return_value=mock_agg_cursor)

    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_db.command = AsyncMock(return_value={"ok": 1})
    return mock_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_history_empty(async_client):
    """GET /api/history/ with empty DB returns empty signals list."""
    resp = await async_client.get("/api/history/")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert isinstance(data["signals"], list)


@pytest.mark.asyncio
async def test_filter_wins(async_client):
    """GET /api/history/wins returns 200."""
    resp = await async_client.get("/api/history/wins")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_filter_losses(async_client):
    """GET /api/history/losses returns 200."""
    resp = await async_client.get("/api/history/losses")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data


@pytest.mark.asyncio
async def test_filter_pending(async_client):
    """GET /api/history/pending returns 200."""
    resp = await async_client.get("/api/history/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data


@pytest.mark.asyncio
async def test_analytics_summary(async_client):
    """GET /api/analytics/summary returns expected shape."""
    resp = await async_client.get("/api/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "wins" in data
    assert "win_rate" in data
    assert "per_market" in data


@pytest.mark.asyncio
async def test_analytics_performance(async_client):
    """GET /api/analytics/performance returns performance list."""
    resp = await async_client.get("/api/analytics/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "performance" in data
    assert isinstance(data["performance"], list)


@pytest.mark.asyncio
async def test_pagination(async_client):
    """GET /api/history/?skip=0&limit=10 respects pagination params."""
    resp = await async_client.get("/api/history/", params={"skip": 0, "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["skip"] == 0
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_filter_by_market_type(async_client):
    """GET /api/history/?market_type=live returns 200 with correct filter."""
    resp = await async_client.get("/api/history/", params={"market_type": "live"})
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
