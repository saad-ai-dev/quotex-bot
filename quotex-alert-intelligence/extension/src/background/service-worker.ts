// ============================================================
// Quotex Alert Intelligence - Background Service Worker
// ALERT-ONLY system - NO trade execution
// ============================================================

import type {
  Settings,
  AlertEvent,
  MonitoringState,
  HealthResponse,
  Signal,
} from "@shared/types";

type MessageType =
  | "START_MONITORING"
  | "STOP_MONITORING"
  | "GET_STATUS"
  | "NEW_ALERT"
  | "SETTINGS_UPDATED"
  | "INGEST_DATA"
  | "CHECK_HEALTH";

interface ExtensionMessage {
  type: MessageType;
  payload?: unknown;
}

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

let ws: WebSocket | null = null;
let settings: Settings = { ...DEFAULT_SETTINGS };
let monitoringState: MonitoringState = {
  is_monitoring: false,
  is_connected: false,
  market_type: null,
  current_asset: null,
  last_alert: null,
};
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_BASE_DELAY_MS = 1000;

// ----- Initialization -----

chrome.runtime.onInstalled.addListener(async () => {
  const stored = await chrome.storage.local.get("settings");
  if (stored.settings) {
    settings = { ...DEFAULT_SETTINGS, ...stored.settings };
  } else {
    await chrome.storage.local.set({ settings: DEFAULT_SETTINGS });
  }
  await persistState();
});

chrome.runtime.onStartup.addListener(async () => {
  await loadState();
  if (settings.monitoring_enabled) {
    startMonitoring();
  }
});

// ----- Alarm-based periodic checks -----

chrome.alarms.create("health-check", { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "health-check" && monitoringState.is_monitoring) {
    await checkBackendHealth();
  }
});

// ----- Message Handling -----

chrome.runtime.onMessage.addListener(
  (
    message: ExtensionMessage,
    _sender: chrome.runtime.MessageSender,
    sendResponse: (response?: unknown) => void
  ) => {
    handleMessage(message)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: String(err) }));
    return true; // keep channel open for async
  }
);

async function handleMessage(message: ExtensionMessage): Promise<unknown> {
  switch (message.type) {
    case "START_MONITORING":
      return startMonitoring();

    case "STOP_MONITORING":
      return stopMonitoring();

    case "GET_STATUS":
      return { state: monitoringState, settings };

    case "NEW_ALERT":
      return handleNewAlert(message.payload as AlertEvent);

    case "SETTINGS_UPDATED":
      return updateSettings(message.payload as Partial<Settings>);

    case "INGEST_DATA":
      return forwardIngest(message.payload);

    case "CHECK_HEALTH":
      return checkBackendHealth();

    default:
      return { error: "Unknown message type" };
  }
}

// ----- Monitoring Lifecycle -----

async function startMonitoring(): Promise<{ success: boolean }> {
  settings.monitoring_enabled = true;
  monitoringState.is_monitoring = true;
  await persistState();

  if (settings.use_websocket) {
    connectWebSocket();
  }

  // Notify content scripts
  broadcastToTabs({ type: "MONITORING_STARTED" });
  return { success: true };
}

async function stopMonitoring(): Promise<{ success: boolean }> {
  settings.monitoring_enabled = false;
  monitoringState.is_monitoring = false;
  disconnectWebSocket();
  await persistState();

  broadcastToTabs({ type: "MONITORING_STOPPED" });
  return { success: true };
}

// ----- WebSocket Management -----

function connectWebSocket(): void {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const wsUrl = settings.backend_url.replace(/^http/, "ws") + "/ws/alerts";

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectAttempts = 0;
      monitoringState.is_connected = true;
      persistState();
      broadcastToTabs({ type: "CONNECTION_STATUS", payload: { connected: true } });
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const alertEvent: AlertEvent = JSON.parse(event.data as string);
        handleNewAlert(alertEvent);
      } catch {
        console.warn("[QAI] Failed to parse WS message:", event.data);
      }
    };

    ws.onclose = () => {
      monitoringState.is_connected = false;
      persistState();
      broadcastToTabs({ type: "CONNECTION_STATUS", payload: { connected: false } });
      scheduleReconnect();
    };

    ws.onerror = () => {
      console.warn("[QAI] WebSocket error");
    };
  } catch (err) {
    console.error("[QAI] WebSocket connection failed:", err);
    scheduleReconnect();
  }
}

