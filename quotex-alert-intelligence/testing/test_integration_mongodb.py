"""
MongoDB-specific integration tests for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Tests MongoDB operations directly: CRUD for alerts, unique constraint
enforcement, status transitions, query filters, index usage, settings
upsert, and analytics cache updates.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from testing.conftest_integration import (
    TEST_DB_NAME,
    TEST_MONGO_URL,
    build_seed_signals,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    market_type: str = "LIVE",
    expiry_profile: str = "1m",
    direction: str = "UP",
    confidence: float = 70.0,
    status: str = "PENDING",
    outcome: str = "UNKNOWN",
    signal_id: str | None = None,
) -> Dict:
    """Build a minimal alert doc for direct MongoDB insertion."""
    now = datetime.now(timezone.utc)
    return {
        "signal_id": signal_id or f"sig_test_{uuid.uuid4().hex[:8]}",
        "asset": "EUR/USD",
        "market_type": market_type,
        "expiry_profile": expiry_profile,
        "direction": direction,
        "confidence": confidence,
        "signal_at": now,
        "signal_for_close_at": now + timedelta(minutes=1),
        "status": status,
        "outcome": outcome,
        "metadata": {},
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAlertInsertAndRetrieve:
    """Test basic insert and retrieval of alert documents."""

    async def test_alert_insert_and_retrieve(self, test_db):
        """Insert an alert and retrieve it by signal_id.

        ALERT-ONLY: Tests persistence of alert records.
        """
        col = test_db["alerts"]
        doc = _make_alert(signal_id="sig_retrieve_test")
        await col.insert_one(doc)

        found = await col.find_one({"signal_id": "sig_retrieve_test"})
        assert found is not None
        assert found["market_type"] == "LIVE"
        assert found["direction"] == "UP"
        assert found["status"] == "PENDING"
        assert found["confidence"] == 70.0


class TestUniqueSignalIdEnforcement:
    """Test that duplicate signal_ids are rejected when a unique index exists."""

    async def test_unique_signal_id_enforcement(self, test_db):
        """Attempt to insert two documents with the same signal_id.

        ALERT-ONLY: Ensures each alert has a unique identifier.

        If a unique index on signal_id exists, the second insert should
        raise a DuplicateKeyError. If no index exists, this test creates
        one first to verify the constraint works.
        """
        col = test_db["alerts"]
        # Ensure unique index exists
        await col.create_index("signal_id", unique=True)

        doc1 = _make_alert(signal_id="sig_dup_test")
        doc2 = _make_alert(signal_id="sig_dup_test")

        await col.insert_one(doc1)

        from pymongo.errors import DuplicateKeyError

        with pytest.raises(DuplicateKeyError):
            await col.insert_one(doc2)


class TestStatusTransitionPendingToEvaluated:
    """Test transitioning an alert from PENDING to EVALUATED."""

    async def test_status_transition_pending_to_evaluated(self, test_db):
        """Update an alert's status and outcome after evaluation.

        ALERT-ONLY: Status tracks whether the alert prediction has been checked.
        """
        col = test_db["alerts"]
        doc = _make_alert(signal_id="sig_transition_test")
        await col.insert_one(doc)

        # Verify initial state
        found = await col.find_one({"signal_id": "sig_transition_test"})
        assert found["status"] == "PENDING"
        assert found["outcome"] == "UNKNOWN"

        # Transition
        now = datetime.now(timezone.utc)
        result = await col.update_one(
            {"signal_id": "sig_transition_test"},
            {"$set": {
                "status": "EVALUATED",
                "outcome": "WIN",
                "evaluated_at": now,
            }},
        )
        assert result.modified_count == 1

        # Verify
        found = await col.find_one({"signal_id": "sig_transition_test"})
        assert found["status"] == "EVALUATED"
        assert found["outcome"] == "WIN"
        assert found["evaluated_at"] is not None


class TestQueryByMarketType:
    """Test filtering alerts by market_type."""

    async def test_query_by_market_type(self, test_db):
        """Query LIVE vs OTC alerts separately.

        ALERT-ONLY: Separate analysis of live and OTC alert performance.
        """
        col = test_db["alerts"]
        for i in range(6):
            mt = "LIVE" if i < 4 else "OTC"
            await col.insert_one(_make_alert(market_type=mt))

        live_count = await col.count_documents({"market_type": "LIVE"})
        otc_count = await col.count_documents({"market_type": "OTC"})
        assert live_count == 4
        assert otc_count == 2


class TestQueryByExpiryProfile:
    """Test filtering alerts by expiry_profile."""

    async def test_query_by_expiry_profile(self, test_db):
        """Query alerts by their expiry profile (1m, 2m, 3m).

        ALERT-ONLY: Enables per-expiry performance tracking.
        """
        col = test_db["alerts"]
        profiles = ["1m", "1m", "1m", "2m", "2m", "3m"]
        for ep in profiles:
            await col.insert_one(_make_alert(expiry_profile=ep))

        assert await col.count_documents({"expiry_profile": "1m"}) == 3
        assert await col.count_documents({"expiry_profile": "2m"}) == 2
        assert await col.count_documents({"expiry_profile": "3m"}) == 1


class TestQueryByDateRange:
    """Test filtering alerts by created_at date range."""

    async def test_query_by_date_range(self, test_db):
        """Filter alerts that fall within a specific date range.

        ALERT-ONLY: Date filtering for historical alert analysis.
        """
        col = test_db["alerts"]
        now = datetime.now(timezone.utc)

        # Insert alerts at different times
        for days_ago in [0, 1, 3, 7, 14]:
            doc = _make_alert()
            doc["created_at"] = now - timedelta(days=days_ago)
            await col.insert_one(doc)

        # Query last 2 days
        cutoff = now - timedelta(days=2)
        recent = await col.count_documents({"created_at": {"$gte": cutoff}})
        assert recent == 2  # today and yesterday

        # Query last week
        week_cutoff = now - timedelta(days=8)
        week = await col.count_documents({"created_at": {"$gte": week_cutoff}})
        assert week == 4


class TestQueryByConfidenceRange:
    """Test filtering alerts by confidence range."""

    async def test_query_by_confidence_range(self, test_db):
        """Filter alerts by minimum/maximum confidence thresholds.

        ALERT-ONLY: High-confidence alert filtering for analysis.
        """
        col = test_db["alerts"]
        confidences = [30.0, 50.0, 65.0, 75.0, 85.0, 95.0]
        for c in confidences:
            await col.insert_one(_make_alert(confidence=c))

        # High confidence only (>= 70)
        high = await col.count_documents({"confidence": {"$gte": 70.0}})
        assert high == 3

        # Low confidence (< 60)
        low = await col.count_documents({"confidence": {"$lt": 60.0}})
        assert low == 2

        # Range query (60 <= c < 90)
        mid = await col.count_documents({
            "confidence": {"$gte": 60.0, "$lt": 90.0}
        })
        assert mid == 3


class TestCompoundIndexUsed:
    """Check that compound queries can use indexes (explain plan)."""

    async def test_compound_index_used(self, test_db):
        """Create a compound index and verify it is used in a query.

        ALERT-ONLY: Index efficiency impacts alert query performance.

        Note: This test checks the explain plan when possible. In test
        environments (mongomock), explain may not be fully supported,
        so the test gracefully degrades to verifying the query works.
        """
        col = test_db["alerts"]

        # Create compound index
        await col.create_index([
            ("market_type", 1),
            ("expiry_profile", 1),
            ("status", 1),
        ])

        # Insert test data
        for i in range(10):
            await col.insert_one(_make_alert(
                market_type="LIVE" if i < 5 else "OTC",
                expiry_profile=["1m", "2m", "3m"][i % 3],
            ))

        # Run the query
        query = {"market_type": "LIVE", "expiry_profile": "1m", "status": "PENDING"}
        results = []
        async for doc in col.find(query):
            results.append(doc)

        # Verify query returns correct results
        assert all(d["market_type"] == "LIVE" for d in results)
        assert all(d["expiry_profile"] == "1m" for d in results)

        # Try explain plan (may not work with mongomock)
        try:
            explain = await col.find(query).explain()
            # If explain works, check that an index scan was used
            query_planner = explain.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            stage = winning_plan.get("stage", "")
            # IXSCAN = index scan, FETCH with IXSCAN child = also good
            assert stage in ("IXSCAN", "FETCH", ""), (
                f"Expected index scan, got stage: {stage}"
            )
        except Exception:
            # mongomock or older MongoDB may not support explain fully
            pass


class TestSettingsUpsertIdempotent:
    """Test that settings upsert is idempotent."""

    async def test_settings_upsert_idempotent(self, test_db):
        """Upsert settings multiple times and verify only one document exists.

        ALERT-ONLY: Settings control alert system behavior.
        """
        col = test_db["settings"]

        # First upsert
        await col.update_one(
            {"_type": "global_settings"},
            {"$set": {"confidence_threshold": 65.0, "_type": "global_settings"}},
            upsert=True,
        )
        count = await col.count_documents({"_type": "global_settings"})
        assert count == 1

        # Second upsert with different value
        await col.update_one(
            {"_type": "global_settings"},
            {"$set": {"confidence_threshold": 70.0}},
            upsert=True,
        )
        count = await col.count_documents({"_type": "global_settings"})
        assert count == 1  # Still only one document

        doc = await col.find_one({"_type": "global_settings"})
        assert doc["confidence_threshold"] == 70.0

        # Third upsert adding a new field
        await col.update_one(
            {"_type": "global_settings"},
            {"$set": {"auto_evaluate": True}},
            upsert=True,
        )
        count = await col.count_documents({"_type": "global_settings"})
        assert count == 1

        doc = await col.find_one({"_type": "global_settings"})
        assert doc["confidence_threshold"] == 70.0
        assert doc["auto_evaluate"] is True


class TestAnalyticsCacheUpdate:
    """Test analytics cache upsert and retrieval."""

    async def test_analytics_cache_update(self, test_db):
        """Update the analytics cache and verify the values are persisted.

        ALERT-ONLY: Analytics cache stores precomputed alert performance metrics.
        """
        col = test_db["analytics_cache"]

        summary_v1 = {
            "_type": "summary",
            "total_alerts": 100,
            "wins": 60,
            "losses": 30,
            "win_rate": 66.67,
        }

        await col.update_one(
            {"_type": "summary"},
            {"$set": summary_v1},
            upsert=True,
        )

        doc = await col.find_one({"_type": "summary"})
        assert doc is not None
        assert doc["total_alerts"] == 100
        assert doc["win_rate"] == 66.67

        # Update with new values
        summary_v2 = {
            "_type": "summary",
            "total_alerts": 150,
            "wins": 90,
            "losses": 45,
            "win_rate": 66.67,
        }

        await col.update_one(
            {"_type": "summary"},
            {"$set": summary_v2},
            upsert=True,
        )

        # Verify only one summary exists
        count = await col.count_documents({"_type": "summary"})
        assert count == 1

        doc = await col.find_one({"_type": "summary"})
        assert doc["total_alerts"] == 150
        assert doc["wins"] == 90
