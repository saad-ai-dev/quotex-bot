"""
Price Action Detector - Alert-only analysis module.
Identifies candlestick patterns: engulfing, pin bar, rejection, breakout, inside bar, etc.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any


class PriceActionDetector:
    """Detects candlestick-based price action patterns."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all price action pattern detections."""
        if len(candles) < 5:
            return {"patterns": []}

        patterns = []
        patterns.extend(self.detect_engulfing(candles))
        patterns.extend(self.detect_pin_bar(candles))
        patterns.extend(self.detect_rejection_candle(candles))
        patterns.extend(self.detect_breakout_candle(candles))
        patterns.extend(self.detect_failed_breakout(candles))
        patterns.extend(self.detect_inside_bar(candles))
        patterns.extend(self.detect_momentum_candle(candles))
        patterns.extend(self.detect_indecision(candles))

        return {"patterns": patterns}

    def detect_engulfing(self, candles: List[Dict]) -> List[Dict]:
        """Detect bullish/bearish engulfing: current body fully engulfs previous body."""
        results = []
        for i in range(1, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            prev_body_top = max(prev["open"], prev["close"])
            prev_body_bot = min(prev["open"], prev["close"])
            curr_body_top = max(curr["open"], curr["close"])
            curr_body_bot = min(curr["open"], curr["close"])
            curr_body = curr_body_top - curr_body_bot
            prev_body = prev_body_top - prev_body_bot

            if prev_body <= 0:
                continue

            if curr_body_top > prev_body_top and curr_body_bot < prev_body_bot:
                direction = "bullish" if curr["close"] > curr["open"] else "bearish"
                strength = round(min(curr_body / prev_body / 2.0, 1.0), 4)
                results.append({"name": "engulfing", "direction": direction,
                                "strength": strength, "candle_index": i})
        return results

    def detect_pin_bar(self, candles: List[Dict]) -> List[Dict]:
        """Detect pin bars: long wick with small body (wick >= 2x body)."""
        results = []
        for i, c in enumerate(candles):
            body = abs(c["close"] - c["open"])
            upper_wick = c["high"] - max(c["open"], c["close"])
            lower_wick = min(c["open"], c["close"]) - c["low"]
            total_range = c["high"] - c["low"]
            if body <= 0 or total_range <= 0:
                continue

            if upper_wick >= 2 * body and upper_wick > lower_wick:
                strength = round(min(upper_wick / body / 4.0, 1.0), 4)
                results.append({"name": "pin_bar", "direction": "bearish",
                                "strength": strength, "candle_index": i})
            elif lower_wick >= 2 * body and lower_wick > upper_wick:
                strength = round(min(lower_wick / body / 4.0, 1.0), 4)
                results.append({"name": "pin_bar", "direction": "bullish",
                                "strength": strength, "candle_index": i})
        return results

    def detect_rejection_candle(self, candles: List[Dict]) -> List[Dict]:
        """Detect candles with significant wick rejection (wick > 60% of total range)."""
        results = []
        for i, c in enumerate(candles):
            total_range = c["high"] - c["low"]
            if total_range <= 0:
                continue
            upper_wick = c["high"] - max(c["open"], c["close"])
            lower_wick = min(c["open"], c["close"]) - c["low"]

            if upper_wick / total_range > 0.6:
                strength = round(upper_wick / total_range, 4)
                results.append({"name": "rejection_candle", "direction": "bearish",
                                "strength": strength, "candle_index": i})
            elif lower_wick / total_range > 0.6:
                strength = round(lower_wick / total_range, 4)
                results.append({"name": "rejection_candle", "direction": "bullish",
                                "strength": strength, "candle_index": i})
        return results

    def detect_breakout_candle(self, candles: List[Dict], lookback: int = 10) -> List[Dict]:
        """Detect breakout candles: large body, small wicks, closing beyond recent range."""
        results = []
        if len(candles) < lookback + 1:
            return results

        for i in range(lookback, len(candles)):
            c = candles[i]
            body = abs(c["close"] - c["open"])
            total_range = c["high"] - c["low"]
            if total_range <= 0 or body <= 0:
                continue

            body_ratio = body / total_range
            if body_ratio < 0.7:
                continue

            recent_highs = np.array([x["high"] for x in candles[i - lookback:i]])
            recent_lows = np.array([x["low"] for x in candles[i - lookback:i]])
            range_high = np.max(recent_highs)
            range_low = np.min(recent_lows)

            if c["close"] > range_high and c["close"] > c["open"]:
                strength = round(body_ratio, 4)
                results.append({"name": "breakout_candle", "direction": "bullish",
                                "strength": strength, "candle_index": i})
            elif c["close"] < range_low and c["close"] < c["open"]:
                strength = round(body_ratio, 4)
                results.append({"name": "breakout_candle", "direction": "bearish",
                                "strength": strength, "candle_index": i})
        return results

    def detect_failed_breakout(self, candles: List[Dict], lookback: int = 10) -> List[Dict]:
        """Detect failed breakouts: breaks a level then immediately reclaims."""
        results = []
        if len(candles) < lookback + 2:
            return results

        for i in range(lookback + 1, len(candles)):
            prev = candles[i - 1]
            curr = candles[i]
            recent_highs = np.array([x["high"] for x in candles[i - lookback - 1:i - 1]])
            recent_lows = np.array([x["low"] for x in candles[i - lookback - 1:i - 1]])
            range_high = np.max(recent_highs)
            range_low = np.min(recent_lows)

            if prev["high"] > range_high and curr["close"] < range_high:
                results.append({"name": "failed_breakout", "direction": "bearish",
                                "strength": 0.7, "candle_index": i})
            elif prev["low"] < range_low and curr["close"] > range_low:
                results.append({"name": "failed_breakout", "direction": "bullish",
                                "strength": 0.7, "candle_index": i})
        return results

    def detect_inside_bar(self, candles: List[Dict]) -> List[Dict]:
        """Detect inside bars: current high/low entirely within previous high/low."""
        results = []
        for i in range(1, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            if curr["high"] <= prev["high"] and curr["low"] >= prev["low"]:
                direction = "bullish" if curr["close"] > curr["open"] else "bearish"
                prev_range = prev["high"] - prev["low"]
                curr_range = curr["high"] - curr["low"]
                compression = 1.0 - (curr_range / prev_range) if prev_range > 0 else 0.0
                results.append({"name": "inside_bar", "direction": direction,
                                "strength": round(compression, 4), "candle_index": i})
        return results

    def detect_momentum_candle(self, candles: List[Dict], lookback: int = 10) -> List[Dict]:
        """Detect momentum candles: body size significantly above recent average."""
        results = []
        if len(candles) < lookback + 1:
            return results

        bodies = np.array([abs(c["close"] - c["open"]) for c in candles])
        for i in range(lookback, len(candles)):
            avg_body = np.mean(bodies[i - lookback:i])
            if avg_body <= 0:
                continue
            ratio = bodies[i] / avg_body
            if ratio >= 2.0:
                direction = "bullish" if candles[i]["close"] > candles[i]["open"] else "bearish"
                strength = round(min(ratio / 4.0, 1.0), 4)
                results.append({"name": "momentum_candle", "direction": direction,
                                "strength": strength, "candle_index": i})
        return results

    def detect_indecision(self, candles: List[Dict]) -> List[Dict]:
        """Detect indecision/doji candles: small body, roughly equal upper/lower wicks."""
        results = []
        for i, c in enumerate(candles):
            total_range = c["high"] - c["low"]
            if total_range <= 0:
                continue
            body = abs(c["close"] - c["open"])
            upper_wick = c["high"] - max(c["open"], c["close"])
            lower_wick = min(c["open"], c["close"]) - c["low"]

            body_ratio = body / total_range
            if body_ratio > 0.3:
                continue

            if upper_wick <= 0 or lower_wick <= 0:
                continue
            wick_symmetry = min(upper_wick, lower_wick) / max(upper_wick, lower_wick)
            if wick_symmetry > 0.5:
                strength = round((1.0 - body_ratio) * wick_symmetry, 4)
                results.append({"name": "indecision", "direction": "neutral",
                                "strength": strength, "candle_index": i})
        return results
