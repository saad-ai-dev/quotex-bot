"""
Candle sequence generator for historical replay testing.
ALERT-ONLY system - generates test data for signal validation, NOT for trading.
"""
import random
import numpy as np
from typing import List, Dict, Any, Optional


class CandleGenerator:
    """Generates deterministic candle sequences for replay testing."""

    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)

    def generate_uptrend(self, n=30, base=1.0800, volatility=0.0005) -> List[Dict]:
        """Clear uptrend with HH+HL structure."""
        candles = []
        price = base
        for i in range(n):
            drift = volatility * self.rng.uniform(0.5, 2.0)
            body = volatility * self.rng.uniform(0.2, 1.5)
            wick_up = volatility * self.rng.uniform(0.1, 0.5)
            wick_dn = volatility * self.rng.uniform(0.1, 0.5)

            # Uptrend: mostly bullish candles
            if self.rng.random() < 0.7:  # 70% bullish
                o = price
                c = price + body
            else:  # pullback
                o = price + body * 0.3
                c = price - body * 0.2

            h = max(o, c) + wick_up
            l = min(o, c) - wick_dn
            candles.append({
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "timestamp": float(1700000000 + i * 60),
            })
            price = c + drift * 0.3
        return candles

    def generate_downtrend(self, n=30, base=1.0900, volatility=0.0005) -> List[Dict]:
        """Clear downtrend with LH+LL structure."""
        candles = []
        price = base
        for i in range(n):
            drift = volatility * self.rng.uniform(0.5, 2.0)
            body = volatility * self.rng.uniform(0.2, 1.5)
            wick_up = volatility * self.rng.uniform(0.1, 0.5)
            wick_dn = volatility * self.rng.uniform(0.1, 0.5)

            if self.rng.random() < 0.7:
                o = price
                c = price - body
            else:
                o = price - body * 0.3
                c = price + body * 0.2

            h = max(o, c) + wick_up
            l = min(o, c) - wick_dn
            candles.append({
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "timestamp": float(1700000000 + i * 60),
            })
            price = c - drift * 0.3
        return candles

    def generate_range(self, n=30, base=1.0850, amplitude=0.0015) -> List[Dict]:
        """Sideways/choppy market."""
        candles = []
        price = base
        for i in range(n):
            body = amplitude * self.rng.uniform(0.1, 0.6)
            wick_up = amplitude * self.rng.uniform(0.05, 0.3)
            wick_dn = amplitude * self.rng.uniform(0.05, 0.3)
            direction = 1 if self.rng.random() > 0.5 else -1
            o = price
            c = price + direction * body
            # Keep in range
            if c > base + amplitude:
                c = base + amplitude * 0.5
            elif c < base - amplitude:
                c = base - amplitude * 0.5
            h = max(o, c) + wick_up
            l = min(o, c) - wick_dn
            candles.append({
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "timestamp": float(1700000000 + i * 60),
            })
            price = c
        return candles

    def generate_reversal_up(self, n=30, base=1.0850) -> List[Dict]:
        """Downtrend then reversal to uptrend. Expected: UP signal near end."""
        down = self.generate_downtrend(n // 2, base, 0.0004)
        self.rng = np.random.RandomState(self.rng.randint(0, 100000))
        up = self.generate_uptrend(n - n // 2, down[-1]["close"], 0.0006)
        for i, c in enumerate(up):
            c["timestamp"] = float(1700000000 + (n // 2 + i) * 60)
        return down + up

    def generate_reversal_down(self, n=30, base=1.0850) -> List[Dict]:
        """Uptrend then reversal to downtrend. Expected: DOWN signal near end."""
        up = self.generate_uptrend(n // 2, base, 0.0004)
        self.rng = np.random.RandomState(self.rng.randint(0, 100000))
        down = self.generate_downtrend(n - n // 2, up[-1]["close"], 0.0006)
        for i, c in enumerate(down):
            c["timestamp"] = float(1700000000 + (n // 2 + i) * 60)
        return up + down

    def generate_otc_alternating(self, n=30, base=1.0850) -> List[Dict]:
        """OTC-like alternating pattern."""
        candles = []
        price = base
        for i in range(n):
            body = 0.0003 * self.rng.uniform(0.5, 2.0)
            wick = 0.0001 * self.rng.uniform(0.5, 1.5)
            if i % 2 == 0:
                o, c = price, price + body
            else:
                o, c = price, price - body
            h = max(o, c) + wick
            l = min(o, c) - wick
            candles.append({
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "timestamp": float(1700000000 + i * 60),
            })
            price = c
        return candles

    def generate_otc_spike_reversal(self, n=30, base=1.0850) -> List[Dict]:
        """OTC spike then reversal."""
        candles = self.generate_range(n - 5, base, 0.0005)
        price = candles[-1]["close"]
        # Spike up
        for i in range(3):
            body = 0.002 * self.rng.uniform(0.8, 1.5)
            o = price
            c = price + body
            h = c + 0.0002
            l = o - 0.0001
            candles.append({
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "timestamp": float(1700000000 + (n - 5 + i) * 60),
            })
            price = c
        # Sharp reversal
        for i in range(2):
            body = 0.003 * self.rng.uniform(0.8, 1.5)
            o = price
            c = price - body
            h = o + 0.0002
            l = c - 0.0002
            candles.append({
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(l, 5),
                "close": round(c, 5),
                "timestamp": float(1700000000 + (n - 2 + i) * 60),
            })
            price = c
        return candles

    def generate_batch(self, count=50, seed_start=100) -> List[Dict[str, Any]]:
        """Generate a batch of diverse candle sequences with expected outcomes.

        ALERT-ONLY: These sequences simulate market conditions for signal
        validation testing. No real market data or trading is involved.
        """
        batch = []
        generators = [
            ("uptrend", self.generate_uptrend, "UP"),
            ("downtrend", self.generate_downtrend, "DOWN"),
            ("range", self.generate_range, "NO_TRADE"),
            ("reversal_up", self.generate_reversal_up, "UP"),
            ("reversal_down", self.generate_reversal_down, "DOWN"),
            ("otc_alternating", self.generate_otc_alternating, "NO_TRADE"),
            ("otc_spike_reversal", self.generate_otc_spike_reversal, "DOWN"),
        ]
        for i in range(count):
            self.rng = np.random.RandomState(seed_start + i)
            gen_name, gen_func, expected = generators[i % len(generators)]
            market_type = "OTC" if "otc" in gen_name else "LIVE"
            candles = gen_func(n=30)
            # The "actual" next candle direction for evaluation
            last_close = candles[-1]["close"]
            next_body = 0.0003 * (
                1 if expected == "UP"
                else -1 if expected == "DOWN"
                else (1 if self.rng.random() > 0.5 else -1)
            )
            actual_direction = "bullish" if next_body > 0 else "bearish"
            if abs(next_body) < 0.00005:
                actual_direction = "neutral"

            batch.append({
                "sequence_id": f"seq_{seed_start + i:04d}",
                "pattern_type": gen_name,
                "market_type": market_type,
                "expected_direction": expected,
                "actual_next_candle_direction": actual_direction,
                "candles": candles,
            })
        return batch
