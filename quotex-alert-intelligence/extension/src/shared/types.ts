// ============================================================
// Quotex Alert Intelligence - Shared Type Definitions
// ALERT-ONLY system - NO trade execution
// ============================================================

export interface CandleData {
  open: number;
  high: number;
  low: number;
  close: number;
  timestamp: number;
}

export type MarketType = "otc" | "real";
export type ExpiryProfile = "short" | "medium" | "long";
export type PredictionDirection = "CALL" | "PUT";
export type SignalStatus = "pending" | "win" | "loss" | "expired" | "skipped";
export type AlertEventType =
  | "new_signal"
  | "signal_update"
  | "signal_resolved"
  | "connection_status";

export interface Signal {
  signal_id: string;
  market_type: MarketType;
  asset_name: string;
  expiry_profile: ExpiryProfile;
  prediction_direction: PredictionDirection;
  confidence: number;
  bullish_score: number;
  bearish_score: number;
  reasons: string[];
  detected_features: string[];
  status: SignalStatus;
  outcome: SignalStatus | null;
  timestamps: {
    created_at: string;
    evaluated_at: string | null;
    expires_at: string | null;
  };
}

export interface AlertEvent {
  event_type: AlertEventType;
  signal: Signal | null;
  message?: string;
  timestamp?: string;
}

export interface Settings {
  backend_url: string;
  monitoring_enabled: boolean;
  market_mode: MarketType;
  expiry_profile: ExpiryProfile;
  min_confidence_threshold: number;
  sound_alerts_enabled: boolean;
  browser_notifications_enabled: boolean;
  screenshot_logging_enabled: boolean;
  parse_interval_ms: number;
  use_websocket: boolean;
  auto_detect_market: boolean;
}

export interface ChartRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MonitoringState {
  is_monitoring: boolean;
  is_connected: boolean;
  market_type: MarketType | null;
  current_asset: string | null;
  last_alert: AlertEvent | null;
}

export interface HealthResponse {
  status: string;
  version?: string;
  uptime?: number;
}

export interface SignalQueryParams {
  market_type?: MarketType;
  asset_name?: string;
  status?: SignalStatus;
  limit?: number;
  offset?: number;
}

export interface HistoryQueryParams {
  market_type?: MarketType;
  asset_name?: string;
  limit?: number;
  offset?: number;
  from_date?: string;
  to_date?: string;
}

export interface AnalyticsSummary {
  total_signals: number;
  wins: number;
  losses: number;
  pending: number;
  win_rate: number;
  avg_confidence: number;
  by_market: Record<string, { wins: number; losses: number; win_rate: number }>;
  by_asset: Record<string, { wins: number; losses: number; win_rate: number }>;
}

export interface PerformanceData {
  period: string;
  signals: number;
  wins: number;
  losses: number;
  win_rate: number;
}

export interface SignalEvaluationData {
  outcome: "win" | "loss";
  close_price?: number;
  notes?: string;
}

export interface IngestPayload {
  market_type: MarketType;
  asset_name: string;
  expiry_profile: ExpiryProfile;
  candles: CandleData[];
  chart_region?: ChartRegion;
}
