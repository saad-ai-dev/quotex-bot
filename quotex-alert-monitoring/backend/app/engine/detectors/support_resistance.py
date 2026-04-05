"""
Support and Resistance Detector - Alert-only analysis module.
Identifies key price levels, clusters them into zones, and scores them by relevance.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any


class SupportResistanceDetector:
    """Detects support/resistance levels from price action and scores them."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full support/resistance analysis."""
        if len(candles) < 6:
            return self._empty_result()

        closes = np.array([c["close"] for c in candles])
        current_price = closes[-1]

        peaks, troughs = self.find_local_extrema(candles)

        resistance_zones = self.cluster_levels(peaks)
        support_zones = self.cluster_levels(troughs)

        for zone in resistance_zones:
            zone["score"] = self.score_zone(zone, candles)
        for zone in support_zones:
            zone["score"] = self.score_zone(zone, candles)

        resistance_zones.sort(key=lambda z: z["score"], reverse=True)
        support_zones.sort(key=lambda z: z["score"], reverse=True)

        above = [z for z in resistance_zones if z["level"] > current_price]
        below = [z for z in support_zones if z["level"] < current_price]
        above.sort(key=lambda z: z["level"])
        below.sort(key=lambda z: z["level"], reverse=True)

        nearest_resistance = self._format_zone(above[0]) if above else None
        nearest_support = self._format_zone(below[0]) if below else None

        res_strength = nearest_resistance["strength"] if nearest_resistance else 0.0
        sup_strength = nearest_support["strength"] if nearest_support else 0.0

        return {
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "all_support_zones": [self._format_zone(z) for z in support_zones],
            "all_resistance_zones": [self._format_zone(z) for z in resistance_zones],
            "support_strength": round(sup_strength, 4),
            "resistance_strength": round(res_strength, 4),
        }

    def find_local_extrema(self, candles: List[Dict], lookback: int = 3) -> tuple:
        """Identify peaks (local highs) and troughs (local lows)."""
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        peaks = []
        troughs = []

        for i in range(lookback, len(candles) - lookback):
            left_h = highs[i - lookback:i]
            right_h = highs[i + 1:i + 1 + lookback]
            if highs[i] > np.max(left_h) and highs[i] > np.max(right_h):
                peaks.append(float(highs[i]))

            left_l = lows[i - lookback:i]
            right_l = lows[i + 1:i + 1 + lookback]
            if lows[i] < np.min(left_l) and lows[i] < np.min(right_l):
                troughs.append(float(lows[i]))

        return peaks, troughs

    def cluster_levels(self, levels: List[float], tolerance_pct: float = 0.1) -> List[Dict]:
        """Group nearby price levels into zones using percentage-based clustering."""
        if not levels:
            return []
        sorted_levels = sorted(levels)
        clusters = []
        current_cluster = [sorted_levels[0]]

        for i in range(1, len(sorted_levels)):
            cluster_mean = np.mean(current_cluster)
            pct_diff = abs(sorted_levels[i] - cluster_mean) / cluster_mean * 100
            if pct_diff <= tolerance_pct:
                current_cluster.append(sorted_levels[i])
            else:
                clusters.append(current_cluster[:])
                current_cluster = [sorted_levels[i]]
        clusters.append(current_cluster)

        zones = []
        for cluster in clusters:
            arr = np.array(cluster)
            zones.append({
                "level": float(np.mean(arr)),
                "upper": float(np.max(arr)),
                "lower": float(np.min(arr)),
                "touches": len(cluster),
                "levels": cluster,
            })
        return zones

    def score_zone(self, zone: Dict, candles: List[Dict]) -> float:
        """Score a zone by touch count, rejection strength, freshness, and distance."""
        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        current_price = closes[-1]
        level = zone["level"]

        touch_score = min(zone["touches"] / 5.0, 1.0)

        wick_sizes = []
        for i, c in enumerate(candles):
            upper_wick = c["high"] - max(c["open"], c["close"])
            lower_wick = min(c["open"], c["close"]) - c["low"]
            body = abs(c["close"] - c["open"])
            if abs(c["high"] - level) / level < 0.001 and body > 0:
                wick_sizes.append(upper_wick / body if body > 0 else 0)
            if abs(c["low"] - level) / level < 0.001 and body > 0:
                wick_sizes.append(lower_wick / body if body > 0 else 0)
        rejection_score = min(np.mean(wick_sizes) / 3.0, 1.0) if wick_sizes else 0.0

        recent_window = max(len(candles) // 3, 1)
        recent_closes = closes[-recent_window:]
        recent_touch = np.any(np.abs(recent_closes - level) / level < 0.002)
        freshness_score = 0.8 if recent_touch else 0.3

        dist_pct = abs(current_price - level) / current_price
        distance_score = max(1.0 - dist_pct * 20, 0.0)

        total = (touch_score * 0.3 + rejection_score * 0.25 +
                 freshness_score * 0.25 + distance_score * 0.2)
        return float(np.clip(total, 0.0, 1.0))

    @staticmethod
    def _format_zone(zone: Dict) -> Dict:
        return {
            "level": round(zone["level"], 6),
            "strength": round(zone.get("score", 0.0), 4),
            "touches": zone["touches"],
            "freshness": "recent" if zone.get("score", 0) > 0.5 else "stale",
        }

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "nearest_support": None,
            "nearest_resistance": None,
            "all_support_zones": [],
            "all_resistance_zones": [],
            "support_strength": 0.0,
            "resistance_strength": 0.0,
        }
