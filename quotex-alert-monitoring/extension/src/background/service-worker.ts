/**
 * Quotex Alert Monitor - Background Service Worker
 * Relays messages between content script and popup.
 * Tracks trade state persistence.
 */

import type { ExtensionMessage, Signal } from "../shared/types";

// ---- State ----
let monitoring = false;
let connected = false;
let lastSignal: Signal | null = null;

// Restore persisted state
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
  if (!sender.id) { sendResponse({ ok: false }); return true; }

  switch (message.type) {
    case "GET_STATE":
      sendResponse({ monitoring, connected, lastSignal });
      break;

    case "TOGGLE_MONITORING":
      monitoring = message.enabled;
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

    case "TRADE_EXECUTED":
      // Show notification for trade execution
      const dir = message.direction;
      chrome.notifications.create(`trade_${Date.now()}`, {
        type: "basic",
        iconUrl: "icons/icon-128.png",
        title: `Trade Placed: ${dir}`,
        message: `Auto-trade executed a ${dir} trade`,
        priority: 2,
      });
      sendResponse({ ok: true });
      break;

    case "TRADE_RESULT":
      sendResponse({ ok: true });
      break;

    default:
      sendResponse({ ok: true });
  }
  return true;
}

function forwardToContentScripts(message: ExtensionMessage): void {
  chrome.tabs.query(
    { url: ["*://quotex.io/*", "*://*.quotex.io/*", "*://qxbroker.com/*", "*://*.qxbroker.com/*", "*://market-qx.trade/*", "*://*.market-qx.trade/*"] },
    (tabs) => {
      for (const tab of tabs) {
        if (tab.id) chrome.tabs.sendMessage(tab.id, message).catch(() => {});
      }
    }
  );
}

function showSignalNotification(signal: Signal): void {
  if (!signal || signal.direction === "NO_TRADE") return;
  const arrow = signal.direction === "UP" ? "\u2B06" : "\u2B07";
  chrome.notifications.create(`signal_${Date.now()}`, {
    type: "basic",
    iconUrl: "icons/icon-128.png",
    title: `${arrow} ${signal.direction} Alert - ${signal.asset}`,
    message: `Confidence: ${signal.confidence}% | ALERT`,
    priority: 2,
  });
}

// ---- Event Listeners ----
chrome.runtime.onMessage.addListener(handleMessage);

chrome.runtime.onInstalled.addListener((details) => {
  console.log("[AlertMonitor BG] Installed:", details.reason);
});

// Keep alive
chrome.alarms.create("keepAlive", { periodInMinutes: 0.4 });
chrome.alarms.onAlarm.addListener(() => {});

console.log("[AlertMonitor BG] Service worker started");
