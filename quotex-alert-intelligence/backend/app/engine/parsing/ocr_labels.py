"""
OCR Label Parser - ALERT-ONLY system.
Extracts text labels (prices, timestamps, asset names) from chart images using OCR.
No trade execution - provides contextual label data for analysis only.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.info("pytesseract not available - OCR label parsing disabled")


class OCRLabelParser:
    """Extracts text labels from chart screenshot edges using OCR.

    ALERT-ONLY: Provides contextual information (asset name, price scale,
    timestamps) for analytical enhancement, not for trade execution.
    """

    # Typical label regions as fractions of image dimensions
    PRICE_AXIS_RIGHT_FRACTION = 0.12  # rightmost 12% for price labels
    PRICE_AXIS_LEFT_FRACTION = 0.08   # leftmost 8% for price labels (some layouts)
    TIME_AXIS_BOTTOM_FRACTION = 0.08  # bottom 8% for timestamps
    HEADER_TOP_FRACTION = 0.06        # top 6% for asset name / header

    def parse_labels(
        self,
        image: "np.ndarray",
        region: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Extract text labels from chart image edges.

        Args:
            image: OpenCV BGR image (numpy array).
            region: Optional dict specifying a sub-region to focus on,
                with keys 'x', 'y', 'width', 'height'.

        Returns:
            Dict with keys:
                - asset_name: str or None
                - price_scale: list of float values found on price axis
                - timestamps: list of str timestamps found on time axis
                - raw_text: dict mapping region names to raw OCR output
        """
        empty_result: Dict[str, Any] = {
            "asset_name": None,
            "price_scale": [],
            "timestamps": [],
            "raw_text": {},
        }

        if not TESSERACT_AVAILABLE or not CV2_AVAILABLE:
            logger.debug("OCR dependencies not available, returning empty labels")
            return empty_result

        if image is None or image.size == 0:
            return empty_result

        try:
            if region is not None:
                image = self._crop_to_region(image, region)
                if image is None:
                    return empty_result

            img_h, img_w = image.shape[:2]
            result = dict(empty_result)

            # Extract asset name from header area
            header_region = image[0 : int(img_h * self.HEADER_TOP_FRACTION), :]
            header_text = self._ocr_region(header_region)
            result["raw_text"]["header"] = header_text
            result["asset_name"] = self._extract_asset_name(header_text)

            # Extract price labels from right edge
            right_x = int(img_w * (1.0 - self.PRICE_AXIS_RIGHT_FRACTION))
            price_region = image[:, right_x:]
            price_text = self._ocr_region(price_region)
            result["raw_text"]["price_axis"] = price_text
            result["price_scale"] = self._extract_prices(price_text)

            # Extract timestamps from bottom edge
            bottom_y = int(img_h * (1.0 - self.TIME_AXIS_BOTTOM_FRACTION))
            time_region = image[bottom_y:, :]
            time_text = self._ocr_region(time_region)
            result["raw_text"]["time_axis"] = time_text
            result["timestamps"] = self._extract_timestamps(time_text)

            logger.info(
                "OCR extracted: asset=%s, %d prices, %d timestamps",
                result["asset_name"],
                len(result["price_scale"]),
                len(result["timestamps"]),
            )
            return result

        except Exception as exc:
            logger.exception("OCR label parsing failed: %s", exc)
            return empty_result

    def _crop_to_region(
        self, image: "np.ndarray", region: Dict[str, int]
    ) -> Optional["np.ndarray"]:
        """Crop image to specified region."""
        try:
            x = int(region.get("x", 0))
            y = int(region.get("y", 0))
            w = int(region.get("width", image.shape[1]))
            h = int(region.get("height", image.shape[0]))
            img_h, img_w = image.shape[:2]
            x = max(0, min(x, img_w - 1))
            y = max(0, min(y, img_h - 1))
            w = max(1, min(w, img_w - x))
            h = max(1, min(h, img_h - y))
            return image[y : y + h, x : x + w]
        except (TypeError, ValueError):
            return None

    def _ocr_region(self, region_image: "np.ndarray") -> str:
        """Run OCR on an image region and return raw text."""
        if region_image is None or region_image.size == 0:
            return ""

        # Preprocess: convert to grayscale, increase contrast, threshold
        gray = cv2.cvtColor(region_image, cv2.COLOR_BGR2GRAY)
        # Apply adaptive thresholding for better text detection
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2,
        )

        # Upscale small regions for better OCR accuracy
        h, w = thresh.shape
        if h < 40 or w < 100:
            scale = max(2, 60 // max(h, 1))
            thresh = cv2.resize(
                thresh, (w * scale, h * scale),
                interpolation=cv2.INTER_CUBIC,
            )

        try:
            text = pytesseract.image_to_string(
                thresh,
                config="--psm 6 -c tessedit_char_whitelist=0123456789.:/-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ",
            )
            return text.strip()
        except Exception as exc:
            logger.debug("Tesseract OCR failed: %s", exc)
            return ""

    def _extract_asset_name(self, header_text: str) -> Optional[str]:
        """Extract asset/pair name from header text.

        Looks for common patterns like 'EUR/USD', 'BTC/USDT', 'GOLD', etc.
        """
        if not header_text:
            return None

        import re

        # Match currency pair patterns: ABC/DEF or ABC-DEF
        pair_match = re.search(r"[A-Z]{2,6}[/\-][A-Z]{2,6}", header_text.upper())
        if pair_match:
            return pair_match.group(0)

        # Match single asset names (at least 3 uppercase letters)
        asset_match = re.search(r"\b[A-Z]{3,10}\b", header_text.upper())
        if asset_match:
            return asset_match.group(0)

        return None

    def _extract_prices(self, price_text: str) -> List[float]:
        """Extract numerical price values from price axis text."""
        if not price_text:
            return []

        import re

        prices: List[float] = []
        # Match decimal numbers (e.g., 1.23456, 45678.90)
        matches = re.findall(r"\d+\.?\d*", price_text)
        for m in matches:
            try:
                val = float(m)
                if val > 0:
                    prices.append(val)
            except ValueError:
                continue

        # Sort prices descending (top of chart = highest price)
        prices.sort(reverse=True)
        return prices

    def _extract_timestamps(self, time_text: str) -> List[str]:
        """Extract timestamp strings from time axis text."""
        if not time_text:
            return []

        import re

        timestamps: List[str] = []

        # Match HH:MM or HH:MM:SS patterns
        time_matches = re.findall(r"\d{1,2}:\d{2}(?::\d{2})?", time_text)
        timestamps.extend(time_matches)

        # Match date patterns like YYYY-MM-DD or MM/DD
        date_matches = re.findall(
            r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}", time_text
        )
        timestamps.extend(date_matches)

        return timestamps
