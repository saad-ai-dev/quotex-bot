"""
Shared fixtures for the Quotex Alert Monitoring backend test suite.
ALERT-ONLY system -- no trade execution logic is tested here.
"""

import asyncio
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_candle(open_: float, high: float, low: float, close: float, ts: float) -> Dict[str, Any]:
    """Build a single candle dict with OHLC + timestamp.
    All price values are treated as *offsets in pips* from a 1.0800 base.
    The helper converts them: base + offset * 0.0001.
    """
    base = 1.0800
    scale = 0.0001
    return {
        "open": base + open_ * scale,
        "high": base + high * scale,
        "low": base + low * scale,
        "close": base + close * scale,
        "timestamp": ts,
    }


# ---------------------------------------------------------------------------
# Candle fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_candles() -> List[Dict[str, Any]]:
    """30 uptrend candles with pronounced HH + HL swings.

    Wave 1 up  (0-3)   peak high ~40
    Pullback 1 (4-7)   trough low ~5
    Wave 2 up  (8-12)  peak high ~70
    Pullback 2 (13-16) trough low ~25
    Wave 3 up  (17-22) peak high ~110
    Pullback 3 (23-26) trough low ~55
    Final push (27-29) new high ~120

    With lookback=3 the swing detector should find clear peaks and troughs.
    """
    candles = [
        # --- Wave 1 up (0-3) ---
        _make_candle(0, 10, -2, 8, 1000),       # 0  move up
        _make_candle(8, 22, 6, 20, 1060),        # 1  strong bull
        _make_candle(20, 35, 18, 33, 1120),      # 2  continuation
        _make_candle(33, 40, 30, 36, 1180),      # 3  peak candle

        # --- Pullback 1 (4-7) ---
        _make_candle(36, 37, 25, 26, 1240),      # 4  pullback start
        _make_candle(26, 28, 12, 14, 1300),      # 5  deeper pull
        _make_candle(14, 16, 5, 8, 1360),        # 6  trough candle
        _make_candle(8, 18, 7, 16, 1420),        # 7  bounce

        # --- Wave 2 up (8-12) ---
        _make_candle(16, 30, 14, 28, 1480),      # 8  impulse
        _make_candle(28, 45, 26, 42, 1540),      # 9  strong
        _make_candle(42, 60, 40, 58, 1600),      # 10 continuation
        _make_candle(58, 70, 56, 65, 1660),      # 11 peak
        _make_candle(65, 68, 55, 57, 1720),      # 12 start pullback

        # --- Pullback 2 (13-16) ---
        _make_candle(57, 58, 40, 42, 1780),      # 13
        _make_candle(42, 44, 30, 32, 1840),      # 14
        _make_candle(32, 34, 25, 28, 1900),      # 15 trough
        _make_candle(28, 38, 26, 36, 1960),      # 16 bounce

        # --- Wave 3 up (17-22) ---
        _make_candle(36, 50, 34, 48, 2020),      # 17
        _make_candle(48, 65, 46, 62, 2080),      # 18
        _make_candle(62, 85, 60, 82, 2140),      # 19
        _make_candle(82, 100, 80, 97, 2200),     # 20
        _make_candle(97, 110, 95, 105, 2260),    # 21 peak
        _make_candle(105, 108, 88, 90, 2320),    # 22 start pull

        # --- Pullback 3 (23-26) ---
        _make_candle(90, 92, 70, 72, 2380),      # 23
        _make_candle(72, 74, 58, 60, 2440),      # 24
        _make_candle(60, 62, 55, 58, 2500),      # 25 trough
        _make_candle(58, 70, 56, 68, 2560),      # 26 bounce

        # --- Final push (27-29) ---
        _make_candle(68, 90, 66, 88, 2620),      # 27
        _make_candle(88, 110, 86, 108, 2680),    # 28
        _make_candle(108, 120, 106, 118, 2740),  # 29 new high
    ]
    return candles


@pytest.fixture
def sample_bearish_candles() -> List[Dict[str, Any]]:
    """30 downtrend candles with pronounced LH + LL swings (mirror of uptrend)."""
    candles = [
        # --- Wave 1 down (0-3) ---
        _make_candle(120, 122, 112, 114, 1000),   # 0
        _make_candle(114, 116, 100, 102, 1060),   # 1
        _make_candle(102, 104, 85, 88, 1120),     # 2
        _make_candle(88, 90, 78, 80, 1180),       # 3  low ~78

        # --- Pullback 1 up (4-8): peak at idx 6, high ~105 ---
        _make_candle(80, 85, 78, 83, 1240),       # 4
        _make_candle(83, 92, 81, 90, 1300),       # 5
        _make_candle(90, 105, 88, 100, 1360),     # 6  swing high ~105 (LH vs 122)
        _make_candle(100, 98, 85, 88, 1420),      # 7  drop
        _make_candle(88, 90, 75, 78, 1480),       # 8

        # --- Wave 2 down (9-12): lower low ---
        _make_candle(78, 80, 60, 62, 1540),       # 9
        _make_candle(62, 64, 45, 48, 1600),       # 10
        _make_candle(48, 50, 38, 40, 1660),       # 11 low ~38 (LL vs 78)
        _make_candle(40, 48, 37, 46, 1720),       # 12

        # --- Pullback 2 up (13-17): peak at idx 15, high ~80 ---
        _make_candle(46, 55, 44, 53, 1780),       # 13
        _make_candle(53, 65, 51, 63, 1840),       # 14
        _make_candle(63, 80, 61, 76, 1900),       # 15 swing high ~80 (LH vs 105)
        _make_candle(76, 74, 60, 62, 1960),       # 16 drop
        _make_candle(62, 64, 50, 52, 2020),       # 17

        # --- Wave 3 down (18-22): lower low ---
        _make_candle(52, 54, 35, 38, 2080),       # 18
        _make_candle(38, 40, 22, 25, 2140),       # 19
        _make_candle(25, 27, 10, 12, 2200),       # 20
        _make_candle(12, 14, 2, 5, 2260),         # 21 low ~2 (LL vs 38)
        _make_candle(5, 12, 1, 10, 2320),         # 22

        # --- Pullback 3 up (23-26): peak at idx 25, high ~45 ---
        _make_candle(10, 20, 8, 18, 2380),        # 23
        _make_candle(18, 30, 16, 28, 2440),       # 24
        _make_candle(28, 45, 26, 40, 2500),       # 25 swing high ~45 (LH vs 80)
        _make_candle(40, 38, 28, 30, 2560),       # 26 drop

        # --- Final drop (27-29): new low ---
        _make_candle(30, 32, 15, 18, 2620),       # 27
        _make_candle(18, 20, 5, 8, 2680),         # 28
        _make_candle(8, 10, -5, -2, 2740),        # 29 new low ~-5
    ]
    return candles


