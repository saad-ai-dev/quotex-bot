import React from 'react';
import { Signal } from '../services/api';

interface SignalCardProps {
  signal: Signal | null;
  isNew?: boolean;
}

function formatTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '--:--:--';
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return String(dateStr);
  }
}

function getDirectionBadgeClass(direction: string): string {
  switch (direction?.toUpperCase()) {
    case 'UP': return 'badge badge-large badge-up';
    case 'DOWN': return 'badge badge-large badge-down';
    default: return 'badge badge-large badge-no_trade';
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

function getConfidenceColor(confidence: number): string {
  if (confidence >= 70) return 'var(--green)';
  if (confidence >= 50) return 'var(--yellow)';
  return 'var(--red)';
}

const SignalCard: React.FC<SignalCardProps> = ({ signal, isNew }) => {
  if (!signal) {
    return (
      <div className="card" style={{ padding: 32, textAlign: 'center' }}>
        <div style={{ fontSize: 18, color: 'var(--text-secondary)', marginBottom: 8 }}>
          Waiting for alerts...
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          Alerts will appear here when the monitoring system detects a signal
        </div>
      </div>
    );
  }

  const direction = signal.prediction_direction?.toUpperCase() || 'NO_TRADE';
  const glowClass = isNew
    ? direction === 'UP' ? 'alert-new-up' : direction === 'DOWN' ? 'alert-new-down' : ''
    : '';

  return (
    <div className={`card ${glowClass}`} style={{ padding: 24 }}>
      {/* Top Row: Direction + Outcome */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span className={getDirectionBadgeClass(direction)}>
            {direction === 'UP' ? '\u2191 UP' : direction === 'DOWN' ? '\u2193 DOWN' : 'NO TRADE'}
          </span>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>LATEST ALERT</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{formatTime(signal.created_at)}</div>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>OUTCOME</div>
          <span className={getOutcomeBadgeClass(signal.outcome)}>
            {signal.outcome || 'PENDING'}
          </span>
        </div>
      </div>

      {/* Confidence Bar */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>CONFIDENCE</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: getConfidenceColor(signal.confidence) }}>
            {signal.confidence.toFixed(1)}%
          </span>
        </div>
        <div className="confidence-bar-container">
          <div
            className="confidence-bar-fill"
            style={{
              width: `${Math.min(100, signal.confidence)}%`,
              background: getConfidenceColor(signal.confidence),
            }}
          />
        </div>
      </div>

      {/* Info Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>ASSET</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            <span style={{
              color: signal.market_type === 'LIVE' ? 'var(--green)' : 'var(--blue)',
            }}>
              {signal.asset_name || signal.market_type?.toUpperCase() || 'N/A'}
            </span>
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>EXPIRY</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{signal.expiry_profile || '--'}</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>EVALUATE AT</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{formatTime(signal.signal_for_close_at)}</div>
        </div>
      </div>

      {/* Entry / Close Price */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20, padding: '12px 16px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>ENTRY PRICE</div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace', color: 'var(--text-primary)' }}>
            {signal.entry_price != null ? signal.entry_price.toFixed(5) : '--'}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>CLOSE PRICE</div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace', color: signal.close_price != null && signal.entry_price != null ? (signal.close_price > signal.entry_price ? 'var(--green)' : signal.close_price < signal.entry_price ? 'var(--red)' : 'var(--text-primary)') : 'var(--text-muted)' }}>
            {signal.close_price != null ? signal.close_price.toFixed(5) : 'Pending...'}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>P/L</div>
          {signal.entry_price != null && signal.close_price != null ? (() => {
            const diff = signal.close_price - signal.entry_price;
            const pips = Math.abs(diff * 100000).toFixed(1);
            const isProfit = (direction === 'UP' && diff > 0) || (direction === 'DOWN' && diff < 0);
            return (
              <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace', color: isProfit ? 'var(--green)' : 'var(--red)' }}>
                {isProfit ? '+' : '-'}{pips} pips
              </div>
            );
          })() : (
            <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace', color: 'var(--text-muted)' }}>--</div>
          )}
        </div>
      </div>

      {/* Reasons */}
      {signal.reasons && signal.reasons.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>REASONS</div>
          <ul className="reasons-list">
            {signal.reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Signal ID */}
      <div style={{ marginTop: 16, fontSize: 11, color: 'var(--text-muted)' }}>
        ID: {signal.signal_id}
      </div>
    </div>
  );
};

export default SignalCard;
