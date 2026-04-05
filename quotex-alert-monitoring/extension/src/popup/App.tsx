/**
 * Quotex Alert Monitor - Popup
 * Shows monitoring status + auto-trade controls.
 */

import React, { useEffect, useState } from "react";
import type { Signal, ExtensionMessage, TradeSettings } from "../shared/types";

interface PopupState {
  monitoring: boolean;
  connected: boolean;
  lastSignal: Signal | null;
}

interface TradeState {
  autoTradeEnabled: boolean;
  maxConsecutiveLosses: number;
  consecutiveLosses: number;
  totalTrades: number;
  wins: number;
  losses: number;
  tradingPaused: boolean;
}

const App: React.FC = () => {
  const [state, setState] = useState<PopupState>({
    monitoring: false,
    connected: false,
    lastSignal: null,
  });

  const [trade, setTrade] = useState<TradeState>({
    autoTradeEnabled: false,
    maxConsecutiveLosses: 3,
    consecutiveLosses: 0,
    totalTrades: 0,
    wins: 0,
    losses: 0,
    tradingPaused: false,
  });

  const [maxLossInput, setMaxLossInput] = useState("3");

  // Fetch state from background + content script
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

    // Get trade state from content script
    fetchTradeState();
    const iv = setInterval(fetchTradeState, 2000);
    return () => clearInterval(iv);
  }, []);

  function fetchTradeState() {
    // Send to ALL quotex tabs to get trade state
    chrome.tabs.query(
      { url: ["*://quotex.io/*", "*://*.quotex.io/*", "*://qxbroker.com/*", "*://*.qxbroker.com/*", "*://market-qx.trade/*", "*://*.market-qx.trade/*"] },
      (tabs) => {
        for (const tab of tabs) {
          if (tab.id) {
            chrome.tabs.sendMessage(tab.id, { type: "GET_TRADE_STATE" } as ExtensionMessage, (resp) => {
              if (chrome.runtime.lastError) return;
              if (resp) {
                setTrade({
                  autoTradeEnabled: resp.autoTradeEnabled ?? false,
                  maxConsecutiveLosses: resp.maxConsecutiveLosses ?? 3,
                  consecutiveLosses: resp.consecutiveLosses ?? 0,
                  totalTrades: resp.totalTrades ?? 0,
                  wins: resp.wins ?? 0,
                  losses: resp.losses ?? 0,
                  tradingPaused: resp.tradingPaused ?? false,
                });
                setMaxLossInput(String(resp.maxConsecutiveLosses ?? 3));
              }
            });
            break; // Only need first tab
          }
        }
      }
    );
  }

  const toggleMonitoring = () => {
    const newVal = !state.monitoring;
    setState(prev => ({ ...prev, monitoring: newVal }));
    chrome.runtime.sendMessage({ type: "TOGGLE_MONITORING", enabled: newVal } as ExtensionMessage);
  };

  const toggleAutoTrade = () => {
    const newEnabled = !trade.autoTradeEnabled;
    const settings: TradeSettings = {
      autoTradeEnabled: newEnabled,
      maxConsecutiveLosses: parseInt(maxLossInput) || 3,
    };
    // Send to content script
    sendToContentScript({ type: "SET_TRADE_SETTINGS", payload: settings } as ExtensionMessage);
    setTrade(prev => ({ ...prev, autoTradeEnabled: newEnabled }));
  };

  const updateMaxLosses = () => {
    const val = parseInt(maxLossInput) || 3;
    const settings: TradeSettings = {
      autoTradeEnabled: trade.autoTradeEnabled,
      maxConsecutiveLosses: val,
    };
    sendToContentScript({ type: "SET_TRADE_SETTINGS", payload: settings } as ExtensionMessage);
    setTrade(prev => ({ ...prev, maxConsecutiveLosses: val }));
  };

  const resetTradeState = () => {
    sendToContentScript({ type: "RESET_TRADE_STATE" } as ExtensionMessage);
    setTrade(prev => ({ ...prev, consecutiveLosses: 0, tradingPaused: false, totalTrades: 0, wins: 0, losses: 0 }));
  };

  function sendToContentScript(message: ExtensionMessage) {
    chrome.tabs.query(
      { url: ["*://quotex.io/*", "*://*.quotex.io/*", "*://qxbroker.com/*", "*://*.qxbroker.com/*", "*://market-qx.trade/*", "*://*.market-qx.trade/*"] },
      (tabs) => {
        for (const tab of tabs) {
          if (tab.id) chrome.tabs.sendMessage(tab.id, message).catch(() => {});
        }
      }
    );
  }

  const { monitoring, connected, lastSignal } = state;
  const winRate = trade.totalTrades > 0 ? ((trade.wins / trade.totalTrades) * 100).toFixed(1) : "0.0";

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>Quotex Alert Monitor</h1>
        <span style={styles.badge}>v2</span>
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

      {/* Auto-Trade Controls */}
      <div style={{ ...styles.card, border: trade.autoTradeEnabled ? "1px solid #da3633" : "1px solid #21262d" }}>
        <div style={styles.cardHeader}>
          AUTO-TRADE
          {trade.tradingPaused && (
            <span style={{ fontSize: 9, color: "#f85149", marginLeft: 8, fontWeight: 700 }}>PAUSED</span>
          )}
        </div>

        {/* Enable/Disable Toggle */}
        <div style={styles.toggleRow}>
          <span style={{ color: trade.autoTradeEnabled ? "#f85149" : "#8b949e", fontSize: 12 }}>
            {trade.autoTradeEnabled ? "ENABLED" : "Disabled"}
          </span>
          <button
            style={{
              ...styles.toggleBtn,
              backgroundColor: trade.autoTradeEnabled ? "#e74c3c" : "#da6633",
              fontSize: 11,
              padding: "5px 12px",
            }}
            onClick={toggleAutoTrade}
          >
            {trade.autoTradeEnabled ? "Disable" : "Enable"}
          </button>
        </div>

        {/* Max Consecutive Losses */}
        <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "#8b949e", flex: 1 }}>Max Consecutive Losses:</span>
          <input
            type="number"
            min="1"
            max="20"
            value={maxLossInput}
            onChange={(e) => setMaxLossInput(e.target.value)}
            onBlur={updateMaxLosses}
            onKeyDown={(e) => e.key === "Enter" && updateMaxLosses()}
            style={styles.input}
          />
        </div>

        {/* Trade Stats */}
        {trade.totalTrades > 0 && (
          <div style={{ marginTop: 10, borderTop: "1px solid #21262d", paddingTop: 8 }}>
            <div style={styles.statRow}>
              <span>Total Trades</span>
              <span style={styles.statValue}>{trade.totalTrades}</span>
            </div>
            <div style={styles.statRow}>
              <span>Wins / Losses</span>
              <span>
                <span style={{ color: "#2ecc71", fontWeight: 600 }}>{trade.wins}</span>
                {" / "}
                <span style={{ color: "#e74c3c", fontWeight: 600 }}>{trade.losses}</span>
              </span>
            </div>
            <div style={styles.statRow}>
              <span>Win Rate</span>
              <span style={{ ...styles.statValue, color: parseFloat(winRate) >= 50 ? "#2ecc71" : "#e74c3c" }}>{winRate}%</span>
            </div>
            <div style={styles.statRow}>
              <span>Consecutive Losses</span>
              <span style={{ ...styles.statValue, color: trade.consecutiveLosses > 0 ? "#e74c3c" : "#8b949e" }}>
                {trade.consecutiveLosses} / {trade.maxConsecutiveLosses}
              </span>
            </div>
          </div>
        )}

        {/* Paused Warning */}
        {trade.tradingPaused && (
          <div style={{ marginTop: 8, padding: "6px 10px", backgroundColor: "rgba(248,81,73,0.15)", borderRadius: 4, fontSize: 11, color: "#f85149" }}>
            Trading paused after {trade.consecutiveLosses} consecutive losses. Alerts still active.
            <button
              style={{ ...styles.toggleBtn, backgroundColor: "#da6633", fontSize: 10, padding: "3px 10px", marginTop: 6, display: "block" }}
              onClick={resetTradeState}
            >
              Reset & Resume
            </button>
          </div>
        )}
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

      <div style={styles.footer}>
        {trade.autoTradeEnabled
          ? "AUTO-TRADE ENABLED - Bot will place trades on signals"
          : "ALERT ONLY - No trades are executed"}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: { width: 340, minHeight: 400, backgroundColor: "#0f1117", color: "#e1e4e8", fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: 13 },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: "1px solid #21262d", background: "linear-gradient(135deg, #161b22, #0d1117)" },
  title: { fontSize: 15, fontWeight: 600, margin: 0, color: "#f0f6fc" },
  badge: { fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 3, backgroundColor: "#da3633", color: "#fff" },
  statusBar: { display: "flex", alignItems: "center", gap: 8, padding: "8px 16px", borderBottom: "1px solid #21262d", fontSize: 11, color: "#8b949e" },
  dot: { display: "inline-block", width: 8, height: 8, borderRadius: "50%", flexShrink: 0 },
  card: { backgroundColor: "#161b22", borderRadius: 6, padding: 12, margin: "8px 16px", border: "1px solid #21262d" },
  cardHeader: { fontSize: 11, fontWeight: 600, color: "#f0f6fc", marginBottom: 8, letterSpacing: 0.5, textTransform: "uppercase" as const },
  toggleRow: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  toggleBtn: { padding: "6px 16px", border: "none", borderRadius: 4, color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 12 },
  statRow: { display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 12 },
  statValue: { fontWeight: 600, color: "#58a6ff" },
  emptyText: { color: "#484f58", fontSize: 12, textAlign: "center" as const, padding: "8px 0" },
  footer: { padding: "8px 16px", borderTop: "1px solid #21262d", fontSize: 10, color: "#484f58", textAlign: "center" as const },
  input: { width: 50, padding: "4px 6px", backgroundColor: "#0d1117", border: "1px solid #30363d", borderRadius: 4, color: "#f0f6fc", fontSize: 12, textAlign: "center" as const },
};

export default App;
