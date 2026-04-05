import React, { useEffect, useState } from 'react';
import { useHistory } from '../hooks/useHistory';
import { getAnalyticsSummary, AnalyticsSummary } from '../services/api';
import HistoryTable from '../components/HistoryTable';

const HistoryPage: React.FC = () => {
  const { history, total, loading, error, filters, setFilters, refresh, totalPages } = useHistory();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);

  // Local filter state (applied on button click)
  const [localMarket, setLocalMarket] = useState(filters.market_type);
  const [localExpiry, setLocalExpiry] = useState(filters.expiry_profile);
  const [localOutcome, setLocalOutcome] = useState(filters.outcome);
  const [localMinConf, setLocalMinConf] = useState(filters.min_confidence);

  useEffect(() => {
    getAnalyticsSummary()
      .then(setSummary)
      .catch(() => {});
  }, []);

  const applyFilters = () => {
    setFilters({
      market_type: localMarket,
      expiry_profile: localExpiry,
      outcome: localOutcome,
      min_confidence: localMinConf,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') applyFilters();
  };

  const summaryItems = summary ? [
    { label: 'Total Alerts', value: summary.total, color: 'var(--blue)' },
    { label: 'Wins', value: summary.wins, color: 'var(--green)' },
    { label: 'Losses', value: summary.losses, color: 'var(--red)' },
    { label: 'Pending', value: summary.pending ?? 0, color: 'var(--yellow)' },
    {
      label: 'Win Rate',
      value: `${(summary.win_rate ?? 0).toFixed(1)}%`,
      color: (summary.win_rate ?? 0) >= 50 ? 'var(--green)' : 'var(--red)',
    },
  ] : [];

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Alert History</h1>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          Browse and filter past alert signals. Total: {total} records.
        </div>
      </div>

      {/* Summary Stats Bar */}
      {summary && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${summaryItems.length}, 1fr)`,
          gap: 12,
          marginBottom: 16,
        }}>
          {summaryItems.map((item) => (
            <div key={item.label} className="card" style={{ textAlign: 'center', padding: '12px 8px' }}>
              <div className="card-header">{item.label}</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: item.color }}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filter Row */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="filter-row" onKeyDown={handleKeyDown}>
          <div className="filter-group">
            <label>Market</label>
            <select value={localMarket} onChange={(e) => setLocalMarket(e.target.value)}>
              <option value="All">All</option>
              <option value="LIVE">LIVE</option>
              <option value="OTC">OTC</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Expiry</label>
            <select value={localExpiry} onChange={(e) => setLocalExpiry(e.target.value)}>
              <option value="all">All</option>
              <option value="1m">1m</option>
              <option value="2m">2m</option>
              <option value="3m">3m</option>
              <option value="5m">5m</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Outcome</label>
            <select value={localOutcome} onChange={(e) => setLocalOutcome(e.target.value)}>
              <option value="All">All</option>
              <option value="WIN">WIN</option>
              <option value="LOSS">LOSS</option>
              <option value="PENDING">PENDING</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Min Confidence: {localMinConf}%</label>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={localMinConf}
              onChange={(e) => setLocalMinConf(Number(e.target.value))}
              style={{ width: 120 }}
            />
          </div>

          <button className="btn btn-primary" onClick={applyFilters}>
            Apply Filters
          </button>

          <button className="btn" onClick={refresh} style={{ marginLeft: 'auto' }}>
            Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card" style={{
          marginBottom: 16,
          padding: '12px 16px',
          borderColor: 'var(--red)',
          color: 'var(--red)',
          fontSize: 13,
        }}>
          Error: {error}
        </div>
      )}

      {/* History Table */}
      <HistoryTable signals={history} loading={loading} />

      {/* Pagination */}
      {total > 0 && (
        <div className="pagination">
          <button
            disabled={filters.page <= 1}
            onClick={() => setFilters({ page: 1 })}
          >
            First
          </button>
          <button
            disabled={filters.page <= 1}
            onClick={() => setFilters({ page: filters.page - 1 })}
          >
            Prev
          </button>
          <span>
            Page {filters.page} of {totalPages} ({total} total)
          </span>
          <button
            disabled={filters.page >= totalPages}
            onClick={() => setFilters({ page: filters.page + 1 })}
          >
            Next
          </button>
          <button
            disabled={filters.page >= totalPages}
            onClick={() => setFilters({ page: totalPages })}
          >
            Last
          </button>
        </div>
      )}
    </div>
  );
};

export default HistoryPage;
