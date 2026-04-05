"""WebSocket endpoint for real-time alert push notifications."""

import asyncio
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket connected. Total connections: %d",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket disconnected. Total connections: %d",
            len(self.active_connections),
        )

    async def broadcast(self, message: str) -> None:
        """Send a message to every connected client.

        Silently drops connections that are no longer open.
        """
        stale: List[WebSocket] = []
        for conn in self.active_connections:
            try:
                if conn.client_state == WebSocketState.CONNECTED:
                    await conn.send_text(message)
                else:
                    stale.append(conn)
            except Exception:
                stale.append(conn)
        for conn in stale:
            self.disconnect(conn)


# Singleton -- importable by other modules (e.g. signal ingest route)
manager = ConnectionManager()


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Accept a WebSocket connection and keep it alive for alert push events."""
    await manager.connect(websocket)
    try:
        while True:
            # Wait for client messages (used as keep-alive / ping-pong)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                # Respond to explicit ping
                if data.strip().lower() == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send a server-side ping to keep the connection alive
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        manager.disconnect(websocket)
