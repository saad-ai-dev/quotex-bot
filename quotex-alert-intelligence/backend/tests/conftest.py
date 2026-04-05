"""
Shared pytest fixtures for the Quotex Alert Intelligence test suite.

ALERT-ONLY system -- all fixtures support testing of chart analysis
and signal generation. No trade execution logic exists.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Candle data fixtures
# ---------------------------------------------------------------------------

def _make_candle(open_: float, high: float, low: float, close: float, ts: float) -> Dict[str, Any]:
    """Helper to create a single candle dict."""
    return {"open": open_, "high": high, "low": low, "close": close, "timestamp": ts}


@pytest.fixture
def sample_candles() -> List[Dict[str, Any]]:
    """30 realistic EUR/USD candles in a clear uptrend with pronounced pullbacks.
    Creates identifiable swing highs and swing lows (HH + HL = bullish).
    ALERT-ONLY: used to test analytical detectors, not trade logic.
    """
    base = 1.08000
    ts_start = 1700000000.0
    candles = []
    # Design: clear wave structure with pullbacks deep enough for lookback=3
    # Wave 1 up, pullback, Wave 2 higher up, pullback higher, Wave 3 highest
    offsets = [
        # Wave 1 up (0-3)
        (0, 8, -5, 5),
        (5, 15, 2, 12),
        (12, 25, 8, 22),
        (22, 40, 18, 35),       # Peak 1: high=40
        # Pullback 1 (4-7) - clear decline
        (35, 38, 20, 22),
        (22, 25, 12, 15),
        (15, 20, 8, 10),        # Trough 1: low=8
        (10, 18, 5, 15),
        # Wave 2 up (8-12) - higher than wave 1
        (15, 25, 10, 22),
        (22, 35, 18, 32),
        (32, 48, 28, 45),
        (45, 60, 40, 55),
        (55, 70, 50, 65),       # Peak 2: high=70 > 40 (HH)
        # Pullback 2 (13-16) - stays above trough 1
        (65, 68, 45, 48),
        (48, 52, 35, 38),
        (38, 42, 25, 28),       # Trough 2: low=25 > 8 (HL)
        (28, 35, 22, 32),
        # Wave 3 up (17-22) - highest
        (32, 42, 28, 40),
        (40, 55, 35, 50),
        (50, 65, 45, 60),
        (60, 80, 55, 75),
        (75, 95, 70, 90),
        (90, 110, 85, 105),     # Peak 3: high=110 > 70 (HH)
        # Pullback 3 (23-26)
        (105, 108, 80, 85),
        (85, 90, 65, 70),
        (70, 78, 55, 60),       # Trough 3: low=55 > 25 (HL)
        (60, 70, 52, 65),
        # Final push (27-29)
        (65, 80, 58, 75),
        (75, 95, 68, 88),
        (88, 120, 82, 115),     # New high: 120
    ]
    for i, (o, h, l, c) in enumerate(offsets):
        candles.append(_make_candle(
            open_=base + o * 0.0001,
            high=base + h * 0.0001,
            low=base + l * 0.0001,
            close=base + c * 0.0001,
            ts=ts_start + i * 60,
        ))
    return candles


@pytest.fixture
def sample_bearish_candles() -> List[Dict[str, Any]]:
    """30 EUR/USD candles in a clear downtrend with pronounced pullbacks.
    Creates identifiable LH + LL = bearish structure.
    ALERT-ONLY: used for bearish detector testing.
    """
    base = 1.09000
    ts_start = 1700000000.0
    candles = []
    # Mirror of uptrend: clear wave structure going down
    offsets = [
        # Wave 1 down (0-3)
        (0, 5, -8, -5),
        (-5, -2, -15, -12),
        (-12, -8, -25, -22),
        (-22, -18, -40, -35),    # Trough 1: low=-40
        # Pullback 1 up (4-7)
        (-35, -20, -38, -22),
        (-22, -12, -25, -15),
        (-15, -8, -18, -10),     # Peak 1: high=-8
        (-10, -5, -15, -12),
        # Wave 2 down (8-12) - lower than wave 1
        (-12, -8, -22, -18),
        (-18, -12, -32, -28),
        (-28, -22, -48, -42),
        (-42, -35, -58, -52),
        (-52, -45, -70, -62),    # Trough 2: low=-70 < -40 (LL)
        # Pullback 2 up (13-16) - stays below peak 1
        (-62, -42, -65, -45),
        (-45, -32, -48, -35),
        (-35, -22, -38, -25),    # Peak 2: high=-22 < -8 (LH)
        (-25, -18, -30, -28),
        # Wave 3 down (17-22)
        (-28, -22, -40, -35),
        (-35, -28, -52, -48),
        (-48, -40, -65, -58),
        (-58, -50, -80, -72),
        (-72, -62, -95, -85),
        (-85, -75, -110, -100),  # Trough 3: low=-110 (LL)
        # Pullback 3 (23-26)
        (-100, -78, -105, -82),
        (-82, -62, -88, -68),
        (-68, -50, -72, -55),    # Peak 3: high=-50 < -22 (LH)
        (-55, -48, -62, -58),
        # Final drop (27-29)
        (-58, -50, -75, -68),
        (-68, -58, -90, -82),
        (-82, -72, -120, -110),
    ]
    for i, (o, h, l, c) in enumerate(offsets):
        candles.append(_make_candle(
            open_=base + o * 0.0001,
            high=base + h * 0.0001,
            low=base + l * 0.0001,
            close=base + c * 0.0001,
            ts=ts_start + i * 60,
        ))
    return candles


@pytest.fixture
def sample_choppy_candles() -> List[Dict[str, Any]]:
    """30 EUR/USD candles going sideways with lots of direction changes.
    ALERT-ONLY: used to test chop detection.
    """
    base = 1.08500
    ts_start = 1700000000.0
    candles = []
    # Alternating small bullish/bearish around the same level
    offsets = [
        (0, 8, -5, 5),
        (5, 10, -2, -1),
        (-1, 7, -8, 4),
        (4, 9, -3, -2),
        (-2, 6, -7, 3),
        (3, 10, -4, -1),
        (-1, 8, -6, 5),
        (5, 11, -3, -2),
        (-2, 7, -8, 4),
        (4, 10, -5, -1),
        (-1, 6, -7, 3),
        (3, 9, -4, -3),
        (-3, 5, -8, 2),
        (2, 8, -6, -1),
        (-1, 7, -5, 4),
        (4, 10, -3, -2),
        (-2, 6, -7, 3),
        (3, 9, -5, -1),
        (-1, 8, -6, 5),
        (5, 11, -2, -3),
        (-3, 5, -8, 2),
        (2, 9, -4, -1),
        (-1, 7, -6, 4),
        (4, 10, -3, -2),
        (-2, 6, -7, 3),
        (3, 8, -5, -1),
        (-1, 7, -6, 4),
        (4, 9, -4, -2),
        (-2, 6, -7, 3),
        (3, 8, -5, 0),
    ]
    for i, (o, h, l, c) in enumerate(offsets):
        candles.append(_make_candle(
            open_=base + o * 0.0001,
            high=base + h * 0.0001,
            low=base + l * 0.0001,
            close=base + c * 0.0001,
            ts=ts_start + i * 60,
        ))
    return candles


@pytest.fixture
def sample_otc_candles() -> List[Dict[str, Any]]:
    """30 candles with OTC-like patterns: spikes, reversals, alternating.
    ALERT-ONLY: used to test OTC-specific pattern detectors.
    """
    base = 1.08500
    ts_start = 1700000000.0
    candles = []
    offsets = [
        # Alternating up/down sequence (indices 0-7)
        (0, 12, -3, 8),       # up
        (8, 13, 0, 2),        # down
        (2, 14, -2, 10),      # up
        (10, 15, 2, 3),       # down
        (3, 15, -1, 11),      # up
        (11, 16, 3, 4),       # down
        (4, 14, -2, 10),      # up
        (10, 15, 2, 3),       # down
        # Spike and reversal (indices 8-11)
        (3, 8, -2, 5),        # normal
        (5, 40, 0, 35),       # BIG spike up
        (35, 38, 10, 12),     # sharp reversal down
        (12, 18, 5, 8),       # continuation down
        # Compression then burst (indices 12-18)
        (8, 11, 6, 9),        # tiny range
        (9, 12, 7, 10),       # tiny range
        (10, 12, 8, 9),       # tiny range
        (9, 11, 7, 10),       # tiny range
        (10, 12, 8, 9),       # tiny range
        (9, 35, 5, 30),       # BURST out of compression
        # More alternating (indices 18-24)
        (30, 38, 22, 24),     # down
        (24, 32, 18, 28),     # up
        (28, 34, 20, 22),     # down
        (22, 30, 16, 26),     # up
        (26, 32, 18, 20),     # down
        (20, 28, 14, 24),     # up
        (24, 30, 16, 18),     # down
        # Stair drift then snapback (indices 25-29)
        (18, 22, 16, 20),     # small up
        (20, 24, 18, 22),     # small up
        (22, 26, 20, 24),     # small up
        (24, 28, 22, 26),     # small up
        (26, 30, 8, 10),      # SNAPBACK down
    ]
    for i, (o, h, l, c) in enumerate(offsets):
        candles.append(_make_candle(
            open_=base + o * 0.0001,
            high=base + h * 0.0001,
            low=base + l * 0.0001,
            close=base + c * 0.0001,
            ts=ts_start + i * 60,
        ))
    return candles


@pytest.fixture
def sample_signal_create() -> Dict[str, Any]:
    """Dict matching the SignalCreate schema.
    ALERT-ONLY: represents a chart analysis request, not a trade order.
    """
    return {
        "market_type": "LIVE",
        "asset_name": "EUR/USD (OTC)",
        "expiry_profile": "1m",
        "chart_snapshot_meta": {
            "parse_mode": "full",
            "region_x": 0,
            "region_y": 0,
            "region_width": 800,
            "region_height": 600,
            "raw_confidence": 92.5,
        },
        "candles": [
            {"open": 1.08100, "high": 1.08120, "low": 1.08090, "close": 1.08115, "timestamp": 1700000000.0},
            {"open": 1.08115, "high": 1.08130, "low": 1.08105, "close": 1.08125, "timestamp": 1700000060.0},
        ],
        "parse_mode": "full",
        "chart_read_confidence": 92.5,
    }


@pytest.fixture
def sample_settings() -> Dict[str, Any]:
    """Dict matching the SettingsRead schema.
    ALERT-ONLY: controls analytical configuration, not trade parameters.
    """
    return {
        "backend_url": "http://localhost:8000",
        "monitoring_enabled": True,
        "market_mode": "auto",
        "expiry_profile": "1m",
        "min_confidence_threshold": 65.0,
        "sound_alerts_enabled": True,
        "browser_notifications_enabled": True,
        "screenshot_logging_enabled": False,
        "parse_interval_ms": 2000,
        "use_websocket": True,
        "auto_detect_market": True,
        "live_profile_weights": {
            "market_structure": 15,
            "support_resistance": 15,
            "price_action": 20,
        },
        "otc_profile_weights": {
            "market_structure": 14,
            "otc_patterns": 12,
        },
    }


# ---------------------------------------------------------------------------
# Async HTTP client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client():
    """httpx.AsyncClient wired to the FastAPI test app.
    ALERT-ONLY: tests API endpoints for alert management, not trade execution.
    """
    import httpx
    from unittest.mock import AsyncMock, patch

    # Patch MongoDB connection and APScheduler so the app can start without a real DB
    with patch("app.db.mongo.connect", new_callable=AsyncMock), \
         patch("app.db.mongo.close_connection", new_callable=AsyncMock), \
         patch("app.db.mongo.get_database") as mock_get_db, \
         patch("app.db.indexes.create_indexes", new_callable=AsyncMock), \
         patch("app.main.scheduler") as mock_scheduler:

        # Make the database ping succeed
        mock_db = MagicMock()
        mock_db.command = AsyncMock(return_value={"ok": 1})
        mock_get_db.return_value = mock_db

        # Prevent scheduler from actually starting
        mock_scheduler.add_job = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()

        from app.main import app
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client


# ---------------------------------------------------------------------------
# Mock DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Patches all MongoDB repository calls with AsyncMocks.
    ALERT-ONLY: mocks the alert/analytics data layer.
    """
    with patch("app.db.repositories.alerts_repo.insert_alert", new_callable=AsyncMock) as mock_insert, \
         patch("app.db.repositories.alerts_repo.get_alert_by_signal_id", new_callable=AsyncMock) as mock_get, \
         patch("app.db.repositories.alerts_repo.get_alerts", new_callable=AsyncMock) as mock_list, \
         patch("app.db.repositories.alerts_repo.get_alerts_count", new_callable=AsyncMock) as mock_count, \
         patch("app.db.repositories.alerts_repo.update_alert_outcome", new_callable=AsyncMock) as mock_update, \
         patch("app.db.repositories.alerts_repo.get_pending_alerts", new_callable=AsyncMock) as mock_pending, \
         patch("app.db.repositories.alerts_repo.get_recent_alerts", new_callable=AsyncMock) as mock_recent, \
         patch("app.db.repositories.analytics_repo.get_cached_summary", new_callable=AsyncMock) as mock_summary, \
         patch("app.db.repositories.analytics_repo.get_performance_by_market_and_expiry", new_callable=AsyncMock) as mock_perf:

        mock_insert.return_value = "mock_id"
        mock_get.return_value = None
        mock_list.return_value = []
        mock_count.return_value = 0
        mock_update.return_value = True
        mock_pending.return_value = []
        mock_recent.return_value = []
        mock_summary.return_value = None
        mock_perf.return_value = []

        yield {
            "insert_alert": mock_insert,
            "get_alert_by_signal_id": mock_get,
            "get_alerts": mock_list,
            "get_alerts_count": mock_count,
            "update_alert_outcome": mock_update,
            "get_pending_alerts": mock_pending,
            "get_recent_alerts": mock_recent,
            "get_cached_summary": mock_summary,
            "get_performance_by_market_and_expiry": mock_perf,
        }
