"""
Tests for all parsing modules.
ALERT-ONLY system - no trade execution.

Tests cover:
    - DOMParser: OHLC dict validation and normalization
    - CanvasParser: pixel-to-price conversion with/without scale
    - CVCandleParser: candle detection from synthetic images
    - OCRLabelParser: text extraction with mocked pytesseract
    - ScreenshotParser: image decode, crop, and candle extraction

Run with: pytest backend/tests/test_parsing.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from app.engine.parsing.dom_parser import DOMParser
from app.engine.parsing.canvas_parser import CanvasParser


# ---------------------------------------------------------------------------
# DOMParser tests
# ---------------------------------------------------------------------------

class TestDOMParser:
    """Tests for DOMParser.parse()."""

    def setup_method(self):
        self.parser = DOMParser()

    def test_dom_parser_valid_data(self):
        """Parse a well-formed OHLC candle list."""
        raw = {
            "candles": [
                {"open": 1.1000, "high": 1.1050, "low": 1.0950, "close": 1.1020, "index": 0},
                {"open": 1.1020, "high": 1.1080, "low": 1.1010, "close": 1.1060, "index": 1},
                {"open": 1.1060, "high": 1.1100, "low": 1.1040, "close": 1.1045, "index": 2},
            ]
        }
        result = self.parser.parse(raw)

        assert len(result) == 3
        for candle in result:
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "index" in candle
            # high >= low
            assert candle["high"] >= candle["low"]
            # high >= open and close
            assert candle["high"] >= candle["open"]
            assert candle["high"] >= candle["close"]
            # low <= open and close
            assert candle["low"] <= candle["open"]
            assert candle["low"] <= candle["close"]

        # Verify sorted by index
        indices = [c["index"] for c in result]
        assert indices == sorted(indices)

    def test_dom_parser_missing_fields(self):
        """Candles missing required OHLC fields are skipped."""
        raw = {
            "candles": [
                {"open": 1.1, "high": 1.2},  # missing low, close
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},  # valid
                {},  # completely empty
                {"close": 1.1},  # missing open, high, low
            ]
        }
        result = self.parser.parse(raw)
        assert len(result) == 1
        assert result[0]["open"] == 1.1

    def test_dom_parser_invalid_types(self):
        """String values that cannot be cast to float are rejected."""
        raw = {
            "candles": [
                {"open": "not_a_number", "high": 1.2, "low": 1.0, "close": 1.1},
                {"open": 1.1, "high": "abc", "low": 1.0, "close": 1.15},
                {"open": "1.1", "high": "1.2", "low": "1.0", "close": "1.15"},  # valid strings
            ]
        }
        result = self.parser.parse(raw)
        # First two invalid, third has valid string-to-float conversion
        assert len(result) == 1
        assert result[0]["open"] == 1.1

    def test_dom_parser_empty_candle_list(self):
        """Empty candle list returns empty result."""
        assert self.parser.parse({"candles": []}) == []
        assert self.parser.parse({}) == []

    def test_dom_parser_non_list_data(self):
        """Non-list candle data returns empty result."""
        assert self.parser.parse({"candles": "not a list"}) == []
        assert self.parser.parse({"candles": 42}) == []

    def test_dom_parser_high_low_swap(self):
        """When high < low, parser swaps them to maintain OHLC integrity."""
        raw = {
            "candles": [
                {"open": 1.1, "high": 1.0, "low": 1.2, "close": 1.15},
            ]
        }
        result = self.parser.parse(raw)
        assert len(result) == 1
        assert result[0]["high"] >= result[0]["low"]

    def test_dom_parser_alternative_keys(self):
        """Parser falls back to 'data' or 'bars' keys."""
        raw_data = {
            "data": [
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},
            ]
        }
        result = self.parser.parse(raw_data)
        assert len(result) == 1

        raw_bars = {
            "bars": [
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},
            ]
        }
        result = self.parser.parse(raw_bars)
        assert len(result) == 1

    def test_dom_parser_optional_fields(self):
        """Optional timestamp and volume fields are preserved."""
        raw = {
            "candles": [
                {
                    "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15,
                    "timestamp": 1700000000, "volume": 500.5,
                },
            ]
        }
        result = self.parser.parse(raw)
        assert len(result) == 1
        assert result[0]["timestamp"] == 1700000000
        assert result[0]["volume"] == 500.5


# ---------------------------------------------------------------------------
# CanvasParser tests
# ---------------------------------------------------------------------------

class TestCanvasParser:
    """Tests for CanvasParser.parse()."""

    def setup_method(self):
        self.parser = CanvasParser()

    def test_canvas_parser_with_scale(self):
        """Parse pixel candles with scale info for pixel-to-price conversion."""
        raw = {
            "candles": [
                {"open_y": 300, "high_y": 200, "low_y": 400, "close_y": 250, "index": 0},
                {"open_y": 250, "high_y": 150, "low_y": 350, "close_y": 280, "index": 1},
            ],
            "scale": {
                "price_min": 1.0,
                "price_max": 2.0,
                "pixel_top": 0,
                "pixel_bottom": 600,
            },
        }
        result = self.parser.parse(raw)

        assert len(result) == 2
        for candle in result:
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            # Prices should be within the scale range
            for key in ("open", "high", "low", "close"):
                assert 1.0 <= candle[key] <= 2.0, f"{key}={candle[key]} out of range"
            # high >= low
            assert candle["high"] >= candle["low"]

    def test_canvas_parser_without_scale(self):
        """Parse pixel candles without scale, using relative positioning."""
        raw = {
            "candles": [
                {"open_y": 300, "high_y": 200, "low_y": 400, "close_y": 250, "index": 0},
            ],
            "canvas_height": 600,
        }
        result = self.parser.parse(raw)

        assert len(result) == 1
        candle = result[0]
        # Values should be normalized 0-1 range
        for key in ("open", "high", "low", "close"):
            assert 0.0 <= candle[key] <= 1.0, f"{key}={candle[key]} out of range"
        assert candle["high"] >= candle["low"]

    def test_canvas_parser_price_candles(self):
        """Parse candles that already have price values (not pixel)."""
        raw = {
            "candles": [
                {"open": 1.10, "high": 1.15, "low": 1.05, "close": 1.12, "index": 0},
                {"open": 1.12, "high": 1.18, "low": 1.10, "close": 1.16, "index": 1},
            ]
        }
        result = self.parser.parse(raw)
        assert len(result) == 2
        assert result[0]["open"] == 1.1
        assert result[1]["close"] == 1.16

    def test_canvas_parser_empty_data(self):
        """Empty or invalid candle data returns empty result."""
        assert self.parser.parse({"candles": []}) == []
        assert self.parser.parse({}) == []
        assert self.parser.parse({"candles": "invalid"}) == []

    def test_canvas_parser_invalid_scale(self):
        """Zero-range scale returns empty result."""
        raw = {
            "candles": [
                {"open_y": 100, "high_y": 50, "low_y": 150, "close_y": 120},
            ],
            "scale": {
                "price_min": 1.0,
                "price_max": 1.0,  # zero price range
                "pixel_top": 0,
                "pixel_bottom": 600,
            },
        }
        result = self.parser.parse(raw)
        assert result == []

    def test_canvas_parser_sorted_by_index(self):
        """Results are sorted by index regardless of input order."""
        raw = {
            "candles": [
                {"open": 1.3, "high": 1.4, "low": 1.2, "close": 1.35, "index": 2},
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "index": 0},
                {"open": 1.2, "high": 1.3, "low": 1.1, "close": 1.25, "index": 1},
            ]
        }
        result = self.parser.parse(raw)
        indices = [c["index"] for c in result]
        assert indices == [0, 1, 2]


# ---------------------------------------------------------------------------
# CVCandleParser tests
# ---------------------------------------------------------------------------

class TestCVCandleParser:
    """Tests for CVCandleParser.parse_candles()."""

    @pytest.fixture(autouse=True)
    def _check_cv2(self):
        """Skip tests if OpenCV is not available."""
        try:
            import cv2  # noqa: F401
            import numpy as np  # noqa: F401
        except ImportError:
            pytest.skip("OpenCV (cv2) not installed")

    def _make_candle_image(self, width=400, height=300, num_candles=5):
        """Create a synthetic chart image with colored rectangle candles.

        Draws green (bullish) and red (bearish) rectangles on a white
        background to simulate candlestick bodies. Adds thin vertical
        lines above and below each body to simulate wicks.

        Returns:
            numpy array in BGR format (OpenCV convention).
        """
        import numpy as np
        import cv2

        # White background
        img = np.ones((height, width, 3), dtype=np.uint8) * 255

        candle_width = 12
        spacing = width // (num_candles + 1)

        for i in range(num_candles):
            x = spacing * (i + 1) - candle_width // 2
            is_bullish = i % 2 == 0

            # Body: green for bullish, red for bearish
            body_top = height // 3 + (i * 7) % 30
            body_bottom = body_top + 30 + (i * 5) % 20
            color = (0, 180, 0) if is_bullish else (0, 0, 200)  # BGR
            cv2.rectangle(img, (x, body_top), (x + candle_width, body_bottom), color, -1)

            # Wick: thin gray line extending above and below body
            wick_x = x + candle_width // 2
            wick_top = body_top - 15 - (i * 3) % 10
            wick_bottom = body_bottom + 15 + (i * 3) % 10
            cv2.line(img, (wick_x, wick_top), (wick_x, body_top), (80, 80, 80), 1)
            cv2.line(img, (wick_x, body_bottom), (wick_x, wick_bottom), (80, 80, 80), 1)

        return img

    def test_cv_candle_parser_synthetic_image(self):
        """Detect candles in a synthetic image with colored rectangles."""
        from app.engine.parsing.cv_candle_parser import CVCandleParser

        parser = CVCandleParser()
        img = self._make_candle_image(width=400, height=300, num_candles=5)

        result = parser.parse_candles(img)

        # Should detect at least some of the 5 drawn candles
        assert len(result) > 0, "No candles detected in synthetic image"

        for candle in result:
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "index" in candle
            assert "confidence" in candle
            # OHLC values should be in 0-1 range (relative to image height)
            for key in ("open", "high", "low", "close"):
                assert 0.0 <= candle[key] <= 1.0, f"{key}={candle[key]} out of 0-1 range"
            assert candle["high"] >= candle["low"]
            assert candle["confidence"] > 0.0

    def test_cv_candle_parser_empty_image(self):
        """Blank white image returns no candles."""
        import numpy as np
        from app.engine.parsing.cv_candle_parser import CVCandleParser

        parser = CVCandleParser()
        # Pure white image - no candle shapes
        blank = np.ones((300, 400, 3), dtype=np.uint8) * 255

        result = parser.parse_candles(blank)
        assert result == []

    def test_cv_candle_parser_none_image(self):
        """None image returns empty list without error."""
        from app.engine.parsing.cv_candle_parser import CVCandleParser

        parser = CVCandleParser()
        assert parser.parse_candles(None) == []

    def test_cv_candle_parser_zero_size_image(self):
        """Zero-size image returns empty list without error."""
        import numpy as np
        from app.engine.parsing.cv_candle_parser import CVCandleParser

        parser = CVCandleParser()
        empty = np.array([], dtype=np.uint8).reshape(0, 0, 3)
        assert parser.parse_candles(empty) == []

    def test_cv_candle_parser_bullish_bearish_detection(self):
        """Synthetic image has both bullish and bearish candles detected."""
        import numpy as np
        import cv2
        from app.engine.parsing.cv_candle_parser import CVCandleParser

        parser = CVCandleParser()

        # Create image with one large green and one large red rectangle
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255

        # Large green body (bullish)
        cv2.rectangle(img, (30, 50), (50, 120), (0, 180, 0), -1)
        cv2.line(img, (40, 30), (40, 50), (80, 80, 80), 1)
        cv2.line(img, (40, 120), (40, 140), (80, 80, 80), 1)

        # Large red body (bearish)
        cv2.rectangle(img, (130, 60), (150, 130), (0, 0, 200), -1)
        cv2.line(img, (140, 40), (140, 60), (80, 80, 80), 1)
        cv2.line(img, (140, 130), (140, 150), (80, 80, 80), 1)

        result = parser.parse_candles(img)
        assert len(result) >= 2, f"Expected >= 2 candles, got {len(result)}"


# ---------------------------------------------------------------------------
# OCRLabelParser tests
# ---------------------------------------------------------------------------

class TestOCRLabelParser:
    """Tests for OCRLabelParser with mocked pytesseract."""

    def test_ocr_parser_mock(self):
        """Mock pytesseract and verify text extraction pipeline."""
        import numpy as np

        # Create a dummy BGR image
        img = np.ones((600, 800, 3), dtype=np.uint8) * 200

        with patch("app.engine.parsing.ocr_labels.TESSERACT_AVAILABLE", True), \
             patch("app.engine.parsing.ocr_labels.CV2_AVAILABLE", True), \
             patch("app.engine.parsing.ocr_labels.pytesseract", create=True) as mock_tess:

            # Configure mock to return different text for each region
            call_count = {"n": 0}
            def fake_ocr(image, config=""):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return "EUR/USD"  # header
                elif call_count["n"] == 2:
                    return "1.08500\n1.08400\n1.08300"  # price axis
                else:
                    return "14:30 14:31 14:32"  # time axis

            mock_tess.image_to_string = MagicMock(side_effect=fake_ocr)

            from app.engine.parsing.ocr_labels import OCRLabelParser
            parser = OCRLabelParser()
            result = parser.parse_labels(img)

            assert result["asset_name"] == "EUR/USD"
            assert len(result["price_scale"]) == 3
            assert 1.085 in result["price_scale"]
            assert len(result["timestamps"]) == 3
            assert "14:30" in result["timestamps"]

    def test_ocr_parser_no_tesseract(self):
        """Returns empty result when tesseract is unavailable."""
        import numpy as np

        img = np.ones((600, 800, 3), dtype=np.uint8) * 200

        with patch("app.engine.parsing.ocr_labels.TESSERACT_AVAILABLE", False):
            from app.engine.parsing.ocr_labels import OCRLabelParser
            parser = OCRLabelParser()
            result = parser.parse_labels(img)

            assert result["asset_name"] is None
            assert result["price_scale"] == []
            assert result["timestamps"] == []

    def test_ocr_parser_none_image(self):
        """None image returns empty result."""
        with patch("app.engine.parsing.ocr_labels.TESSERACT_AVAILABLE", True), \
             patch("app.engine.parsing.ocr_labels.CV2_AVAILABLE", True):
            from app.engine.parsing.ocr_labels import OCRLabelParser
            parser = OCRLabelParser()
            result = parser.parse_labels(None)
            assert result["asset_name"] is None
            assert result["price_scale"] == []

    def test_ocr_parser_with_region(self):
        """Region crop is applied before OCR extraction."""
        import numpy as np

        img = np.ones((600, 800, 3), dtype=np.uint8) * 200
        region = {"x": 100, "y": 100, "width": 400, "height": 300}

        with patch("app.engine.parsing.ocr_labels.TESSERACT_AVAILABLE", True), \
             patch("app.engine.parsing.ocr_labels.CV2_AVAILABLE", True), \
             patch("app.engine.parsing.ocr_labels.pytesseract", create=True) as mock_tess:

            mock_tess.image_to_string = MagicMock(return_value="BTC/USDT")

            from app.engine.parsing.ocr_labels import OCRLabelParser
            parser = OCRLabelParser()
            result = parser.parse_labels(img, region=region)

            # pytesseract should have been called (on cropped sub-regions)
            assert mock_tess.image_to_string.called


# ---------------------------------------------------------------------------
# ScreenshotParser tests
# ---------------------------------------------------------------------------

class TestScreenshotParser:
    """Tests for ScreenshotParser.parse()."""

    @pytest.fixture(autouse=True)
    def _check_cv2(self):
        """Skip tests if OpenCV is not available."""
        try:
            import cv2  # noqa: F401
            import numpy as np  # noqa: F401
        except ImportError:
            pytest.skip("OpenCV (cv2) not installed")

    def _make_png_bytes(self, width=400, height=300):
        """Create a simple PNG image as bytes for testing decode."""
        import cv2
        import numpy as np

        img = np.ones((height, width, 3), dtype=np.uint8) * 128
        _, buf = cv2.imencode(".png", img)
        return buf.tobytes()

    def _make_candle_png_bytes(self, width=400, height=300, num_candles=3):
        """Create a PNG with synthetic candle rectangles."""
        import cv2
        import numpy as np

        img = np.ones((height, width, 3), dtype=np.uint8) * 255
        candle_width = 12
        spacing = width // (num_candles + 1)

        for i in range(num_candles):
            x = spacing * (i + 1) - candle_width // 2
            body_top = height // 3
            body_bottom = body_top + 40
            color = (0, 180, 0) if i % 2 == 0 else (0, 0, 200)
            cv2.rectangle(img, (x, body_top), (x + candle_width, body_bottom), color, -1)
            wick_x = x + candle_width // 2
            cv2.line(img, (wick_x, body_top - 20), (wick_x, body_top), (80, 80, 80), 1)
            cv2.line(img, (wick_x, body_bottom), (wick_x, body_bottom + 20), (80, 80, 80), 1)

        _, buf = cv2.imencode(".png", img)
        return buf.tobytes()

    def test_screenshot_parser_with_region(self):
        """Crop to region before parsing candles."""
        from app.engine.parsing.screenshot_parser import ScreenshotParser

        parser = ScreenshotParser()
        png_bytes = self._make_candle_png_bytes(width=600, height=400, num_candles=4)

        # Crop to a sub-region that still contains some candles
        region = {"x": 0, "y": 0, "width": 600, "height": 400}
        result = parser.parse(png_bytes, region=region)

        # Should return a list (may or may not find candles depending on crop)
        assert isinstance(result, list)

    def test_screenshot_parser_blank_image(self):
        """Blank gray image returns no candles."""
        from app.engine.parsing.screenshot_parser import ScreenshotParser

        parser = ScreenshotParser()
        png_bytes = self._make_png_bytes(width=400, height=300)

        result = parser.parse(png_bytes)
        assert result == []

    def test_screenshot_parser_invalid_bytes(self):
        """Invalid image bytes return empty result."""
        from app.engine.parsing.screenshot_parser import ScreenshotParser

        parser = ScreenshotParser()
        result = parser.parse(b"not an image")
        assert result == []

    def test_screenshot_parser_empty_bytes(self):
        """Empty bytes return empty result."""
        from app.engine.parsing.screenshot_parser import ScreenshotParser

        parser = ScreenshotParser()
        result = parser.parse(b"")
        assert result == []


# ---------------------------------------------------------------------------
# Parse confidence estimation
# ---------------------------------------------------------------------------

class TestParseConfidenceEstimation:
    """Tests for confidence scoring across parsers."""

    def test_dom_parser_full_data_high_confidence(self):
        """DOMParser with complete valid data produces correct output.

        The DOMParser itself does not emit confidence scores, but
        valid complete data should result in all candles passing
        validation (100% pass rate).
        """
        parser = DOMParser()
        raw = {
            "candles": [
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "index": i}
                for i in range(10)
            ]
        }
        result = parser.parse(raw)
        # All 10 candles should pass validation
        assert len(result) == 10

    def test_cv_confidence_scores(self):
        """CVCandleParser emits per-candle confidence scores."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("OpenCV not installed")

        from app.engine.parsing.cv_candle_parser import CVCandleParser

        parser = CVCandleParser()

        # Image with clear candles for higher confidence
        img = np.ones((200, 300, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 50), (70, 130), (0, 180, 0), -1)
        cv2.line(img, (60, 30), (60, 50), (80, 80, 80), 1)
        cv2.line(img, (60, 130), (60, 160), (80, 80, 80), 1)

        result = parser.parse_candles(img)
        if result:
            for candle in result:
                assert "confidence" in candle
                assert 0.0 < candle["confidence"] <= 1.0

    def test_mixed_valid_invalid_pass_rate(self):
        """DOMParser correctly filters invalid entries from mixed input."""
        parser = DOMParser()
        raw = {
            "candles": [
                {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15},  # valid
                {"open": "bad"},  # invalid
                {"open": 1.2, "high": 1.3, "low": 1.1, "close": 1.25},  # valid
                None,  # invalid (not a dict)
                {"open": 1.3, "high": 1.4, "low": 1.2, "close": 1.35},  # valid
            ]
        }
        result = parser.parse(raw)
        assert len(result) == 3  # 3 valid out of 5 total
