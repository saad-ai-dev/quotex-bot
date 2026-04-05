"""
Supply and Demand Zone Detector - Alert-only analysis module.
Identifies consolidation bases followed by strong impulse moves as supply/demand zones.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any, Optional


class SupplyDemandDetector:
    """Detects supply and demand zones from price consolidation and impulse patterns."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full supply/demand zone analysis."""
        if len(candles) < 10:
            return self._empty_result()

        demand_zones = self.find_demand_zones(candles)
        supply_zones = self.find_supply_zones(candles)

        for zone in demand_zones:
            zone["score"] = self.score_zone(zone, candles)
        for zone in supply_zones:
            zone["score"] = self.score_zone(zone, candles)

        demand_zones.sort(key=lambda z: z["score"], reverse=True)
        supply_zones.sort(key=lambda z: z["score"], reverse=True)

        current_price = candles[-1]["close"]
        nearest_demand = self._find_nearest(demand_zones, current_price, "below")
        nearest_supply = self._find_nearest(supply_zones, current_price, "above")

        return {
            "demand_zones": demand_zones,
            "supply_zones": supply_zones,
            "nearest_demand": nearest_demand,
            "nearest_supply": nearest_supply,
        }

    def find_demand_zones(self, candles: List[Dict]) -> List[Dict]:
        """Find demand zones: consolidation/base followed by strong upward move."""
        zones = []
        bodies = np.array([abs(c["close"] - c["open"]) for c in candles])
        avg_body = np.mean(bodies)
        if avg_body <= 0:
            return zones

        for i in range(2, len(candles) - 3):
            # Check for consolidation: small bodies in a tight range
            base_candles = candles[i - 2:i + 1]
            base_bodies = bodies[i - 2:i + 1]
            base_ranges = np.array([c["high"] - c["low"] for c in base_candles])

            is_tight = np.all(base_bodies < avg_body * 0.8)
            if not is_tight:
                continue

            base_high = max(c["high"] for c in base_candles)
            base_low = min(c["low"] for c in base_candles)

            # Check for strong departure upward
            impulse_candles = candles[i + 1:min(i + 4, len(candles))]
            impulse_bodies = np.array([abs(ic["close"] - ic["open"]) for ic in impulse_candles])
            bullish_impulse = all(
                ic["close"] > ic["open"] and ib > avg_body * 1.2
                for ic, ib in zip(impulse_candles, impulse_bodies)
            )

            if bullish_impulse and len(impulse_candles) >= 2:
                departure = impulse_candles[-1]["close"] - base_high
                zones.append({
                    "type": "demand",
                    "zone_high": float(base_high),
                    "zone_low": float(base_low),
                    "base_start_index": i - 2,
                    "base_end_index": i,
                    "departure_strength": float(departure / avg_body) if avg_body > 0 else 0.0,
                    "timestamp": candles[i].get("timestamp"),
                })
        return zones

    def find_supply_zones(self, candles: List[Dict]) -> List[Dict]:
        """Find supply zones: consolidation/base followed by strong downward move."""
        zones = []
        bodies = np.array([abs(c["close"] - c["open"]) for c in candles])
        avg_body = np.mean(bodies)
        if avg_body <= 0:
            return zones

        for i in range(2, len(candles) - 3):
            base_candles = candles[i - 2:i + 1]
            base_bodies = bodies[i - 2:i + 1]

            is_tight = np.all(base_bodies < avg_body * 0.8)
            if not is_tight:
                continue

            base_high = max(c["high"] for c in base_candles)
            base_low = min(c["low"] for c in base_candles)

            impulse_candles = candles[i + 1:min(i + 4, len(candles))]
            impulse_bodies = np.array([abs(ic["close"] - ic["open"]) for ic in impulse_candles])
            bearish_impulse = all(
                ic["close"] < ic["open"] and ib > avg_body * 1.2
                for ic, ib in zip(impulse_candles, impulse_bodies)
            )

            if bearish_impulse and len(impulse_candles) >= 2:
                departure = base_low - impulse_candles[-1]["close"]
                zones.append({
                    "type": "supply",
                    "zone_high": float(base_high),
                    "zone_low": float(base_low),
                    "base_start_index": i - 2,
                    "base_end_index": i,
                    "departure_strength": float(departure / avg_body) if avg_body > 0 else 0.0,
                    "timestamp": candles[i].get("timestamp"),
                })
        return zones

    def score_zone(self, zone: Dict, candles: List[Dict]) -> float:
        """Score a zone by freshness, retest count, departure strength, and structure overlap."""
        total_candles = len(candles)
        zone_end = zone["base_end_index"]
        zone_high = zone["zone_high"]
        zone_low = zone["zone_low"]

        # Freshness: more recent zones score higher
        recency_ratio = zone_end / total_candles if total_candles > 0 else 0.0
        freshness_score = recency_ratio

        # Retest count: how many times price returned to zone after formation
        retest_count = 0
        for i in range(zone_end + 3, total_candles):
            if candles[i]["low"] <= zone_high and candles[i]["high"] >= zone_low:
                retest_count += 1
        # Fewer retests = fresher zone = higher score (up to 3 retests is ok)
        retest_score = max(1.0 - retest_count * 0.25, 0.0)

        # Departure strength
        dep_strength = zone.get("departure_strength", 0.0)
        dep_score = float(np.clip(dep_strength / 5.0, 0.0, 1.0))

        # Structure overlap: check if zone aligns with a swing point
        closes = np.array([c["close"] for c in candles])
        zone_mid = (zone_high + zone_low) / 2.0
        near_swing = 0.0
        for i in range(3, total_candles - 3):
            if candles[i]["low"] < candles[i - 1]["low"] and candles[i]["low"] < candles[i + 1]["low"]:
                if abs(candles[i]["low"] - zone_mid) / zone_mid < 0.003:
                    near_swing = 1.0
                    break
            if candles[i]["high"] > candles[i - 1]["high"] and candles[i]["high"] > candles[i + 1]["high"]:
                if abs(candles[i]["high"] - zone_mid) / zone_mid < 0.003:
                    near_swing = 1.0
                    break

        total = (freshness_score * 0.25 + retest_score * 0.25 +
                 dep_score * 0.3 + near_swing * 0.2)
        return round(float(np.clip(total, 0.0, 1.0)), 4)

    def _find_nearest(self, zones: List[Dict], current_price: float,
                      direction: str) -> Optional[Dict]:
        """Find nearest zone above or below current price."""
        candidates = []
        for z in zones:
            mid = (z["zone_high"] + z["zone_low"]) / 2.0
            if direction == "below" and mid < current_price:
                candidates.append(z)
            elif direction == "above" and mid > current_price:
                candidates.append(z)

        if not candidates:
            return None

        if direction == "below":
            candidates.sort(key=lambda z: z["zone_high"], reverse=True)
        else:
            candidates.sort(key=lambda z: z["zone_low"])
        return candidates[0]

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "demand_zones": [],
            "supply_zones": [],
            "nearest_demand": None,
            "nearest_supply": None,
        }