@pytest.fixture
def sample_choppy_candles() -> List[Dict[str, Any]]:
    """30 sideways/choppy candles oscillating around a mean with frequent direction changes."""
    base_offsets = [
        50, 52, 48, 51, 47, 53, 49, 52, 48, 50,
        53, 47, 51, 49, 52, 48, 50, 53, 47, 51,
        49, 52, 48, 50, 53, 47, 51, 49, 52, 48,
    ]
    candles = []
    for i, offset in enumerate(base_offsets):
        # Alternating bull/bear with small bodies, creating chop
        if i % 2 == 0:
            o = offset
            c = offset + 2
        else:
            o = offset + 2
            c = offset
        h = max(o, c) + 3
        l = min(o, c) - 3
        candles.append(_make_candle(o, h, l, c, 1000 + i * 60))
    return candles


@pytest.fixture
def sample_otc_candles() -> List[Dict[str, Any]]:
    """30 OTC-like candles with alternating patterns and spike reversals."""
    candles = []
    # Build alternating up/down candles with occasional spikes
    base = 50
    for i in range(30):
        if i % 2 == 0:
            # Bullish candle
            o = base
            c = base + 5
        else:
            # Bearish candle
            o = base + 5
            c = base

        # Add spike at index 14-15 (large range + reversal)
        if i == 14:
            o = base
            c = base + 20
            h = base + 25
            l = base - 2
            candles.append(_make_candle(o, h, l, c, 1000 + i * 60))
            continue
        if i == 15:
            o = base + 20
            c = base + 2
            h = base + 22
            l = base
            candles.append(_make_candle(o, h, l, c, 1000 + i * 60))
            continue

        h = max(o, c) + 3
        l = min(o, c) - 3
        candles.append(_make_candle(o, h, l, c, 1000 + i * 60))
    return candles


# ---------------------------------------------------------------------------
# Async HTTP client fixture for API tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client():
    """Provide an httpx.AsyncClient wired to the FastAPI test app.

    Patches MongoDB and APScheduler so no real connections are needed.
    ALERT-ONLY: Tests the monitoring API, not trade infrastructure.
    """
    # Patch MongoDB motor client and APScheduler before importing app
    with patch("app.main.AsyncIOMotorClient") as mock_motor, \
         patch("app.main.MONGO_URL", "mongodb://testhost:27017"), \
         patch("app.main.MONGO_DB_NAME", "test_db"):

        # Build a mock database that supports the operations used in lifespan
        mock_db = MagicMock()
        mock_collection = MagicMock()

        # create_index returns a coroutine
        mock_collection.create_index = AsyncMock(return_value="ok")
        mock_collection.count_documents = AsyncMock(return_value=0)

        # find() returns a chainable cursor whose to_list is async
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_collection.find = MagicMock(return_value=mock_cursor)

        # aggregate() for analytics
        mock_agg_cursor = MagicMock()
        mock_agg_cursor.to_list = AsyncMock(return_value=[])
        mock_collection.aggregate = MagicMock(return_value=mock_agg_cursor)

        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_db.command = AsyncMock(return_value={"ok": 1})

        mock_client_instance = MagicMock()
        mock_client_instance.__getitem__ = MagicMock(return_value=mock_db)
        mock_client_instance.close = MagicMock()
        mock_motor.return_value = mock_client_instance

        # Patch APScheduler to be a no-op
        with patch("app.main.AsyncIOScheduler", create=True) as mock_sched_cls:
            mock_scheduler = MagicMock()
            mock_scheduler.start = MagicMock()
            mock_scheduler.shutdown = MagicMock()
            mock_scheduler.add_job = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            # Also patch the import inside lifespan
            with patch.dict("sys.modules", {
                "apscheduler.schedulers.asyncio": MagicMock(AsyncIOScheduler=mock_sched_cls),
                "apscheduler.triggers.interval": MagicMock(IntervalTrigger=MagicMock()),
            }):
                # Now import the app (after patches are in place)
                from app.main import app

                # Override get_db dependency to return our mock
                from app.api.deps import get_db
                app.dependency_overrides[get_db] = lambda: mock_db

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    yield client

                app.dependency_overrides.clear()
