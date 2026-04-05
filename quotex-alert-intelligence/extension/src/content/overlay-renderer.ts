// ============================================================
// Quotex Alert Intelligence - Overlay Renderer
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { MonitoringState, Signal, SignalStatus } from "@shared/types";

interface RecentOutcome {
  direction: string;
  outcome: SignalStatus;
  confidence: number;
}

export class OverlayRenderer {
  private container: HTMLDivElement;
  private badgeEl: HTMLDivElement | null = null;
  private alertEl: HTMLDivElement | null = null;
  private countdownEl: HTMLDivElement | null = null;
  private countdownTimer: ReturnType<typeof setInterval> | null = null;
  private isConnected = false;
  private recentOutcomes: RecentOutcome[] = [];
  private currentState: MonitoringState | null = null;

  constructor(container: HTMLDivElement) {
    this.container = container;
    this.createBadge();
  }

  render(state: MonitoringState): void {
    this.currentState = state;
    this.isConnected = state.is_connected;
    this.updateBadge(state);
  }

  showAlert(signal: Signal): void {
    // Remove existing alert
    if (this.alertEl) {
      this.alertEl.remove();
      this.alertEl = null;
    }

    this.alertEl = document.createElement("div");
    this.alertEl.style.cssText = `
      position: fixed;
      top: 80px;
      right: 16px;
      width: 280px;
      background: rgba(15, 15, 25, 0.95);
      border: 1px solid ${signal.prediction_direction === "CALL" ? "#00e676" : "#ff1744"};
      border-radius: 12px;
      padding: 16px;
      z-index: 999999;
      pointer-events: auto;
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: #e0e0e0;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
      animation: qai-slide-in 0.3s ease-out;
    `;

    // Inject animation keyframes if not already present
    this.ensureAnimationStyles();

    const dirColor = signal.prediction_direction === "CALL" ? "#00e676" : "#ff1744";
    const arrow = signal.prediction_direction === "CALL" ? "\u25B2" : "\u25BC";

    this.alertEl.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
        <div style="font-size: 28px; color: ${dirColor}; line-height: 1;">${arrow}</div>
        <div>
          <div style="font-size: 18px; font-weight: 700; color: ${dirColor};">
            ${signal.prediction_direction}
          </div>
          <div style="font-size: 11px; color: #888; margin-top: 2px;">
            ${signal.asset_name} &middot; ${signal.market_type.toUpperCase()}
          </div>
        </div>
        <div style="margin-left: auto; text-align: right;">
          <div style="font-size: 22px; font-weight: 700; font-family: monospace; color: ${dirColor};">
            ${Math.round(signal.confidence)}%
          </div>
          <div style="font-size: 10px; color: #888;">confidence</div>
        </div>
      </div>
      <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 10px; margin-bottom: 8px;">
        <div style="font-size: 10px; text-transform: uppercase; color: #666; margin-bottom: 4px; letter-spacing: 0.5px;">Reasons</div>
        ${signal.reasons
          .slice(0, 3)
          .map(
            (r) =>
              `<div style="font-size: 12px; color: #b0b0b0; padding: 2px 0; display: flex; align-items: baseline; gap: 6px;">
                <span style="color: ${dirColor}; font-size: 8px;">\u25CF</span> ${r}
              </div>`
          )
          .join("")}
      </div>
      <div style="display: flex; gap: 8px; margin-top: 10px;">
        <span style="
          background: rgba(255,255,255,0.06);
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 11px;
          color: #aaa;
        ">${signal.expiry_profile}</span>
        <span style="
          background: rgba(255,255,255,0.06);
          padding: 3px 8px;
          border-radius: 4px;
          font-size: 11px;
          color: #aaa;
        ">B:${Math.round(signal.bullish_score)} / R:${Math.round(signal.bearish_score)}</span>
      </div>
      <div style="
        position: absolute; top: 8px; right: 12px;
        cursor: pointer; color: #666; font-size: 16px;
        pointer-events: auto; line-height: 1;
      " id="qai-alert-close">\u00D7</div>
    `;

    this.container.appendChild(this.alertEl);

    // Close button
    const closeBtn = this.alertEl.querySelector("#qai-alert-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        if (this.alertEl) {
          this.alertEl.remove();
          this.alertEl = null;
        }
      });
    }

    // Track outcome
    this.recentOutcomes.unshift({
      direction: signal.prediction_direction,
      outcome: signal.status,
      confidence: signal.confidence,
    });
    if (this.recentOutcomes.length > 3) this.recentOutcomes.length = 3;
    this.updateBadge(this.currentState);

    // Auto-dismiss after 15 seconds
    setTimeout(() => {
      if (this.alertEl) {
        this.alertEl.style.animation = "qai-slide-out 0.3s ease-in forwards";
        setTimeout(() => {
          if (this.alertEl) {
            this.alertEl.remove();
            this.alertEl = null;
          }
        }, 300);
      }
    }, 15000);
  }

  showCountdown(seconds: number): void {
    if (this.countdownTimer) {
      clearInterval(this.countdownTimer);
    }

    if (!this.countdownEl) {
      this.countdownEl = document.createElement("div");
      this.countdownEl.style.cssText = `
        position: fixed;
        bottom: 80px;
        right: 16px;
        background: rgba(15, 15, 25, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 10px;
        padding: 10px 16px;
        z-index: 999999;
        pointer-events: none;
        font-family: monospace;
        color: #e0e0e0;
        text-align: center;
      `;
      this.container.appendChild(this.countdownEl);
    }

    let remaining = seconds;

    const update = () => {
      if (!this.countdownEl) return;
      const color = remaining <= 5 ? "#ff1744" : remaining <= 15 ? "#ffc107" : "#00e676";
      this.countdownEl.innerHTML = `
        <div style="font-size: 10px; text-transform: uppercase; color: #666; letter-spacing: 0.5px;">Candle Close</div>
        <div style="font-size: 28px; font-weight: 700; color: ${color}; margin-top: 4px;">${remaining}s</div>
      `;
    };

    update();

    this.countdownTimer = setInterval(() => {
      remaining--;
      if (remaining <= 0) {
        if (this.countdownTimer) clearInterval(this.countdownTimer);
        if (this.countdownEl) {
          this.countdownEl.remove();
          this.countdownEl = null;
        }
        return;
      }
      update();
    }, 1000);
  }

  updateConnectionStatus(connected: boolean): void {
    this.isConnected = connected;
    this.updateBadge(this.currentState);
  }

  destroy(): void {
    if (this.countdownTimer) clearInterval(this.countdownTimer);
    if (this.badgeEl) this.badgeEl.remove();
    if (this.alertEl) this.alertEl.remove();
    if (this.countdownEl) this.countdownEl.remove();
    this.badgeEl = null;
    this.alertEl = null;
    this.countdownEl = null;
  }

  // ----- Private -----

  private createBadge(): void {
    this.badgeEl = document.createElement("div");
    this.badgeEl.style.cssText = `
      position: fixed;
      top: 16px;
      right: 16px;
      background: rgba(15, 15, 25, 0.9);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 10px;
      padding: 10px 14px;
      z-index: 999999;
      pointer-events: auto;
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: #e0e0e0;
      font-size: 12px;
      min-width: 160px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    `;
    this.container.appendChild(this.badgeEl);
  }

  private updateBadge(state: MonitoringState | null): void {
    if (!this.badgeEl) return;

    const isMonitoring = state?.is_monitoring ?? false;
    const marketType = state?.market_type ?? null;
    const currentAsset = state?.current_asset ?? null;
    const connDot = this.isConnected ? "#00e676" : "#ff1744";
    const monitorText = isMonitoring ? "Monitoring" : "Stopped";
    const monitorColor = isMonitoring ? "#00e676" : "#888";

    let outcomesHtml = "";
    if (this.recentOutcomes.length > 0) {
      const items = this.recentOutcomes.map((o) => {
        const bg =
          o.outcome === "win"
            ? "rgba(0,230,118,0.15)"
            : o.outcome === "loss"
            ? "rgba(255,23,68,0.15)"
            : "rgba(255,193,7,0.15)";
        const color =
          o.outcome === "win" ? "#00e676" : o.outcome === "loss" ? "#ff1744" : "#ffc107";
        const arrow = o.direction === "CALL" ? "\u25B2" : "\u25BC";
        const label =
          o.outcome === "win" ? "W" : o.outcome === "loss" ? "L" : "?";
        return `<span style="background:${bg}; color:${color}; padding:2px 6px; border-radius:3px; font-size:10px; font-weight:600;">${arrow}${label}</span>`;
      });
      outcomesHtml = `
        <div style="display:flex; gap:4px; margin-top:8px;">
          ${items.join("")}
        </div>
      `;
    }

    let expiryHtml = "";
    if (state?.last_alert?.signal) {
      expiryHtml = `<span style="color:#888; font-size:10px; margin-left:8px;">${state.last_alert.signal.expiry_profile}</span>`;
    }

    this.badgeEl.innerHTML = `
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
        <div style="width:7px; height:7px; border-radius:50%; background:${connDot}; flex-shrink:0;"></div>
        <span style="font-weight:600; color:${monitorColor}; font-size:12px;">${monitorText}</span>
        ${expiryHtml}
      </div>
      ${
        marketType || currentAsset
          ? `<div style="font-size:11px; color:#888;">
               ${currentAsset ? `<span style="color:#b0b0b0;">${currentAsset}</span>` : ""}
               ${marketType ? `<span style="background:rgba(255,255,255,0.06); padding:1px 6px; border-radius:3px; margin-left:6px; font-size:10px;">${marketType.toUpperCase()}</span>` : ""}
             </div>`
          : ""
      }
      ${outcomesHtml}
    `;
  }

  private ensureAnimationStyles(): void {
    if (document.getElementById("qai-animation-styles")) return;

    const style = document.createElement("style");
    style.id = "qai-animation-styles";
    style.textContent = `
      @keyframes qai-slide-in {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
      @keyframes qai-slide-out {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }
}
