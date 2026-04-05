import React, { useState } from 'react';
import { Signal } from '../services/api';

interface HistoryTableProps {
  signals: Signal[];
  loading?: boolean;
}

type SortField = 'created_at' | 'market_type' | 'expiry_profile' | 'prediction_direction' | 'confidence' | 'outcome';
type SortDir = 'asc' | 'desc';

function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '--';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return String(dateStr);
  }
}

function getDirectionBadgeClass(direction: string): string {
  switch (direction?.toUpperCase()) {
    case 'UP': return 'badge badge-up';
    case 'DOWN': return 'badge badge-down';
    default: return 'badge badge-no_trade';
  }
}

function getOutcomeBadgeClass(outcome: string | null | undefined): string {
  switch (outcome?.toUpperCase()) {
    case 'WIN': return 'badge badge-win';
    case 'LOSS': return 'badge badge-loss';
    case 'PENDING': return 'badge badge-pending';
    default: return 'badge badge-neutral';
  }
}

const HistoryTable: React.FC<HistoryTableProps> = ({ signals, loading }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sorted = [...signals].sort((a, b) => {
    let aVal: string | number = '';
    let bVal: string | number = '';

    switch (sortField) {
      case 'created_at':
        aVal = a.created_at || '';
        bVal = b.created_at || '';
        break;
      case 'market_type':
        aVal = a.market_type || '';
        bVal = b.market_type || '';
        break;
      case 'expiry_profile':
        aVal = a.expiry_profile || '';
        bVal = b.expiry_profile || '';
        break;
      case 'prediction_direction':
        aVal = a.prediction_direction || '';
        bVal = b.prediction_direction || '';
        break;
      case 'confidence':
        aVal = a.confidence || 0;
        bVal = b.confidence || 0;
        break;
      case 'outcome':
        aVal = a.outcome || '';
        bVal = b.outcome || '';
        break;
    }

    if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const sortIndicator = (field: SortField) => {
    if (sortField !== field) return ' \u2195';
    return sortDir === 'asc' ? ' \u2191' : ' \u2193';
  };

  if (loading) {
    return (
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <div className="pulse" style={{ color: 'var(--text-secondary)' }}>Loading history...</div>
      </div>
    );
  }

  if (signals.length === 0) {
    return (
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ color: 'var(--text-secondary)' }}>No signals match the current filters</div>
      </div>
    );
  }

  return (
    <div className="card table-container" style={{ padding: 0 }}>
      <table>
        <thead>
          <tr>
            <th onClick={() => handleSort('created_at')}>Time{sortIndicator('created_at')}</th>
            <th onClick={() => handleSort('market_type')}>Market{sortIndicator('market_type')}</th>
            <th onClick={() => handleSort('prediction_direction')}>Direction{sortIndicator('prediction_direction')}</th>
            <th>Entry</th>
            <th>Close</th>
            <th>P/L</th>
            <th onClick={() => handleSort('confidence')}>Conf{sortIndicator('confidence')}</th>
            <th onClick={() => handleSort('outcome')}>Outcome{sortIndicator('outcome')}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((signal) => {
            const isExpanded = expandedId === signal.signal_id;
            return (
              <React.Fragment key={signal.signal_id}>
                <tr
                  className={isExpanded ? 'expanded-row' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpandedId(isExpanded ? null : signal.signal_id)}
                >
                  <td>{formatTime(signal.created_at)}</td>
                  <td>
                    <span style={{
                      color: signal.market_type === 'LIVE' ? 'var(--green)' : 'var(--blue)',
                      fontWeight: 600,
                    }}>
                      {signal.asset_name || signal.market_type || 'N/A'}
                    </span>
                  </td>
                  <td>
                    <span className={getDirectionBadgeClass(signal.prediction_direction)}>
                      {signal.prediction_direction?.toUpperCase() || 'N/A'}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                    {signal.entry_price != null ? signal.entry_price.toFixed(5) : '--'}
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12, color: signal.close_price != null && signal.entry_price != null ? (signal.close_price > signal.entry_price ? 'var(--green)' : signal.close_price < signal.entry_price ? 'var(--red)' : '') : 'var(--text-muted)' }}>
                    {signal.close_price != null ? signal.close_price.toFixed(5) : '--'}
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12, fontWeight: 600 }}>
                    {signal.entry_price != null && signal.close_price != null ? (() => {
                      const diff = signal.close_price! - signal.entry_price!;
                      const pips = Math.abs(diff * 100000).toFixed(1);
                      const dir = signal.prediction_direction?.toUpperCase();
                      const isProfit = (dir === 'UP' && diff > 0) || (dir === 'DOWN' && diff < 0);
                      return <span style={{ color: isProfit ? 'var(--green)' : 'var(--red)' }}>{isProfit ? '+' : '-'}{pips}</span>;
                    })() : '--'}
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{signal.confidence?.toFixed(1)}%</span>
                  </td>
                  <td>
                    <span className={getOutcomeBadgeClass(signal.outcome)}>
                      {signal.outcome || 'PENDING'}
                    </span>
                  </td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={8} style={{ padding: 0 }}>
                      <div className="expanded-details">
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                          {/* Left: Reasons */}
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase' }}>
                              Reasons
                            </div>
                            {signal.reasons && signal.reasons.length > 0 ? (
                              <ul className="reasons-list">
                                {signal.reasons.map((r, i) => (
                                  <li key={i}>{r}</li>
                                ))}
                              </ul>
                            ) : (
                              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No reasons recorded</div>
                            )}
                          </div>

                          {/* Right: Details */}
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase' }}>
                              Details
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
                              <div style={{ color: 'var(--text-muted)' }}>Signal ID:</div>
                              <div style={{ fontFamily: 'monospace', fontSize: 11 }}>{signal.signal_id}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Created:</div>
                              <div>{formatTime(signal.created_at)}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Evaluate at:</div>
                              <div>{formatTime(signal.signal_for_close_at)}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Evaluated at:</div>
                              <div>{formatTime(signal.evaluated_at)}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Entry Price:</div>
                              <div style={{ fontFamily: 'monospace', fontWeight: 600 }}>{signal.entry_price != null ? signal.entry_price.toFixed(5) : '--'}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Close Price:</div>
                              <div style={{ fontFamily: 'monospace', fontWeight: 600, color: signal.close_price != null && signal.entry_price != null ? (signal.close_price > signal.entry_price ? 'var(--green)' : 'var(--red)') : '' }}>{signal.close_price != null ? signal.close_price.toFixed(5) : '--'}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Bullish Score:</div>
                              <div style={{ color: 'var(--green)' }}>{signal.bullish_score?.toFixed(1)}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Bearish Score:</div>
                              <div style={{ color: 'var(--red)' }}>{signal.bearish_score?.toFixed(1)}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Asset:</div>
                              <div>{signal.asset_name || 'N/A'}</div>

                              <div style={{ color: 'var(--text-muted)' }}>Expiry:</div>
                              <div>{signal.expiry_profile || '--'}</div>
                            </div>

                            {/* Scores */}
                            {signal.penalties && Object.keys(signal.penalties).length > 0 && (
                              <div style={{ marginTop: 12 }}>
                                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase' }}>
                                  Scores
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 13 }}>
                                  {Object.entries(signal.penalties).map(([key, val]) => (
                                    <React.Fragment key={key}>
                                      <div style={{ color: 'var(--text-muted)' }}>{key}:</div>
                                      <div>{typeof val === 'number' ? val.toFixed(3) : String(val)}</div>
                                    </React.Fragment>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default HistoryTable;
