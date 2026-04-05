/**
 * Quotex Alert Monitor - Background Service Worker
 * ALERT-ONLY: Relays messages between content script and popup.
 * Does NOT execute any trades.
 */

import type { ExtensionMessage, Signal } from "../shared/types";

// ---- State ----

let monitoring = false;
let connected = false;
let lastSignal: Signal | null = null;

// Restore persisted state (service worker can restart at any time in MV3)
chrome.storage.local.get(["monitoring", "lastSignal"], (result) => {
  if (result.monitoring !== undefined) monitoring = result.monitoring;
  if (result.lastSignal !== undefined) lastSignal = result.lastSignal;
});

// ---- Message Handling ----

function handleMessage(
  message: ExtensionMessage,
  sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  if (!sender.id) {
    sendResponse({ ok: false });
    return true;
  }

  switch (message.type) {
    case "GET_STATE":
      sendResponse({ monitoring, connected, lastSignal });
      break;

    case "TOGGLE_MONITORING":
      monitoring = message.enabled;
      // Persist so it survives service worker restart
      chrome.storage.local.set({ monitoring });
      forwardToContentScripts(message);
      sendResponse({ ok: true, monitoring });
      break;

    case "NEW_SIGNAL":
      lastSignal = message.payload;
      chrome.storage.local.set({ lastSignal });
      showSignalNotification(message.payload);
      sendResponse({ ok: true });
      break;

    case "CONTENT_STATUS":
      connected = message.payload?.active ?? false;
      sendResponse({ ok: true });
      break;

    default:
      sendResponse({ ok: true });
  }

  return true;
}

/** Forward a message to all Quotex content scripts */
function forwardToContentScripts(message: ExtensionMessage): void {
  chrome.tabs.query(
    { url: ["*://quotex.io/*", "*://*.quotex.io/*", "*://qxbroker.com/*", "*://*.qxbroker.com/*"] },
    (tabs) => {
      for (const tab of tabs) {
        if (tab.id) {
          chrome.tabs.sendMessage(tab.id, message).catch(() => {});
        }
      }
    }
  );
}

/** Show a Chrome notification for a signal */
function showSignalNotification(signal: Signal): void {
  if (!signal || signal.direction === "NO_TRADE") return;
  const arrow = signal.direction === "UP" ? "\u2B06" : "\u2B07";
  chrome.notifications.create(`signal_${Date.now()}`, {
    type: "basic",
    iconUrl: "icons/icon-128.png",
    title: `${arrow} ${signal.direction} Alert - ${signal.asset}`,
    message: `Confidence: ${signal.confidence}% | ${signal.market} | ALERT ONLY`,
    priority: 2,
  });
}

// ---- Event Listeners ----

chrome.runtime.onMessage.addListener(handleMessage);

chrome.runtime.onInstalled.addListener((details) => {
  console.log("[AlertMonitor BG] Installed:", details.reason, "(ALERT-ONLY)");
});

// Keep service worker alive with periodic alarm
chrome.alarms.create("keepAlive", { periodInMinutes: 0.4 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "keepAlive") {
    // Just keeps the service worker from going idle
  }
});

console.log("[AlertMonitor BG] Service worker started (ALERT-ONLY)");
