"""
Integration test fixtures for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Provides fixtures for integration tests that use a real test MongoDB
(via mongomock or a dedicated test database). These fixtures ensure
clean state between tests and seed realistic test data.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict, List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Attempt to use mongomock for an in-process mock, fall back to a real
# test database if mongomock-motor is not installed.
# ---------------------------------------------------------------------------
try:
    import mongomock
    from mongomock.mongo_client import MongoClient as MockSyncClient

    USE_MONGOMOCK = True
except ImportError:
    USE_MONGOMOCK = False

from motor.motor_asyncio import AsyncIOMotorClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEST_DB_NAME = "quotex_alerts_test"
TEST_MONGO_URL = "mongodb://localhost:27017"

# Collections used by the application
COLLECTIONS = ["alerts", "settings", "analytics_cache", "sessions"]


# ---------------------------------------------------------------------------
# MongoDB fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mongo_url() -> str:
    """Return the MongoDB connection URL for testing."""
    return TEST_MONGO_URL


@pytest_asyncio.fixture(scope="session")
async def test_mongo_client(mongo_url: str) -> AsyncGenerator[AsyncIOMotorClient, None]:
    """Create a Motor async client pointing to the test database.

    ALERT-ONLY: This client is used exclusively for reading / writing
    alert and analytics data. No trade execution occurs.
    """
    client = AsyncIOMotorClient(mongo_url)
    yield client
    client.close()


@pytest_asyncio.fixture(scope="session")
async def test_db(test_mongo_client: AsyncIOMotorClient):
    """Return the test database instance."""
    return test_mongo_client[TEST_DB_NAME]


@pytest_asyncio.fixture(autouse=True)
async def clean_collections(test_db) -> None:
    """Drop all known collections before each test to ensure clean state.

    This runs automatically before every test function so that tests
    are fully isolated from one another.
    """
    for col_name in COLLECTIONS:
        await test_db[col_name].delete_many({})


# ---------------------------------------------------------------------------
# Seed data helpers
# ---------------------------------------------------------------------------


def _make_signal_doc(
    index: int,
    market_type: str,
    expiry_profile: str,
    direction: str,
    confidence: float,
    status: str,
    outcome: str,
) -> Dict:
    """Build a single alert document matching the schema used by alerts_repo."""
    now = datetime.now(timezone.utc)
    signal_id = f"sig_test_{uuid.uuid4().hex[:8]}"
    return {
        "signal_id": signal_id,
        "asset": "EUR/USD",
        "market_type": market_type,
        "expiry_profile": expiry_profile,
        "direction": direction,
        "confidence": confidence,
        "signal_at": now - timedelta(minutes=index),
        "signal_for_close_at": now - timedelta(minutes=index - 1),
        "status": status,
        "outcome": outcome,
        "metadata": {"test_index": index},
        "created_at": now - timedelta(minutes=index),
    }


def build_seed_signals(count: int = 20) -> List[Dict]:
    """Generate a list of mixed signal documents for seeding.

    Produces a mix of:
      - WIN signals (evaluated)
      - LOSS signals (evaluated)
      - NEUTRAL signals (evaluated)
      - PENDING signals (not yet evaluated)

    ALERT-ONLY: These are alert records, not trade records.

    Args:
        count: Total number of signals to generate (default 20).

    Returns:
        List of alert document dicts ready for MongoDB insertion.
    """
    signals: List[Dict] = []
    market_types = ["LIVE", "OTC"]
    expiry_profiles = ["1m", "2m", "3m"]
    directions = ["UP", "DOWN"]

    for i in range(count):
        mt = market_types[i % 2]
        ep = expiry_profiles[i % 3]
        direction = directions[i % 2]
        confidence = 50.0 + (i * 2.5) % 50

        # Distribute outcomes: 8 WIN, 5 LOSS, 3 NEUTRAL, 4 PENDING
        if i < 8:
            status, outcome = "EVALUATED", "WIN"
        elif i < 13:
            status, outcome = "EVALUATED", "LOSS"
        elif i < 16:
            status, outcome = "EVALUATED", "NEUTRAL"
        else:
            status, outcome = "PENDING", "UNKNOWN"

        signals.append(
            _make_signal_doc(i, mt, ep, direction, confidence, status, outcome)
        )

    return signals


@pytest_asyncio.fixture()
async def seeded_db(test_db) -> List[Dict]:
    """Seed the test database with 20 mixed signals and return them.

    ALERT-ONLY: Seeds alert records for analytical validation.
    """
    signals = build_seed_signals(20)
    await test_db["alerts"].insert_many(signals)
    return signals


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------


def _patch_app_db(app, test_db):
    """Monkey-patch the app's mongo module to use the test database.

    This replaces the production database reference with the test database
    so that the FastAPI app reads and writes to test collections.
    """
    import app.db.mongo as mongo_module

    mongo_module._database = test_db
    mongo_module._client = test_db.client


@pytest_asyncio.fixture()
async def api_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX AsyncClient bound to the FastAPI app with test DB.

    ALERT-ONLY: The test client exercises alert endpoints, not trade endpoints.
    """
    # Import app lazily to avoid import-time side effects
    import sys
    import os

    backend_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "backend")
    )
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from app.main import app

    _patch_app_db(app, test_db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
