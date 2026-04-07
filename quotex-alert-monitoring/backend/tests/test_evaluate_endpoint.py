"""
End-to-end test for the /evaluate endpoint fix (BONUS gap).

Validates that the evaluate endpoint correctly compares actual_close
against entry_price instead of checking actual_close > 0.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_evaluate_compares_against_entry_price(async_client):
    """POST /{signal_id}/evaluate should compare actual_close vs entry_price."""
    # Set up mock to return a signal document with entry_price
    signal_doc = {
        "signal_id": "test-signal-001",
        "prediction_direction": "UP",
        "entry_price": 1.08500,
        "status": "PENDING",
        "confidence": 65.0,
        "bullish_score": 70.0,
        "bearish_score": 35.0,
    }

    # We need to mock the collection operations
    with patch("app.api.routes.signals.SignalOrchestrator"):
        from app.api.deps import get_db

        mock_db = MagicMock()
        mock_collection = MagicMock()

        # find_one returns our signal doc
        mock_collection.find_one = AsyncMock(side_effect=[
            dict(signal_doc),  # First call (get doc to check)
            {**signal_doc, "status": "EVALUATED", "outcome": "LOSS", "actual_close": 1.08480},  # Second call (return updated)
        ])
        mock_collection.update_one = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        # Override the DB dependency
        async_client._transport.app.dependency_overrides[get_db] = lambda: mock_db

        # Price went DOWN (1.08480 < 1.08500 entry) but prediction was UP → LOSS
        response = await async_client.post(
            "/api/signals/test-signal-001/evaluate",
            json={"actual_close": 1.08480},
        )

        assert response.status_code == 200

        # Verify update_one was called with the correct outcome
        update_call = mock_collection.update_one.call_args
        update_fields = update_call[0][1]["$set"]
        assert update_fields["outcome"] == "LOSS", \
            f"Expected LOSS (close < entry for UP), got {update_fields['outcome']}"
        assert update_fields["status"] == "EVALUATED"


@pytest.mark.asyncio
async def test_evaluate_up_win(async_client):
    """UP prediction with actual_close > entry_price should be WIN."""
    signal_doc = {
        "signal_id": "test-signal-002",
        "prediction_direction": "UP",
        "entry_price": 1.08500,
        "status": "PENDING",
    }

    with patch("app.api.routes.signals.SignalOrchestrator"):
        from app.api.deps import get_db

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(side_effect=[
            dict(signal_doc),
            {**signal_doc, "status": "EVALUATED", "outcome": "WIN", "actual_close": 1.08520},
        ])
        mock_collection.update_one = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        async_client._transport.app.dependency_overrides[get_db] = lambda: mock_db

        response = await async_client.post(
            "/api/signals/test-signal-002/evaluate",
            json={"actual_close": 1.08520},
        )

        assert response.status_code == 200
        update_fields = mock_collection.update_one.call_args[0][1]["$set"]
        assert update_fields["outcome"] == "WIN"


@pytest.mark.asyncio
async def test_evaluate_missing_entry_price_returns_unknown(async_client):
    """When entry_price is None, outcome should be UNKNOWN."""
    signal_doc = {
        "signal_id": "test-signal-003",
        "prediction_direction": "DOWN",
        "entry_price": None,
        "status": "PENDING",
    }

    with patch("app.api.routes.signals.SignalOrchestrator"):
        from app.api.deps import get_db

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(side_effect=[
            dict(signal_doc),
            {**signal_doc, "status": "EVALUATED", "outcome": "UNKNOWN"},
        ])
        mock_collection.update_one = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        async_client._transport.app.dependency_overrides[get_db] = lambda: mock_db

        response = await async_client.post(
            "/api/signals/test-signal-003/evaluate",
            json={"actual_close": 1.08480},
        )

        assert response.status_code == 200
        update_fields = mock_collection.update_one.call_args[0][1]["$set"]
        assert update_fields["outcome"] == "UNKNOWN"
