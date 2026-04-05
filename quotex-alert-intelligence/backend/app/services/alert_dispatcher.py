"""Alert dispatcher for WebSocket broadcasting.

ALERT-ONLY system -- dispatches alert notifications and evaluation updates
to connected WebSocket clients. No trade signals or execution commands
are dispatched.
"""

import json
from typing import Any, Dict

from app.core.logging import get_logger

logger = get_logger(__name__)


class AlertDispatcher:
    """Dispatches alert events over WebSocket connections.

    ALERT-ONLY: Events are informational notifications about signal
    predictions and their evaluation outcomes. No trade instructions
    are sent.
    """

    @staticmethod
    def _get_connection_manager():
        """Lazily import the WebSocket connection manager to avoid circular imports."""
        try:
            from app.api.routers.websocket import manager
            return manager
        except ImportError:
            logger.warning(
                "WebSocket manager not available -- "
                "app.api.routes.websocket module not found"
            )
            return None

    @staticmethod
    async def dispatch_new_alert(signal: Dict[str, Any]) -> None:
        """Broadcast a new alert signal to all connected WebSocket clients.

        ALERT-ONLY: This pushes a prediction notification, not a trade order.

        Args:
            signal: The full alert document dict.
        """
        manager = AlertDispatcher._get_connection_manager()
        if manager is None:
            return

        event = {
            "event_type": "new_alert",
            "signal": _serialize_signal(signal),
        }

        try:
            payload = json.dumps(event, default=str)
            await manager.broadcast(payload)
            logger.info(
                f"Dispatched new_alert event for signal "
                f"{signal.get('signal_id', 'unknown')} to WebSocket clients"
            )
        except Exception as exc:
            logger.error(f"Failed to dispatch new_alert event: {exc}")

    @staticmethod
    async def dispatch_evaluation_update(signal: Dict[str, Any]) -> None:
        """Broadcast an evaluation update to all connected WebSocket clients.

        ALERT-ONLY: This pushes an outcome notification (WIN/LOSS/etc.),
        not a trade settlement.

        Args:
            signal: The updated alert document dict after evaluation.
        """
        manager = AlertDispatcher._get_connection_manager()
        if manager is None:
            return

        event = {
            "event_type": "evaluation_update",
            "signal": _serialize_signal(signal),
        }

        try:
            payload = json.dumps(event, default=str)
            await manager.broadcast(payload)
            logger.info(
                f"Dispatched evaluation_update event for signal "
                f"{signal.get('signal_id', 'unknown')} | "
                f"outcome={signal.get('outcome', 'N/A')}"
            )
        except Exception as exc:
            logger.error(f"Failed to dispatch evaluation_update event: {exc}")


def _serialize_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Create a JSON-safe copy of a signal document for WebSocket transmission.

    Strips MongoDB _id and converts datetime objects to ISO strings.
    """
    serialized = {}
    for key, value in signal.items():
        if key == "_id":
            continue
        serialized[key] = value
    return serialized
