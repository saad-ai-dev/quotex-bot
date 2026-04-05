/**
 * Quotex Alert Monitor - Popup
 * ALERT-ONLY: Shows monitoring status. No trade execution.
 */

import React, { useEffect, useState } from "react";
import type { Signal, ExtensionMessage } from "../shared/types";

interface PopupState {
  monitoring: boolean;
  connected: boolean;
  lastSignal: Signal | null;
}

const App: React.FC = () => {
  const [state, setState] = useState<PopupState>({
    monitoring: false,
    connected: false,
    lastSignal: null,
  });

  // Fetch state from background once on mount
  useEffect(() => {
    chrome.runtime.sendMessage(
      { type: "GET_STATE" } as ExtensionMessage,
      (response: PopupState | undefined) => {
        if (chrome.runtime.lastError) return;
        if (response) {
          setState({
            monitoring: response.monitoring ?? false,
            connected: response.connected ?? false,
            lastSignal: response.lastSignal ?? null,
          });
        }
      }
    );
  }, []);

  const toggleMonitoring = () => {
    const newVal = !state.monitoring;
    setState(prev => ({ ...prev, monitoring: newVal }));
    chrome.runtime.sendMessage({
      type: "TOGGLE_MONITORING",
      enabled: newVal,
    } as ExtensionMessage);
  };

  const { monitoring, connected, lastSignal } = state;

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>Quotex Alert Monitor</h1>
        <span style={styles.badge}>ALERT ONLY</span>
      </div>

      {/* Connection Status */}
      <div style={styles.statusBar}>
        <span style={{ ...styles.dot, backgroundColor: connected ? "#2ecc71" : "#e74c3c" }} />
        <span>Backend: {connected ? "Connected" : "Disconnected"}</span>
      </div>

      {/* Monitoring Toggle */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>MONITORING</div>
        <div style={styles.toggleRow}>
          <span style={{ color: monitoring ? "#2ecc71" : "#8b949e" }}>
            {monitoring ? "Active" : "Inactive"}
          </span>
          <button
            style={{ ...styles.toggleBtn, backgroundColor: monitoring ? "#e74c3c" : "#2ecc71" }}
            onClick={toggleMonitoring}
          >
            {monitoring ? "Stop" : "Start"}
          </button>
        </div>
      </div>

      {/* Backend Info */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>BACKEND</div>
        <div style={styles.statRow}><span>URL</span><span style={styles.statValue}>http://localhost:8000</span></div>
        <div style={styles.statRow}><span>Market Mode</span><span style={styles.statValue}>LIVE</span></div>
        <div style={styles.statRow}><span>Expiry</span><span style={styles.statValue}>1m</span></div>
      </div>

      {/* Last Signal */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>LAST SIGNAL</div>
        {lastSignal ? (
          <>
            <div style={styles.statRow}>
              <span>Asset</span>
              <span style={styles.statValue}>{lastSignal.asset || "N/A"}</span>
            </div>
            <div style={styles.statRow}>
              <span>Direction</span>
              <span style={{ ...styles.statValue, color: lastSignal.direction === "UP" ? "#2ecc71" : "#e74c3c" }}>
                {lastSignal.direction === "UP" ? "\u25B2" : "\u25BC"} {lastSignal.direction}
              </span>
            </div>
            <div style={styles.statRow}>
              <span>Confidence</span>
              <span style={styles.statValue}>{lastSignal.confidence}%</span>
            </div>
          </>
        ) : (
          <div style={styles.emptyText}>No signals yet</div>
        )}
      </div>

      <div style={styles.footer}>ALERT ONLY - No trades are executed.</div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { width: 340, minHeight: 380, backgroundColor: "#0f1117", color: "#e1e4e8", fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: 13 },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid #21262d", background: "linear-gradient(135deg, #161b22, #0d1117)" },
  title: { fontSize: 15, fontWeight: 600, margin: 0, color: "#f0f6fc" },
  badge: { fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 3, backgroundColor: "#da3633", color: "#fff" },
  statusBar: { display: "flex", alignItems: "center", gap: 8, padding: "8px 16px", borderBottom: "1px solid #21262d", fontSize: 11, color: "#8b949e" },
  dot: { display: "inline-block", width: 8, height: 8, borderRadius: "50%", flexShrink: 0 },
  card: { backgroundColor: "#161b22", borderRadius: 6, padding: 12, margin: "10px 16px", border: "1px solid #21262d" },
  cardHeader: { fontSize: 12, fontWeight: 600, color: "#f0f6fc", marginBottom: 8, letterSpacing: 0.5 },
  toggleRow: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  toggleBtn: { padding: "6px 16px", border: "none", borderRadius: 4, color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 12 },
  statRow: { display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #21262d", fontSize: 12 },
  statValue: { fontWeight: 600, color: "#58a6ff" },
  emptyText: { color: "#484f58", fontSize: 12, textAlign: "center" as const, padding: "8px 0" },
  footer: { padding: "8px 16px", borderTop: "1px solid #21262d", fontSize: 10, color: "#484f58", textAlign: "center" as const },
};

export default App;