function disconnectWebSocket(): void {
  if (ws) {
    ws.close();
    ws = null;
  }
  monitoringState.is_connected = false;
}

function scheduleReconnect(): void {
  if (!monitoringState.is_monitoring || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    return;
  }
  reconnectAttempts++;
  const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, Math.min(reconnectAttempts, 6));
  setTimeout(() => {
    if (monitoringState.is_monitoring) {
      connectWebSocket();
    }
  }, delay);
}

// ----- Alert Handling (ALERT-ONLY - NO trade execution) -----

async function handleNewAlert(alertEvent: AlertEvent): Promise<{ delivered: boolean }> {
  monitoringState.last_alert = alertEvent;
  await persistState();

  // Store alert in recent alerts list
  const stored = await chrome.storage.local.get("recentAlerts");
  const recentAlerts: AlertEvent[] = stored.recentAlerts || [];
  recentAlerts.unshift(alertEvent);
  if (recentAlerts.length > 50) recentAlerts.length = 50;
  await chrome.storage.local.set({ recentAlerts });

  // Forward to content scripts for overlay display
  broadcastToTabs({ type: "NEW_ALERT", payload: alertEvent });

  // Browser notification if enabled
  if (settings.browser_notifications_enabled && alertEvent.signal) {
    showBrowserNotification(alertEvent.signal);
  }

  return { delivered: true };
}

function showBrowserNotification(signal: Signal): void {
  const direction = signal.prediction_direction;
  const confidence = Math.round(signal.confidence);
  const arrow = direction === "CALL" ? "\u2191" : "\u2193";

  chrome.notifications.create(`alert-${signal.signal_id}`, {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: `${arrow} ${direction} Alert - ${confidence}% Confidence`,
    message: `${signal.asset_name} | ${signal.market_type.toUpperCase()} | ${signal.expiry_profile}\nReasons: ${signal.reasons.slice(0, 2).join(", ")}`,
    priority: 2,
  });
}

// ----- Settings -----

async function updateSettings(partial: Partial<Settings>): Promise<{ success: boolean }> {
  settings = { ...settings, ...partial };
  await chrome.storage.local.set({ settings });

  // Reconnect WS if backend URL changed
  if (partial.backend_url && monitoringState.is_monitoring && settings.use_websocket) {
    disconnectWebSocket();
    connectWebSocket();
  }

  broadcastToTabs({ type: "SETTINGS_UPDATED", payload: settings });
  return { success: true };
}

// ----- Backend Communication -----

async function checkBackendHealth(): Promise<HealthResponse | { error: string }> {
  try {
    const resp = await fetch(`${settings.backend_url}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data: HealthResponse = await resp.json();
    monitoringState.is_connected = true;
    await persistState();
    return data;
  } catch (err) {
    monitoringState.is_connected = false;
    await persistState();
    return { error: String(err) };
  }
}

async function forwardIngest(payload: unknown): Promise<unknown> {
  try {
    const resp = await fetch(`${settings.backend_url}/signals/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return await resp.json();
  } catch (err) {
    return { error: String(err) };
  }
}

// ----- Utilities -----

async function persistState(): Promise<void> {
  await chrome.storage.local.set({
    settings,
    monitoringState,
  });
}

async function loadState(): Promise<void> {
  const stored = await chrome.storage.local.get(["settings", "monitoringState"]);
  if (stored.settings) {
    settings = { ...DEFAULT_SETTINGS, ...stored.settings };
  }
  if (stored.monitoringState) {
    monitoringState = { ...monitoringState, ...stored.monitoringState };
    // Reset connection on startup - will re-establish
    monitoringState.is_connected = false;
  }
}

function broadcastToTabs(message: { type: string; payload?: unknown }): void {
  chrome.tabs.query({ url: ["*://quotex.io/*", "*://*.quotex.io/*", "*://quotex.com/*", "*://*.quotex.com/*"] }, (tabs) => {
    for (const tab of tabs) {
      if (tab.id) {
        chrome.tabs.sendMessage(tab.id, message).catch(() => {
          // Tab may not have content script loaded
        });
      }
    }
  });
}
