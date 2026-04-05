"""
Session Service - manages monitoring session lifecycle.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.db.repositories import sessions_repo

logger = get_logger(__name__)


class SessionService:
    """Manages monitoring session start/end lifecycle.

    ALERT-ONLY: Sessions represent dashboard monitoring periods,
    not trading sessions. No positions are opened or closed.
    """

    @staticmethod
    async def start_session(metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start a new monitoring session.

        If there is already an active session, it is ended first.

        Args:
            metadata: Optional metadata (e.g. user agent, market focus).

        Returns:
            The newly created session document.
        """
        # End any existing active session
        active = await sessions_repo.get_active_session()
        if active:
            logger.info(
                "Ending previous active session %s before starting new one",
                active["_id"],
            )
            await sessions_repo.end_session(active["_id"])

        session_id = await sessions_repo.create_session(metadata)
        session = await sessions_repo.get_active_session()

        logger.info("Monitoring session started: %s", session_id)
        return session or {"_id": session_id, "is_active": True}

    @staticmethod
    async def end_session() -> bool:
        """End the currently active monitoring session.

        Returns:
            True if a session was ended, False if none was active.
        """
        active = await sessions_repo.get_active_session()
        if not active:
            logger.info("No active monitoring session to end")
            return False

        success = await sessions_repo.end_session(active["_id"])
        if success:
            logger.info("Monitoring session ended: %s", active["_id"])
        return success

    @staticmethod
    async def get_current_session() -> Optional[Dict[str, Any]]:
        """Get the currently active session, if any.

        Returns:
            Active session document or None.
        """
        return await sessions_repo.get_active_session()

    @staticmethod
    async def increment_alert_count(session_id: Optional[str] = None) -> None:
        """Increment the alerts_generated counter on the active session.

        Args:
            session_id: Explicit session ID. If None, uses the active session.
        """
        if session_id is None:
            active = await sessions_repo.get_active_session()
            if not active:
                return
            session_id = active["_id"]

        from app.db.mongo import get_collection
        from bson import ObjectId

        col = get_collection("sessions")
        await col.update_one(
            {"_id": ObjectId(session_id) if isinstance(session_id, str) else session_id},
            {"$inc": {"alerts_generated": 1}},
        )
