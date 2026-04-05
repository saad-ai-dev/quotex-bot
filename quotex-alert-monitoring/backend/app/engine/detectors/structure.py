"""
Market Structure Detector - Alert-only analysis module.
Identifies trend bias, breaks of structure, changes of character, and chop conditions.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any, Optional


class MarketStructureDetector:
    """Detects market structure elements: swing points, trend bias, BOS, CHoCH, and chop."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run full market structure analysis on candle data."""
        if len(candles) < 6:
            return self._empty_result()

        swing_highs = self.find_swing_highs(candles)
        swing_lows = self.find_swing_lows(candles)
        trend_bias = self.detect_trend_bias(swing_highs, swing_lows)

        all_swings = sorted(swing_highs + swing_lows, key=lambda s: s["index"])
        recent_bos = self.detect_break_of_structure(candles, all_swings)
        recent_choch = self.detect_change_of_character(candles, all_swings)
        chop_prob = self.detect_chop(candles)

        closes = np.array([c["close"] for c in candles])
        momentum_state = self._compute_momentum(closes)

        return {
            "trend_bias": trend_bias,
            "recent_bos": recent_bos,
            "recent_choch": recent_choch,
            "chop_probability": round(chop_prob, 4),
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "momentum_state": momentum_state,
        }

    def find_swing_highs(self, candles: List[Dict], lookback: int = 3) -> List[Dict]:
        """Find local maxima in highs using a rolling window comparison."""
        highs = np.array([c["high"] for c in candles])
        swings = []
        for i in range(lookback, len(highs) - lookback):
            window_left = highs[i - lookback:i]
            window_right = highs[i + 1:i + 1 + lookback]
            if highs[i] > np.max(window_left) and highs[i] > np.max(window_right):
                swings.append({
                    "index": i,
                    "price": float(highs[i]),
                    "type": "high",
                    "timestamp": candles[i].get("timestamp"),
                })
        return swings

    def find_swing_lows(self, candles: List[Dict], lookback: int = 3) -> List[Dict]:
        """Find local minima in lows using a rolling window comparison."""
        lows = np.array([c["low"] for c in candles])
        swings = []
        for i in range(lookback, len(lows) - lookback):
            window_left = lows[i - lookback:i]
            window_right = lows[i + 1:i + 1 + lookback]
            if lows[i] < np.min(window_left) and lows[i] < np.min(window_right):
                swings.append({
                    "index": i,
                    "price": float(lows[i]),
                    "type": "low",
                    "timestamp": candles[i].get("timestamp"),
                })
        return swings

    def detect_trend_bias(self, swing_highs: List[Dict], swing_lows: List[Dict]) -> str:
        """Determine trend bias from swing point sequences.
        HH + HL = bullish, LH + LL = bearish, else ranging."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "ranging"

        sh = swing_highs[-2:]
        sl = swing_lows[-2:]
        higher_highs = sh[1]["price"] > sh[0]["price"]
        higher_lows = sl[1]["price"] > sl[0]["price"]
        lower_highs = sh[1]["price"] < sh[0]["price"]
        lower_lows = sl[1]["price"] < sl[0]["price"]

        if higher_highs and higher_lows:
            return "bullish"
        elif lower_highs and lower_lows:
            return "bearish"
        return "ranging"

    def detect_break_of_structure(self, candles: List[Dict], swings: List[Dict]) -> Optional[Dict]:
        """Detect price breaking past the most recent swing point in the trend direction."""
        if len(swings) < 2 or len(candles) < 2:
            return None

        closes = np.array([c["close"] for c in candles])
        last_candle_close = closes[-1]

        recent_swing_highs = [s for s in swings if s["type"] == "high"]
        recent_swing_lows = [s for s in swings if s["type"] == "low"]

        if recent_swing_highs:
            last_sh = recent_swing_highs[-1]
            if last_candle_close > last_sh["price"]:
                return {"direction": "bullish", "broken_level": last_sh["price"],
                        "swing_index": last_sh["index"]}

        if recent_swing_lows:
            last_sl = recent_swing_lows[-1]
            if last_candle_close < last_sl["price"]:
                return {"direction": "bearish", "broken_level": last_sl["price"],
                        "swing_index": last_sl["index"]}
        return None

    def detect_change_of_character(self, candles: List[Dict], swings: List[Dict]) -> Optional[Dict]:
        """Detect first break against the prevailing trend (CHoCH)."""
        if len(swings) < 4:
            return None

        swing_highs = [s for s in swings if s["type"] == "high"]
        swing_lows = [s for s in swings if s["type"] == "low"]
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None

        prev_trend = self.detect_trend_bias(swing_highs[:-1], swing_lows[:-1])
        closes = np.array([c["close"] for c in candles])
        current_close = closes[-1]

        if prev_trend == "bullish" and swing_lows:
            last_sl = swing_lows[-1]
            if current_close < last_sl["price"]:
                return {"direction": "bearish_choch", "broken_level": last_sl["price"],
                        "previous_trend": "bullish"}

        if prev_trend == "bearish" and swing_highs:
            last_sh = swing_highs[-1]
            if current_close > last_sh["price"]:
                return {"direction": "bullish_choch", "broken_level": last_sh["price"],
                        "previous_trend": "bearish"}
        return None

    def detect_chop(self, candles: List[Dict], window: int = 10) -> float:
        """Compute chop probability: ratio of directionless oscillation in recent window."""
        if len(candles) < window:
            window = len(candles)
        closes = np.array([c["close"] for c in candles[-window:]])
        changes = np.diff(closes)
        if len(changes) < 2:
            return 0.5

        sign_changes = np.sum(np.diff(np.sign(changes)) != 0)
        max_sign_changes = len(changes) - 1
        chop_ratio = sign_changes / max_sign_changes if max_sign_changes > 0 else 0.5

        net_move = abs(closes[-1] - closes[0])
        total_move = np.sum(np.abs(changes))
        efficiency = net_move / total_move if total_move > 0 else 0.0

        chop_prob = (chop_ratio * 0.6) + ((1.0 - efficiency) * 0.4)
        return float(np.clip(chop_prob, 0.0, 1.0))

    def _compute_momentum(self, closes: np.ndarray) -> str:
        """Classify momentum from recent close changes."""
        if len(closes) < 5:
            return "neutral"
        recent = closes[-5:]
        pct_changes = np.diff(recent) / recent[:-1]
        avg_change = np.mean(pct_changes)
        if avg_change > 0.002:
            return "accelerating_up"
        elif avg_change < -0.002:
            return "accelerating_down"
        elif avg_change > 0:
            return "drifting_up"
        elif avg_change < 0:
            return "drifting_down"
        return "neutral"

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "trend_bias": "insufficient_data",
            "recent_bos": None,
            "recent_choch": None,
            "chop_probability": 0.5,
            "swing_highs": [],
            "swing_lows": [],
            "momentum_state": "neutral",
        }
