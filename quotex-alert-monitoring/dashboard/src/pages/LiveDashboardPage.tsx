import React, { useState, useEffect, useCallback } from 'react';
import { useAlerts } from '../hooks/useAlerts';
import { getHealth, getAnalyticsSummary, getSettings, getSignals, HealthResponse, AnalyticsSummary, Settings, Signal } from '../services/api';
import StatusCard from '../components/StatusCard';
import SignalCard from '../components/SignalCard';
import SummaryBar, { SummaryStats } from '../components/SummaryBar';

function formatTime(dateStr: string | undefined | null): string {
  if (!dateStr) return '--:--:--';
  try { return new Date(dateStr).toLocaleTimeString('en-US', { hour12: false }); }
  catch { return String(dateStr); }
}

function dirBadge(d: string): string {
  switch (d?.toUpperCase()) {
    case 'UP': return 'badge badge-up';
    case 'DOWN': return 'badge badge-down';
    default: return 'badge badge-no_trade';
  }
}

function outBadge(o: string | null | undefined): string {
  switch (o?.toUpperCase()) {
    case 'WIN': return 'badge badge-win';
    case 'LOSS': return 'badge badge-loss';
    case 'PENDING': return 'badge badge-pending';
    default: return 'badge badge-neutral';
  }
}

