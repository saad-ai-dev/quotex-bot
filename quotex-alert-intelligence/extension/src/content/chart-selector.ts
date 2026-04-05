// ============================================================
// Quotex Alert Intelligence - Chart Selector
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { ChartRegion } from "@shared/types";

const STORAGE_KEY = "qai_chart_region";

export class ChartSelector {
  private isEnabled = false;
  private region: ChartRegion | null = null;
  private overlayEl: HTMLDivElement | null = null;
  private selectionEl: HTMLDivElement | null = null;
  private startX = 0;
  private startY = 0;
  private isDragging = false;

  private onMouseDown = this.handleMouseDown.bind(this);
  private onMouseMove = this.handleMouseMove.bind(this);
  private onMouseUp = this.handleMouseUp.bind(this);

  enable(): void {
    if (this.isEnabled) return;
    this.isEnabled = true;

    // Create fullscreen overlay for selection
    this.overlayEl = document.createElement("div");
    this.overlayEl.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 9999999;
      cursor: crosshair;
      background: rgba(0, 0, 0, 0.3);
    `;

    // Instruction text
    const instructions = document.createElement("div");
    instructions.style.cssText = `
      position: absolute;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(0, 0, 0, 0.8);
      color: #00ff88;
      padding: 12px 24px;
      border-radius: 8px;
      font-family: monospace;
      font-size: 14px;
      pointer-events: none;
      border: 1px solid #00ff88;
    `;
    instructions.textContent = "Drag to select chart region. Press ESC to cancel.";
    this.overlayEl.appendChild(instructions);

    // Selection rectangle
    this.selectionEl = document.createElement("div");
    this.selectionEl.style.cssText = `
      position: absolute;
      border: 2px dashed #00ff88;
      background: rgba(0, 255, 136, 0.1);
      display: none;
      pointer-events: none;
    `;
    this.overlayEl.appendChild(this.selectionEl);

    document.body.appendChild(this.overlayEl);

    this.overlayEl.addEventListener("mousedown", this.onMouseDown);
    document.addEventListener("mousemove", this.onMouseMove);
    document.addEventListener("mouseup", this.onMouseUp);
    document.addEventListener("keydown", this.handleKeyDown);
  }

  disable(): void {
    if (!this.isEnabled) return;
    this.isEnabled = false;
    this.isDragging = false;

    if (this.overlayEl) {
      this.overlayEl.removeEventListener("mousedown", this.onMouseDown);
      this.overlayEl.remove();
      this.overlayEl = null;
    }

    document.removeEventListener("mousemove", this.onMouseMove);
    document.removeEventListener("mouseup", this.onMouseUp);
    document.removeEventListener("keydown", this.handleKeyDown);
    this.selectionEl = null;
  }

  getRegion(): ChartRegion | null {
    return this.region;
  }

  async saveRegion(): Promise<void> {
    if (!this.region) return;
    await chrome.storage.local.set({ [STORAGE_KEY]: this.region });
  }

  async loadRegion(): Promise<ChartRegion | null> {
    const stored = await chrome.storage.local.get(STORAGE_KEY);
    if (stored[STORAGE_KEY]) {
      this.region = stored[STORAGE_KEY] as ChartRegion;
      return this.region;
    }
    return null;
  }

  drawSelectionOverlay(): void {
    if (!this.region) return;

    // Remove any existing saved-region overlay
    const existing = document.getElementById("qai-saved-region");
    if (existing) existing.remove();

    const el = document.createElement("div");
    el.id = "qai-saved-region";
    el.style.cssText = `
      position: fixed;
      left: ${this.region.x}px;
      top: ${this.region.y}px;
      width: ${this.region.width}px;
      height: ${this.region.height}px;
      border: 1px solid rgba(0, 255, 136, 0.4);
      background: transparent;
      z-index: 999998;
      pointer-events: none;
      border-radius: 2px;
    `;
    document.body.appendChild(el);

    // Auto-hide after 3 seconds
    setTimeout(() => el.remove(), 3000);
  }

  // ----- Private handlers -----

  private handleMouseDown(e: MouseEvent): void {
    this.isDragging = true;
    this.startX = e.clientX;
    this.startY = e.clientY;

    if (this.selectionEl) {
      this.selectionEl.style.display = "block";
      this.selectionEl.style.left = `${e.clientX}px`;
      this.selectionEl.style.top = `${e.clientY}px`;
      this.selectionEl.style.width = "0px";
      this.selectionEl.style.height = "0px";
    }
  }

  private handleMouseMove(e: MouseEvent): void {
    if (!this.isDragging || !this.selectionEl) return;

    const x = Math.min(this.startX, e.clientX);
    const y = Math.min(this.startY, e.clientY);
    const w = Math.abs(e.clientX - this.startX);
    const h = Math.abs(e.clientY - this.startY);

    this.selectionEl.style.left = `${x}px`;
    this.selectionEl.style.top = `${y}px`;
    this.selectionEl.style.width = `${w}px`;
    this.selectionEl.style.height = `${h}px`;
  }

  private handleMouseUp(e: MouseEvent): void {
    if (!this.isDragging) return;
    this.isDragging = false;

    const x = Math.min(this.startX, e.clientX);
    const y = Math.min(this.startY, e.clientY);
    const w = Math.abs(e.clientX - this.startX);
    const h = Math.abs(e.clientY - this.startY);

    // Minimum selection size
    if (w > 20 && h > 20) {
      this.region = { x, y, width: w, height: h };
      this.saveRegion();
    }

    this.disable();

    // Show the saved region briefly
    if (this.region) {
      this.drawSelectionOverlay();
    }
  }

  private handleKeyDown = (e: KeyboardEvent): void => {
    if (e.key === "Escape") {
      this.disable();
    }
  };
}
