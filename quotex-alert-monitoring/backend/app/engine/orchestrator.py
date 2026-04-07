"""
Signal Orchestrator - ALERT-ONLY system.
Coordinates all detectors, scoring, and signal generation.
No trade execution - produces alert data for DB storage only.
"""

import logging
from typing import Any, Dict, List, Optional

from app.engine.detectors.structure import MarketStructureDetector
from app.engine.detectors.support_resistance import SupportResistanceDetector
from app.engine.detectors.price_action import PriceActionDetector
from app.engine.detectors.liquidity import LiquidityDetector
from app.engine.detectors.order_blocks import OrderBlockDetector
from app.engine.detectors.fvg import FairValueGapDetector
from app.engine.detectors.supply_demand import SupplyDemandDetector
from app.engine.detectors.volume_proxy import VolumeProxyDetector
from app.engine.detectors.otc_patterns import OTCPatternDetector
from app.engine.scoring_engine import ScoringEngine
from app.engine.profiles.live import LiveProfile
from app.engine.profiles.otc import OTCProfile

logger = logging.getLogger(__name__)


class SignalOrchestrator:
    """Orchestrates detector analysis and scoring to produce alert signals.

    ALERT-ONLY: This class never executes trades. It produces structured
    signal data suitable for database storage and UI display.
    """

    def __init__(self) -> None:
        self._detectors = self._load_detectors()
        self._profiles = {
            "live": LiveProfile(),
            "otc": OTCProfile(),
        }

    def _load_detectors(self) -> Dict[str, Any]:
        """Instantiate all available detector modules."""
        return {
            "market_structure": MarketStructureDetector(),
            "support_resistance": SupportResistanceDetector(),
            "price_action": PriceActionDetector(),
            "liquidity": LiquidityDetector(),
            "order_blocks": OrderBlockDetector(),
            "fvg": FairValueGapDetector(),
            "supply_demand": SupplyDemandDetector(),
            "volume_proxy": VolumeProxyDetector(),
            "otc_patterns": OTCPatternDetector(),
        }

    async def analyze(
        self,
        candles: List[Dict[str, Any]],
        market_type: str,
        expiry_profile: str,
        parse_mode: str = "dom",
        chart_read_confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """Run full analysis pipeline and return signal data dict.

        ALERT-ONLY: Returns analytical data, never executes trades.

        Args:
            candles: List of candle dicts with open, high, low, close keys.
            market_type: 'live' or 'otc'.
            expiry_profile: Expiry duration string, e.g. '1m', '2m', '3m'.
            parse_mode: How candles were obtained ('dom', 'canvas', 'screenshot').
            chart_read_confidence: 0.0-1.0 confidence in parsed candle data quality.

        Returns:
            Complete signal data dict ready for DB storage.
        """
        try:
            # Sanity check: reject mixed-asset candle data
            # All close prices should be within 50% of the median
            if len(candles) >= 3:
                close_vals = [c["close"] for c in candles]
                median_close = sorted(close_vals)[len(close_vals) // 2]
                if median_close > 0:
                    outliers = sum(1 for v in close_vals if abs(v - median_close) / median_close > 0.5)
                    if outliers > len(candles) * 0.2:
                        logger.warning("Candle data looks corrupted (mixed assets?): %d/%d outliers", outliers, len(candles))
                        return {
                            "bullish_score": 0.0, "bearish_score": 0.0, "confidence": 0.0,
                            "prediction_direction": "NO_TRADE",
                            "reasons": ["Candle data appears corrupted (mixed assets)"],
                            "detected_features": {}, "penalties": {},
                            "market_type": market_type, "expiry_profile": expiry_profile,
                            "parse_mode": parse_mode, "chart_read_confidence": chart_read_confidence,
                            "candle_count": len(candles), "detector_results_raw": {},
                        }

            profile_config = self._load_profile(market_type, expiry_profile)
            detector_results = self._run_detectors(candles, market_type)
            detector_results["_meta"] = {
                "candle_count": len(candles),
                "parse_mode": parse_mode,
                "chart_read_confidence": chart_read_confidence,
            }

            scoring_engine = ScoringEngine(profile_config)
            scores = scoring_engine.compute_scores(detector_results)

            # Apply direct trend analysis to boost/correct direction
            scores = self._apply_trend_analysis(candles, scores)

            direction = scores["prediction_direction"]
            reasons = self._build_reasons(detector_results, direction)
            detected_features = self._build_detected_features(detector_results, scores)

            return {
                "bullish_score": scores["bullish_score"],
                "bearish_score": scores["bearish_score"],
                "confidence": scores["confidence"],
                "prediction_direction": direction,
                "reasons": reasons,
                "detected_features": detected_features,
                "penalties": scores["penalties"],
                "market_type": market_type,
                "expiry_profile": expiry_profile,
                "parse_mode": parse_mode,
                "chart_read_confidence": chart_read_confidence,
                "candle_count": len(candles),
                "detector_results_raw": detector_results,
            }

        except Exception as exc:
            logger.exception("Analysis pipeline failed: %s", exc)
            return {
                "bullish_score": 0.0,
                "bearish_score": 0.0,
                "confidence": 0.0,
                "prediction_direction": "NO_TRADE",
                "reasons": [f"Analysis error: {str(exc)}"],
                "detected_features": {},
                "penalties": {},
                "market_type": market_type,
                "expiry_profile": expiry_profile,
                "parse_mode": parse_mode,
                "chart_read_confidence": chart_read_confidence,
                "candle_count": len(candles),
                "detector_results_raw": {},
            }

    def _run_detectors(
        self, candles: List[Dict[str, Any]], market_type: str
    ) -> Dict[str, Any]:
        """Execute each detector and collect results."""
        results: Dict[str, Any] = {}

        for name, detector in self._detectors.items():
            try:
                result = detector.detect(candles)
                results[name] = self._normalize_detector_result(name, result)
            except Exception as exc:
                logger.warning("Detector '%s' failed: %s", name, exc)
                results[name] = {
                    "bullish_contribution": 0.0,
                    "bearish_contribution": 0.0,
                    "error": str(exc),
                }

        return results

    def _normalize_detector_result(
        self, name: str, raw_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure every detector result has bullish/bearish contributions.

        Translates detector-specific outputs into the standard scoring
        interface expected by ScoringEngine. Each contribution is on a 0-10 scale.
        """
        if "bullish_contribution" in raw_result and "bearish_contribution" in raw_result:
            return raw_result

        normalized = dict(raw_result)
        bull = 0.0
        bear = 0.0

        if name == "market_structure":
            trend = raw_result.get("trend_bias", "ranging")
            if trend == "bullish":
                bull += 4.0
            elif trend == "bearish":
                bear += 4.0

            bos = raw_result.get("recent_bos")
            if bos:
                if bos.get("direction") == "bullish":
                    bull += 3.0
                elif bos.get("direction") == "bearish":
                    bear += 3.0

            choch = raw_result.get("recent_choch")
            if choch:
                if choch.get("direction") == "bullish_choch":
                    bull += 2.5
                elif choch.get("direction") == "bearish_choch":
                    bear += 2.5

            momentum = raw_result.get("momentum_state", "neutral")
            if momentum in ("accelerating_up", "drifting_up"):
                bull += 1.5 if "accelerating" in momentum else 0.5
            elif momentum in ("accelerating_down", "drifting_down"):
                bear += 1.5 if "accelerating" in momentum else 0.5

        elif name == "support_resistance":
            sup_str = raw_result.get("support_strength", 0.0)
            res_str = raw_result.get("resistance_strength", 0.0)
            nearest_sup = raw_result.get("nearest_support")
            nearest_res = raw_result.get("nearest_resistance")
            # Strong support below = bullish (price likely to bounce up)
            if nearest_sup:
                bull += min(sup_str * 8.0, 7.0)
            # Strong resistance above = bearish (price likely to reject down)
            if nearest_res:
                bear += min(res_str * 8.0, 7.0)
            # If both are strong, contributions cancel partially
            if nearest_sup and nearest_res:
                bull += 1.5
                bear += 1.5

        elif name == "price_action":
            patterns = raw_result.get("patterns", [])
            for p in patterns:
                direction = p.get("direction", "")
                strength = float(p.get("strength", 0.5))
                score = strength * 3.0
                if "bullish" in direction:
                    bull += score
                elif "bearish" in direction:
                    bear += score

        elif name == "liquidity":
            liq_above = raw_result.get("liquidity_above", False)
            liq_below = raw_result.get("liquidity_below", False)
            sweep = raw_result.get("recent_sweep")
            stop_hunt = raw_result.get("stop_hunt_detected", False)
            # Liquidity above attracts price up (bullish magnet)
            if liq_above:
                bull += 3.0
            # Liquidity below attracts price down (bearish magnet)
            if liq_below:
                bear += 3.0
            # Sweep + reclaim indicates reversal
            if sweep and stop_hunt:
                sweep_dir = sweep.get("direction", "")
                if sweep_dir == "bullish_sweep":
                    bear += 2.0  # swept highs, likely reversal down
                elif sweep_dir == "bearish_sweep":
                    bull += 2.0  # swept lows, likely reversal up

        elif name == "order_blocks":
            active_obs = raw_result.get("active_obs", [])
            retested_obs = raw_result.get("retested_obs", [])
            for ob in active_obs + retested_obs:
                ob_type = ob.get("type", "")
                if ob_type == "bullish":
                    bull += 2.5
                elif ob_type == "bearish":
                    bear += 2.5

        elif name == "fvg":
            bullish_fvgs = raw_result.get("bullish_fvgs", [])
            bearish_fvgs = raw_result.get("bearish_fvgs", [])
            active_fvgs = raw_result.get("active_fvgs", [])
            # Active unfilled FVGs act as magnets
            for fvg in active_fvgs:
                if fvg.get("direction") == "bullish":
                    bull += 2.0
                elif fvg.get("direction") == "bearish":
                    bear += 2.0
            # Count of FVGs adds minor signal
            if bullish_fvgs:
                bull += min(len(bullish_fvgs) * 0.5, 2.0)
            if bearish_fvgs:
                bear += min(len(bearish_fvgs) * 0.5, 2.0)

        elif name == "supply_demand":
            nearest_demand = raw_result.get("nearest_demand")
            nearest_supply = raw_result.get("nearest_supply")
            demand_zones = raw_result.get("demand_zones", [])
            supply_zones = raw_result.get("supply_zones", [])
            # Demand zone below = bullish support
            if nearest_demand:
                score = float(nearest_demand.get("score", 0.5))
                bull += min(score * 6.0, 7.0)
            # Supply zone above = bearish resistance
            if nearest_supply:
                score = float(nearest_supply.get("score", 0.5))
                bear += min(score * 6.0, 7.0)

        elif name == "volume_proxy":
            proxy_score = raw_result.get("proxy_volume_score", 0.0)
            wick_imb = raw_result.get("wick_imbalance", 0.0)
            velocity = raw_result.get("velocity", 0.0)
            burst = raw_result.get("burst_detected", False)
            # Positive wick imbalance = buying pressure (bullish)
            if wick_imb > 0:
                bull += min(abs(wick_imb) * 5.0, 4.0)
            elif wick_imb < 0:
                bear += min(abs(wick_imb) * 5.0, 4.0)
            # Positive velocity = upward momentum
            if velocity > 0:
                bull += min(abs(velocity) * 500, 3.0)
            elif velocity < 0:
                bear += min(abs(velocity) * 500, 3.0)
            # Burst amplifies the direction
            if burst:
                if velocity > 0:
                    bull += 2.0
                elif velocity < 0:
                    bear += 2.0

        elif name == "otc_patterns":
            patterns = raw_result.get("patterns", [])
            for p in patterns:
                direction = p.get("direction", "")
                strength = float(p.get("strength", 0.5))
                score = strength * 3.0
                if "bullish" in direction:
                    bull += score
                elif "bearish" in direction:
                    bear += score
            template_score = raw_result.get("template_score", 0.0)
            # High template score means predictable pattern
            if template_score > 0.6:
                dominant = raw_result.get("dominant_pattern")
                if dominant and "bullish" in dominant.get("direction", ""):
                    bull += 2.0
                elif dominant and "bearish" in dominant.get("direction", ""):
                    bear += 2.0

        normalized["bullish_contribution"] = min(bull, 10.0)
        normalized["bearish_contribution"] = min(bear, 10.0)
        return normalized

    def _apply_trend_analysis(self, candles: List[Dict[str, Any]], scores: Dict[str, Any]) -> Dict[str, Any]:
        """Primary signal generator — adaptive strategy for LIVE and OTC.

        Detects market regime and applies the right strategy:
        1. TRENDING: Pullback entry in dominant trend direction.
        2. ALTERNATING (OTC): Follow the alternation pattern.
        3. FLAT/CHOPPY: NO_TRADE — sit out.

        Rules:
        - Only ONE direction per signal. Never contradictory.
        - High selectivity — skip ambiguous setups.
        """
        if len(candles) < 8:
            scores.setdefault("execution_context", {})
            return scores

        import numpy as np
        closes = np.array([c["close"] for c in candles])
        opens = np.array([c["open"] for c in candles])

        total = len(candles)

        # ================================================================
        # METRICS
        # ================================================================
        ema_fast = float(np.mean(closes[-4:]))
        ema_slow = float(np.mean(closes[-10:])) if total >= 10 else float(np.mean(closes))
        price_change = float(closes[-1]) - float(closes[0])
        price_range = float(np.max(closes) - np.min(closes))
        avg_price = float(np.mean(closes))
        range_pct = (price_range / avg_price * 100) if avg_price > 0 else 0

        full_bull = int(np.sum(closes > opens))
        full_bear = int(np.sum(closes < opens))
        trend_strength = abs(full_bull - full_bear) / total
        recent_window = min(12, total)
        recent_high = float(np.max(closes[-recent_window:]))
        recent_low = float(np.min(closes[-recent_window:]))
        recent_range = recent_high - recent_low
        if recent_range > 0:
            recent_range_position = (float(closes[-1]) - recent_low) / recent_range
        else:
            recent_range_position = 0.5

        # Candle direction sequence (True=bullish, False=bearish, None=doji)
        directions = []
        for c in candles:
            if c["close"] > c["open"]:
                directions.append(True)
            elif c["close"] < c["open"]:
                directions.append(False)
            else:
                directions.append(None)

        last = candles[-1]
        prev = candles[-2] if total >= 2 else None
        last_bullish = last["close"] > last["open"]
        last_bearish = last["close"] < last["open"]
        prev_bullish = prev["close"] > prev["open"] if prev else False
        prev_bearish = prev["close"] < prev["open"] if prev else False

        # ================================================================
        # VOLATILITY FILTER — skip dead/flat markets
        # ================================================================
        min_range_pct = 0.005  # Very low threshold — only skip truly dead markets
        if range_pct < min_range_pct:
            scores["prediction_direction"] = "NO_TRADE"
            return scores

        # ================================================================
        # REGIME DETECTION
        # ================================================================

        # Check for ALTERNATING pattern in last 6 candles
        # Pattern: the last 6 candles alternate direction (UDUDUD or DUDUDU)
        recent_dirs = [d for d in directions[-6:] if d is not None]
        alternating_count = 0
        if len(recent_dirs) >= 4:
            for i in range(1, len(recent_dirs)):
                if recent_dirs[i] != recent_dirs[i - 1]:
                    alternating_count += 1
            alternation_ratio = alternating_count / (len(recent_dirs) - 1)
        else:
            alternation_ratio = 0.0

        is_alternating = alternation_ratio >= 0.60 and len(recent_dirs) >= 4

        # Check for TRENDING
        trend = "NONE"
        if ema_fast > ema_slow and price_change > 0 and full_bull > full_bear:
            trend = "UP"
        elif ema_fast < ema_slow and price_change < 0 and full_bear > full_bull:
            trend = "DOWN"
        elif price_change > 0 and full_bull >= full_bear + 3:
            trend = "UP"
        elif price_change < 0 and full_bear >= full_bull + 3:
            trend = "DOWN"

        is_trending = trend != "NONE" and trend_strength >= 0.20

        # Consecutive candles from the end
        consecutive_up = 0
        consecutive_down = 0
        for c in reversed(candles):
            if c["close"] > c["open"]:
                if consecutive_down > 0:
                    break
                consecutive_up += 1
            elif c["close"] < c["open"]:
                if consecutive_up > 0:
                    break
                consecutive_down += 1
            else:
                break

        signal_direction = "NO_TRADE"
        signal_reason = ""
        strategy_name = "none"
        regime = "RANGING"
        bull_score = scores["bullish_score"]
        bear_score = scores["bearish_score"]
        confidence = scores["confidence"]

        logger.info(
            "Regime: trend=%s str=%.2f alt_ratio=%.2f range=%.4f%% "
            "ema_f=%.5f ema_s=%.5f chg=%.5f bull=%d bear=%d "
            "consec_up=%d consec_dn=%d last_bull=%s",
            trend, trend_strength, alternation_ratio, range_pct,
            ema_fast, ema_slow, price_change, full_bull, full_bear,
            consecutive_up, consecutive_down, last_bullish,
        )

        # ================================================================
        # STRATEGY 1: PULLBACK ENTRY in dominant trend (HIGHEST PRIORITY)
        # Confirmed pullback: prev candle was against trend, last candle
        # is WITH the trend = the pullback is over, trend resumes.
        # ================================================================
        if is_trending:
            regime = "TRENDING"
            # Pullback confirmation: the resumption candle (last) should have a
            # body at least as large as the pullback candle (prev) to confirm
            # the pullback is over and the trend is resuming.
            last_body = abs(last["close"] - last["open"])
            prev_body = abs(prev["close"] - prev["open"]) if prev else 0

            if trend == "DOWN" and last_bearish and prev_bullish and last_body >= prev_body * 0.8:
                # Pullback (prev=bull) ended, trend (last=bear) resumed
                bear_score = min(100, bear_score + 25)
                bull_score = max(0, bull_score - 15)
                confidence = min(100, 50 + trend_strength * 25 + min(range_pct, 0.5) * 10)
                signal_direction = "DOWN"
                signal_reason = f"pullback_entry_down (str={trend_strength:.2f})"
                strategy_name = "pullback_trend"

            elif trend == "UP" and last_bullish and prev_bearish and last_body >= prev_body * 0.8:
                bull_score = min(100, bull_score + 25)
                bear_score = max(0, bear_score - 15)
                confidence = min(100, 50 + trend_strength * 25 + min(range_pct, 0.5) * 10)
                signal_direction = "UP"
                signal_reason = f"pullback_entry_up (str={trend_strength:.2f})"
                strategy_name = "pullback_trend"

        # ================================================================
        # STRATEGY 1b: TREND FOLLOWING (no pullback needed)
        # Controlled continuation entry for strong trends that are not yet
        # overextended. This increases trade frequency without buying/selling
        # the absolute edge of the move.
        # ================================================================
        if signal_direction == "NO_TRADE" and is_trending:
            ema_gap_pct = abs(ema_fast - ema_slow) / avg_price * 100 if avg_price > 0 else 0.0
            not_overextended_up = recent_range_position <= 0.72 and consecutive_up <= 2
            not_overextended_down = recent_range_position >= 0.28 and consecutive_down <= 2

            if (
                trend == "UP"
                and last_bullish
                and trend_strength >= 0.18
                and ema_gap_pct >= 0.02
                and not_overextended_up
            ):
                bull_score = min(100, bull_score + 14)
                bear_score = max(0, bear_score - 8)
                confidence = min(100, max(confidence, 52 + trend_strength * 20))
                signal_direction = "UP"
                signal_reason = f"continuation_up (str={trend_strength:.2f}, gap={ema_gap_pct:.3f}%)"
                strategy_name = "trend_continuation"

            elif (
                trend == "DOWN"
                and last_bearish
                and trend_strength >= 0.18
                and ema_gap_pct >= 0.02
                and not_overextended_down
            ):
                bear_score = min(100, bear_score + 14)
                bull_score = max(0, bull_score - 8)
                confidence = min(100, max(confidence, 52 + trend_strength * 20))
                signal_direction = "DOWN"
                signal_reason = f"continuation_down (str={trend_strength:.2f}, gap={ema_gap_pct:.3f}%)"
                strategy_name = "trend_continuation"

        # ================================================================
        # STRATEGY 2: MEAN REVERSION — after 2-3 moves in one direction,
        # predict REVERSAL. OTC markets tend to bounce back.
        # ================================================================
        if is_alternating and not is_trending:
            regime = "ALTERNATING"

        if signal_direction == "NO_TRADE" and total >= 4 and not is_trending:
            last_moves = []
            for i in range(-3, 0):
                if total + i >= 1:
                    move = float(closes[i]) - float(closes[i - 1])
                    last_moves.append(move)

            if len(last_moves) >= 2:
                # 3-move reversal (strongest signal)
                # Require a meaningful move (>= ~2 pips on majors) to avoid trading on noise
                if len(last_moves) == 3:
                    all_up = all(m > 0 for m in last_moves)
                    all_down = all(m < 0 for m in last_moves)
                    total_move = sum(last_moves)
                    move_pct = abs(total_move) / avg_price * 100 if avg_price > 0 else 0

                    # After 3 UP moves → predict DOWN (reversal)
                    if all_up and move_pct > 0.02:
                        signal_direction = "DOWN"
                        bear_score = min(100, bear_score + 18)
                        confidence = min(100, 52 + move_pct * 50)
                        signal_reason = f"revert_after_3up (move={move_pct:.4f}%)"
                        strategy_name = "mean_reversion"
                    # After 3 DOWN moves → predict UP (reversal)
                    elif all_down and move_pct > 0.02:
                        signal_direction = "UP"
                        bull_score = min(100, bull_score + 18)
                        confidence = min(100, 52 + move_pct * 50)
                        signal_reason = f"revert_after_3down (move={move_pct:.4f}%)"
                        strategy_name = "mean_reversion"

                # 2-move reversal (weaker, needs bigger move — >= ~5 pips on majors)
                if signal_direction == "NO_TRADE":
                    last_2 = last_moves[-2:]
                    both_up = all(m > 0 for m in last_2)
                    both_down = all(m < 0 for m in last_2)
                    total_2 = sum(last_2)
                    move_pct_2 = abs(total_2) / avg_price * 100 if avg_price > 0 else 0

                    if both_up and move_pct_2 > 0.05:
                        signal_direction = "DOWN"
                        bear_score = min(100, bear_score + 12)
                        confidence = min(100, 48 + move_pct_2 * 40)
                        signal_reason = f"revert_after_2up (move={move_pct_2:.4f}%)"
                        strategy_name = "mean_reversion"
                    elif both_down and move_pct_2 > 0.05:
                        signal_direction = "UP"
                        bull_score = min(100, bull_score + 12)
                        confidence = min(100, 48 + move_pct_2 * 40)
                        signal_reason = f"revert_after_2down (move={move_pct_2:.4f}%)"
                        strategy_name = "mean_reversion"

            if last_moves:
                moves_str = ", ".join(f"{m:+.6f}" for m in last_moves)
                logger.info("Momentum check: moves=[%s] signal=%s", moves_str, signal_direction)

        # ================================================================
        # CONFIDENCE GATE — only trade high-conviction setups
        # ================================================================
        if signal_direction != "NO_TRADE" and confidence < 40:
            signal_direction = "NO_TRADE"

        scores["bullish_score"] = round(bull_score, 2)
        scores["bearish_score"] = round(bear_score, 2)
        scores["confidence"] = round(max(0, min(100, confidence)), 2)
        scores["prediction_direction"] = signal_direction
        scores["execution_context"] = {
            "regime": regime,
            "trend": trend,
            "trend_strength": round(trend_strength, 4),
            "alternation_ratio": round(alternation_ratio, 4),
            "range_pct": round(range_pct, 5),
            "recent_range_position": round(recent_range_position, 4),
            "strategy_name": strategy_name,
            "is_trending": is_trending,
            "is_alternating": is_alternating,
            "consecutive_up": consecutive_up,
            "consecutive_down": consecutive_down,
        }

        if signal_reason:
            logger.info(">>> SIGNAL: %s conf=%.1f", signal_reason, confidence)

        return scores

    def _load_profile(self, market_type: str, expiry_profile: str) -> Dict[str, Any]:
        """Load the appropriate profile configuration."""
        profile_key = market_type.lower()
        profile = self._profiles.get(profile_key)
        if profile is None:
            logger.warning(
                "Unknown market type '%s', falling back to live profile", market_type
            )
            profile = self._profiles["live"]
        return profile.get_config(expiry_profile)

    def _build_reasons(
        self, detector_results: Dict[str, Any], direction: str
    ) -> List[str]:
        """Build human-readable list of reasons supporting the signal direction.

        ALERT-ONLY: These reasons explain the analytical finding, not a trade recommendation.
        """
        reasons: List[str] = []

        # Market structure reasons
        structure = detector_results.get("market_structure", {})
        trend = structure.get("trend_bias", "unknown")
        if trend not in ("ranging", "insufficient_data", "unknown"):
            reasons.append(f"Market structure shows {trend} trend bias")

        bos = structure.get("recent_bos")
        if bos:
            reasons.append(
                f"Break of structure detected ({bos['direction']}) "
                f"at price {bos.get('broken_level', 'N/A')}"
            )

        choch = structure.get("recent_choch")
        if choch:
            reasons.append(
                f"Change of character detected ({choch['direction']}), "
                f"previous trend was {choch.get('previous_trend', 'unknown')}"
            )

        chop = structure.get("chop_probability", 0.5)
        if chop > 0.7:
            reasons.append(f"High chop probability ({chop:.1%}) - caution advised")
        elif chop < 0.3:
            reasons.append(f"Low chop probability ({chop:.1%}) - clean price action")

        momentum = structure.get("momentum_state", "neutral")
        if momentum != "neutral":
            reasons.append(f"Momentum state: {momentum.replace('_', ' ')}")

        # Support/resistance reasons
        sr = detector_results.get("support_resistance", {})
        nearest_sup = sr.get("nearest_support")
        nearest_res = sr.get("nearest_resistance")
        if nearest_sup:
            reasons.append(
                f"Support at {nearest_sup.get('level', 'N/A')} "
                f"(strength {nearest_sup.get('strength', 0):.2f})"
            )
        if nearest_res:
            reasons.append(
                f"Resistance at {nearest_res.get('level', 'N/A')} "
                f"(strength {nearest_res.get('strength', 0):.2f})"
            )

        # Price action pattern reasons
        pa = detector_results.get("price_action", {})
        patterns = pa.get("patterns", [])
        if patterns:
            recent = [p for p in patterns if p.get("candle_index", 0) >= len(patterns) - 3]
            if not recent:
                recent = patterns[-3:]
            for p in recent[:3]:
                reasons.append(
                    f"Price action: {p.get('name', 'unknown')} "
                    f"({p.get('direction', 'N/A')}, strength {p.get('strength', 0):.2f})"
                )

        # Liquidity reasons
        liq = detector_results.get("liquidity", {})
        if liq.get("stop_hunt_detected"):
            reasons.append("Stop hunt / liquidity sweep detected with reclaim")
        elif liq.get("recent_sweep"):
            sweep = liq["recent_sweep"]
            reasons.append(f"Liquidity sweep detected ({sweep.get('direction', 'N/A')})")

        # Order block reasons
        ob = detector_results.get("order_blocks", {})
        active_obs = ob.get("active_obs", []) + ob.get("retested_obs", [])
        if active_obs:
            types = [o.get("type", "") for o in active_obs[:2]]
            reasons.append(f"Active order blocks: {', '.join(types)}")

        # FVG reasons
        fvg = detector_results.get("fvg", {})
        active_fvgs = fvg.get("active_fvgs", [])
        if active_fvgs:
            dirs = [f.get("direction", "") for f in active_fvgs[:2]]
            reasons.append(f"Unfilled FVGs: {', '.join(dirs)}")

        # Supply/demand reasons
        sd = detector_results.get("supply_demand", {})
        if sd.get("nearest_demand"):
            reasons.append("Price near demand zone")
        if sd.get("nearest_supply"):
            reasons.append("Price near supply zone")

        # Volume proxy reasons
        vp = detector_results.get("volume_proxy", {})
        if vp.get("burst_detected"):
            reasons.append("Volume burst detected (proxy)")
        vol_state = vp.get("volatility_state")
        if vol_state and vol_state != "normal":
            reasons.append(f"Volatility state: {vol_state}")

        # OTC pattern reasons
        otc = detector_results.get("otc_patterns", {})
        otc_patterns = otc.get("patterns", [])
        if otc_patterns:
            for p in otc_patterns[:2]:
                reasons.append(
                    f"OTC pattern: {p.get('name', 'unknown')} ({p.get('direction', 'N/A')})"
                )

        if direction == "NO_TRADE":
            reasons.append("No clear directional edge detected")

        if not reasons:
            reasons.append("Insufficient detector data for detailed reasoning")

        return reasons

    def _build_detected_features(
        self, detector_results: Dict[str, Any], scores: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a summary dict of all detected features across detectors."""
        features: Dict[str, Any] = {}

        # Market structure
        structure = detector_results.get("market_structure", {})
        features["trend_bias"] = structure.get("trend_bias", "unknown")
        features["has_bos"] = structure.get("recent_bos") is not None
        features["has_choch"] = structure.get("recent_choch") is not None
        features["chop_probability"] = structure.get("chop_probability", 0.5)
        features["momentum_state"] = structure.get("momentum_state", "neutral")
        features["swing_high_count"] = len(structure.get("swing_highs", []))
        features["swing_low_count"] = len(structure.get("swing_lows", []))

        # Support/resistance
        sr = detector_results.get("support_resistance", {})
        features["has_nearby_support"] = sr.get("nearest_support") is not None
        features["has_nearby_resistance"] = sr.get("nearest_resistance") is not None
        features["support_zone_count"] = len(sr.get("all_support_zones", []))
        features["resistance_zone_count"] = len(sr.get("all_resistance_zones", []))

        # Price action
        pa = detector_results.get("price_action", {})
        pa_patterns = pa.get("patterns", [])
        features["price_action_pattern_count"] = len(pa_patterns)
        features["price_action_patterns"] = [
            p.get("name") for p in pa_patterns[-5:]
        ]

        # Liquidity
        liq = detector_results.get("liquidity", {})
        features["liquidity_above"] = liq.get("liquidity_above", False)
        features["liquidity_below"] = liq.get("liquidity_below", False)
        features["stop_hunt_detected"] = liq.get("stop_hunt_detected", False)

        # Order blocks
        ob = detector_results.get("order_blocks", {})
        features["active_order_block_count"] = len(ob.get("active_obs", []))
        features["retested_order_block_count"] = len(ob.get("retested_obs", []))

        # FVG
        fvg = detector_results.get("fvg", {})
        features["active_fvg_count"] = len(fvg.get("active_fvgs", []))
        features["bullish_fvg_count"] = len(fvg.get("bullish_fvgs", []))
        features["bearish_fvg_count"] = len(fvg.get("bearish_fvgs", []))

        # Supply/demand
        sd = detector_results.get("supply_demand", {})
        features["has_nearby_demand"] = sd.get("nearest_demand") is not None
        features["has_nearby_supply"] = sd.get("nearest_supply") is not None

        # Volume proxy
        vp = detector_results.get("volume_proxy", {})
        features["proxy_volume_score"] = vp.get("proxy_volume_score", 0.0)
        features["burst_detected"] = vp.get("burst_detected", False)

        # OTC patterns
        otc = detector_results.get("otc_patterns", {})
        features["otc_pattern_count"] = len(otc.get("patterns", []))

        # Meta
        meta = detector_results.get("_meta", {})
        features["candle_count"] = meta.get("candle_count", 0)
        features["parse_mode"] = meta.get("parse_mode", "unknown")

        execution_context = scores.get("execution_context", {})
        features["regime"] = execution_context.get("regime", "UNKNOWN")
        features["strategy_name"] = execution_context.get("strategy_name", "none")
        features["trend"] = execution_context.get("trend", "NONE")
        features["trend_strength"] = execution_context.get("trend_strength", 0.0)
        features["alternation_ratio"] = execution_context.get("alternation_ratio", 0.0)
        features["range_pct"] = execution_context.get("range_pct", 0.0)
        features["recent_range_position"] = execution_context.get("recent_range_position", 0.5)
        features["consecutive_up"] = execution_context.get("consecutive_up", 0)
        features["consecutive_down"] = execution_context.get("consecutive_down", 0)
        features["agreeing_detector_count"] = scores.get("agreeing_count", 0)
        features["score_gap"] = scores.get("score_gap", 0.0)

        return features
