"""
Tests for the /health endpoint.

ALERT-ONLY system -- health check verifies service and database status.
No trade execution endpoints exist.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    """Health endpoint returns 200 with status 'ok'.
    ALERT-ONLY: confirms the alert service is running.
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_response_schema(async_client):
    """Health response contains all required fields.
    ALERT-ONLY: service metadata, not trade status.
    """
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()

    # Required fields in the health response
    assert "status" in data
    assert "service" in data
    assert "database" in data

    # Verify types
    assert isinstance(data["status"], str)
    assert isinstance(data["service"], str)
    assert isinstance(data["database"], str)

    # Service name must be correct
    assert data["service"] == "quotex-alert-intelligence"

    # Database should report a status string
    assert data["database"] in ("connected", "disconnected")