const LiveDashboardPage: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [recentSignals, setRecentSignals] = useState<Signal[]>([]);
  const [backendOk, setBackendOk] = useState(false);
  const [isNew, setIsNew] = useState(false);

  const onNewAlert = useCallback(() => { setIsNew(true); setTimeout(() => setIsNew(false), 2000); }, []);
  const { alerts: wsAlerts, wsStatus, latestAlert } = useAlerts(onNewAlert);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [h, s, a, sig] = await Promise.all([
          getHealth().catch(() => null),
          getSettings().catch(() => null),
          getAnalyticsSummary().catch(() => null),
          getSignals({ limit: 50, directional_only: 1 }).catch(() => null),
        ]);
        if (!active) return;
        setBackendOk(!!h && h.status !== 'error');
        if (h) setHealth(h);
        if (s) setSettings(s);
        if (a) setSummary(a);
        if (sig?.signals) setRecentSignals(sig.signals);
      } catch { if (active) setBackendOk(false); }
    }
    poll();
    const iv = setInterval(poll, 5000);
    return () => { active = false; clearInterval(iv); };
  }, []);

  // Merge WS alerts with polled signals, dedup by signal_id
  const allAlerts = React.useMemo(() => {
    const map = new Map<string, Signal>();
    for (const s of recentSignals) map.set(s.signal_id, s);
    for (const s of wsAlerts) map.set(s.signal_id, s);
    // Only show directional signals (UP/DOWN), sorted by time
    return [...map.values()]
      .filter(s => s.prediction_direction === 'UP' || s.prediction_direction === 'DOWN')
      .sort((a, b) => {
      return (b.created_at || '').localeCompare(a.created_at || '');
    }).slice(0, 50);
  }, [recentSignals, wsAlerts]);

  // Only show PENDING directional signals. Evaluated (WIN/LOSS) go to history only.
  const pendingAlerts = allAlerts.filter(s => s.status === 'PENDING');
  const latest = pendingAlerts[0] || null;

  // Compute live/otc counts from allAlerts
  const liveCount = allAlerts.filter(s => s.market_type === 'LIVE').length;
  const otcCount = allAlerts.filter(s => s.market_type === 'OTC').length;

  const stats: SummaryStats = {
    total_today: summary?.total ?? allAlerts.length,
    wins: summary?.wins ?? 0,
    losses: summary?.losses ?? 0,
    pending: summary?.pending ?? allAlerts.filter(s => s.status === 'PENDING').length,
    live_alerts: liveCount,
    otc_alerts: otcCount,
  };

  const wsMap: Record<string, { value: string; status: 'ok' | 'warning' | 'error' }> = {
    connected: { value: 'Connected', status: 'ok' },
    connecting: { value: 'Reconnecting...', status: 'warning' },
    disconnected: { value: 'Offline', status: 'error' },
  };
  const ws = wsMap[wsStatus] || wsMap.disconnected;

  const monitoringOn = settings?.monitoring_enabled ?? false;
  const market = settings?.market_mode || 'N/A';
  const expiry = settings?.expiry_profile || 'N/A';

  return (
    <div className="page-container">
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
          Quotex Alert Monitor
          <span style={{ fontSize: 11, fontWeight: 600, marginLeft: 12, padding: '3px 10px', borderRadius: 10, background: 'var(--blue-bg)', color: 'var(--blue)', border: '1px solid rgba(88,166,255,0.3)', verticalAlign: 'middle' }}>ALERT ONLY</span>
        </h1>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Monitoring signals in real-time. No trade execution.</div>
      </div>

      {/* Status */}
      <div className="grid-row grid-3">
        <StatusCard label="Monitoring" value={monitoringOn ? 'ON' : 'OFF'} status={monitoringOn ? 'ok' : 'error'} />
        <StatusCard label="Backend" value={backendOk ? (health?.db_status === 'connected' ? 'Connected' : 'Degraded') : 'Disconnected'} status={backendOk ? (health?.db_status === 'connected' ? 'ok' : 'warning') : 'error'} />
        <StatusCard label="WebSocket" value={ws.value} status={ws.status} />
      </div>

      {/* Config */}
      <div className="grid-row grid-2">
        <div className="card" style={{ padding: '12px 16px' }}>
          <div className="card-header" style={{ marginBottom: 2 }}>Market</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: market.toUpperCase() === 'LIVE' ? 'var(--green)' : 'var(--blue)' }}>{market.toUpperCase()}</div>
        </div>
        <div className="card" style={{ padding: '12px 16px' }}>
          <div className="card-header" style={{ marginBottom: 2 }}>Expiry Period</div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{expiry.toUpperCase()}</div>
        </div>
      </div>

      <SummaryBar stats={stats} />

      {/* Active Signals - show ALL pending directional alerts */}
      {(() => {
        const activeSignals = allAlerts.filter(s =>
          (s.prediction_direction === 'UP' || s.prediction_direction === 'DOWN') &&
          s.status === 'PENDING' &&
          s.outcome !== 'WIN' && s.outcome !== 'LOSS'
        );
        return activeSignals.length > 0 ? (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase' }}>
              Active Signals ({activeSignals.length})
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {activeSignals.map((sig, i) => (
                <SignalCard key={sig.signal_id} signal={sig} isNew={isNew && i === 0} />
              ))}
            </div>
          </div>
        ) : (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase' }}>Latest Alert</div>
            <SignalCard signal={latest} isNew={isNew} />
          </div>
        );
      })()}

      {/* Recent Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16, marginBottom: 16 }}>

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Pending Alerts</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{pendingAlerts.length} pending</div>
          </div>
          <div className="card" style={{ padding: 0, maxHeight: 400, overflowY: 'auto' }}>
            {pendingAlerts.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>No pending alerts — all signals evaluated. Check History for results.</div>
            ) : (
              <div style={{ padding: 8 }}>
                {pendingAlerts.map((sig, i) => (
                  <div key={sig.signal_id} className="alert-row fade-in" style={{ animationDelay: `${i * 30}ms`, gridTemplateColumns: '72px 64px 90px 50px 50px 70px 72px' }}>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{formatTime(sig.created_at)}</span>
                    <span className={dirBadge(sig.prediction_direction)} style={{ fontSize: 10, padding: '1px 7px' }}>{sig.prediction_direction || 'N/A'}</span>
                    <span style={{ fontSize: 11, fontWeight: 600, color: sig.market_type === 'LIVE' ? 'var(--green)' : 'var(--blue)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={sig.asset_name || sig.market_type}>{sig.asset_name || sig.market_type}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{sig.expiry_profile || '--'}</span>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{sig.confidence?.toFixed(1)}%</span>
                    <span className={outBadge(sig.outcome || sig.status)} style={{ fontSize: 10, padding: '1px 7px' }}>{sig.outcome || sig.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LiveDashboardPage;
