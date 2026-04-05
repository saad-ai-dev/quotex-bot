"""
Alert Dispatcher - broadcasts signal events to WebSocket clients.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

import json
from datetime import datetime
from typing import Any, Dict, Set

from app.core.logging import get_logger

logger = get_logger(__name__)


def _serialize(obj: Any) -> Any:
    """JSON serializer for datetime and other non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


class _WebSocketManager:
    """Manages connected WebSocket clients for real-time alert broadcasting.

    ALERT-ONLY: Broadcasts analytical alerts, never trade instructions.
    """

    def __init__(self) -> None:
        self._connections: Set = set()

    async def connect(self, websocket) -> None:
        """Register a new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(
            "WebSocket client connected (%d total)", len(self._connections)
        )

    def disconnect(self, websocket) -> None:
        """Remove a disconnected WebSocket client."""
        self._connections.discard(websocket)
        logger.info(
            "WebSocket client disconnected (%d remaining)",
            len(self._connections),
        )

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send a JSON message to all connected clients.

        Disconnected clients are silently removed.
        """
        if not self._connections:
            return

        payload = json.dumps(message, default=_serialize)
        dead: Set = set()

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._connections.discard(ws)

        if dead:
            logger.debug("Cleaned up %d dead WebSocket connections", len(dead))

    @property
    def client_count(self) -> int:
        return len(self._connections)


# Module-level singleton
ws_manager = _WebSocketManager()


class AlertDispatcher:
    """Static methods for dispatching typed alert events via WebSocket.

    ALERT-ONLY: All events are informational. No trade commands are sent.
    """

    @staticmethod
    async def broadcast_new_signal(signal_doc: Dict[str, Any]) -> None:
        """Broadcast a newly created signal alert.

        Args:
            signal_doc: The full alert document from MongoDB.
        """
        message = {
            "type": "new_signal",
            "data": signal_doc,
        }
        await ws_manager.broadcast(message)
        logger.debug("Broadcast new_signal: %s", signal_doc.get("signal_id"))

    @staticmethod
    async def broadcast_evaluation(signal_doc: Dict[str, Any]) -> None:
        """Broadcast an evaluation update for a signal.

        Args:
            signal_doc: The updated alert document.
        """
        message = {
            "type": "evaluation_update",
            "data": signal_doc,
        }
        await ws_manager.broadcast(message)
        logger.debug(
            "Broadcast evaluation_update: %s -> %s",
            signal_doc.get("signal_id"),
            signal_doc.get("outcome"),
        )

    @staticmethod
    async def broadcast_stats(stats: Dict[str, Any]) -> None:
        """Broadcast updated dashboard statistics.

        Args:
            stats: Summary statistics dict.
        """
        message = {
            "type": "stats_update",
            "data": stats,
        }
        await ws_manager.broadcast(message)

    @staticmethod
    async def broadcast_metrics(metrics: Dict[str, Any]) -> None:
        """Broadcast refreshed analytics metrics.

        Args:
            metrics: Analytics summary dict.
        """
        message = {
            "type": "metrics_update",
            "data": metrics,
        }
        await ws_manager.broadcast(message)
