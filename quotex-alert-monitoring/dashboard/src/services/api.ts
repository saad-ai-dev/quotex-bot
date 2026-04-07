// Use relative URLs so requests go through the same host (works with ngrok proxy)
const BASE_URL = import.meta.env.VITE_API_URL || '';

interface FetchOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, string | number | undefined>;
}

async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, params } = options;

  let url = `${BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '' && value !== 'All' && value !== 'all') {
        searchParams.append(key, String(value));
      }
    });
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`API ${method} ${endpoint} failed (${res.status}): ${text}`);
  }

  return res.json();
}

// --- Types matching the actual backend response shapes ---

export interface Signal {
  signal_id: string;
  prediction_direction: 'UP' | 'DOWN' | 'NO_TRADE';
  confidence: number;
  market_type: string;
  expiry_profile: string;
  asset_name?: string | null;
  bullish_score: number;
  bearish_score: number;
  reasons: string[];
  detected_features?: Record<string, unknown>;
  penalties?: Record<string, number>;
  parse_mode?: string;
  chart_read_confidence?: number;
  candle_count?: number;
  status: string;
  outcome?: string | null;
  entry_price?: number | null;
  close_price?: number | null;
  actual_close?: number | null;
  created_at: string;
  signal_for_close_at?: string | null;
  evaluated_at?: string | null;
  execution_ready?: boolean;
  execution_blockers?: string[];
  was_executed?: boolean;
  execution_status?: string;
  executed_at?: string | null;
}

export interface SignalListResponse {
  signals: Signal[];
  total: number;
  skip: number;
  limit: number;
}

export interface HealthResponse {
  status: string;
  service: string;
  db_status: string;
  uptime_seconds: number;
  description?: string;
}

export interface Settings {
  monitoring_enabled?: boolean;
  market_mode?: string;
  expiry_profile?: string;
  sound_enabled?: boolean;
  min_confidence_threshold?: number;
}

export interface AnalyticsSummary {
  total: number;
  evaluated: number;
  pending: number;
  wins: number;
  losses: number;
  neutral: number;
  unknown: number;
  win_rate: number;
  per_market?: Record<string, { total_evaluated: number; wins: number; losses: number; win_rate: number }>;
  per_expiry?: Record<string, { total_evaluated: number; wins: number; losses: number; win_rate: number }>;
}

// --- API Functions matching actual backend routes ---

export function getHealth(): Promise<HealthResponse> {
  return apiFetch('/health');
}

export function getSettings(): Promise<Settings> {
  return apiFetch('/api/settings/');
}

export function updateSettings(data: Partial<Settings>): Promise<Settings> {
  return apiFetch('/api/settings/', { method: 'PUT', body: data });
}

export function getSignals(params?: Record<string, string | number | undefined>): Promise<SignalListResponse> {
  return apiFetch('/api/signals/', { params });
}

export function getSignal(id: string): Promise<Signal> {
  return apiFetch(`/api/signals/${id}`);
}

export function getHistory(params?: Record<string, string | number | undefined>): Promise<SignalListResponse> {
  return apiFetch('/api/history/', { params });
}

export function getWins(): Promise<SignalListResponse> {
  return apiFetch('/api/history/wins');
}

export function getLosses(): Promise<SignalListResponse> {
  return apiFetch('/api/history/losses');
}

export function getPending(): Promise<SignalListResponse> {
  return apiFetch('/api/history/pending');
}

export function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return apiFetch('/api/analytics/summary');
}

export function getPerformance(): Promise<unknown> {
  return apiFetch('/api/analytics/performance');
}
