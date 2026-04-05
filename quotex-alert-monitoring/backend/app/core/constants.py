"""
Application-wide constants.
ALERT-ONLY monitoring dashboard - no trade execution.
"""


class MarketType:
    """Supported market types for alert monitoring."""
    LIVE = "live"
    OTC = "otc"
    ALL = [LIVE, OTC]


class ExpiryProfile:
    """Supported expiry profiles (candle durations) for signal evaluation."""
    ONE_MIN = "1m"
    TWO_MIN = "2m"
    THREE_MIN = "3m"
    ALL = [ONE_MIN, TWO_MIN, THREE_MIN]


class Direction:
    """Predicted price direction from the analysis engine."""
    UP = "UP"
    DOWN = "DOWN"
    NO_TRADE = "NO_TRADE"
    ALL = [UP, DOWN, NO_TRADE]


class Outcome:
    """Evaluated outcome of a signal prediction."""
    WIN = "WIN"
    LOSS = "LOSS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"
    ALL = [WIN, LOSS, NEUTRAL, UNKNOWN]


class Status:
    """Signal evaluation status."""
    PENDING = "pending"
    EVALUATED = "evaluated"
    ALL = [PENDING, EVALUATED]
