"""
Volume Proxy Detector - Alert-only analysis module.
Estimates volume-like signals from price action when actual volume data is unavailable.
Uses range expansion, wick imbalance, velocity, and burst detection.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any


class VolumeProxyDetector:
    """Infers volume-like metrics from price data alone (range, wicks, velocity)."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full volume proxy analysis."""
        if len(candles) < 5:
            return self._empty_result()

        range_exp = self.compute_range_expansion(candles)
        wick_imb = self.compute_wick_imbalance(candles)
        velocity = self.compute_velocity(candles)
        burst_score, burst_detected = self.compute_burst_score(candles)
        proxy_score = self._compute_proxy_volume_score(range_exp, wick_imb, velocity, burst_score)
        vol_state = self._classify_volatility(candles)

        return {
            "proxy_volume_score": round(proxy_score, 4),
            "range_expansion": round(range_exp, 4),
            "wick_imbalance": round(wick_imb, 4),
            "velocity": round(velocity, 6),
            "burst_detected": burst_detected,
            "is_proxy": True,
            "note": "Volume estimated from price action; no real volume data available.",
            "volatility_state": vol_state,
        }

    def compute_range_expansion(self, candles: List[Dict], lookback: int = 10) -> float:
        """Compare the most recent candle range to the average range over lookback period."""
        ranges = np.array([c["high"] - c["low"] for c in candles])
        if len(ranges) < 2:
            return 1.0

        window = min(lookback, len(ranges) - 1)
        avg_range = np.mean(ranges[-window - 1:-1])
        if avg_range <= 0:
            return 1.0

        current_range = ranges[-1]
        return float(current_range / avg_range)

    def compute_wick_imbalance(self, candles: List[Dict], lookback: int = 5) -> float:
        """Compute ratio of upper wick sum to lower wick sum over recent candles.
        Values > 1 indicate more upper wicks (selling pressure).
        Values < 1 indicate more lower wicks (buying pressure).
        """
        recent = candles[-lookback:] if len(candles) >= lookback else candles

        upper_wicks = np.array([
            c["high"] - max(c["open"], c["close"]) for c in recent
        ])
        lower_wicks = np.array([
            min(c["open"], c["close"]) - c["low"] for c in recent
        ])

        total_upper = np.sum(upper_wicks)
        total_lower = np.sum(lower_wicks)

        if total_lower <= 0:
            return 2.0 if total_upper > 0 else 1.0
        return float(total_upper / total_lower)

    def compute_velocity(self, candles: List[Dict], lookback: int = 5) -> float:
        """Compute rate of price change over recent candles (close-to-close per candle)."""
        window = min(lookback, len(candles))
        if window < 2:
            return 0.0

        closes = np.array([c["close"] for c in candles[-window:]])
        total_change = closes[-1] - closes[0]
        avg_price = np.mean(closes)

        if avg_price <= 0:
            return 0.0

        pct_velocity = (total_change / avg_price) / (window - 1)
        return float(pct_velocity)

    def compute_burst_score(self, candles: List[Dict], compression_window: int = 6,
                            burst_window: int = 2) -> tuple:
        """Detect sudden range expansion after compression.
        Returns (score, burst_detected) tuple.
        """
        if len(candles) < compression_window + burst_window:
            return 0.0, False

        ranges = np.array([c["high"] - c["low"] for c in candles])

        compression_ranges = ranges[-(compression_window + burst_window):-burst_window]
        burst_ranges = ranges[-burst_window:]

        avg_compressed = np.mean(compression_ranges)
        avg_burst = np.mean(burst_ranges)

        if avg_compressed <= 0:
            return 0.0, False

        ratio = avg_burst / avg_compressed

        # Check that compression was actually tight (below overall average)
        overall_avg = np.mean(ranges)
        was_compressed = avg_compressed < overall_avg * 0.7

        burst_detected = ratio > 2.0 and was_compressed
        score = float(np.clip((ratio - 1.0) / 3.0, 0.0, 1.0))

        return score, burst_detected

    def _compute_proxy_volume_score(self, range_exp: float, wick_imb: float,
                                    velocity: float, burst_score: float) -> float:
        """Combine all proxy metrics into a single volume activity score (0 to 1)."""
        range_component = float(np.clip((range_exp - 0.5) / 2.0, 0.0, 1.0))
        imbalance_component = float(np.clip(abs(wick_imb - 1.0) / 1.5, 0.0, 1.0))
        velocity_component = float(np.clip(abs(velocity) * 100, 0.0, 1.0))
        burst_component = burst_score

        score = (range_component * 0.35 + imbalance_component * 0.15 +
                 velocity_component * 0.25 + burst_component * 0.25)
        return float(np.clip(score, 0.0, 1.0))

    def _classify_volatility(self, candles: List[Dict]) -> str:
        """Classify current volatility state from recent ranges."""
        ranges = np.array([c["high"] - c["low"] for c in candles])
        if len(ranges) < 5:
            return "normal"

        avg_range = np.mean(ranges)
        recent_avg = np.mean(ranges[-3:])

        if avg_range <= 0:
            return "normal"

        ratio = recent_avg / avg_range
        if ratio > 1.5:
            return "expanding"
        elif ratio < 0.6:
            return "compressing"
        return "normal"

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "proxy_volume_score": 0.0,
            "range_expansion": 1.0,
            "wick_imbalance": 1.0,
            "velocity": 0.0,
            "burst_detected": False,
            "is_proxy": True,
            "note": "Insufficient data for volume proxy analysis.",
            "volatility_state": "unknown",
        }
