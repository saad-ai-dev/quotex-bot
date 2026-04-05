"""
Live Market Profile - ALERT-ONLY system.
Provides configuration for live (real) market analysis.
No trade execution - configures analytical parameters only.
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Base path for shared config files
SHARED_CONFIGS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "shared", "configs")
)


# Sensible defaults for live market analysis
DEFAULT_LIVE_CONFIG: Dict[str, Any] = {
    "market_type": "live",
    "weights": {
        "market_structure": 15,
        "support_resistance": 15,
        "price_action": 20,
        "liquidity": 10,
        "order_blocks": 10,
        "fvg": 8,
        "supply_demand": 10,
        "volume_proxy": 7,
        "otc_patterns": 0,  # Not used for live markets
    },
    "direction_threshold": 30.0,
    "direction_margin": 8.0,
    "min_ideal_candles": 20,
    "timing_reliability": 1.0,
}

# Per-expiry overrides for live markets
EXPIRY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "1m": {
        "min_ideal_candles": 15,
        "direction_threshold": 32.0,
        "direction_margin": 10.0,
    },
    "2m": {
        "min_ideal_candles": 20,
        "direction_threshold": 30.0,
        "direction_margin": 8.0,
    },
    "3m": {
        "min_ideal_candles": 25,
        "direction_threshold": 28.0,
        "direction_margin": 7.0,
    },
}


class LiveProfile:
    """Configuration profile for live market signal analysis.

    ALERT-ONLY: These settings control analytical behavior,
    not trade execution parameters.
    """

    def get_config(self, expiry_profile: str) -> Dict[str, Any]:
        """Load and return configuration for a live market expiry profile.

        Attempts to load from shared/configs/live_{expiry}.json first.
        Falls back to built-in defaults if the file is not found.

        Args:
            expiry_profile: Expiry duration string, e.g. '1m', '2m', '3m'.

        Returns:
            Complete configuration dict with weights and thresholds.
        """
        # Try loading from file
        config = self._load_from_file(expiry_profile)
        if config is not None:
            return config

        # Build from defaults
        config = dict(DEFAULT_LIVE_CONFIG)
        config["weights"] = dict(DEFAULT_LIVE_CONFIG["weights"])
        config["expiry_profile"] = expiry_profile

        # Apply expiry-specific overrides
        overrides = EXPIRY_OVERRIDES.get(expiry_profile, {})
        config.update(overrides)

        logger.debug(
            "Using default live config for expiry '%s' (no config file found)",
            expiry_profile,
        )
        return config

    def _load_from_file(self, expiry_profile: str) -> Dict[str, Any] | None:
        """Attempt to load config from shared/configs/live_{expiry}.json."""
        filename = f"live_{expiry_profile}.json"
        filepath = os.path.join(SHARED_CONFIGS_DIR, filename)

        if not os.path.isfile(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info("Loaded live profile config from %s", filepath)
            # Ensure required keys exist by merging with defaults
            merged = dict(DEFAULT_LIVE_CONFIG)
            merged["weights"] = dict(DEFAULT_LIVE_CONFIG["weights"])
            merged.update(config)
            if "weights" in config:
                merged["weights"].update(config["weights"])
            merged["expiry_profile"] = expiry_profile
            return merged
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load config from %s: %s", filepath, exc)
            return None
