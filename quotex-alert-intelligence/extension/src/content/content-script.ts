// ============================================================
// Quotex Alert Intelligence - Content Script
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { AlertEvent, MonitoringState, Settings } from "@shared/types";
import { ChartObserver } from "./chart-observer";
import { OverlayRenderer } from "./overlay-renderer";

const QUOTEX_CHART_SELECTORS = [
  ".chart-area",
  "#chart-container",
  '[class*="chart"]',
  "canvas",
];

let chartObserver: ChartObserver | null = null;
let overlayRenderer: OverlayRenderer | null = null;
let overlayContainer: HTMLDivElement | null = null;
let isMonitoring = false;

// ----- Initialization -----

function init(): void {
  if (!isQuotexChartPage()) {
    return;
  }

  createOverlayContainer();
  setupMessageListener();
  requestInitialState();
}

function isQuotexChartPage(): boolean {
  const url = window.location.href;
  const isQuotex =
    url.includes("quotex.io") || url.includes("quotex.com");
  if (!isQuotex) return false;

  // Check for chart presence after a short delay (DOM may still load)
  return true;
}

function createOverlayContainer(): void {
  if (overlayContainer) return;

  overlayContainer = document.createElement("div");
  overlayContainer.id = "qai-overlay-root";
  overlayContainer.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    z-index: 999999;
    pointer-events: none;
    width: 100%;
    height: 100%;
  `;
  document.body.appendChild(overlayContainer);

  overlayRenderer = new OverlayRenderer(overlayContainer);
}

// ----- Message Handling -----

function setupMessageListener(): void {
  chrome.runtime.onMessage.addListener(
    (
      message: { type: string; payload?: unknown },
      _sender: chrome.runtime.MessageSender,
      sendResponse: (response?: unknown) => void
    ) => {
      switch (message.type) {
        case "MONITORING_STARTED":
          startChartObservation();
          sendResponse({ ok: true });
          break;

        case "MONITORING_STOPPED":
          stopChartObservation();
          sendResponse({ ok: true });
          break;

        case "NEW_ALERT":
          handleAlert(message.payload as AlertEvent);
          sendResponse({ ok: true });
          break;

        case "CONNECTION_STATUS":
          handleConnectionStatus(
            (message.payload as { connected: boolean }).connected
          );
          sendResponse({ ok: true });
          break;

        case "SETTINGS_UPDATED":
          handleSettingsUpdate(message.payload as Settings);
          sendResponse({ ok: true });
          break;

        default:
          sendResponse({ ok: false, error: "Unknown message" });
      }
      return true;
    }
  );
}

function requestInitialState(): void {
  chrome.runtime.sendMessage({ type: "GET_STATUS" }, (response) => {
    if (chrome.runtime.lastError) return;
    if (response && response.state) {
      const state = response.state as MonitoringState;
      if (overlayRenderer) {
        overlayRenderer.render(state);
      }
      if (state.is_monitoring) {
        startChartObservation();
      }
    }
  });
}

// ----- Chart Observation -----

function startChartObservation(): void {
  if (isMonitoring) return;
  isMonitoring = true;

  // Wait for chart element to appear
  waitForChartElement().then((chartElement) => {
    if (!chartElement) {
      console.warn("[QAI] Could not find chart element");
      return;
    }

    chartObserver = new ChartObserver(chartElement);
    chartObserver.observe();

    if (overlayRenderer) {
      overlayRenderer.render({
        is_monitoring: true,
        is_connected: false,
        market_type: chartObserver.getMarketType(),
        current_asset: chartObserver.getAssetName(),
        last_alert: null,
      });
    }
  });
}

function stopChartObservation(): void {
  isMonitoring = false;
  if (chartObserver) {
    chartObserver.stop();
    chartObserver = null;
  }
  if (overlayRenderer) {
    overlayRenderer.render({
      is_monitoring: false,
      is_connected: false,
      market_type: null,
      current_asset: null,
      last_alert: null,
    });
  }
}

async function waitForChartElement(): Promise<HTMLElement | null> {
  // Try immediate lookup
  for (const selector of QUOTEX_CHART_SELECTORS) {
    const el = document.querySelector<HTMLElement>(selector);
    if (el) return el;
  }

  // Wait up to 10 seconds
  return new Promise((resolve) => {
    let attempts = 0;
    const interval = setInterval(() => {
      attempts++;
      for (const selector of QUOTEX_CHART_SELECTORS) {
        const el = document.querySelector<HTMLElement>(selector);
        if (el) {
          clearInterval(interval);
          resolve(el);
          return;
        }
      }
      if (attempts > 20) {
        clearInterval(interval);
        resolve(null);
      }
    }, 500);
  });
}

// ----- Event Handlers -----

function handleAlert(alertEvent: AlertEvent): void {
  if (!overlayRenderer) return;

  if (alertEvent.signal) {
    overlayRenderer.showAlert(alertEvent.signal);
  }
}

function handleConnectionStatus(connected: boolean): void {
  if (overlayRenderer) {
    overlayRenderer.updateConnectionStatus(connected);
  }
}

function handleSettingsUpdate(newSettings: Settings): void {
  if (chartObserver && newSettings.parse_interval_ms) {
    chartObserver.stop();
    chartObserver.observe(newSettings.parse_interval_ms);
  }
}

// ----- Cleanup -----

window.addEventListener("beforeunload", () => {
  if (chartObserver) chartObserver.stop();
  if (overlayRenderer) overlayRenderer.destroy();
  if (overlayContainer) overlayContainer.remove();
});

// Start
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
