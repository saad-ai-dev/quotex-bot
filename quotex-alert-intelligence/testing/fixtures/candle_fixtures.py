"""
Comprehensive candle fixture generator for testing the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Provides reproducible candle sequences for unit tests, integration tests,
and replay validation. Each generator returns a list of dicts with
open, high, low, close, timestamp keys.
"""

import math
import random
import time
from typing import Dict, List


def _make_candle(
    open_: float,
    high: float,
    low: float,
    close: float,
    ts: float,
) -> Dict[str, float]:
    """Create a single candle dict with proper OHLC structure."""
    return {
        "open": round(open_, 6),
        "high": round(high, 6),
        "low": round(low, 6),
        "close": round(close, 6),
        "timestamp": ts,
    }


def generate_uptrend(
    n: int = 30,
    start_price: float = 1.0800,
    step: float = 0.0005,
) -> List[Dict[str, float]]:
    """Generate a series of candles forming a steady uptrend.

    Each candle moves up by approximately `step`, with small random noise
    for realistic OHLC variation.

    Args:
        n: Number of candles to generate.
        start_price: Opening price of the first candle.
        step: Average price increment per candle.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(100)
    candles = []
    base_ts = time.time() - (n * 60)
    price = start_price

    for i in range(n):
        noise = rng.uniform(-step * 0.3, step * 0.3)
        open_ = price
        close = price + step + noise
        high = max(open_, close) + rng.uniform(0, step * 0.5)
        low = min(open_, close) - rng.uniform(0, step * 0.3)
        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_downtrend(
    n: int = 30,
    start_price: float = 1.0900,
    step: float = 0.0005,
) -> List[Dict[str, float]]:
    """Generate a series of candles forming a steady downtrend.

    Each candle moves down by approximately `step`.

    Args:
        n: Number of candles to generate.
        start_price: Opening price of the first candle.
        step: Average price decrement per candle.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(200)
    candles = []
    base_ts = time.time() - (n * 60)
    price = start_price

    for i in range(n):
        noise = rng.uniform(-step * 0.3, step * 0.3)
        open_ = price
        close = price - step + noise
        high = max(open_, close) + rng.uniform(0, step * 0.3)
        low = min(open_, close) - rng.uniform(0, step * 0.5)
        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_range(
    n: int = 30,
    center: float = 1.0850,
    amplitude: float = 0.0010,
) -> List[Dict[str, float]]:
    """Generate ranging / sideways candles oscillating around a center price.

    Uses a sine wave to create regular oscillation within a bounded range.

    Args:
        n: Number of candles to generate.
        center: Central price of the range.
        amplitude: Maximum deviation from center.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(300)
    candles = []
    base_ts = time.time() - (n * 60)

    for i in range(n):
        phase = (2 * math.pi * i) / max(n / 3, 1)
        mid = center + amplitude * math.sin(phase)
        noise = rng.uniform(-amplitude * 0.2, amplitude * 0.2)
        open_ = mid + noise
        close = mid - noise + rng.uniform(-amplitude * 0.15, amplitude * 0.15)
        high = max(open_, close) + rng.uniform(0, amplitude * 0.3)
        low = min(open_, close) - rng.uniform(0, amplitude * 0.3)
        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))

    return candles


def generate_breakout(n: int = 30) -> List[Dict[str, float]]:
    """Generate candles showing consolidation then a breakout move.

    First 2/3 of candles form a tight range, then the final 1/3 breaks out
    sharply to the upside.

    Args:
        n: Total number of candles.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(400)
    candles = []
    base_ts = time.time() - (n * 60)
    center = 1.0850
    amplitude = 0.0005
    breakout_start = int(n * 0.66)

    price = center
    for i in range(n):
        if i < breakout_start:
            # Consolidation phase
            noise = rng.uniform(-amplitude, amplitude)
            open_ = price + noise * 0.5
            close = price + noise
            high = max(open_, close) + rng.uniform(0, amplitude * 0.3)
            low = min(open_, close) - rng.uniform(0, amplitude * 0.3)
        else:
            # Breakout phase - strong upward move
            step = 0.0008 + rng.uniform(0, 0.0004)
            open_ = price
            close = price + step
            high = close + rng.uniform(0, 0.0003)
            low = open_ - rng.uniform(0, 0.0001)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_reversal(n: int = 30) -> List[Dict[str, float]]:
    """Generate candles showing a trend then a reversal.

    First half trends upward, then reverses downward with a clear
    rejection / reversal pattern at the top.

    Args:
        n: Total number of candles.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(500)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0800
    midpoint = n // 2

    for i in range(n):
        if i < midpoint:
            # Uptrend
            step = 0.0004 + rng.uniform(0, 0.0002)
            open_ = price
            close = price + step
            high = close + rng.uniform(0, 0.0002)
            low = open_ - rng.uniform(0, 0.0001)
        elif i == midpoint:
            # Reversal candle: big upper wick (rejection)
            open_ = price
            high = price + 0.0010
            close = price - 0.0003
            low = close - 0.0001
        else:
            # Downtrend
            step = 0.0004 + rng.uniform(0, 0.0002)
            open_ = price
            close = price - step
            high = open_ + rng.uniform(0, 0.0001)
            low = close - rng.uniform(0, 0.0002)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_otc_spiky(n: int = 30) -> List[Dict[str, float]]:
    """Generate OTC-style candles with alternating spikes.

    OTC markets often show quick spike-and-retrace behavior. This
    generator alternates between up and down spikes to simulate that.

    Args:
        n: Number of candles to generate.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(600)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0850

    for i in range(n):
        spike_size = rng.uniform(0.0005, 0.0015)
        if i % 2 == 0:
            # Up spike then retrace
            open_ = price
            high = price + spike_size
            close = price + rng.uniform(-0.0002, 0.0003)
            low = min(open_, close) - rng.uniform(0, 0.0002)
        else:
            # Down spike then retrace
            open_ = price
            low = price - spike_size
            close = price + rng.uniform(-0.0003, 0.0002)
            high = max(open_, close) + rng.uniform(0, 0.0002)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_otc_compression_burst(n: int = 30) -> List[Dict[str, float]]:
    """Generate OTC-style compression followed by a burst move.

    Simulates the common OTC pattern of very tight ranges (compression)
    followed by a sudden large move (burst).

    Args:
        n: Number of candles to generate.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(700)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0850
    burst_start = int(n * 0.75)

    for i in range(n):
        if i < burst_start:
            # Compression: very small candles
            tiny = rng.uniform(-0.0001, 0.0001)
            open_ = price
            close = price + tiny
            high = max(open_, close) + rng.uniform(0, 0.00005)
            low = min(open_, close) - rng.uniform(0, 0.00005)
        else:
            # Burst: large candles in one direction
            burst_step = rng.uniform(0.0006, 0.0012)
            open_ = price
            close = price + burst_step
            high = close + rng.uniform(0, 0.0003)
            low = open_ - rng.uniform(0, 0.0001)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_with_fvg(n: int = 30) -> List[Dict[str, float]]:
    """Generate candles with an intentional fair value gap.

    Creates a sequence where candle i+2's low is above candle i's high,
    forming a bullish FVG around the midpoint.

    Args:
        n: Number of candles to generate.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(800)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0800
    fvg_index = n // 2

    for i in range(n):
        if i == fvg_index:
            # Pre-gap candle: small body
            open_ = price
            close = price + 0.0002
            high = close + 0.0001
            low = open_ - 0.0001
        elif i == fvg_index + 1:
            # Gap candle: strong displacement upward
            open_ = price + 0.0005
            close = price + 0.0015
            high = close + 0.0002
            low = open_ - 0.0001
        elif i == fvg_index + 2:
            # Post-gap candle: low stays above pre-gap high to form FVG
            open_ = price
            close = price + 0.0003
            high = close + 0.0002
            low = open_ - 0.0001
        else:
            # Normal candle
            step = rng.uniform(-0.0003, 0.0004)
            open_ = price
            close = price + step
            high = max(open_, close) + rng.uniform(0, 0.0002)
            low = min(open_, close) - rng.uniform(0, 0.0002)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_with_order_block(n: int = 30) -> List[Dict[str, float]]:
    """Generate candles with an identifiable order block.

    Creates a bearish candle (the order block) followed by strong bullish
    displacement, making the bearish candle a bullish order block.

    Args:
        n: Number of candles to generate.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(900)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0850
    ob_index = n // 3

    for i in range(n):
        if i == ob_index:
            # The order block candle: bearish
            open_ = price
            close = price - 0.0006
            high = open_ + 0.0001
            low = close - 0.0001
        elif i in (ob_index + 1, ob_index + 2, ob_index + 3):
            # Strong displacement candles: bullish
            open_ = price
            close = price + 0.0008
            high = close + 0.0002
            low = open_ - 0.0001
        else:
            # Normal
            step = rng.uniform(-0.0002, 0.0003)
            open_ = price
            close = price + step
            high = max(open_, close) + rng.uniform(0, 0.0002)
            low = min(open_, close) - rng.uniform(0, 0.0002)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_liquidity_sweep(n: int = 30) -> List[Dict[str, float]]:
    """Generate candles with equal highs then a liquidity sweep.

    Creates several candles with nearly equal highs (forming a liquidity
    pool), then a candle that sweeps above before reversing down.

    Args:
        n: Number of candles to generate.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(1000)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0850
    equal_high_level = 1.0870
    eq_start = n // 3
    sweep_index = eq_start + 5

    for i in range(n):
        if eq_start <= i < sweep_index:
            # Equal highs formation
            open_ = price
            close = price + rng.uniform(-0.0002, 0.0002)
            high = equal_high_level + rng.uniform(-0.00005, 0.00005)
            low = min(open_, close) - rng.uniform(0, 0.0003)
        elif i == sweep_index:
            # Sweep candle: goes above equal highs then reverses
            open_ = price
            high = equal_high_level + 0.0005
            close = price - 0.0004
            low = close - 0.0002
        else:
            step = rng.uniform(-0.0003, 0.0003)
            open_ = price
            close = price + step
            high = max(open_, close) + rng.uniform(0, 0.0002)
            low = min(open_, close) - rng.uniform(0, 0.0002)

        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_doji_heavy(n: int = 30) -> List[Dict[str, float]]:
    """Generate candles with many doji / indecision candles.

    Most candles have very small bodies but longer wicks, indicating
    indecision in the market.

    Args:
        n: Number of candles to generate.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(1100)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0850

    for i in range(n):
        # Very small body
        body = rng.uniform(-0.00005, 0.00005)
        open_ = price
        close = price + body
        # Long wicks relative to body
        wick_up = rng.uniform(0.0002, 0.0006)
        wick_down = rng.uniform(0.0002, 0.0006)
        high = max(open_, close) + wick_up
        low = min(open_, close) - wick_down
        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles


def generate_random_walk(
    n: int = 30,
    seed: int = 42,
) -> List[Dict[str, float]]:
    """Generate a random walk of candles for baseline testing.

    Uses a seeded RNG for reproducibility. Each candle's close is
    the previous close plus a random step.

    Args:
        n: Number of candles to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of candle dicts sorted by timestamp ascending.
    """
    rng = random.Random(seed)
    candles = []
    base_ts = time.time() - (n * 60)
    price = 1.0850

    for i in range(n):
        step = rng.gauss(0, 0.0003)
        open_ = price
        close = price + step
        wick_up = abs(rng.gauss(0, 0.0001))
        wick_down = abs(rng.gauss(0, 0.0001))
        high = max(open_, close) + wick_up
        low = min(open_, close) - wick_down
        candles.append(_make_candle(open_, high, low, close, base_ts + i * 60))
        price = close

    return candles
