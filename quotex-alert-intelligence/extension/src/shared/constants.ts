// ============================================================
// Quotex Alert Intelligence - Constants
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { Settings, MarketType, ExpiryProfile } from "./types";

export const DEFAULT_BACKEND_URL = "http://localhost:8000";

export const WS_URL = "ws://localhost:8000/ws/alerts";

export const QUOTEX_URL_PATTERN =
  /^https?:\/\/(.*\.)?quotex\.(io|com)(\/.*)?$/;

export const MARKET_TYPES: { value: MarketType; label: string }[] = [
  { value: "otc", label: "OTC Market" },
  { value: "real", label: "Real Market" },
];

export const EXPIRY_PROFILES: { value: ExpiryProfile; label: string }[] = [
  { value: "short", label: "Short (30s - 1m)" },
  { value: "medium", label: "Medium (2m - 5m)" },
  { value: "long", label: "Long (10m - 15m)" },
];

export const ALERT_SOUND_URL = "assets/alert.mp3";

export const DEFAULT_SETTINGS: Settings = {
  backend_url: DEFAULT_BACKEND_URL,
  monitoring_enabled: false,
  market_mode: "otc",
  expiry_profile: "medium",
  min_confidence_threshold: 0.65,
  sound_alerts_enabled: true,
  browser_notifications_enabled: true,
  screenshot_logging_enabled: false,
  parse_interval_ms: 5000,
  use_websocket: true,
  auto_detect_market: true,
};

export const STORAGE_KEYS = {
  SETTINGS: "qai_settings",
  MONITORING_STATE: "qai_monitoring_state",
  RECENT_ALERTS: "qai_recent_alerts",
} as const;

export const MAX_RECONNECT_DELAY_MS = 30000;
export const INITIAL_RECONNECT_DELAY_MS = 1000;
export const PING_INTERVAL_MS = 30000;
