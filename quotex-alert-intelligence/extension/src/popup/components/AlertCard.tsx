// ============================================================
// Quotex Alert Intelligence - Alert Card Component
// ALERT-ONLY system - NO trade execution
// ============================================================

import React from "react";
import type { AlertEvent } from "@shared/types";

interface AlertCardProps {
  alert: AlertEvent;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export const AlertCard: React.FC<AlertCardProps> = ({ alert }) => {
  const signal = alert.signal;
  if (!signal) {
    return (
      <div style={styles.card}>
        <div style={styles.messageOnly}>
          {alert.message || "Connection event"}
        </div>
      </div>
    );
  }

  const isCall = signal.prediction_direction === "CALL";
  const dirColor = isCall ? "#00e676" : "#ff1744";
  const arrow = isCall ? "\u25B2" : "\u25BC";
  const confidence = Math.round(signal.confidence);

  const outcomeColor =
    signal.outcome === "win"
      ? "#00e676"
      : signal.outcome === "loss"
      ? "#ff1744"
      : "#ffc107";

  const outcomeBg =
    signal.outcome === "win"
      ? "rgba(0,230,118,0.12)"
      : signal.outcome === "loss"
      ? "rgba(255,23,68,0.12)"
      : "rgba(255,193,7,0.12)";

  const outcomeLabel =
    signal.outcome === "win"
      ? "WIN"
      : signal.outcome === "loss"
      ? "LOSS"
      : "PENDING";

  const createdAt = signal.timestamps.created_at;

  return (
    <div style={styles.card}>
      <div style={styles.topRow}>
        <div style={{ ...styles.arrow, color: dirColor }}>{arrow}</div>
        <div style={styles.info}>
          <div style={{ ...styles.direction, color: dirColor }}>
            {signal.prediction_direction}
          </div>
          <div style={styles.meta}>
            {signal.asset_name} &middot; {signal.market_type.toUpperCase()}
          </div>
        </div>
        <div style={styles.right}>
          <div style={{ ...styles.confidence, color: dirColor }}>
            {confidence}%
          </div>
        </div>
      </div>
      <div style={styles.bottomRow}>
        <span style={styles.expiryBadge}>{signal.expiry_profile}</span>
        <span
          style={{
            ...styles.outcomeBadge,
            color: outcomeColor,
            background: outcomeBg,
            borderColor: outcomeColor,
          }}
        >
          {outcomeLabel}
        </span>
        <span style={styles.timeAgo}>
          {createdAt ? timeAgo(createdAt) : ""}
        </span>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 8,
    padding: "10px 12px",
    marginBottom: 6,
  },
  topRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  arrow: {
    fontSize: 20,
    fontWeight: 700,
    lineHeight: 1,
    flexShrink: 0,
  },
  info: {
    flex: 1,
    minWidth: 0,
  },
  direction: {
    fontSize: 13,
    fontWeight: 700,
  },
  meta: {
    fontSize: 10,
    color: "#888",
    marginTop: 1,
  },
  right: {
    textAlign: "right" as const,
    flexShrink: 0,
  },
  confidence: {
    fontSize: 18,
    fontWeight: 700,
    fontFamily: "monospace",
  },
  bottomRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginTop: 8,
  },
  expiryBadge: {
    background: "rgba(255,255,255,0.06)",
    color: "#aaa",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 10,
  },
  outcomeBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid",
  },
  timeAgo: {
    fontSize: 10,
    color: "#666",
    marginLeft: "auto",
  },
  messageOnly: {
    fontSize: 12,
    color: "#888",
    padding: 4,
  },
};
