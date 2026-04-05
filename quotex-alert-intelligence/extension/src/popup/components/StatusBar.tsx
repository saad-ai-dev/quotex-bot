// ============================================================
// Quotex Alert Intelligence - Status Bar Component
// ALERT-ONLY system - NO trade execution
// ============================================================

import React from "react";
import type { MarketType } from "@shared/types";

interface StatusBarProps {
  isConnected: boolean;
  isMonitoring: boolean;
  marketType: MarketType | null;
  currentAsset?: string | null;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  isConnected,
  isMonitoring,
  marketType,
  currentAsset,
}) => {
  const dotColor = isConnected ? "#00e676" : "#ff1744";
  const statusText = isMonitoring ? "Monitoring" : "Stopped";
  const statusColor = isMonitoring ? "#00e676" : "#888";

  return (
    <div style={styles.container}>
      <div style={styles.left}>
        <div
          style={{
            ...styles.dot,
            backgroundColor: dotColor,
            boxShadow: `0 0 6px ${dotColor}`,
          }}
        />
        <span style={{ ...styles.statusText, color: statusColor }}>
          {statusText}
        </span>
      </div>
      <div style={styles.right}>
        {currentAsset && (
          <span style={styles.assetName}>{currentAsset}</span>
        )}
        {marketType && (
          <span style={styles.marketBadge}>{marketType.toUpperCase()}</span>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 14px",
    background: "rgba(255,255,255,0.03)",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.06)",
  },
  left: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    flexShrink: 0,
  },
  statusText: {
    fontSize: 13,
    fontWeight: 600,
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  assetName: {
    fontSize: 12,
    color: "#b0b0b0",
    fontWeight: 500,
  },
  marketBadge: {
    fontSize: 10,
    color: "#aaa",
    background: "rgba(255,255,255,0.06)",
    padding: "2px 8px",
    borderRadius: 4,
    fontWeight: 600,
    letterSpacing: "0.5px",
  },
};
