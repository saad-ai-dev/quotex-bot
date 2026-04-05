"""Chart / candle math utilities for the Quotex Alert Intelligence system.

ALERT-ONLY system -- these computations support signal analysis,
NOT trade execution logic.
"""

from typing import Any, Dict, List


def normalize_candles(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure all candle dicts have required OHLC fields with correct types.

    Missing fields default to 0.0. Timestamps default to 0.0 if absent.
    Returns a new list of normalized candle dicts.
    """
    normalized: List[Dict[str, Any]] = []
    for c in candles:
        normalized.append({
            "open": float(c.get("open", 0.0) or 0.0),
            "high": float(c.get("high", 0.0) or 0.0),
            "low": float(c.get("low", 0.0) or 0.0),
            "close": float(c.get("close", 0.0) or 0.0),
            "timestamp": float(c.get("timestamp", 0.0) or 0.0),
        })
    return normalized


def compute_atr(candles: List[Dict[str, Any]], period: int = 14) -> float:
    """Compute the Average True Range (ATR) over the given period.

    Uses the classic ATR formula: average of true ranges over the last
    `period` candles. Returns 0.0 if insufficient data.
    """
    if len(candles) < 2:
        return 0.0

    true_ranges: List[float] = []
    for i in range(1, len(candles)):
        high = float(candles[i].get("high", 0.0) or 0.0)
        low = float(candles[i].get("low", 0.0) or 0.0)
        prev_close = float(candles[i - 1].get("close", 0.0) or 0.0)

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(tr)

    if not true_ranges:
        return 0.0

    # Use the last `period` true ranges (or all if fewer available)
    relevant = true_ranges[-period:]
    return sum(relevant) / len(relevant)


def compute_candle_body(candle: Dict[str, Any]) -> float:
    """Compute the absolute body size of a candle (|close - open|)."""
    open_price = float(candle.get("open", 0.0) or 0.0)
    close_price = float(candle.get("close", 0.0) or 0.0)
    return abs(close_price - open_price)


def compute_candle_range(candle: Dict[str, Any]) -> float:
    """Compute the full range of a candle (high - low)."""
    high = float(candle.get("high", 0.0) or 0.0)
    low = float(candle.get("low", 0.0) or 0.0)
    return high - low


def compute_upper_wick(candle: Dict[str, Any]) -> float:
    """Compute the upper wick length of a candle."""
    high = float(candle.get("high", 0.0) or 0.0)
    open_price = float(candle.get("open", 0.0) or 0.0)
    close_price = float(candle.get("close", 0.0) or 0.0)
    return high - max(open_price, close_price)


def compute_lower_wick(candle: Dict[str, Any]) -> float:
    """Compute the lower wick length of a candle."""
    low = float(candle.get("low", 0.0) or 0.0)
    open_price = float(candle.get("open", 0.0) or 0.0)
    close_price = float(candle.get("close", 0.0) or 0.0)
    return min(open_price, close_price) - low


def is_bullish(candle: Dict[str, Any]) -> bool:
    """Return True if the candle closed above its open (bullish)."""
    open_price = float(candle.get("open", 0.0) or 0.0)
    close_price = float(candle.get("close", 0.0) or 0.0)
    return close_price > open_price


def is_bearish(candle: Dict[str, Any]) -> bool:
    """Return True if the candle closed below its open (bearish)."""
    open_price = float(candle.get("open", 0.0) or 0.0)
    close_price = float(candle.get("close", 0.0) or 0.0)
    return close_price < open_price


def is_doji(candle: Dict[str, Any], threshold: float = 0.1) -> bool:
    """Return True if the candle is a doji (body is very small relative to range).

    A candle is considered a doji when its body is less than `threshold`
    fraction of its total range.
    """
    body = compute_candle_body(candle)
    full_range = compute_candle_range(candle)

    if full_range == 0.0:
        # No range at all -- effectively a doji
        return True

    return (body / full_range) < threshold
