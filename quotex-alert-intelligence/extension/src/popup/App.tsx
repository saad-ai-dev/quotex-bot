// ============================================================
// Quotex Alert Intelligence - Popup App
// ALERT-ONLY system - NO trade execution
// ============================================================

import React, { useEffect } from "react";
import { useStore } from "./store/useStore";
import { StatusBar } from "./components/StatusBar";
import { AlertCard } from "./components/AlertCard";

export const App: React.FC = () => {
  const {
    settings,
    isMonitoring,
    isConnected,
    recentAlerts,
    marketType,
    toggleMonitoring,
    updateSettings,
    loadFromStorage,
  } = useStore();

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  const recentFive = recentAlerts.slice(0, 5);
  const currentAsset = recentAlerts[0]?.signal?.asset_name ?? null;

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.title}>Quotex Alert Intelligence</div>
        <div style={styles.subtitle}>ALERT-ONLY - No Trade Execution</div>
      </div>

      {/* Status Bar */}
      <StatusBar
        isConnected={isConnected}
        isMonitoring={isMonitoring}
        marketType={marketType}
        currentAsset={currentAsset}
      />

      {/* Monitoring Toggle */}
      <div style={styles.section}>
        <button
          onClick={toggleMonitoring}
          style={{
            ...styles.toggleBtn,
            background: isMonitoring
              ? "linear-gradient(135deg, #d32f2f, #b71c1c)"
              : "linear-gradient(135deg, #00e676, #00c853)",
            color: isMonitoring ? "#fff" : "#0a0a0a",
          }}
        >
          {isMonitoring ? "Stop Monitoring" : "Start Monitoring"}
        </button>
      </div>

      {/* Settings Section */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Settings</div>

        {/* Backend URL */}
        <div style={styles.field}>
          <label style={styles.label}>Backend URL</label>
          <input
            type="text"
            value={settings.backend_url}
            onChange={(e) => updateSettings({ backend_url: e.target.value })}
            style={styles.input}
            placeholder="http://localhost:8000"
          />
        </div>

        {/* Market Mode */}
        <div style={styles.field}>
          <label style={styles.label}>Market Mode</label>
          <select
            value={settings.auto_detect_market ? "auto" : settings.market_mode}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "auto") {
                updateSettings({ auto_detect_market: true });
              } else {
                updateSettings({
                  auto_detect_market: false,
                  market_mode: val as "otc" | "real",
                });
              }
            }}
            style={styles.select}
          >
            <option value="auto">Auto Detect</option>
            <option value="real">Live</option>
            <option value="otc">OTC</option>
          </select>
        </div>

        {/* Expiry Profile */}
        <div style={styles.field}>
          <label style={styles.label}>Expiry Profile</label>
          <select
            value={settings.expiry_profile}
            onChange={(e) =>
              updateSettings({
                expiry_profile: e.target.value as "short" | "medium" | "long",
              })
            }
            style={styles.select}
          >
            <option value="short">1 Minute</option>
            <option value="medium">2 Minutes</option>
            <option value="long">3 Minutes</option>
          </select>
        </div>

        {/* Confidence Threshold */}
        <div style={styles.field}>
          <label style={styles.label}>
            Min Confidence: {settings.min_confidence_threshold}%
          </label>
          <input
            type="range"
            min={30}
            max={95}
            step={5}
            value={settings.min_confidence_threshold}
            onChange={(e) =>
              updateSettings({
                min_confidence_threshold: parseInt(e.target.value, 10),
              })
            }
            style={styles.slider}
          />
        </div>
      </div>

      {/* Alert Toggles */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>Notifications</div>
        <div style={styles.checkRow}>
          <label style={styles.checkLabel}>
            <input
              type="checkbox"
              checked={settings.sound_alerts_enabled}
              onChange={(e) =>
                updateSettings({ sound_alerts_enabled: e.target.checked })
              }
              style={styles.checkbox}
            />
            Sound Alerts
          </label>
        </div>
        <div style={styles.checkRow}>
          <label style={styles.checkLabel}>
            <input
              type="checkbox"
              checked={settings.browser_notifications_enabled}
              onChange={(e) =>
                updateSettings({
                  browser_notifications_enabled: e.target.checked,
                })
              }
              style={styles.checkbox}
            />
            Browser Notifications
          </label>
        </div>
      </div>

      {/* Recent Alerts */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          Recent Alerts
          {recentFive.length > 0 && (
            <span style={styles.alertCount}>{recentFive.length}</span>
          )}
        </div>
        {recentFive.length === 0 ? (
          <div style={styles.emptyState}>No alerts yet</div>
        ) : (
          recentFive.map((alert, i) => <AlertCard key={i} alert={alert} />)
        )}
      </div>

      {/* Footer Buttons */}
      <div style={styles.footer}>
        <button
          onClick={() => chrome.tabs.create({ url: "history/index.html" })}
          style={styles.footerBtn}
        >
          View History
        </button>
        <button
          onClick={() => chrome.runtime.openOptionsPage()}
          style={styles.footerBtn}
        >
          Options
        </button>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: 360,
    maxHeight: 560,
    overflowY: "auto",
    background: "#0d0d14",
    color: "#e0e0e0",
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  header: {
    textAlign: "center",
    paddingBottom: 4,
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  title: {
    fontSize: 15,
    fontWeight: 700,
    color: "#ffffff",
    letterSpacing: "0.3px",
  },
  subtitle: {
    fontSize: 10,
    color: "#666",
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: "1px",
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    color: "#888",
    textTransform: "uppercase",
    letterSpacing: "0.8px",
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  alertCount: {
    background: "rgba(0,230,118,0.15)",
    color: "#00e676",
    fontSize: 10,
    fontWeight: 700,
    padding: "1px 6px",
    borderRadius: 10,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  label: {
    fontSize: 11,
    color: "#999",
  },
  input: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 6,
    padding: "8px 10px",
    color: "#e0e0e0",
    fontSize: 12,
    outline: "none",
    fontFamily: "monospace",
  },
  select: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 6,
    padding: "8px 10px",
    color: "#e0e0e0",
    fontSize: 12,
    outline: "none",
    appearance: "none" as const,
    cursor: "pointer",
  },
  slider: {
    width: "100%",
    accentColor: "#00e676",
    cursor: "pointer",
  },
  toggleBtn: {
    width: "100%",
    padding: "12px 0",
    border: "none",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
    letterSpacing: "0.5px",
    transition: "opacity 0.2s",
  },
  checkRow: {
    display: "flex",
    alignItems: "center",
  },
  checkLabel: {
    fontSize: 12,
    color: "#b0b0b0",
    display: "flex",
    alignItems: "center",
    gap: 8,
    cursor: "pointer",
  },
  checkbox: {
    accentColor: "#00e676",
    cursor: "pointer",
  },
  emptyState: {
    textAlign: "center",
    color: "#555",
    fontSize: 12,
    padding: "16px 0",
  },
  footer: {
    display: "flex",
    gap: 8,
    paddingTop: 8,
    borderTop: "1px solid rgba(255,255,255,0.06)",
  },
  footerBtn: {
    flex: 1,
    padding: "8px 0",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 6,
    color: "#aaa",
    fontSize: 12,
    cursor: "pointer",
    fontWeight: 500,
  },
};
