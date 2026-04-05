"""
DOM Parser - ALERT-ONLY system.
Parses candle data extracted from Quotex DOM elements by the browser extension.
No trade execution - provides parsed candle data for analysis only.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DOMParser:
    """Parses candle data from DOM-extracted raw data.

    ALERT-ONLY: Produces normalized candle data for analytical detectors,
    not for trade execution.

    Expects raw_data to contain a list of OHLC entries, typically extracted
    by the browser extension from the Quotex chart DOM.
    """

    REQUIRED_FIELDS = ("open", "high", "low", "close")

    def parse(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse and validate candle data from DOM extraction.

        Args:
            raw_data: Dict expected to have a 'candles' key containing a list
                of dicts, each with at minimum 'open', 'high', 'low', 'close'.
                Optional fields: 'timestamp', 'volume', 'index'.

        Returns:
            List of normalized candle dicts sorted by index/timestamp.
        """
        candle_list = raw_data.get("candles", [])
        if not candle_list:
            # Try alternative keys
            candle_list = raw_data.get("data", raw_data.get("bars", []))

        if not isinstance(candle_list, list):
            logger.warning("DOM parser received non-list candle data, type=%s", type(candle_list).__name__)
            return []

        parsed: List[Dict[str, Any]] = []
        for i, entry in enumerate(candle_list):
            candle = self._normalize_candle(entry, fallback_index=i)
            if candle is not None:
                parsed.append(candle)

        if len(parsed) < len(candle_list):
            logger.info(
                "DOM parser: %d/%d candles passed validation",
                len(parsed), len(candle_list),
            )

        # Sort by index to ensure chronological order
        parsed.sort(key=lambda c: c["index"])
        return parsed

    def _normalize_candle(
        self, entry: Any, fallback_index: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Validate and normalize a single candle entry.

        Returns None if the entry is invalid or missing required fields.
        """
        if not isinstance(entry, dict):
            return None

        try:
            o = float(entry["open"])
            h = float(entry["high"])
            l = float(entry["low"])  # noqa: E741
            c = float(entry["close"])
        except (KeyError, TypeError, ValueError):
            return None

        # Basic OHLC sanity checks
        if h < l:
            logger.debug("Candle at index %d has high < low, swapping", fallback_index)
            h, l = l, h  # noqa: E741

        if h < max(o, c):
            h = max(o, c)
        if l > min(o, c):
            l = min(o, c)  # noqa: E741

        candle: Dict[str, Any] = {
            "open": round(o, 6),
            "high": round(h, 6),
            "low": round(l, 6),
            "close": round(c, 6),
            "index": entry.get("index", fallback_index),
        }

        # Optional fields
        if "timestamp" in entry:
            candle["timestamp"] = entry["timestamp"]
        if "volume" in entry:
            try:
                candle["volume"] = float(entry["volume"])
            except (TypeError, ValueError):
                pass

        return candle
