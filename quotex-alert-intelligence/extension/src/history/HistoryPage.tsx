// ============================================================
// Quotex Alert Intelligence - History Page
// ALERT-ONLY system - NO trade execution
// ============================================================

import React, { useEffect, useState, useCallback } from "react";
import type {
  Signal,
  MarketType,
  ExpiryProfile,
  SignalStatus,
  Settings,
} from "@shared/types";

const PAGE_SIZE = 20;

interface HistoryFilters {
  market_type: MarketType | "all";
  expiry_profile: ExpiryProfile | "all";
  outcome: SignalStatus | "all";
  from_date: string;
  to_date: string;
}

interface SummaryStats {
  total: number;
  wins: number;
  losses: number;
  winRate: number;
}

const DEFAULT_FILTERS: HistoryFilters = {
  market_type: "all",
  expiry_profile: "all",
  outcome: "all",
  from_date: "",
  to_date: "",
};

export const HistoryPage: React.FC = () => {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [filters, setFilters] = useState<HistoryFilters>({ ...DEFAULT_FILTERS });
  const [page, setPage] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [backendUrl, setBackendUrl] = useState("http://localhost:8000");
  const [summary, setSummary] = useState<SummaryStats>({
    total: 0,
    wins: 0,
    losses: 0,
    winRate: 0,
  });

  useEffect(() => {
    chrome.storage.local.get("settings", (result) => {
      if (result.settings) {
        const s = result.settings as Settings;
        setBackendUrl(s.backend_url);
      }
    });
  }, []);

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(page * PAGE_SIZE));

      if (filters.market_type !== "all") {
        params.set("market_type", filters.market_type);
      }
      if (filters.outcome !== "all") {
        params.set("status", filters.outcome);
      }
      if (filters.from_date) {
        params.set("from_date", filters.from_date);
      }
      if (filters.to_date) {
        params.set("to_date", filters.to_date);
      }

      const resp = await fetch(
        `${backendUrl}/signals/history?${params.toString()}`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      let items: Signal[] = Array.isArray(data) ? data : data.signals || [];

      // Client-side filter for expiry_profile if the API doesn't support it
      if (filters.expiry_profile !== "all") {
        items = items.filter(
          (s: Signal) => s.expiry_profile === filters.expiry_profile
        );
      }

      setSignals(items);
      setTotalCount(data.total ?? items.length);

      // Compute summary from all returned data
      const wins = items.filter((s: Signal) => s.outcome === "win").length;
      const losses = items.filter((s: Signal) => s.outcome === "loss").length;
      const total = items.length;
      setSummary({
        total,
        wins,
        losses,
        winRate: wins + losses > 0 ? (wins / (wins + losses)) * 100 : 0,
      });
    } catch (err) {
      console.error("[QAI] Fetch history error:", err);
      setSignals([]);
    } finally {
      setLoading(false);
    }
  }, [backendUrl, page, filters]);

  useEffect(() => {
    if (backendUrl) {
      fetchSignals();
    }
  }, [fetchSignals, backendUrl]);

  const updateFilter = <K extends keyof HistoryFilters>(
    key: K,
    value: HistoryFilters[K]
  ) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(0);
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div style={styles.page}>
      <div style={styles.content}>
        <h1 style={styles.title}>Signal History</h1>
        <p style={styles.subtitle}>ALERT-ONLY - No Trade Execution</p>

        {/* Summary Stats */}
        <div style={styles.statsRow}>
          <div style={styles.statCard}>
            <div style={styles.statValue}>{summary.total}</div>
            <div style={styles.statLabel}>Total</div>
          </div>
          <div style={styles.statCard}>
            <div style={{ ...styles.statValue, color: "#00e676" }}>
              {summary.wins}
            </div>
            <div style={styles.statLabel}>Wins</div>
          </div>
          <div style={styles.statCard}>
            <div style={{ ...styles.statValue, color: "#ff1744" }}>
              {summary.losses}
            </div>
            <div style={styles.statLabel}>Losses</div>
          </div>
          <div style={styles.statCard}>
            <div
              style={{
                ...styles.statValue,
                color:
                  summary.winRate >= 55
                    ? "#00e676"
                    : summary.winRate >= 45
                    ? "#ffc107"
                    : "#ff1744",
              }}
            >
              {summary.winRate.toFixed(1)}%
            </div>
            <div style={styles.statLabel}>Win Rate</div>
          </div>
        </div>

        {/* Filters */}
        <div style={styles.filterRow}>
          <select
            value={filters.market_type}
            onChange={(e) =>
              updateFilter("market_type", e.target.value as MarketType | "all")
            }
            style={styles.filterSelect}
          >
            <option value="all">All Markets</option>
            <option value="real">Live</option>
            <option value="otc">OTC</option>
          </select>

          <select
            value={filters.expiry_profile}
            onChange={(e) =>
              updateFilter(
                "expiry_profile",
                e.target.value as ExpiryProfile | "all"
              )
            }
            style={styles.filterSelect}
          >
            <option value="all">All Expiry</option>
            <option value="short">1 Min</option>
            <option value="medium">2 Min</option>
            <option value="long">3 Min</option>
          </select>

          <select
            value={filters.outcome}
            onChange={(e) =>
              updateFilter("outcome", e.target.value as SignalStatus | "all")
            }
            style={styles.filterSelect}
          >
            <option value="all">All Outcomes</option>
            <option value="win">Win</option>
            <option value="loss">Loss</option>
            <option value="pending">Pending</option>
            <option value="expired">Expired</option>
          </select>

          <input
            type="date"
            value={filters.from_date}
            onChange={(e) => updateFilter("from_date", e.target.value)}
            style={styles.filterDate}
            placeholder="From"
          />
          <input
            type="date"
            value={filters.to_date}
            onChange={(e) => updateFilter("to_date", e.target.value)}
            style={styles.filterDate}
            placeholder="To"
          />
        </div>

        {/* Table */}
        <div style={styles.tableWrap}>
          {loading ? (
            <div style={styles.loading}>Loading...</div>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Time</th>
                  <th style={styles.th}>Market</th>
                  <th style={styles.th}>Asset</th>
                  <th style={styles.th}>Expiry</th>
                  <th style={styles.th}>Direction</th>
                  <th style={styles.th}>Confidence</th>
                  <th style={styles.th}>Outcome</th>
                </tr>
              </thead>
              <tbody>
                {signals.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={styles.emptyCell}>
                      No signals found
                    </td>
                  </tr>
                ) : (
                  signals.map((signal) => {
                    const isCall = signal.prediction_direction === "CALL";
                    const dirColor = isCall ? "#00e676" : "#ff1744";
                    const arrow = isCall ? "\u25B2" : "\u25BC";
                    const outcomeColor =
                      signal.outcome === "win"
                        ? "#00e676"
                        : signal.outcome === "loss"
                        ? "#ff1744"
                        : "#ffc107";
                    const outcomeLabel =
                      signal.outcome === "win"
                        ? "WIN"
                        : signal.outcome === "loss"
                        ? "LOSS"
                        : signal.outcome === "expired"
                        ? "EXPIRED"
                        : "PENDING";

                    return (
                      <tr key={signal.signal_id} style={styles.tr}>
                        <td style={styles.td}>
                          {formatTime(signal.timestamps.created_at)}
                        </td>
                        <td style={styles.td}>
                          <span style={styles.marketBadge}>
                            {signal.market_type.toUpperCase()}
                          </span>
                        </td>
                        <td style={styles.td}>{signal.asset_name}</td>
                        <td style={styles.td}>{signal.expiry_profile}</td>
                        <td style={{ ...styles.td, color: dirColor, fontWeight: 700 }}>
                          {arrow} {signal.prediction_direction}
                        </td>
                        <td style={styles.tdMono}>
                          {Math.round(signal.confidence)}%
                        </td>
                        <td style={styles.td}>
                          <span
                            style={{
                              ...styles.outcomeBadge,
                              color: outcomeColor,
                              borderColor: outcomeColor,
                              background:
                                signal.outcome === "win"
                                  ? "rgba(0,230,118,0.1)"
                                  : signal.outcome === "loss"
                                  ? "rgba(255,23,68,0.1)"
                                  : "rgba(255,193,7,0.1)",
                            }}
                          >
                            {outcomeLabel}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div style={styles.pagination}>
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            style={{
              ...styles.pageBtn,
              opacity: page === 0 ? 0.3 : 1,
            }}
          >
            Previous
          </button>
          <span style={styles.pageInfo}>
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            style={{
              ...styles.pageBtn,
              opacity: page >= totalPages - 1 ? 0.3 : 1,
            }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#0a0a12",
    color: "#e0e0e0",
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    padding: "32px 24px",
  },
  content: {
    maxWidth: 960,
    margin: "0 auto",
  },
  title: {
    fontSize: 24,
    fontWeight: 700,
    color: "#fff",
    margin: 0,
  },
  subtitle: {
    fontSize: 12,
    color: "#666",
    margin: "6px 0 24px 0",
    textTransform: "uppercase",
    letterSpacing: "1.5px",
  },
  statsRow: {
    display: "flex",
    gap: 12,
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 10,
    padding: "16px 20px",
    textAlign: "center",
  },
  statValue: {
    fontSize: 28,
    fontWeight: 700,
    fontFamily: "monospace",
    color: "#fff",
  },
  statLabel: {
    fontSize: 11,
    color: "#666",
    textTransform: "uppercase",
    letterSpacing: "0.8px",
    marginTop: 4,
  },
  filterRow: {
    display: "flex",
    gap: 10,
    marginBottom: 16,
    flexWrap: "wrap" as const,
  },
  filterSelect: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#e0e0e0",
    fontSize: 12,
    outline: "none",
    cursor: "pointer",
  },
  filterDate: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 6,
    padding: "8px 12px",
    color: "#e0e0e0",
    fontSize: 12,
    outline: "none",
    colorScheme: "dark" as const,
  },
  tableWrap: {
    overflowX: "auto" as const,
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 10,
    background: "rgba(255,255,255,0.02)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: 13,
  },
  th: {
    textAlign: "left" as const,
    padding: "12px 14px",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
    color: "#888",
    fontSize: 11,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    fontWeight: 700,
  },
  tr: {
    borderBottom: "1px solid rgba(255,255,255,0.03)",
  },
  td: {
    padding: "10px 14px",
    verticalAlign: "middle" as const,
  },
  tdMono: {
    padding: "10px 14px",
    fontFamily: "monospace",
    fontWeight: 600,
  },
  emptyCell: {
    padding: "40px 14px",
    textAlign: "center" as const,
    color: "#555",
  },
  marketBadge: {
    background: "rgba(255,255,255,0.06)",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.5px",
  },
  outcomeBadge: {
    padding: "3px 10px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 700,
    border: "1px solid",
    display: "inline-block",
  },
  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    marginTop: 20,
  },
  pageBtn: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 6,
    padding: "8px 20px",
    color: "#e0e0e0",
    fontSize: 12,
    cursor: "pointer",
  },
  pageInfo: {
    fontSize: 12,
    color: "#888",
  },
  loading: {
    padding: "40px 0",
    textAlign: "center",
    color: "#666",
    fontSize: 14,
  },
};
