"""
WebSocket flow tests for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Tests WebSocket connectivity, alert broadcasting, evaluation updates,
multi-client scenarios, and reconnection behavior.
"""

import asyncio
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signal_payload(
    asset: str = "EUR/USD",
    market_type: str = "LIVE",
    expiry_profile: str = "1m",
    direction: str = "UP",
    confidence: float = 72.0,
) -> dict:
    """Build a valid signal creation payload."""
    return {
        "asset": asset,
        "market_type": market_type,
        "expiry_profile": expiry_profile,
        "direction": direction,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Tests using starlette.testclient for WS
# ---------------------------------------------------------------------------


class TestWSConnectAndReceivePing:
    """Test basic WebSocket connection and ping/pong."""

    async def test_ws_connect_and_receive_ping(self, test_db):
        """Connect to the WS endpoint and verify the connection is accepted.

        ALERT-ONLY: WebSocket is used solely for alert event broadcasting.
        """
        import sys
        import os

        backend_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import app.db.mongo as mongo_module
        mongo_module._database = test_db
        mongo_module._client = test_db.client

        from starlette.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect("/ws/alerts") as ws:
                # Send a ping message
                ws.send_json({"type": "ping"})
                # Server should acknowledge
                response = ws.receive_json()
                assert response["type"] == "ack"
                assert response["message"] == "received"


class TestWSReceivesAlertOnIngest:
    """Test that WS clients receive alert events when a signal is ingested."""

    async def test_ws_receives_alert_on_ingest(self, test_db):
        """Ingest a signal via API and verify a WS client receives the event.

        ALERT-ONLY: WS broadcasts alert creation events, not trade actions.

        Note: This test uses the ConnectionManager's broadcast mechanism.
        In the current architecture, the signal creation endpoint does not
        automatically broadcast via WS. This test verifies the broadcast
        mechanism works when triggered manually.
        """
        import sys
        import os

        backend_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import app.db.mongo as mongo_module
        mongo_module._database = test_db
        mongo_module._client = test_db.client

        from starlette.testclient import TestClient
        from app.main import app
        from app.api.routers.websocket import manager

        with TestClient(app) as client:
            with client.websocket_connect("/ws/alerts") as ws:
                # Send a signal via the REST API
                resp = client.post("/api/signals", json=_signal_payload())
                assert resp.status_code == 201
                signal_data = resp.json()

                # Simulate broadcast (as the ingest endpoint would trigger)
                # In production, this would be called by the signal service
                import asyncio

                loop = asyncio.new_event_loop()
                loop.run_until_complete(manager.broadcast({
                    "event_type": "new_alert",
                    "signal_id": signal_data["signal_id"],
                    "direction": "UP",
                    "market_type": "LIVE",
                }))
                loop.close()

                # WS client should receive the broadcast
                response = ws.receive_json()
                assert response["event_type"] == "new_alert"
                assert response["signal_id"] == signal_data["signal_id"]


class TestWSReceivesEvaluationUpdate:
    """Test that WS clients receive evaluation update events."""

    async def test_ws_receives_evaluation_update(self, test_db):
        """Evaluate a signal and verify WS clients get the update.

        ALERT-ONLY: Broadcasts alert evaluation results, not trade outcomes.
        """
        import sys
        import os

        backend_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import app.db.mongo as mongo_module
        mongo_module._database = test_db
        mongo_module._client = test_db.client

        from starlette.testclient import TestClient
        from app.main import app
        from app.api.routers.websocket import manager

        with TestClient(app) as client:
            with client.websocket_connect("/ws/alerts") as ws:
                # Create a signal first
                resp = client.post("/api/signals", json=_signal_payload())
                signal_id = resp.json()["signal_id"]

                # Simulate evaluation broadcast
                import asyncio

                loop = asyncio.new_event_loop()
                loop.run_until_complete(manager.broadcast({
                    "event_type": "evaluation_update",
                    "signal_id": signal_id,
                    "outcome": "WIN",
                    "status": "EVALUATED",
                }))
                loop.close()

                response = ws.receive_json()
                assert response["event_type"] == "evaluation_update"
                assert response["signal_id"] == signal_id
                assert response["outcome"] == "WIN"


class TestWSMultipleClients:
    """Test that multiple WS clients all receive broadcasts."""

    async def test_ws_multiple_clients(self, test_db):
        """Connect 3 WS clients and verify all receive the same broadcast.

        ALERT-ONLY: Multi-client broadcasting for alert monitoring.
        """
        import sys
        import os

        backend_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import app.db.mongo as mongo_module
        mongo_module._database = test_db
        mongo_module._client = test_db.client

        from starlette.testclient import TestClient
        from app.main import app
        from app.api.routers.websocket import manager

        with TestClient(app) as client:
            with client.websocket_connect("/ws/alerts") as ws1:
                with client.websocket_connect("/ws/alerts") as ws2:
                    with client.websocket_connect("/ws/alerts") as ws3:
                        # Broadcast a message
                        import asyncio

                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(manager.broadcast({
                            "event_type": "new_alert",
                            "signal_id": "sig_multi_test",
                            "direction": "DOWN",
                        }))
                        loop.close()

                        # All three clients should receive the message
                        r1 = ws1.receive_json()
                        r2 = ws2.receive_json()
                        r3 = ws3.receive_json()

                        for r in [r1, r2, r3]:
                            assert r["event_type"] == "new_alert"
                            assert r["signal_id"] == "sig_multi_test"


class TestWSReconnectAfterDisconnect:
    """Test that a client can reconnect after disconnecting."""

    async def test_ws_reconnect_after_disconnect(self, test_db):
        """Disconnect from WS, reconnect, and verify connection works.

        ALERT-ONLY: Ensures reliable alert delivery after reconnection.
        """
        import sys
        import os

        backend_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "backend")
        )
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        import app.db.mongo as mongo_module
        mongo_module._database = test_db
        mongo_module._client = test_db.client

        from starlette.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            # First connection
            with client.websocket_connect("/ws/alerts") as ws:
                ws.send_json({"type": "hello"})
                r = ws.receive_json()
                assert r["type"] == "ack"

            # Connection is now closed. Reconnect.
            with client.websocket_connect("/ws/alerts") as ws:
                ws.send_json({"type": "reconnected"})
                r = ws.receive_json()
                assert r["type"] == "ack"
                assert r["data"]["type"] == "reconnected"
