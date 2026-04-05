"""
Screenshot Parser - ALERT-ONLY system.
Parses candle data from chart screenshot images using computer vision.
No trade execution - provides parsed candle data for analysis only.
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
    logger.warning("OpenCV (cv2) not available - screenshot parsing disabled")


class ScreenshotParser:
    """Parses candle data from chart screenshot images.

    ALERT-ONLY: Extracts candle data from images for analytical detectors,
    not for trade execution.

    Uses OpenCV for image processing and delegates candle detection
    to CVCandleParser.
    """

    def parse(
        self,
        image_bytes: bytes,
        region: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Parse candle data from a screenshot image.

        Args:
            image_bytes: Raw image bytes (PNG, JPG, etc.).
            region: Optional crop region dict with keys 'x', 'y', 'width', 'height'.
                If provided, only this region of the image is analyzed.

        Returns:
            List of candle dicts extracted from the image. Empty list if
            OpenCV is unavailable or parsing fails.
        """
        if not CV2_AVAILABLE:
            logger.error("Cannot parse screenshot: OpenCV not installed")
            return []

        try:
            image = self._decode_image(image_bytes)
            if image is None:
                logger.error("Failed to decode image from bytes")
                return []

            if region is not None:
                image = self._crop_to_region(image, region)
                if image is None:
                    logger.error("Failed to crop image to specified region")
                    return []

            from app.engine.parsing.cv_candle_parser import CVCandleParser
            parser = CVCandleParser()
            candles = parser.parse_candles(image)

            logger.info(
                "Screenshot parser extracted %d candles from image (%dx%d)",
                len(candles), image.shape[1], image.shape[0],
            )
            return candles

        except Exception as exc:
            logger.exception("Screenshot parsing failed: %s", exc)
            return []

    def _decode_image(self, image_bytes: bytes) -> Optional[Any]:
        """Decode raw image bytes into an OpenCV numpy array."""
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return image

    def _crop_to_region(
        self, image: Any, region: Dict[str, int]
    ) -> Optional[Any]:
        """Crop the image to the specified region.

        Args:
            image: OpenCV image (numpy array).
            region: Dict with 'x', 'y', 'width', 'height'.

        Returns:
            Cropped image or None if region is invalid.
        """
        try:
            x = int(region.get("x", 0))
            y = int(region.get("y", 0))
            w = int(region.get("width", image.shape[1]))
            h = int(region.get("height", image.shape[0]))

            img_h, img_w = image.shape[:2]

            # Clamp to image bounds
            x = max(0, min(x, img_w - 1))
            y = max(0, min(y, img_h - 1))
            w = max(1, min(w, img_w - x))
            h = max(1, min(h, img_h - y))

            return image[y : y + h, x : x + w]
        except (TypeError, ValueError) as exc:
            logger.warning("Invalid crop region %s: %s", region, exc)
            return None
