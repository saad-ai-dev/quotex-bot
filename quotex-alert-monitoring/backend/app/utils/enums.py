"""Enums for the Quotex Alert Intelligence system.

ALERT-ONLY system -- these enums describe alert/signal metadata,
NOT trade execution parameters.
"""

from enum import Enum


class MarketType(str, Enum):
    """Market type: LIVE or OTC (over-the-counter)."""
    LIVE = "LIVE"
    OTC = "OTC"


class ExpiryProfile(str, Enum):
    """Candle expiry / timeframe profile for alerts."""
    ONE_MIN = "1m"
    TWO_MIN = "2m"
    THREE_MIN = "3m"


class Direction(str, Enum):
    """Predicted candle direction for the alert signal."""
    UP = "UP"
    DOWN = "DOWN"
    NO_TRADE = "NO_TRADE"


class Outcome(str, Enum):
    """Evaluation outcome of a signal after the candle closes."""
    WIN = "WIN"
    LOSS = "LOSS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class SignalStatus(str, Enum):
    """Lifecycle status of an alert signal."""
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"


class ParseMode(str, Enum):
    """Method used to parse/read chart data from the Quotex UI."""
    DOM = "DOM"
    CANVAS = "CANVAS"
    CV = "CV"
    OCR = "OCR"
