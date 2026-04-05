// ============================================================
// Quotex Alert Intelligence - Options Page
// ALERT-ONLY system - NO trade execution
// ============================================================

import React, { useEffect, useState } from "react";
import type { Settings } from "@shared/types";

const DEFAULT_SETTINGS: Settings = {
  backend_url: "http://localhost:8000",
  monitoring_enabled: false,
  market_mode: "otc",
  expiry_profile: "short",
  min_confidence_threshold: 60,
  sound_alerts_enabled: true,
  browser_notifications_enabled: true,
  screenshot_logging_enabled: false,
  parse_interval_ms: 5000,
  use_websocket: true,
  auto_detect_market: true,
};

export const OptionsPage: React.FC = () => {
  const [settings, setSettings] = useState<Settings>({ ...DEFAULT_SETTINGS });
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    chrome.storage.sync.get("settings", (result) => {
      if (result.settings) {
        setSettings({ ...DEFAULT_SETTINGS, ...result.settings });
      }
      setLoading(false);
    });
  }, []);

  const updateField = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    await chrome.storage.sync.set({ settings });
    // Also update local storage for the service worker
    await chrome.storage.local.set({ settings });
    // Notify background
    try {
      await chrome.runtime.sendMessage({
        type: "SETTINGS_UPDATED",
        payload: settings,
      });
    } catch {
      // Background might not be active
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (loading) {
    return (
      <div style={styles.page}>
        <div style={styles.loading}>Loading settings...</div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Quotex Alert Intelligence</h1>
        <p style={styles.subtitle}>ALERT-ONLY - No Trade Execution</p>

        {/* Backend URL */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Connection</h2>

          <div style={styles.field}>
            <label style={styles.label}>Backend URL</label>
            <input
              type="text"
              value={settings.backend_url}
              onChange={(e) => updateField("backend_url", e.target.value)}
              style={styles.input}
              placeholder="http://localhost:8000"
            />
            <span style={styles.hint}>
              The URL of the backend analysis server
            </span>
          </div>

          <div style={styles.field}>
            <label style={styles.checkLabel}>
              <input
                type="checkbox"
                checked={settings.use_websocket}
                onChange={(e) => updateField("use_websocket", e.target.checked)}
                style={styles.checkbox}
              />
              Use WebSocket for real-time alerts
            </label>
            <span style={styles.hint}>
              Falls back to polling when disabled
            </span>
          </div>
        </div>

        {/* Parsing */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Chart Parsing</h2>

          <div style={styles.field}>
            <label style={styles.label}>Parse Interval (ms)</label>
            <input
              type="number"
              value={settings.parse_interval_ms}
              onChange={(e) =>
                updateField("parse_interval_ms", parseInt(e.target.value, 10) || 5000)
              }
              style={styles.input}
              min={1000}
              max={60000}
              step={1000}
            />
            <span style={styles.hint}>
              How often to capture chart data (1000-60000ms)
            </span>
          </div>

          <div style={styles.field}>
            <label style={styles.checkLabel}>
              <input
                type="checkbox"
                checked={settings.screenshot_logging_enabled}
                onChange={(e) =>
                  updateField("screenshot_logging_enabled", e.target.checked)
                }
                style={styles.checkbox}
              />
              Enable screenshot logging
            </label>
            <span style={styles.hint}>
              Saves chart screenshots for debugging (increases storage usage)
            </span>
          </div>
        </div>

        {/* Analysis */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Analysis</h2>

          <div style={styles.field}>
            <label style={styles.label}>
              Default Confidence Threshold: {settings.min_confidence_threshold}%
            </label>
            <input
              type="range"
              min={30}
              max={95}
              step={5}
              value={settings.min_confidence_threshold}
              onChange={(e) =>
                updateField(
                  "min_confidence_threshold",
                  parseInt(e.target.value, 10)
                )
              }
              style={styles.slider}
            />
            <div style={styles.sliderLabels}>
              <span>30%</span>
              <span>95%</span>
            </div>
          </div>

          <div style={styles.field}>
            <label style={styles.checkLabel}>
              <input
                type="checkbox"
                checked={settings.auto_detect_market}
                onChange={(e) =>
                  updateField("auto_detect_market", e.target.checked)
                }
                style={styles.checkbox}
              />
              Auto-detect market type (OTC / Live)
            </label>
          </div>
        </div>

        {/* Save */}
        <div style={styles.actions}>
          <button onClick={handleSave} style={styles.saveBtn}>
            {saved ? "Saved!" : "Save Settings"}
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
    display: "flex",
    justifyContent: "center",
    padding: "40px 20px",
  },
  card: {
    width: "100%",
    maxWidth: 560,
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: "32px 36px",
  },
  title: {
    fontSize: 22,
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
  section: {
    marginBottom: 28,
    paddingBottom: 24,
    borderBottom: "1px solid rgba(255,255,255,0.04)",
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: "#888",
    textTransform: "uppercase",
    letterSpacing: "0.8px",
    marginBottom: 16,
    marginTop: 0,
  },
  field: {
    marginBottom: 16,
  },
  label: {
    display: "block",
    fontSize: 13,
    color: "#b0b0b0",
    marginBottom: 6,
  },
  input: {
    width: "100%",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 8,
    padding: "10px 14px",
    color: "#e0e0e0",
    fontSize: 14,
    outline: "none",
    fontFamily: "monospace",
    boxSizing: "border-box" as const,
  },
  hint: {
    display: "block",
    fontSize: 11,
    color: "#555",
    marginTop: 4,
  },
  slider: {
    width: "100%",
    accentColor: "#00e676",
    cursor: "pointer",
  },
  sliderLabels: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 10,
    color: "#555",
    marginTop: 2,
  },
  checkLabel: {
    fontSize: 13,
    color: "#b0b0b0",
    display: "flex",
    alignItems: "center",
    gap: 10,
    cursor: "pointer",
  },
  checkbox: {
    accentColor: "#00e676",
    cursor: "pointer",
    width: 16,
    height: 16,
  },
  actions: {
    marginTop: 8,
  },
  saveBtn: {
    width: "100%",
    padding: "14px 0",
    background: "linear-gradient(135deg, #00e676, #00c853)",
    border: "none",
    borderRadius: 8,
    color: "#0a0a0a",
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    letterSpacing: "0.5px",
  },
  loading: {
    color: "#666",
    fontSize: 14,
    textAlign: "center",
    marginTop: 100,
  },
};
