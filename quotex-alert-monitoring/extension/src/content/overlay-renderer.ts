import type { SignalDirection } from "../shared/types";

export class OverlayRenderer {
  private container: HTMLDivElement | null = null;
  private statusText: string = "Initializing";
  private connected: boolean = false;
  private lastDirection: SignalDirection | null = null;
  private currentPrice: number | null = null;
  private tradeStatus: string | null = null;

  mount(): void {
    if (this.container) return;
    this.container = document.createElement("div");
    this.container.id = "quotex-alert-monitor-overlay";
    this.applyStyles();
    this.render();
    document.body.appendChild(this.container);
  }

  unmount(): void {
    if (this.container) { this.container.remove(); this.container = null; }
  }

  setConnected(value: boolean): void { this.connected = value; this.render(); }
  setStatus(text: string): void { this.statusText = text; this.render(); }
  setLastDirection(direction: SignalDirection | null): void { this.lastDirection = direction; this.render(); }
  setPrice(price: number): void { this.currentPrice = price; this.render(); }
  setTradeStatus(status: string | null): void { this.tradeStatus = status; this.render(); }

  private applyStyles(): void {
    if (!this.container) return;
    Object.assign(this.container.style, {
      position: "fixed", bottom: "10px", right: "10px", zIndex: "999999",
      background: "rgba(13, 17, 23, 0.92)", border: "1px solid rgba(48, 54, 61, 0.8)",
      borderRadius: "8px", padding: "8px 12px",
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      fontSize: "11px", color: "#e1e4e8", backdropFilter: "blur(8px)",
      boxShadow: "0 4px 16px rgba(0, 0, 0, 0.4)", pointerEvents: "none", minWidth: "180px",
    });
  }

  private render(): void {
    if (!this.container) return;
    const t = this.connected ? "#2ecc71" : "#e74c3c";
    const priceText = this.currentPrice !== null ? this.currentPrice.toFixed(5) : "--";
    const dirHtml = this.lastDirection
      ? `<span style="color:${this.lastDirection === "UP" ? "#2ecc71" : "#e74c3c"};font-weight:bold">${this.lastDirection === "UP" ? "\u25B2 UP" : "\u25BC DOWN"}</span>`
      : "";
    const tradeHtml = this.tradeStatus
      ? `<div style="font-size:9px;margin-top:3px;padding:2px 6px;border-radius:3px;background:${this.tradeStatus.includes("PAUSED") ? "rgba(248,81,73,0.2);color:#f85149" : "rgba(63,185,80,0.2);color:#3fb950"};font-weight:600;">${this.tradeStatus}</div>`
      : "";

    this.container.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">
        <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${t};flex-shrink:0;${this.connected ? "box-shadow:0 0 4px rgba(46,204,113,0.6);" : ""}"></span>
        <span style="font-weight:600;color:#f0f6fc;font-size:10px;">Alert Monitor</span>
        <span style="font-size:9px;color:#8b949e;margin-left:auto;">${this.statusText}</span>
      </div>
      <div style="font-size:10px;color:#8b949e;">
        Price: <span style="color:#58a6ff;font-weight:600;">${priceText}</span>
        ${dirHtml ? ` | ${dirHtml}` : ""}
      </div>
      ${tradeHtml}
    `;
  }
}
