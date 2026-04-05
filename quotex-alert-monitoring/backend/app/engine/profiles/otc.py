"""
OTC Market Profile - ALERT-ONLY system.
Provides configuration for OTC (over-the-counter) market analysis.
No trade execution - configures analytical parameters only.

OTC markets have different characteristics than live markets:
- More pattern-driven behavior
- Less volume transparency
- Different timing reliability
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


# Sensible defaults for OTC market analysis
# OTC emphasizes pattern detection and de-emphasizes volume-based signals
DEFAULT_OTC_CONFIG: Dict[str, Any] = {
    "market_type": "otc",
    "weights": {
        "market_structure": 14,
        "support_resistance": 13,
        "price_action": 18,
        "liquidity": 5,          # Less reliable in OTC
        "order_blocks": 8,
        "fvg": 7,
        "supply_demand": 10,
        "volume_proxy": 3,       # Volume data unreliable in OTC
        "otc_patterns": 12,      # OTC-specific pattern weight active
    },
    "direction_threshold": 32.0,  # Slightly higher threshold for OTC
    "direction_margin": 10.0,     # Wider margin required for OTC
    "min_ideal_candles": 25,
    "timing_reliability": 0.85,   # OTC has lower timing reliability
}

# Per-expiry overrides for OTC markets
EXPIRY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "1m": {
        "min_ideal_candles": 20,
        "direction_threshold": 35.0,
        "direction_margin": 12.0,
    },
    "2m": {
        "min_ideal_candles": 25,
        "direction_threshold": 32.0,
        "direction_margin": 10.0,
    },
    "3m": {
        "min_ideal_candles": 30,
        "direction_threshold": 30.0,
        "direction_margin": 9.0,
    },
}


class OTCProfile:
    """Configuration profile for OTC market signal analysis.

    ALERT-ONLY: These settings control analytical behavior for OTC markets,
    not trade execution parameters. OTC markets emphasize pattern-based
    detection over volume and liquidity signals.
    """

    def get_config(self, expiry_profile: str) -> Dict[str, Any]:
        """Load and return configuration for an OTC market expiry profile.

        Attempts to load from shared/configs/otc_{expiry}.json first.
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
        config = dict(DEFAULT_OTC_CONFIG)
        config["weights"] = dict(DEFAULT_OTC_CONFIG["weights"])
        config["expiry_profile"] = expiry_profile

        # Apply expiry-specific overrides
        overrides = EXPIRY_OVERRIDES.get(expiry_profile, {})
        config.update(overrides)

        logger.debug(
            "Using default OTC config for expiry '%s' (no config file found)",
            expiry_profile,
        )
        return config

    def _load_from_file(self, expiry_profile: str) -> Dict[str, Any] | None:
        """Attempt to load config from shared/configs/otc_{expiry}.json."""
        filename = f"otc_{expiry_profile}.json"
        filepath = os.path.join(SHARED_CONFIGS_DIR, filename)

        if not os.path.isfile(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info("Loaded OTC profile config from %s", filepath)
            # Ensure required keys exist by merging with defaults
            merged = dict(DEFAULT_OTC_CONFIG)
            merged["weights"] = dict(DEFAULT_OTC_CONFIG["weights"])
            merged.update(config)
            if "weights" in config:
                merged["weights"].update(config["weights"])
            merged["expiry_profile"] = expiry_profile
            return merged
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load config from %s: %s", filepath, exc)
            return None
