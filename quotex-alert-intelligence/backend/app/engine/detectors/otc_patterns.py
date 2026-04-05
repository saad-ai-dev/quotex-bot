"""
OTC Pattern Detector - Alert-only analysis module.
Identifies patterns common in OTC/synthetic markets: spike reversals, compression bursts,
fake breakouts, alternating cycles, stair drifts, and repeated templates.
No trade execution - provides analytical signals only.
"""

import numpy as np
from typing import List, Dict, Any, Optional


class OTCPatternDetector:
    """Detects OTC-specific patterns that are common in synthetic/algorithmic markets."""

    def detect(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all OTC pattern detections."""
        if len(candles) < 8:
            return self._empty_result()

        patterns = []
        patterns.extend(self.detect_spike_reverse(candles))
        patterns.extend(self.detect_compression_burst(candles))
        patterns.extend(self.detect_fake_breakout_reclaim(candles))
        patterns.extend(self.detect_wick_rejection_patterns(candles))
        patterns.extend(self.detect_alternating_cycles(candles))
        patterns.extend(self.detect_stair_drift_snapback(candles))
        patterns.extend(self.detect_equal_sweep_reversal(candles))

        template_score = self.detect_repeated_templates(candles)
        cycle_detected = any(p["name"] == "alternating_cycle" for p in patterns)

        dominant = None
        if patterns:
            name_counts = {}
            for p in patterns:
                name_counts[p["name"]] = name_counts.get(p["name"], 0) + 1
            dominant = max(name_counts, key=name_counts.get)

        return {
            "patterns": patterns,
            "pattern_count": len(patterns),
            "dominant_pattern": dominant,
            "cycle_detected": cycle_detected,
            "template_match_score": round(template_score, 4),
        }

    def detect_spike_reverse(self, candles: List[Dict]) -> List[Dict]:
        """Detect sharp spike followed by immediate reversal."""
        results = []
        ranges = np.array([c["high"] - c["low"] for c in candles])
        avg_range = np.mean(ranges)

        for i in range(1, len(candles) - 1):
            curr = candles[i]
            nxt = candles[i + 1]
            curr_range = curr["high"] - curr["low"]

            if curr_range < avg_range * 2.0:
                continue

            # Spike up then reverse down
            if curr["close"] > curr["open"] and nxt["close"] < nxt["open"]:
                reversal_pct = abs(nxt["close"] - nxt["open"]) / curr_range
                if reversal_pct > 0.4:
                    results.append({
                        "name": "spike_reverse", "direction": "bearish_reversal",
                        "strength": round(min(reversal_pct, 1.0), 4),
                        "candle_index": i,
                    })

            # Spike down then reverse up
            if curr["close"] < curr["open"] and nxt["close"] > nxt["open"]:
                reversal_pct = abs(nxt["close"] - nxt["open"]) / curr_range
                if reversal_pct > 0.4:
                    results.append({
                        "name": "spike_reverse", "direction": "bullish_reversal",
                        "strength": round(min(reversal_pct, 1.0), 4),
                        "candle_index": i,
                    })
        return results

    def detect_compression_burst(self, candles: List[Dict], comp_len: int = 5) -> List[Dict]:
        """Detect narrow range compression followed by breakout candle."""
        results = []
        if len(candles) < comp_len + 2:
            return results

        ranges = np.array([c["high"] - c["low"] for c in candles])
        overall_avg = np.mean(ranges)

        for i in range(comp_len, len(candles) - 1):
            comp_ranges = ranges[i - comp_len:i]
            avg_comp = np.mean(comp_ranges)

            if avg_comp > overall_avg * 0.6:
                continue

            burst_range = ranges[i]
            if burst_range > avg_comp * 2.5:
                direction = "bullish" if candles[i]["close"] > candles[i]["open"] else "bearish"
                strength = round(float(np.clip(burst_range / (avg_comp * 3), 0.0, 1.0)), 4)
                results.append({
                    "name": "compression_burst", "direction": direction,
                    "strength": strength, "candle_index": i,
                })
        return results

    def detect_fake_breakout_reclaim(self, candles: List[Dict], lookback: int = 8) -> List[Dict]:
        """Detect price breaking a level then immediately coming back."""
        results = []
        if len(candles) < lookback + 2:
            return results

        for i in range(lookback, len(candles) - 1):
            window = candles[i - lookback:i]
            window_high = max(c["high"] for c in window)
            window_low = min(c["low"] for c in window)
            curr = candles[i]
            nxt = candles[i + 1]

            if curr["high"] > window_high and nxt["close"] < window_high:
                results.append({
                    "name": "fake_breakout_reclaim", "direction": "bearish",
                    "strength": 0.75, "candle_index": i,
                })
            elif curr["low"] < window_low and nxt["close"] > window_low:
                results.append({
                    "name": "fake_breakout_reclaim", "direction": "bullish",
                    "strength": 0.75, "candle_index": i,
                })
        return results

    def detect_wick_rejection_patterns(self, candles: List[Dict], window: int = 5) -> List[Dict]:
        """Detect repeated wick rejections at a similar level."""
        results = []
        if len(candles) < window:
            return results

        recent = candles[-window:]
        upper_wicks = np.array([c["high"] - max(c["open"], c["close"]) for c in recent])
        lower_wicks = np.array([min(c["open"], c["close"]) - c["low"] for c in recent])
        highs = np.array([c["high"] for c in recent])
        lows = np.array([c["low"] for c in recent])

        # Check for repeated upper wick rejections at similar high
        if np.std(highs) / np.mean(highs) < 0.002 and np.mean(upper_wicks) > 0:
            avg_body = np.mean([abs(c["close"] - c["open"]) for c in recent])
            if avg_body > 0 and np.mean(upper_wicks) > avg_body * 0.5:
                rejection_count = np.sum(upper_wicks > avg_body * 0.3)
                if rejection_count >= 3:
                    results.append({
                        "name": "wick_rejection_pattern", "direction": "bearish",
                        "strength": round(min(rejection_count / 5.0, 1.0), 4),
                        "candle_index": len(candles) - 1,
                    })

        # Check for repeated lower wick rejections at similar low
        if np.std(lows) / np.mean(lows) < 0.002 and np.mean(lower_wicks) > 0:
            avg_body = np.mean([abs(c["close"] - c["open"]) for c in recent])
            if avg_body > 0 and np.mean(lower_wicks) > avg_body * 0.5:
                rejection_count = np.sum(lower_wicks > avg_body * 0.3)
                if rejection_count >= 3:
                    results.append({
                        "name": "wick_rejection_pattern", "direction": "bullish",
                        "strength": round(min(rejection_count / 5.0, 1.0), 4),
                        "candle_index": len(candles) - 1,
                    })
        return results

    def detect_alternating_cycles(self, candles: List[Dict], min_length: int = 4) -> List[Dict]:
        """Detect alternating up/down candles in sequence."""
        results = []
        directions = np.array([1 if c["close"] > c["open"] else -1 for c in candles])

        streak = 1
        best_start = len(candles) - 1
        for i in range(1, len(directions)):
            if directions[i] != directions[i - 1]:
                streak += 1
            else:
                if streak >= min_length:
                    results.append({
                        "name": "alternating_cycle",
                        "direction": "neutral",
                        "strength": round(min(streak / 8.0, 1.0), 4),
                        "candle_index": i - 1,
                    })
                streak = 1

        if streak >= min_length:
            results.append({
                "name": "alternating_cycle", "direction": "neutral",
                "strength": round(min(streak / 8.0, 1.0), 4),
                "candle_index": len(candles) - 1,
            })
        return results

    def detect_stair_drift_snapback(self, candles: List[Dict], drift_len: int = 6) -> List[Dict]:
        """Detect gradual drift in one direction then sharp reversal."""
        results = []
        if len(candles) < drift_len + 2:
            return results

        closes = np.array([c["close"] for c in candles])

        for i in range(drift_len, len(candles) - 1):
            drift_closes = closes[i - drift_len:i + 1]
            diffs = np.diff(drift_closes)

            # Check for consistent small moves in one direction
            if np.all(diffs > 0):
                avg_step = np.mean(diffs)
                snap = candles[i + 1]
                snap_move = snap["open"] - snap["close"]
                if snap_move > avg_step * drift_len * 0.5:
                    results.append({
                        "name": "stair_drift_snapback", "direction": "bearish_snapback",
                        "strength": round(min(snap_move / (avg_step * drift_len), 1.0), 4),
                        "candle_index": i + 1,
                    })
            elif np.all(diffs < 0):
                avg_step = np.mean(np.abs(diffs))
                snap = candles[i + 1]
                snap_move = snap["close"] - snap["open"]
                if snap_move > avg_step * drift_len * 0.5:
                    results.append({
                        "name": "stair_drift_snapback", "direction": "bullish_snapback",
                        "strength": round(min(snap_move / (avg_step * drift_len), 1.0), 4),
                        "candle_index": i + 1,
                    })
        return results

    def detect_repeated_templates(self, candles: List[Dict], template_length: int = 4) -> float:
        """Detect similar candle sequences repeating. Returns a match score 0-1."""
        if len(candles) < template_length * 3:
            return 0.0

        # Normalize candle patterns to relative body/wick ratios
        patterns = []
        for c in candles:
            total_range = c["high"] - c["low"]
            if total_range <= 0:
                patterns.append((0.0, 0.0, 0.0))
                continue
            body = (c["close"] - c["open"]) / total_range
            upper_wick = (c["high"] - max(c["open"], c["close"])) / total_range
            lower_wick = (min(c["open"], c["close"]) - c["low"]) / total_range
            patterns.append((body, upper_wick, lower_wick))

        patterns_arr = np.array(patterns)
        template = patterns_arr[-template_length:]
        best_similarity = 0.0

        for start in range(len(patterns_arr) - template_length * 2):
            candidate = patterns_arr[start:start + template_length]
            diff = np.sum(np.abs(template - candidate))
            max_diff = template_length * 3.0
            similarity = 1.0 - (diff / max_diff)
            best_similarity = max(best_similarity, similarity)

        return float(np.clip(best_similarity, 0.0, 1.0))

    def detect_equal_sweep_reversal(self, candles: List[Dict]) -> List[Dict]:
        """Detect equal highs/lows being swept then price reversing."""
        results = []
        if len(candles) < 8:
            return results

        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])

        # Look for equal highs swept then reversed
        for i in range(3, len(candles) - 2):
            lookback_highs = highs[max(0, i - 6):i]
            if len(lookback_highs) < 2:
                continue
            max_h = np.max(lookback_highs)
            if max_h == 0:
                continue
            near_max = np.sum(np.abs(lookback_highs - max_h) / max_h < 0.001)
            if near_max >= 2 and highs[i] > max_h:
                if i + 1 < len(candles) and candles[i + 1]["close"] < max_h:
                    results.append({
                        "name": "equal_sweep_reversal", "direction": "bearish",
                        "strength": 0.8, "candle_index": i,
                    })

        # Look for equal lows swept then reversed
        for i in range(3, len(candles) - 2):
            lookback_lows = lows[max(0, i - 6):i]
            if len(lookback_lows) < 2:
                continue
            min_l = np.min(lookback_lows)
            if min_l == 0:
                continue
            near_min = np.sum(np.abs(lookback_lows - min_l) / min_l < 0.001)
            if near_min >= 2 and lows[i] < min_l:
                if i + 1 < len(candles) and candles[i + 1]["close"] > min_l:
                    results.append({
                        "name": "equal_sweep_reversal", "direction": "bullish",
                        "strength": 0.8, "candle_index": i,
                    })
        return results

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "patterns": [],
            "pattern_count": 0,
            "dominant_pattern": None,
            "cycle_detected": False,
            "template_match_score": 0.0,
        }
