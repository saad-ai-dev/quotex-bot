import React, { useState, useEffect } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import LiveDashboardPage from './pages/LiveDashboardPage';
import HistoryPage from './pages/HistoryPage';
import SoundAlertPlayer from './components/SoundAlertPlayer';
import { useAlerts } from './hooks/useAlerts';
import { getSettings } from './services/api';

const App: React.FC = () => {
  const [soundEnabled, setSoundEnabled] = useState(true);
  const { latestAlert } = useAlerts();

  useEffect(() => {
    getSettings()
      .then((s) => {
        if (typeof s.sound_enabled === 'boolean') {
          setSoundEnabled(s.sound_enabled);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Navigation Header */}
      <nav className="nav-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
            Quotex Alert Monitor
          </span>
          <div className="nav-links">
            <NavLink
              to="/"
              end
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              History
            </NavLink>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            className="btn"
            style={{ fontSize: 12, padding: '4px 10px' }}
            onClick={() => setSoundEnabled((v) => !v)}
            title={soundEnabled ? 'Mute alerts' : 'Unmute alerts'}
          >
            {soundEnabled ? '\uD83D\uDD0A Sound ON' : '\uD83D\uDD07 Sound OFF'}
          </button>
        </div>
      </nav>

      {/* Sound Player (global) */}
      <SoundAlertPlayer latestAlert={latestAlert} soundEnabled={soundEnabled} />

      {/* Routes */}
      <Routes>
        <Route path="/" element={<LiveDashboardPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </div>
  );
};

export default App;
