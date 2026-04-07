from app.api.routes.analytics import DIRECTIONAL_FILTER
from app.api.routes.history import _build_history_query


def test_history_query_defaults_to_executed_only_when_requested():
    query = _build_history_query(executed_only=True)
    assert query["was_executed"] is True


def test_history_query_combines_filters_with_execution_truth():
    query = _build_history_query(
        market_type="otc",
        expiry_profile="2m",
        outcome="win",
        min_confidence=60,
        executed_only=True,
    )

    assert query == {
        "market_type": "OTC",
        "expiry_profile": "2m",
        "outcome": "WIN",
        "confidence": {"$gte": 60},
        "was_executed": True,
    }


def test_analytics_directional_filter_requires_real_execution():
    assert DIRECTIONAL_FILTER["prediction_direction"] == {"$in": ["UP", "DOWN"]}
    assert DIRECTIONAL_FILTER["was_executed"] is True
