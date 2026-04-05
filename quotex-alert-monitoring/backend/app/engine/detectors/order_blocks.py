"""
Order Block Detector - Alert-only analysis module.
Identifies order blocks as the last opposing candle before strong displacement moves.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any


class OrderBlockDetector:
    """Detects order blocks, validates displacement, checks retests and invalidations."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full order block analysis."""
        if len(candles) < 8:
            return self._empty_result()

        all_obs = self.find_order_blocks(candles)
        bullish_obs = [ob for ob in all_obs if ob["type"] == "bullish"]
        bearish_obs = [ob for ob in all_obs if ob["type"] == "bearish"]

        active_obs = []
        retested_obs = []
        invalidated_obs = []

        for ob in all_obs:
            retest = self.check_retest(candles, ob)
            invalid = self.check_invalidation(candles, ob)
            if invalid:
                ob["status"] = "invalidated"
                invalidated_obs.append(ob)
            elif retest:
                ob["status"] = "retested"
                retested_obs.append(ob)
                active_obs.append(ob)
            else:
                ob["status"] = "active"
                active_obs.append(ob)

        return {
            "bullish_obs": bullish_obs,
            "bearish_obs": bearish_obs,
            "active_obs": active_obs,
            "retested_obs": retested_obs,
            "invalidated_obs": invalidated_obs,
        }

    def find_order_blocks(self, candles: List[Dict]) -> List[Dict]:
        """Find order blocks: last opposing candle before strong displacement (3+ candle move)."""
        obs = []
        bodies = np.array([abs(c["close"] - c["open"]) for c in candles])
        avg_body = np.mean(bodies) if len(bodies) > 0 else 0

        for i in range(1, len(candles) - 3):
            # Check for bullish displacement (strong up move after down candle)
            if candles[i]["close"] < candles[i]["open"]:  # bearish candle (opposing)
                if self.validate_displacement(candles, i + 1, direction="bullish"):
                    obs.append({
                        "type": "bullish",
                        "index": i,
                        "zone_high": max(candles[i]["open"], candles[i]["close"]),
                        "zone_low": min(candles[i]["open"], candles[i]["close"]),
                        "candle_high": candles[i]["high"],
                        "candle_low": candles[i]["low"],
                        "displacement_strength": self._displacement_strength(
                            candles, i + 1, avg_body),
                        "timestamp": candles[i].get("timestamp"),
                    })

            # Check for bearish displacement (strong down move after up candle)
            if candles[i]["close"] > candles[i]["open"]:  # bullish candle (opposing)
                if self.validate_displacement(candles, i + 1, direction="bearish"):
                    obs.append({
                        "type": "bearish",
                        "index": i,
                        "zone_high": max(candles[i]["open"], candles[i]["close"]),
                        "zone_low": min(candles[i]["open"], candles[i]["close"]),
                        "candle_high": candles[i]["high"],
                        "candle_low": candles[i]["low"],
                        "displacement_strength": self._displacement_strength(
                            candles, i + 1, avg_body),
                        "timestamp": candles[i].get("timestamp"),
                    })
        return obs

    def validate_displacement(self, candles: List[Dict], idx: int,
                              min_strength: float = 1.5, direction: str = "bullish") -> bool:
        """Validate that displacement candles have large bodies relative to average."""
        if idx + 2 >= len(candles):
            return False

        bodies = np.array([abs(c["close"] - c["open"]) for c in candles])
        avg_body = np.mean(bodies)
        if avg_body <= 0:
            return False

        disp_candles = candles[idx:idx + 3]
        strong_count = 0

        for dc in disp_candles:
            dc_body = abs(dc["close"] - dc["open"])
            if dc_body < avg_body * min_strength:
                continue
            if direction == "bullish" and dc["close"] > dc["open"]:
                strong_count += 1
            elif direction == "bearish" and dc["close"] < dc["open"]:
                strong_count += 1

        # Need at least 2 out of 3 candles to be strong in the right direction
        return strong_count >= 2

    def check_retest(self, candles: List[Dict], ob_zone: Dict) -> bool:
        """Check if price has returned to the order block zone after the displacement."""
        ob_idx = ob_zone["index"]
        zone_high = ob_zone["zone_high"]
        zone_low = ob_zone["zone_low"]

        for i in range(ob_idx + 4, len(candles)):
            candle_low = candles[i]["low"]
            candle_high = candles[i]["high"]

            if ob_zone["type"] == "bullish":
                if candle_low <= zone_high and candle_low >= zone_low:
                    return True
            elif ob_zone["type"] == "bearish":
                if candle_high >= zone_low and candle_high <= zone_high:
                    return True
        return False

    def check_invalidation(self, candles: List[Dict], ob_zone: Dict) -> bool:
        """Check if price has closed decisively through the order block."""
        ob_idx = ob_zone["index"]
        zone_low = ob_zone["zone_low"]
        zone_high = ob_zone["zone_high"]
        zone_range = zone_high - zone_low
        threshold = zone_range * 0.5  # must close beyond zone by 50% of zone width

        for i in range(ob_idx + 4, len(candles)):
            close = candles[i]["close"]
            if ob_zone["type"] == "bullish" and close < zone_low - threshold:
                return True
            elif ob_zone["type"] == "bearish" and close > zone_high + threshold:
                return True
        return False

    def _displacement_strength(self, candles: List[Dict], start_idx: int,
                               avg_body: float) -> float:
        """Compute displacement strength as ratio of move to average body."""
        end_idx = min(start_idx + 3, len(candles))
        if end_idx <= start_idx or avg_body <= 0:
            return 0.0
        total_move = abs(candles[end_idx - 1]["close"] - candles[start_idx]["open"])
        return round(float(total_move / avg_body), 4)

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "bullish_obs": [],
            "bearish_obs": [],
            "active_obs": [],
            "retested_obs": [],
            "invalidated_obs": [],
        }
