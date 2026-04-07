/**
 * Quotex Alert Monitor - Shared TypeScript Interfaces
 */

export type SignalDirection = "UP" | "DOWN";

export interface Signal {
  id: string;
  asset: string;
  direction: SignalDirection;
  confidence: number;
  timestamp: string;
  executionReady?: boolean;
  executionBlockers?: string[];
}

export interface CandleData {
  open: number;
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

export interface IngestPayload {
  candles: CandleData[];
  market_type: "LIVE" | "OTC";
  asset_name: string;
  expiry_profile: string;
  parse_mode: string;
  chart_read_confidence: number;
}

/** Auto-trade settings */
export interface TradeSettings {
  autoTradeEnabled: boolean;
  maxConsecutiveLosses: number;  // Stop trading after N consecutive losses
}

/** Trade tracking state */
export interface TradeState {
  consecutiveLosses: number;
  totalTrades: number;
  wins: number;
  losses: number;
  tradingPaused: boolean;  // true when max losses hit
  lastTradeDirection: SignalDirection | null;
  lastTradeTime: string | null;
}

/** Message types exchanged between extension components */
export type ExtensionMessage =
  | { type: "GET_STATE" }
  | { type: "STATE_UPDATE"; payload: { monitoring: boolean; connected: boolean; lastSignal: Signal | null } }
  | { type: "TOGGLE_MONITORING"; enabled: boolean }
  | { type: "NEW_SIGNAL"; payload: Signal }
  | { type: "CONTENT_STATUS"; payload: { active: boolean; asset: string; market: string; candleCount: number } }
  // Auto-trade messages
  | { type: "SET_TRADE_SETTINGS"; payload: TradeSettings }
  | { type: "GET_TRADE_STATE" }
  | { type: "EXECUTE_TRADE"; direction: SignalDirection }
  | { type: "TRADE_RESULT"; outcome: "WIN" | "LOSS" }
  | { type: "RESET_TRADE_STATE" }
  | { type: "TRADE_EXECUTED"; direction: SignalDirection; timestamp: string };
