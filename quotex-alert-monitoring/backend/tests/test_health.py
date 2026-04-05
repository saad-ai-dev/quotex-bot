"""
Tests for the /health endpoint.
ALERT-ONLY: Verifies monitoring system health reporting, not trade engine status.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    """GET /health returns 200 with status 'ok'."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_response_schema(async_client):
    """Health response contains required fields: status, service, db_status."""
    resp = await async_client.get("/health")
    data = resp.json()
    assert "status" in data
    assert "service" in data
    # The route uses 'db_status' rather than 'database'; verify it exists
    assert "db_status" in data
    assert data["service"] == "Quotex Alert Monitoring API"
