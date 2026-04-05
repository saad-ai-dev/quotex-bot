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
            profile_config = self._load_profile(market_type, expiry_profile)
            detector_results = self._run_detectors(candles, market_type)
            detector_results["_meta"] = {
                "candle_count": len(candles),
                "parse_mode": parse_mode,
                "chart_read_confidence": chart_read_confidence,
            }

            scoring_engine = ScoringEngine(profile_config)
            scores = scoring_engine.compute_scores(detector_results)

            direction = scores["prediction_direction"]
            reasons = self._build_reasons(detector_results, direction)
            detected_features = self._build_detected_features(detector_results)

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
        self, detector_results: Dict[str, Any]
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

        return features
