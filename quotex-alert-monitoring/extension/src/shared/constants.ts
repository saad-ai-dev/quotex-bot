/**
 * Quotex Alert Monitor - Constants
 * ALERT-ONLY: Configuration constants for monitoring and alerting.
 */

/** Default backend API URL */
export const BACKEND_URL = "http://localhost:8000";

/** Ingest endpoint */
export const INGEST_ENDPOINT = "/api/signals/ingest";

/** Price sampling interval in ms (1 second) */
export const PRICE_SAMPLE_INTERVAL_MS = 1000;

/** Candle duration in ms (1 minute) */
export const CANDLE_DURATION_MS = 60_000;

/** How often to send candles to backend in ms (15 seconds) */
export const SEND_INTERVAL_MS = 15_000;

/** Number of candles to send each time */
export const CANDLES_TO_SEND = 30;

/** Quotex price selectors - multiple fallbacks */
export const QUOTEX_PRICE_SELECTORS = [
  ".current-price",
  '[class*="price"]',
  ".chart-price",
  '[class*="value"][class*="price"]',
  '[class*="current"][class*="quote"]',
  "svg text[class*='price']",
];

/** Quotex asset name selectors */
export const QUOTEX_ASSET_SELECTORS = [
  ".pair-name",
  '[class*="asset"]',
  '[class*="pair"]',
  '[class*="symbol"]',
  '[class*="instrument"]',
];

/** Default expiry profile */
export const DEFAULT_EXPIRY_PROFILE = "1m";

/** Default parse mode */
export const DEFAULT_PARSE_MODE = "dom";

/** Default chart read confidence */
export const DEFAULT_CHART_READ_CONFIDENCE = 0.9;
