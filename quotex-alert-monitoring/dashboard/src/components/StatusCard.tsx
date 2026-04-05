import React from 'react';

interface StatusCardProps {
  label: string;
  value: string;
  status: 'ok' | 'warning' | 'error';
}

const StatusCard: React.FC<StatusCardProps> = ({ label, value, status }) => {
  return (
    <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px' }}>
      <span className={`status-dot ${status}`} />
      <div>
        <div className="card-header" style={{ marginBottom: 2 }}>{label}</div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>{value}</div>
      </div>
    </div>
  );
};

export default StatusCard;
