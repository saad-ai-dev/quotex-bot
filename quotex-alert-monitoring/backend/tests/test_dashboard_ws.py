"""
Tests for the WebSocket ConnectionManager.
ALERT-ONLY: Validates real-time alert broadcasting, not trade commands.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.routes.websocket import ConnectionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_ws():
    """Create a mock WebSocket object with async send_json and accept."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ws_connection_manager():
    """ConnectionManager tracks connected clients after connect/disconnect."""
    mgr = ConnectionManager()
    ws = _make_mock_ws()

    await mgr.connect(ws)
    assert mgr.active_count == 1

    mgr.disconnect(ws)
    assert mgr.active_count == 0


@pytest.mark.asyncio
async def test_ws_broadcast():
    """Broadcast message reaches a connected client."""
    mgr = ConnectionManager()
    ws = _make_mock_ws()
    await mgr.connect(ws)

    msg = {"type": "alert", "signal_id": "test-001"}
    await mgr.broadcast(msg)

    ws.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_ws_multiple_clients():
    """Broadcast reaches all connected clients."""
    mgr = ConnectionManager()
    ws1 = _make_mock_ws()
    ws2 = _make_mock_ws()
    ws3 = _make_mock_ws()

    await mgr.connect(ws1)
    await mgr.connect(ws2)
    await mgr.connect(ws3)
    assert mgr.active_count == 3

    msg = {"type": "alert", "direction": "UP"}
    await mgr.broadcast(msg)

    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_awaited_once_with(msg)
    ws3.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_ws_disconnect_cleanup():
    """Client removed after disconnect; stale client cleaned up during broadcast."""
    mgr = ConnectionManager()
    ws_good = _make_mock_ws()
    ws_stale = _make_mock_ws()
    ws_stale.send_json = AsyncMock(side_effect=Exception("connection lost"))

    await mgr.connect(ws_good)
    await mgr.connect(ws_stale)
    assert mgr.active_count == 2

    # Broadcast should clean up the stale connection
    msg = {"type": "alert", "signal_id": "cleanup-test"}
    await mgr.broadcast(msg)

    # Stale client should have been removed
    assert mgr.active_count == 1
    ws_good.send_json.assert_awaited_once_with(msg)
