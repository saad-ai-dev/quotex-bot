"""Session service for the Quotex Alert Intelligence system.

ALERT-ONLY system -- sessions track chart monitoring / parsing periods,
NOT trading sessions or position management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.db.repositories import sessions_repo
from app.utils.datetime_utils import now_utc, format_timestamp
from app.utils.ids import generate_signal_id

logger = get_logger(__name__)


class SessionService:
    """Service for managing chart monitoring sessions.

    ALERT-ONLY: A "session" represents a period during which the system
    is actively parsing and analyzing Quotex chart data. No trades are
    opened or managed.
    """

    @staticmethod
    async def start_session(
        market_type: str,
        asset_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a new chart monitoring session.

        Args:
            market_type: LIVE or OTC market type being monitored.
            asset_name: Optional specific asset being monitored.

        Returns:
            The created session document dict.
        """
        # End any currently active session first
        current = await sessions_repo.get_active_session()
        if current:
            current_id = current.get("_id")
            if current_id:
                await sessions_repo.update_session(
                    current_id,
                    {
                        "is_active": False,
                        "ended_at": now_utc(),
                    },
                )
                logger.info(f"Auto-ended previous session {current_id}")

        session_data: Dict[str, Any] = {
            "market_type": market_type,
            "asset_name": asset_name,
            "started_at": now_utc(),
            "ended_at": None,
            "is_active": True,
            "alerts_count": 0,
            "metadata": {},
        }

        session_id = await sessions_repo.create_session(session_data)
        session_data["_id"] = session_id
        logger.info(
            f"Started new monitoring session {session_id} | "
            f"market={market_type} asset={asset_name}"
        )
        return session_data

    @staticmethod
    async def end_session(session_id: str) -> Dict[str, Any]:
        """End an active chart monitoring session.

        Args:
            session_id: The session ID to end.

        Returns:
            The updated session document dict.

        Raises:
            ValueError: If the session is not found or already ended.
        """
        ended_at = now_utc()
        success = await sessions_repo.update_session(
            session_id,
            {
                "is_active": False,
                "ended_at": ended_at,
            },
        )

        if not success:
            raise ValueError(f"Session not found or already ended: {session_id}")

        logger.info(f"Ended monitoring session {session_id}")

        # Return the updated session (re-fetch not directly available,
        # so we construct a minimal response)
        return {
            "_id": session_id,
            "is_active": False,
            "ended_at": ended_at,
        }

    @staticmethod
    async def get_current_session() -> Optional[Dict[str, Any]]:
        """Get the currently active chart monitoring session, if any.

        Returns:
            The active session document dict, or None if no session is active.
        """
        session = await sessions_repo.get_active_session()
        if session is None:
            logger.info("No active monitoring session found")
        return session
