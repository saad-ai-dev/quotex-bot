// ============================================================
// Quotex Alert Intelligence - API Client
// ALERT-ONLY system - NO trade execution
// ============================================================

import type {
  HealthResponse,
  Settings,
  Signal,
  SignalQueryParams,
  SignalEvaluationData,
  HistoryQueryParams,
  AnalyticsSummary,
  PerformanceData,
  IngestPayload,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

export class ApiClient {
  private baseUrl: string;

  constructor(backendUrl: string) {
    this.baseUrl = backendUrl.replace(/\/+$/, "");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = await response.text();
      }
      throw new ApiError(response.status, response.statusText, body);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  private buildQuery(params: Record<string, unknown>): string {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.set(key, String(value));
      }
    }
    const query = searchParams.toString();
    return query ? `?${query}` : "";
  }

  // ---- Health ----

  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  // ---- Settings ----

  async getSettings(): Promise<Settings> {
    return this.request<Settings>("/settings");
  }

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return this.request<Settings>("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  }

  // ---- Signal Ingestion ----

  async ingestSignal(data: IngestPayload): Promise<Signal> {
    return this.request<Signal>("/signals/ingest", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // ---- Signals ----

  async getSignals(params: SignalQueryParams = {}): Promise<Signal[]> {
    const query = this.buildQuery(params as Record<string, unknown>);
    return this.request<Signal[]>(`/signals${query}`);
  }

  async getSignal(signalId: string): Promise<Signal> {
    return this.request<Signal>(
      `/signals/${encodeURIComponent(signalId)}`
    );
  }

  async evaluateSignal(
    signalId: string,
    data: SignalEvaluationData
  ): Promise<Signal> {
    return this.request<Signal>(
      `/signals/${encodeURIComponent(signalId)}/evaluate`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  // ---- History ----

  async getHistory(params: HistoryQueryParams = {}): Promise<Signal[]> {
    const query = this.buildQuery(params as Record<string, unknown>);
    return this.request<Signal[]>(`/history${query}`);
  }

  async getWins(params: HistoryQueryParams = {}): Promise<Signal[]> {
    const query = this.buildQuery(params as Record<string, unknown>);
    return this.request<Signal[]>(`/history/wins${query}`);
  }

  async getLosses(params: HistoryQueryParams = {}): Promise<Signal[]> {
    const query = this.buildQuery(params as Record<string, unknown>);
    return this.request<Signal[]>(`/history/losses${query}`);
  }

  async getPending(params: SignalQueryParams = {}): Promise<Signal[]> {
    const query = this.buildQuery(params as Record<string, unknown>);
    return this.request<Signal[]>(`/signals/pending${query}`);
  }

  // ---- Analytics ----

  async getAnalyticsSummary(): Promise<AnalyticsSummary> {
    return this.request<AnalyticsSummary>("/analytics/summary");
  }

  async getPerformance(): Promise<PerformanceData[]> {
    return this.request<PerformanceData[]>("/analytics/performance");
  }
}
