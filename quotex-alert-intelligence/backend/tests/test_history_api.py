"""
Tests for history and analytics API endpoints.

ALERT-ONLY system -- history endpoints return evaluated alert predictions
and performance analytics. No trade execution data exists.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import Status, Outcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert_doc(
    signal_id: str,
    market_type: str = "LIVE",
    expiry_profile: str = "1m",
    prediction_direction: str = "UP",
    confidence: float = 75.0,
    status: str = Status.EVALUATED,
    outcome: str = Outcome.WIN,
):
    """Build a minimal alert document for testing.
    ALERT-ONLY: represents a prediction record.
    """
    return {
        "signal_id": signal_id,
        "market_type": market_type,
        "expiry_profile": expiry_profile,
        "prediction_direction": prediction_direction,
        "confidence": confidence,
        "status": status,
        "outcome": outcome,
        "bullish_score": 65.0,
        "bearish_score": 25.0,
        "reasons": ["test reason"],
    }


# ---------------------------------------------------------------------------
# History endpoint tests
# ---------------------------------------------------------------------------

class TestGetHistory:
    """Tests for GET /api/history endpoint. ALERT-ONLY."""

    @pytest.mark.asyncio
    async def test_get_history_empty(self, async_client):
        """Returns empty list when no signals exist.
        ALERT-ONLY: empty history means no alerts have been generated.
        """
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=[])
            mock_repo.get_alerts_count = AsyncMock(return_value=0)

            response = await async_client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_history_with_signals(self, async_client):
        """Returns inserted signals.
        ALERT-ONLY: history shows past prediction records.
        """
        alerts = [
            _make_alert_doc("sig_001", outcome=Outcome.WIN),
            _make_alert_doc("sig_002", outcome=Outcome.LOSS),
            _make_alert_doc("sig_003", outcome=Outcome.WIN),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=alerts)
            mock_repo.get_alerts_count = AsyncMock(return_value=3)

            response = await async_client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
        assert data["items"][0]["signal_id"] == "sig_001"
        assert data["items"][1]["signal_id"] == "sig_002"

    @pytest.mark.asyncio
    async def test_filter_wins(self, async_client):
        """Only returns WIN outcomes when filtered.
        ALERT-ONLY: filtering by outcome for accuracy analysis.
        """
        wins = [
            _make_alert_doc("sig_w1", outcome=Outcome.WIN),
            _make_alert_doc("sig_w2", outcome=Outcome.WIN),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=wins)
            mock_repo.get_alerts_count = AsyncMock(return_value=2)

            response = await async_client.get("/api/history?outcome=WIN")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(item["outcome"] == Outcome.WIN for item in data["items"])

    @pytest.mark.asyncio
    async def test_filter_losses(self, async_client):
        """Only returns LOSS outcomes when filtered.
        ALERT-ONLY: filtering by losses for analysis.
        """
        losses = [
            _make_alert_doc("sig_l1", outcome=Outcome.LOSS),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=losses)
            mock_repo.get_alerts_count = AsyncMock(return_value=1)

            response = await async_client.get("/api/history?outcome=LOSS")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["outcome"] == Outcome.LOSS

    @pytest.mark.asyncio
    async def test_filter_pending(self, async_client):
        """Recent endpoint returns pending signals.
        ALERT-ONLY: pending means not yet evaluated.
        """
        pending = [
            _make_alert_doc("sig_p1", status=Status.PENDING, outcome=None),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_recent_alerts = AsyncMock(return_value=pending)

            response = await async_client.get("/api/history/recent?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == Status.PENDING

    @pytest.mark.asyncio
    async def test_filter_by_market_type(self, async_client):
        """Filter history by market_type=LIVE or OTC.
        ALERT-ONLY: separate tracking for LIVE and OTC markets.
        """
        live_alerts = [
            _make_alert_doc("sig_live1", market_type="LIVE"),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=live_alerts)
            mock_repo.get_alerts_count = AsyncMock(return_value=1)

            response = await async_client.get("/api/history?market_type=LIVE")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["market_type"] == "LIVE"

    @pytest.mark.asyncio
    async def test_filter_by_expiry(self, async_client):
        """Filter history by expiry_profile.
        ALERT-ONLY: filter by 1m/2m/3m prediction windows.
        """
        alerts_2m = [
            _make_alert_doc("sig_2m1", expiry_profile="2m"),
            _make_alert_doc("sig_2m2", expiry_profile="2m"),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=alerts_2m)
            mock_repo.get_alerts_count = AsyncMock(return_value=2)

            response = await async_client.get("/api/history?expiry_profile=2m")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert all(item["expiry_profile"] == "2m" for item in data["items"])

    @pytest.mark.asyncio
    async def test_pagination(self, async_client):
        """Skip and limit pagination works.
        ALERT-ONLY: paginating through prediction history.
        """
        # Simulate returning 2 items for skip=5, limit=2
        page_alerts = [
            _make_alert_doc("sig_page1"),
            _make_alert_doc("sig_page2"),
        ]
        with patch("app.api.routers.history.alerts_repo") as mock_repo:
            mock_repo.get_alerts = AsyncMock(return_value=page_alerts)
            mock_repo.get_alerts_count = AsyncMock(return_value=50)

            response = await async_client.get("/api/history?skip=5&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 50
        assert data["skip"] == 5
        assert data["limit"] == 2


# ---------------------------------------------------------------------------
# Analytics endpoint tests
# ---------------------------------------------------------------------------

class TestAnalytics:
    """Tests for analytics endpoints. ALERT-ONLY."""

    @pytest.mark.asyncio
    async def test_analytics_summary(self, async_client):
        """Analytics summary returns correct aggregations.
        ALERT-ONLY: tracks prediction accuracy, not trade P&L.
        """
        with patch("app.api.routers.analytics.analytics_repo") as mock_analytics, \
             patch("app.api.routers.analytics.alerts_repo") as mock_alerts:

            # No cached summary, so it computes live
            mock_analytics.get_cached_summary = AsyncMock(return_value=None)
            mock_alerts.get_alerts_count = AsyncMock(side_effect=[
                100,  # total
                80,   # evaluated
                50,   # wins
                20,   # losses
            ])

            response = await async_client.get("/api/analytics/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_alerts"] == 100
        assert data["evaluated_alerts"] == 80
        assert data["pending_alerts"] == 20  # 100 - 80
        assert data["wins"] == 50
        assert data["losses"] == 20
        # win_rate = 50 / (50+20) * 100 = 71.43
        assert data["win_rate"] == pytest.approx(71.43, abs=0.01)

    @pytest.mark.asyncio
    async def test_analytics_performance(self, async_client):
        """Performance breakdown returns per-market-per-expiry groups.
        ALERT-ONLY: groups prediction performance by market and expiry.
        """
        performance_data = [
            {
                "market_type": "LIVE",
                "expiry_profile": "1m",
                "total": 40,
                "wins": 25,
                "losses": 10,
                "neutrals": 5,
                "avg_confidence": 72.5,
                "win_rate": 71.43,
            },
            {
                "market_type": "OTC",
                "expiry_profile": "2m",
                "total": 30,
                "wins": 12,
                "losses": 15,
                "neutrals": 3,
                "avg_confidence": 65.0,
                "win_rate": 44.44,
            },
        ]
        with patch("app.api.routers.analytics.analytics_repo") as mock_analytics:
            mock_analytics.get_performance_by_market_and_expiry = AsyncMock(
                return_value=performance_data
            )

            response = await async_client.get("/api/analytics/performance")

        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert len(data["groups"]) == 2

        live_group = data["groups"][0]
        assert live_group["market_type"] == "LIVE"
        assert live_group["expiry_profile"] == "1m"
        assert live_group["wins"] == 25
        assert live_group["losses"] == 10
        assert live_group["win_rate"] == pytest.approx(71.43, abs=0.01)

        otc_group = data["groups"][1]
        assert otc_group["market_type"] == "OTC"
        assert otc_group["expiry_profile"] == "2m"
        assert otc_group["wins"] == 12
        assert otc_group["win_rate"] == pytest.approx(44.44, abs=0.01)
