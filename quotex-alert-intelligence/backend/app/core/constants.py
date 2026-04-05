"""Constants for the Quotex Alert Intelligence system."""


class MarketType:
    LIVE = "LIVE"
    OTC = "OTC"

    ALL = [LIVE, OTC]


class ExpiryProfile:
    ONE_MINUTE = "1m"
    TWO_MINUTES = "2m"
    THREE_MINUTES = "3m"

    ALL = [ONE_MINUTE, TWO_MINUTES, THREE_MINUTES]


class Direction:
    UP = "UP"
    DOWN = "DOWN"
    NO_TRADE = "NO_TRADE"

    ALL = [UP, DOWN, NO_TRADE]


class Outcome:
    WIN = "WIN"
    LOSS = "LOSS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"

    ALL = [WIN, LOSS, NEUTRAL, UNKNOWN]


class Status:
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"

    ALL = [PENDING, EVALUATED]
