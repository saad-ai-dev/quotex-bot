"""
WebSocket routes - ALERT-ONLY monitoring system.
Provides real-time alert broadcast to connected dashboard clients.
No trade execution commands over WebSocket.
"""

import asyncio
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections for alert broadcasting.

    ALERT-ONLY: Broadcasts signal alerts and status updates to dashboards.
    No trade orders are sent over WebSocket.
    """

    def __init__(self) -> None:
        self._active_connections: List[WebSocket] = []

    @property
    def active_count(self) -> int:
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info(
            "WebSocket client connected. Active connections: %d",
            self.active_count,
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active list."""
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected. Active connections: %d",
            self.active_count,
        )

    async def broadcast(self, message: dict) -> None:
        """Broadcast a JSON message to all connected clients.

        ALERT-ONLY: Used to push new signal alerts to all dashboards.
        Silently drops connections that have gone stale.
        """
        stale: List[WebSocket] = []
        for connection in self._active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)

        for ws in stale:
            self.disconnect(ws)

        if stale:
            logger.debug("Cleaned up %d stale WebSocket connections", len(stale))

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """Send a JSON message to a specific connected client."""
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.warning("Failed to send personal WS message: %s", exc)
            self.disconnect(websocket)


# ------------------------------------------------------------------
# Singleton manager instance for use across the application
# ------------------------------------------------------------------
manager = ConnectionManager()


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert streaming.

    ALERT-ONLY: Clients receive signal alerts and can send ping/pong
    keepalive messages. No trade commands are accepted.

    Protocol:
        - Server sends JSON alert objects on new signals.
        - Client may send {"type": "ping"} to keep the connection alive.
        - Server responds with {"type": "pong"}.
        - Any other client message is acknowledged but ignored.
    """
    await manager.connect(websocket)

    try:
        while True:
            # Wait for client messages (ping/pong keepalive)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0,  # 60s read timeout
                )
            except asyncio.TimeoutError:
                # Send server-side ping to check connection liveness
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue

            # Handle client messages
            msg_type = data.get("type", "") if isinstance(data, dict) else ""

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "pong":
                # Client responded to our ping, connection is alive
                pass
            else:
                # Unknown message type, acknowledge
                logger.debug("Received unknown WS message type: %s", msg_type)
                await websocket.send_json({
                    "type": "ack",
                    "message": "ALERT-ONLY system - no commands accepted",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected gracefully")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        manager.disconnect(websocket)
