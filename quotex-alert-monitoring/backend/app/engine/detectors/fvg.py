"""
Fair Value Gap (FVG) Detector - Alert-only analysis module.
Identifies imbalances between candle wicks indicating unfilled price gaps.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any


class FairValueGapDetector:
    """Detects fair value gaps, tracks fill status, and identifies price reactions."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full FVG analysis."""
        if len(candles) < 5:
            return self._empty_result()

        raw_fvgs = self.find_fvg(candles)

        bullish_fvgs = []
        bearish_fvgs = []
        active_fvgs = []

        for fvg in raw_fvgs:
            fvg["fill_status"] = self.check_fill_status(candles, fvg)
            if fvg["direction"] == "bullish":
                bullish_fvgs.append(fvg)
            else:
                bearish_fvgs.append(fvg)
            if fvg["fill_status"] != "filled":
                active_fvgs.append(fvg)

        current_in_fvg = self._check_current_in_fvg(candles, active_fvgs)
        fvg_ob_overlap = self._check_fvg_ob_overlap(candles, active_fvgs)

        return {
            "bullish_fvgs": bullish_fvgs,
            "bearish_fvgs": bearish_fvgs,
            "active_fvgs": active_fvgs,
            "current_reaction_in_fvg": current_in_fvg,
            "fvg_ob_overlap": fvg_ob_overlap,
        }

    def find_fvg(self, candles: List[Dict]) -> List[Dict]:
        """Find fair value gaps: gap between candle[i-1] wick and candle[i+1] wick.
        Bullish FVG: candle[i-1].high < candle[i+1].low (gap up)
        Bearish FVG: candle[i-1].low > candle[i+1].high (gap down)
        """
        fvgs = []

        for i in range(1, len(candles) - 1):
            prev = candles[i - 1]
            curr = candles[i]
            nxt = candles[i + 1]

            # Bullish FVG: gap between prev high and next low
            if nxt["low"] > prev["high"]:
                gap_size = nxt["low"] - prev["high"]
                mid_body = abs(curr["close"] - curr["open"])
                fvgs.append({
                    "direction": "bullish",
                    "gap_top": float(nxt["low"]),
                    "gap_bottom": float(prev["high"]),
                    "gap_size": float(gap_size),
                    "center": float((nxt["low"] + prev["high"]) / 2.0),
                    "candle_index": i,
                    "impulse_body": float(mid_body),
                    "timestamp": curr.get("timestamp"),
                })

            # Bearish FVG: gap between prev low and next high
            if prev["low"] > nxt["high"]:
                gap_size = prev["low"] - nxt["high"]
                mid_body = abs(curr["close"] - curr["open"])
                fvgs.append({
                    "direction": "bearish",
                    "gap_top": float(prev["low"]),
                    "gap_bottom": float(nxt["high"]),
                    "gap_size": float(gap_size),
                    "center": float((prev["low"] + nxt["high"]) / 2.0),
                    "candle_index": i,
                    "impulse_body": float(mid_body),
                    "timestamp": curr.get("timestamp"),
                })

        return fvgs

    def check_fill_status(self, candles: List[Dict], fvg: Dict) -> str:
        """Check if an FVG has been partially filled, fully filled, or is unfilled."""
        gap_top = fvg["gap_top"]
        gap_bottom = fvg["gap_bottom"]
        fvg_idx = fvg["candle_index"]
        gap_size = gap_top - gap_bottom

        if gap_size <= 0:
            return "filled"

        max_fill_ratio = 0.0

        for i in range(fvg_idx + 2, len(candles)):
            c = candles[i]
            if fvg["direction"] == "bullish":
                # Price needs to come down into the gap
                if c["low"] <= gap_top:
                    penetration = gap_top - max(c["low"], gap_bottom)
                    fill_ratio = penetration / gap_size
                    max_fill_ratio = max(max_fill_ratio, fill_ratio)
            else:
                # Price needs to come up into the gap
                if c["high"] >= gap_bottom:
                    penetration = min(c["high"], gap_top) - gap_bottom
                    fill_ratio = penetration / gap_size
                    max_fill_ratio = max(max_fill_ratio, fill_ratio)

        if max_fill_ratio >= 0.95:
            return "filled"
        elif max_fill_ratio > 0.0:
            return "partially_filled"
        return "unfilled"

    def _check_current_in_fvg(self, candles: List[Dict], active_fvgs: List[Dict]) -> bool:
        """Check if the current price is reacting within an active FVG."""
        if not active_fvgs or not candles:
            return False
        current = candles[-1]
        current_low = current["low"]
        current_high = current["high"]

        for fvg in active_fvgs:
            gap_top = fvg["gap_top"]
            gap_bottom = fvg["gap_bottom"]
            if current_low <= gap_top and current_high >= gap_bottom:
                return True
        return False

    def _check_fvg_ob_overlap(self, candles: List[Dict], active_fvgs: List[Dict]) -> bool:
        """Heuristic check: does any active FVG overlap with a likely order block zone.
        An OB is approximated as the opposing candle before the FVG impulse."""
        if not active_fvgs:
            return False

        for fvg in active_fvgs:
            idx = fvg["candle_index"]
            if idx < 1:
                continue
            ob_candle = candles[idx - 1]
            ob_top = max(ob_candle["open"], ob_candle["close"])
            ob_bottom = min(ob_candle["open"], ob_candle["close"])

            gap_top = fvg["gap_top"]
            gap_bottom = fvg["gap_bottom"]

            # Check zone overlap
            overlap = min(ob_top, gap_top) - max(ob_bottom, gap_bottom)
            if overlap > 0:
                return True
        return False

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "bullish_fvgs": [],
            "bearish_fvgs": [],
            "active_fvgs": [],
            "current_reaction_in_fvg": False,
            "fvg_ob_overlap": False,
        }
