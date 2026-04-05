import React from 'react';

export interface SummaryStats {
  total_today: number;
  wins: number;
  losses: number;
  pending: number;
  live_alerts: number;
  otc_alerts: number;
  win_rate?: number;
  neutral?: number;
  unknown?: number;
}

interface SummaryBarProps {
  stats: SummaryStats;
}

interface MetricItem {
  label: string;
  value: number | string;
  color?: string;
}

const SummaryBar: React.FC<SummaryBarProps> = ({ stats }) => {
  const metrics: MetricItem[] = [
    { label: 'Total Today', value: stats.total_today, color: 'var(--blue)' },
    { label: 'Wins', value: stats.wins, color: 'var(--green)' },
    { label: 'Losses', value: stats.losses, color: 'var(--red)' },
    { label: 'Pending', value: stats.pending, color: 'var(--yellow)' },
    { label: 'Live Alerts', value: stats.live_alerts, color: 'var(--green)' },
    { label: 'OTC Alerts', value: stats.otc_alerts, color: 'var(--blue)' },
  ];

  return (
    <div className="grid-row grid-6">
      {metrics.map((m) => (
        <div key={m.label} className="card" style={{ textAlign: 'center', padding: '14px 10px' }}>
          <div className="card-header">{m.label}</div>
          <div className="card-value" style={{ color: m.color }}>
            {m.value}
          </div>
        </div>
      ))}
    </div>
  );
};

export default SummaryBar;
