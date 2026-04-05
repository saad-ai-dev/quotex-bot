/**
 * Quotex Alert Monitor - Shared TypeScript Interfaces
 * ALERT-ONLY: These types support monitoring and alerting.
 * No trade execution types are defined.
 */

/** Direction of the signal alert */
export type SignalDirection = "UP" | "DOWN";

/** A trading signal detected by analysis - ALERT-ONLY, not for execution */
export interface Signal {
  id: string;
  asset: string;
  direction: SignalDirection;
  confidence: number;
  timestamp: string;
}

/** Raw candle data matching backend IngestPayload schema */
export interface CandleData {
  open: number;
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

/** Payload sent to POST /api/signals/ingest */
export interface IngestPayload {
  candles: CandleData[];
  market_type: "LIVE" | "OTC";
  asset_name: string;
  expiry_profile: string;
  parse_mode: string;
  chart_read_confidence: number;
}

/** Message types exchanged between extension components */
export type ExtensionMessage =
  | { type: "GET_STATE" }
  | { type: "STATE_UPDATE"; payload: { monitoring: boolean; connected: boolean; lastSignal: Signal | null } }
  | { type: "TOGGLE_MONITORING"; enabled: boolean }
  | { type: "NEW_SIGNAL"; payload: Signal }
  | { type: "CONTENT_STATUS"; payload: { active: boolean; asset: string; market: string; candleCount: number } };
