"""
CV Candle Parser - ALERT-ONLY system.
Uses OpenCV to detect candlestick shapes from chart images.
No trade execution - provides parsed candle data for analysis only.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class CVCandleParser:
    """Detects candlestick shapes in chart images using computer vision.

    ALERT-ONLY: Extracts candle geometry from images for analytical purposes,
    not for trade execution.

    Pipeline:
    1. Convert to grayscale and threshold
    2. Detect vertical line segments (wicks) via morphological operations
    3. Detect rectangular regions (bodies) via contour detection
    4. Pair wicks with bodies by horizontal proximity
    5. Determine bullish/bearish from body color (green/red)
    6. Estimate OHLC from pixel positions
    """

    # Minimum body dimensions (pixels)
    MIN_BODY_WIDTH = 3
    MIN_BODY_HEIGHT = 2
    MAX_BODY_WIDTH = 50

    # Wick detection kernel dimensions
    WICK_KERNEL_WIDTH = 1
    WICK_KERNEL_HEIGHT = 7

    def parse_candles(self, image: "np.ndarray") -> List[Dict[str, Any]]:
        """Detect and parse candlestick shapes from a chart image.

        Args:
            image: OpenCV BGR image (numpy array).

        Returns:
            List of candle dicts with open, high, low, close, index,
            and a confidence score for parsing quality.
        """
        if not CV2_AVAILABLE:
            logger.error("OpenCV not available for candle parsing")
            return []

        if image is None or image.size == 0:
            return []

        try:
            img_h, img_w = image.shape[:2]

            # Detect candle bodies and their colors
            bodies = self._detect_bodies(image)
            if not bodies:
                logger.info("No candle bodies detected in image")
                return []

            # Detect wicks
            wicks = self._detect_wicks(image)

            # Pair wicks to bodies
            candles = self._pair_wicks_and_bodies(bodies, wicks, img_h)

            # Sort left to right (chronological)
            candles.sort(key=lambda c: c["center_x"])

            # Convert pixel positions to relative OHLC
            result = []
            for i, candle in enumerate(candles):
                ohlc = self._pixel_to_ohlc(candle, img_h)
                ohlc["index"] = i
                ohlc["confidence"] = candle.get("confidence", 0.5)
                result.append(ohlc)

            overall_confidence = (
                sum(c["confidence"] for c in result) / len(result)
                if result else 0.0
            )
            logger.info(
                "Detected %d candles with avg confidence %.2f",
                len(result), overall_confidence,
            )
            return result

        except Exception as exc:
            logger.exception("CV candle parsing failed: %s", exc)
            return []

    def _detect_bodies(
        self, image: "np.ndarray"
    ) -> List[Dict[str, Any]]:
        """Detect candle body rectangles and classify as bullish/bearish.

        Uses HSV color detection: green bodies = bullish, red bodies = bearish.
        Falls back to brightness if color detection fails.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Green detection (bullish candles)
        green_lower = np.array([35, 40, 40])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        # Red detection (bearish candles) - red wraps around hue 0/180
        red_lower1 = np.array([0, 40, 40])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([170, 40, 40])
        red_upper2 = np.array([180, 255, 255])
        red_mask = cv2.inRange(hsv, red_lower1, red_upper1) | cv2.inRange(hsv, red_lower2, red_upper2)

        bodies: List[Dict[str, Any]] = []

        for mask, is_bullish in [(green_mask, True), (red_mask, False)]:
            # Clean up mask with morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask_clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_OPEN, kernel, iterations=1)

            contours, _ = cv2.findContours(
                mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w < self.MIN_BODY_WIDTH or h < self.MIN_BODY_HEIGHT:
                    continue
                if w > self.MAX_BODY_WIDTH:
                    continue

                # Aspect ratio filter: bodies should be taller or roughly square
                # but not extremely wide
                aspect = w / h if h > 0 else 999
                if aspect > 3.0:
                    continue

                bodies.append({
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "center_x": x + w // 2,
                    "top_y": y,
                    "bottom_y": y + h,
                    "is_bullish": is_bullish,
                    "confidence": 0.7,
                })

        # Remove overlapping detections (same candle detected in both masks)
        bodies = self._remove_overlapping(bodies)
        return bodies

    def _detect_wicks(self, image: "np.ndarray") -> List[Dict[str, Any]]:
        """Detect thin vertical lines representing candle wicks.

        Uses morphological operations with a vertical kernel to isolate
        thin vertical structures.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Threshold to binary
        _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

        # Vertical kernel to detect thin vertical lines
        vert_kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self.WICK_KERNEL_WIDTH, self.WICK_KERNEL_HEIGHT)
        )
        wick_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vert_kernel)

        # Dilate slightly to connect broken wicks
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
        wick_mask = cv2.dilate(wick_mask, dilate_kernel, iterations=1)

        contours, _ = cv2.findContours(
            wick_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        wicks: List[Dict[str, Any]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Wicks should be thin and tall
            if w > 6 or h < 5:
                continue
            wicks.append({
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "center_x": x + w // 2,
                "top_y": y,
                "bottom_y": y + h,
            })

        return wicks

    def _pair_wicks_and_bodies(
        self,
        bodies: List[Dict[str, Any]],
        wicks: List[Dict[str, Any]],
        img_h: int,
    ) -> List[Dict[str, Any]]:
        """Pair detected wicks with their corresponding candle bodies.

        A wick is paired with a body if its horizontal center is within
        the body's horizontal extent.
        """
        candles: List[Dict[str, Any]] = []

        for body in bodies:
            body_left = body["x"]
            body_right = body["x"] + body["width"]
            body_cx = body["center_x"]

            # Find wicks that align horizontally with this body
            matching_wicks = [
                w for w in wicks
                if body_left - 2 <= w["center_x"] <= body_right + 2
            ]

            if matching_wicks:
                # Combine all matching wicks to find wick extent
                wick_top = min(w["top_y"] for w in matching_wicks)
                wick_bottom = max(w["bottom_y"] for w in matching_wicks)
                confidence = 0.8
            else:
                # No wick found: assume body-only candle (doji or small range)
                wick_top = body["top_y"]
                wick_bottom = body["bottom_y"]
                confidence = 0.5

            # Overall candle extent
            candle_top = min(wick_top, body["top_y"])
            candle_bottom = max(wick_bottom, body["bottom_y"])

            candles.append({
                "center_x": body_cx,
                "body_top_y": body["top_y"],
                "body_bottom_y": body["bottom_y"],
                "wick_top_y": candle_top,
                "wick_bottom_y": candle_bottom,
                "is_bullish": body["is_bullish"],
                "confidence": confidence,
            })

        return candles

    def _pixel_to_ohlc(
        self, candle: Dict[str, Any], img_h: int
    ) -> Dict[str, float]:
        """Convert pixel positions to relative OHLC values.

        Uses inverted Y-axis (canvas convention: y=0 is top = highest price).
        Values are normalized to 0-1 range relative to image height.
        """
        if img_h <= 0:
            return {"open": 0, "high": 0, "low": 0, "close": 0}

        # Convert Y pixels to price (inverted: lower Y = higher price)
        high = 1.0 - (candle["wick_top_y"] / img_h)
        low = 1.0 - (candle["wick_bottom_y"] / img_h)

        if candle["is_bullish"]:
            # Bullish: open at body bottom, close at body top
            open_price = 1.0 - (candle["body_bottom_y"] / img_h)
            close_price = 1.0 - (candle["body_top_y"] / img_h)
        else:
            # Bearish: open at body top, close at body bottom
            open_price = 1.0 - (candle["body_top_y"] / img_h)
            close_price = 1.0 - (candle["body_bottom_y"] / img_h)

        return {
            "open": round(open_price, 6),
            "high": round(high, 6),
            "low": round(low, 6),
            "close": round(close_price, 6),
        }

    def _remove_overlapping(
        self, bodies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove overlapping body detections, keeping the one with larger area."""
        if len(bodies) <= 1:
            return bodies

        # Sort by area (largest first)
        bodies.sort(key=lambda b: b["width"] * b["height"], reverse=True)
        kept: List[Dict[str, Any]] = []

        for body in bodies:
            overlaps = False
            bx1, by1 = body["x"], body["y"]
            bx2, by2 = bx1 + body["width"], by1 + body["height"]

            for existing in kept:
                ex1, ey1 = existing["x"], existing["y"]
                ex2, ey2 = ex1 + existing["width"], ey1 + existing["height"]

                # Compute overlap
                ox1 = max(bx1, ex1)
                oy1 = max(by1, ey1)
                ox2 = min(bx2, ex2)
                oy2 = min(by2, ey2)

                if ox1 < ox2 and oy1 < oy2:
                    overlap_area = (ox2 - ox1) * (oy2 - oy1)
                    body_area = body["width"] * body["height"]
                    if body_area > 0 and overlap_area / body_area > 0.5:
                        overlaps = True
                        break

            if not overlaps:
                kept.append(body)

        return kept
