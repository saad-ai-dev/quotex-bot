"""
Liquidity Detector - Alert-only analysis module.
Identifies equal highs/lows, liquidity pools, sweeps, and reclaims.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any, Optional


class LiquidityDetector:
    """Detects liquidity-related patterns: equal levels, pools, sweeps, and stop hunts."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full liquidity analysis."""
        if len(candles) < 6:
            return self._empty_result()

        equal_highs = self.detect_equal_highs(candles)
        equal_lows = self.detect_equal_lows(candles)
        pools = self.detect_liquidity_pools(candles)

        all_eq_levels = equal_highs + equal_lows
        recent_sweep = self.detect_sweep(candles, all_eq_levels)
        reclaim = self.detect_reclaim(candles, recent_sweep) if recent_sweep else False

        current_price = candles[-1]["close"]
        liq_above = any(lvl["level"] > current_price for lvl in equal_highs)
        liq_below = any(lvl["level"] < current_price for lvl in equal_lows)

        stop_hunt = (recent_sweep is not None and reclaim)

        return {
            "liquidity_above": liq_above,
            "liquidity_below": liq_below,
            "equal_highs": equal_highs,
            "equal_lows": equal_lows,
            "recent_sweep": recent_sweep,
            "reclaim_detected": reclaim,
            "stop_hunt_detected": stop_hunt,
        }

    def detect_equal_highs(self, candles: List[Dict], tolerance_pct: float = 0.05) -> List[Dict]:
        """Find clusters of highs at nearly the same price level."""
        highs = np.array([c["high"] for c in candles])
        return self._find_equal_levels(highs, candles, tolerance_pct, "high")

    def detect_equal_lows(self, candles: List[Dict], tolerance_pct: float = 0.05) -> List[Dict]:
        """Find clusters of lows at nearly the same price level."""
        lows = np.array([c["low"] for c in candles])
        return self._find_equal_levels(lows, candles, tolerance_pct, "low")

    def _find_equal_levels(self, prices: np.ndarray, candles: List[Dict],
                           tolerance_pct: float, level_type: str) -> List[Dict]:
        """Core logic for finding equal highs or lows."""
        if len(prices) < 3:
            return []

        # Find local extrema first
        lookback = 2
        extrema_indices = []
        for i in range(lookback, len(prices) - lookback):
            if level_type == "high":
                if prices[i] >= np.max(prices[i - lookback:i]) and prices[i] >= np.max(prices[i + 1:i + 1 + lookback]):
                    extrema_indices.append(i)
            else:
                if prices[i] <= np.min(prices[i - lookback:i]) and prices[i] <= np.min(prices[i + 1:i + 1 + lookback]):
                    extrema_indices.append(i)

        if len(extrema_indices) < 2:
            return []

        extrema_prices = prices[extrema_indices]
        results = []
        used = set()

        for i in range(len(extrema_indices)):
            if i in used:
                continue
            cluster_indices = [i]
            ref_price = extrema_prices[i]

            for j in range(i + 1, len(extrema_indices)):
                if j in used:
                    continue
                pct_diff = abs(extrema_prices[j] - ref_price) / ref_price * 100
                if pct_diff <= tolerance_pct:
                    cluster_indices.append(j)
                    used.add(j)

            if len(cluster_indices) >= 2:
                used.add(i)
                level_price = float(np.mean(extrema_prices[cluster_indices]))
                candle_indices = [extrema_indices[ci] for ci in cluster_indices]
                results.append({
                    "level": round(level_price, 6),
                    "type": f"equal_{level_type}s",
                    "count": len(cluster_indices),
                    "candle_indices": candle_indices,
                    "first_touch": candle_indices[0],
                    "last_touch": candle_indices[-1],
                })
        return results

    def detect_liquidity_pools(self, candles: List[Dict]) -> List[Dict]:
        """Identify liquidity pools as clusters of equal highs and equal lows."""
        eq_highs = self.detect_equal_highs(candles)
        eq_lows = self.detect_equal_lows(candles)
        pools = []

        for eh in eq_highs:
            pools.append({
                "level": eh["level"],
                "side": "above",
                "strength": min(eh["count"] / 4.0, 1.0),
                "count": eh["count"],
            })
        for el in eq_lows:
            pools.append({
                "level": el["level"],
                "side": "below",
                "strength": min(el["count"] / 4.0, 1.0),
                "count": el["count"],
            })
        return pools

    def detect_sweep(self, candles: List[Dict], equal_levels: List[Dict]) -> Optional[Dict]:
        """Detect if price pierced an equal level and then reversed back."""
        if not equal_levels or len(candles) < 3:
            return None

        for level_info in reversed(equal_levels):
            level = level_info["level"]
            level_type = level_info.get("type", "")

            for i in range(len(candles) - 2, max(len(candles) - 8, 0), -1):
                c = candles[i]
                next_c = candles[i + 1] if i + 1 < len(candles) else None
                if next_c is None:
                    continue

                if "high" in level_type:
                    if c["high"] > level and next_c["close"] < level:
                        return {
                            "direction": "bearish_sweep",
                            "level": level,
                            "sweep_candle_index": i,
                            "pierce_high": c["high"],
                            "reclaim_close": next_c["close"],
                        }
                elif "low" in level_type:
                    if c["low"] < level and next_c["close"] > level:
                        return {
                            "direction": "bullish_sweep",
                            "level": level,
                            "sweep_candle_index": i,
                            "pierce_low": c["low"],
                            "reclaim_close": next_c["close"],
                        }
        return None

    def detect_reclaim(self, candles: List[Dict], sweep: Optional[Dict]) -> bool:
        """Check if price has reclaimed after a sweep."""
        if sweep is None or len(candles) < 2:
            return False

        level = sweep["level"]
        last_close = candles[-1]["close"]

        if sweep["direction"] == "bearish_sweep":
            return last_close < level
        elif sweep["direction"] == "bullish_sweep":
            return last_close > level
        return False

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "liquidity_above": False,
            "liquidity_below": False,
            "equal_highs": [],
            "equal_lows": [],
            "recent_sweep": None,
            "reclaim_detected": False,
            "stop_hunt_detected": False,
        }
