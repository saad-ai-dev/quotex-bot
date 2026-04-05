"""
Timing Engine - ALERT-ONLY system.
Computes evaluation times and timing constraints for signal alerts.
No trade execution - determines when alerts should be evaluated only.
"""

from datetime import datetime, timedelta
from typing import Optional

# Expiry profile to seconds mapping
EXPIRY_SECONDS = {
    "1m": 60,
    "2m": 120,
    "3m": 180,
}


class TimingEngine:
    """Handles timing calculations for alert evaluation windows.

    ALERT-ONLY: Timing is used to schedule evaluation of predictions,
    not to time trade entries or exits.
    """

    @staticmethod
    def compute_evaluation_time(created_at: datetime, expiry_profile: str) -> datetime:
        """Compute when a signal prediction should be evaluated.

        The evaluation time is when we check whether the predicted direction
        was correct, based on the expiry duration.

        Args:
            created_at: Timestamp when the signal/alert was created.
            expiry_profile: Duration string ('1m', '2m', '3m').

        Returns:
            Datetime when the prediction should be evaluated.

        Raises:
            ValueError: If expiry_profile is not recognized.
        """
        seconds = EXPIRY_SECONDS.get(expiry_profile)
        if seconds is None:
            raise ValueError(
                f"Unknown expiry profile '{expiry_profile}'. "
                f"Supported: {list(EXPIRY_SECONDS.keys())}"
            )
        return created_at + timedelta(seconds=seconds)

    @staticmethod
    def is_too_late_for_alert(
        current_time: datetime,
        candle_close_time: datetime,
        min_seconds_before: int = 5,
    ) -> bool:
        """Check if it is too late to generate an alert before a candle closes.

        ALERT-ONLY: Determines whether there is enough time remaining before
        the candle closes to generate a meaningful alert.

        Args:
            current_time: The current wall-clock time.
            candle_close_time: When the current candle is expected to close.
            min_seconds_before: Minimum seconds required before close to
                consider the alert timely. Defaults to 5.

        Returns:
            True if it is too late (remaining time < min_seconds_before).
        """
        remaining = (candle_close_time - current_time).total_seconds()
        return remaining < min_seconds_before

    @staticmethod
    def get_candle_countdown(candle_close_time: datetime, current_time: Optional[datetime] = None) -> int:
        """Get the number of seconds remaining until a candle closes.

        Args:
            candle_close_time: When the candle is expected to close.
            current_time: Optional current time override. Uses datetime.utcnow()
                if not provided.

        Returns:
            Seconds remaining (can be negative if candle already closed).
        """
        if current_time is None:
            current_time = datetime.utcnow()
        delta = (candle_close_time - current_time).total_seconds()
        return int(delta)
