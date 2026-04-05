"""
Canvas Parser - ALERT-ONLY system.
Parses candle data from canvas-extracted pixel coordinate data.
No trade execution - provides parsed candle data for analysis only.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CanvasParser:
    """Parses candle data from canvas pixel extraction.

    ALERT-ONLY: Converts pixel-based chart data into normalized candle
    format for analytical detectors, not for trade execution.

    The browser extension can extract candle positions as pixel coordinates
    from the Quotex HTML5 canvas. This parser converts those pixel values
    back to approximate price levels using scale information.
    """

    def parse(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse candle data from canvas-extracted pixel coordinates.

        Args:
            raw_data: Dict expected to contain:
                - 'candles': list of dicts with pixel-based OHLC
                    (open_y, high_y, low_y, close_y, x) or direct OHLC values.
                - 'scale' (optional): dict with 'price_min', 'price_max',
                    'pixel_top', 'pixel_bottom' for pixel-to-price conversion.
                - 'canvas_height' (optional): height of the canvas element.

        Returns:
            List of normalized candle dicts sorted by position/index.
        """
        candle_list = raw_data.get("candles", [])
        if not isinstance(candle_list, list) or not candle_list:
            logger.warning("Canvas parser received empty or invalid candle list")
            return []

        scale = raw_data.get("scale")
        has_pixel_data = self._is_pixel_data(candle_list[0])

        if has_pixel_data and scale:
            parsed = self._parse_pixel_candles(candle_list, scale)
        elif has_pixel_data and not scale:
            logger.warning(
                "Canvas data has pixel coordinates but no scale info; "
                "using relative positioning"
            )
            parsed = self._parse_pixel_candles_relative(candle_list, raw_data)
        else:
            # Data already has price values, normalize directly
            parsed = self._parse_price_candles(candle_list)

        parsed.sort(key=lambda c: c["index"])
        return parsed

    def _is_pixel_data(self, sample: Any) -> bool:
        """Check whether the candle data uses pixel coordinates."""
        if not isinstance(sample, dict):
            return False
        pixel_keys = {"open_y", "high_y", "low_y", "close_y"}
        return bool(pixel_keys & set(sample.keys()))

    def _parse_pixel_candles(
        self, candle_list: List[Dict], scale: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Convert pixel-coordinate candles to price candles using scale."""
        price_min = float(scale.get("price_min", 0))
        price_max = float(scale.get("price_max", 1))
        pixel_top = float(scale.get("pixel_top", 0))
        pixel_bottom = float(scale.get("pixel_bottom", 1))

        pixel_range = pixel_bottom - pixel_top
        price_range = price_max - price_min

        if pixel_range == 0 or price_range == 0:
            logger.warning("Invalid scale: pixel_range=%s, price_range=%s", pixel_range, price_range)
            return []

        parsed: List[Dict[str, Any]] = []
        for i, entry in enumerate(candle_list):
            try:
                o = self._pixel_to_price(float(entry["open_y"]), pixel_top, pixel_range, price_min, price_range)
                h = self._pixel_to_price(float(entry["high_y"]), pixel_top, pixel_range, price_min, price_range)
                l = self._pixel_to_price(float(entry["low_y"]), pixel_top, pixel_range, price_min, price_range)
                c = self._pixel_to_price(float(entry["close_y"]), pixel_top, pixel_range, price_min, price_range)

                # In canvas, Y is inverted (top=0), so high pixel = low price
                actual_high = max(o, h, l, c)
                actual_low = min(o, h, l, c)

                candle = {
                    "open": round(o, 6),
                    "high": round(actual_high, 6),
                    "low": round(actual_low, 6),
                    "close": round(c, 6),
                    "index": entry.get("index", i),
                }
                if "timestamp" in entry:
                    candle["timestamp"] = entry["timestamp"]
                parsed.append(candle)
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Skipping canvas candle %d: %s", i, exc)
                continue

        return parsed

    def _pixel_to_price(
        self,
        pixel_y: float,
        pixel_top: float,
        pixel_range: float,
        price_min: float,
        price_range: float,
    ) -> float:
        """Convert a Y pixel coordinate to a price value.

        Canvas Y-axis is typically inverted: top of canvas (y=0) = highest price,
        bottom of canvas (y=max) = lowest price.
        """
        # Normalized position (0 = top = highest price, 1 = bottom = lowest price)
        normalized = (pixel_y - pixel_top) / pixel_range
        # Invert: top pixel = max price
        price = price_min + (1.0 - normalized) * price_range
        return price

    def _parse_pixel_candles_relative(
        self, candle_list: List[Dict], raw_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse pixel candles without scale info using relative positioning.

        Without a price scale, we normalize pixel values to a 0-1 range.
        This loses absolute price information but preserves relative candle shapes.
        """
        canvas_height = float(raw_data.get("canvas_height", 600))

        parsed: List[Dict[str, Any]] = []
        for i, entry in enumerate(candle_list):
            try:
                # Normalize to 0-1 range (inverted Y)
                o = 1.0 - (float(entry["open_y"]) / canvas_height)
                h = 1.0 - (float(entry["high_y"]) / canvas_height)
                l = 1.0 - (float(entry["low_y"]) / canvas_height)
                c = 1.0 - (float(entry["close_y"]) / canvas_height)

                actual_high = max(o, h, l, c)
                actual_low = min(o, h, l, c)

                candle = {
                    "open": round(o, 6),
                    "high": round(actual_high, 6),
                    "low": round(actual_low, 6),
                    "close": round(c, 6),
                    "index": entry.get("index", i),
                }
                if "timestamp" in entry:
                    candle["timestamp"] = entry["timestamp"]
                parsed.append(candle)
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Skipping relative candle %d: %s", i, exc)
                continue

        return parsed

    def _parse_price_candles(self, candle_list: List[Dict]) -> List[Dict[str, Any]]:
        """Parse candles that already have direct price values."""
        parsed: List[Dict[str, Any]] = []
        for i, entry in enumerate(candle_list):
            try:
                o = float(entry["open"])
                h = float(entry["high"])
                l = float(entry["low"])  # noqa: E741
                c = float(entry["close"])

                if h < l:
                    h, l = l, h  # noqa: E741
                h = max(h, o, c)
                l = min(l, o, c)  # noqa: E741

                candle: Dict[str, Any] = {
                    "open": round(o, 6),
                    "high": round(h, 6),
                    "low": round(l, 6),
                    "close": round(c, 6),
                    "index": entry.get("index", i),
                }
                if "timestamp" in entry:
                    candle["timestamp"] = entry["timestamp"]
                parsed.append(candle)
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Skipping price candle %d: %s", i, exc)
                continue

        return parsed
