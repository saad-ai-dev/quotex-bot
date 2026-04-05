/**
 * Quotex Alert Monitor - Content Script
 * Captures price from Quotex via WS interception + DOM scan.
 * Sends candles to backend every 5s.
 * Can execute trades by clicking Quotex Up/Down buttons when auto-trade is enabled.
 */

import type { IngestPayload, ExtensionMessage, Signal, SignalDirection, TradeSettings } from "../shared/types";
import {
  BACKEND_URL,
  INGEST_ENDPOINT,
  SEND_INTERVAL_MS,
  CANDLES_TO_SEND,
  DEFAULT_EXPIRY_PROFILE,
  DEFAULT_PARSE_MODE,
  DEFAULT_CHART_READ_CONFIDENCE,
} from "../shared/constants";
import { PriceCollector } from "./chart-observer";
import { OverlayRenderer } from "./overlay-renderer";

// ---- State ----
let priceCollector: PriceCollector | null = null;
let overlay: OverlayRenderer | null = null;
let sendTimer: ReturnType<typeof setInterval> | null = null;
let domScanTimer: ReturnType<typeof setInterval> | null = null;
let monitoring = false;
let backendConnected = false;
let lastPrice: number | null = null;
let tickCount = 0;
let historicalCandles: { open: number; high: number; low: number; close: number; timestamp: number }[] = [];
let wsAssetName: string | null = null; // Asset name from WebSocket data (most reliable)

// ---- Auto-Trade State ----
let tradeSettings: TradeSettings = {
  autoTradeEnabled: false,
  maxConsecutiveLosses: 3,
};
let consecutiveLosses = 0;
let tradingPaused = false;
let totalTrades = 0;
let tradeWins = 0;
let tradeLosses = 0;
let lastTradeTime = 0; // Prevent rapid double-clicks

// Load saved trade settings
chrome.storage.local.get(["tradeSettings", "tradeState"], (result) => {
  if (result.tradeSettings) tradeSettings = result.tradeSettings;
  if (result.tradeState) {
    consecutiveLosses = result.tradeState.consecutiveLosses || 0;
    tradingPaused = result.tradeState.tradingPaused || false;
    totalTrades = result.tradeState.totalTrades || 0;
    tradeWins = result.tradeState.wins || 0;
    tradeLosses = result.tradeState.losses || 0;
  }
});

// ---- Page Detection ----
function isQuotexPage(): boolean {
  const url = window.location.href;
  return url.includes("quotex.io") || url.includes("qxbroker.com") || url.includes("market-qx.trade");
}

// ============================================================================
// TRADE EXECUTION - Finds and clicks Quotex's Up/Down buttons
// ============================================================================

/** Find a button by its visible text content */
function findButtonByText(text: string): HTMLElement | null {
  const buttons = document.querySelectorAll<HTMLElement>("button, a, div[role='button']");
  for (const btn of buttons) {
    const btnText = btn.textContent?.trim().toLowerCase();
    if (btnText === text.toLowerCase()) {
      // Verify it's visible and clickable
      const style = window.getComputedStyle(btn);
      if (style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0") {
        return btn;
      }
    }
  }

  // Fallback: partial match
  for (const btn of buttons) {
    const btnText = btn.textContent?.trim().toLowerCase();
    if (btnText && btnText.includes(text.toLowerCase()) && btnText.length < 20) {
      const style = window.getComputedStyle(btn);
      if (style.display !== "none" && style.visibility !== "hidden") {
        return btn;
      }
    }
  }

  return null;
}

/** Find the Up or Down button on the Quotex trading panel */
function findTradeButton(direction: SignalDirection): HTMLElement | null {
  // Strategy 1: Find by exact text "Up" or "Down"
  const btn = findButtonByText(direction === "UP" ? "Up" : "Down");
  if (btn) return btn;

  // Strategy 2: Find by background color
  // Up button = green, Down button = red/coral
  const allButtons = document.querySelectorAll<HTMLElement>("button");
  for (const b of allButtons) {
    const style = window.getComputedStyle(b);
    const bg = style.backgroundColor;
    const text = b.textContent?.trim().toLowerCase() || "";

    if (direction === "UP") {
      // Green button: rgb(46, 204, 113) or similar green shades
      if ((bg.includes("46, 204") || bg.includes("39, 174") || bg.includes("76, 175") ||
           text === "up" || text === "call" || text === "buy") &&
          style.display !== "none") {
        return b;
      }
    } else {
      // Red button: rgb(231, 76, 60) or similar red shades
      if ((bg.includes("231, 76") || bg.includes("234, 57") || bg.includes("255, 82") ||
           text === "down" || text === "put" || text === "sell") &&
          style.display !== "none") {
        return b;
      }
    }
  }

  return null;
}

/** Execute a trade by clicking the appropriate button */
function executeTrade(direction: SignalDirection): boolean {
  // Cooldown: prevent rapid clicks (min 2 seconds between trades)
  const now = Date.now();
  if (now - lastTradeTime < 2000) {
    console.log("[AutoTrade] Cooldown active, skipping");
    return false;
  }

  // Check if trading is paused due to max losses
  if (tradingPaused) {
    console.log(`[AutoTrade] Trading PAUSED (${consecutiveLosses} consecutive losses). Alert only.`);
    return false;
  }

  // Check if auto-trade is enabled
  if (!tradeSettings.autoTradeEnabled) {
    console.log("[AutoTrade] Auto-trade disabled, alert only");
    return false;
  }

  const button = findTradeButton(direction);
  if (!button) {
    console.error(`[AutoTrade] Could not find ${direction} button on page!`);
    overlay?.setTradeStatus(`${direction} button not found!`);
    return false;
  }

  // Click the button
  console.log(`[AutoTrade] Clicking ${direction} button...`);
  button.click();
  lastTradeTime = now;
  totalTrades++;

  // Notify background
  chrome.runtime.sendMessage({
    type: "TRADE_EXECUTED",
    direction,
    timestamp: new Date().toISOString(),
  } as ExtensionMessage).catch(() => {});

  // Update overlay
  overlay?.setTradeStatus(`${direction} trade placed!`);
  setTimeout(() => overlay?.setTradeStatus(null), 3000);

  // Save state
  saveTradeState();

  console.log(`[AutoTrade] ${direction} trade executed! Total: ${totalTrades}`);
  return true;
}

/** Record a trade result (called when we detect a trade outcome from WS) */
function recordTradeResult(outcome: "WIN" | "LOSS"): void {
  if (outcome === "WIN") {
    tradeWins++;
    consecutiveLosses = 0;
    tradingPaused = false;
  } else {
    tradeLosses++;
    consecutiveLosses++;

    // Check max consecutive losses
    if (consecutiveLosses >= tradeSettings.maxConsecutiveLosses) {
      tradingPaused = true;
      console.log(`[AutoTrade] MAX LOSSES REACHED (${consecutiveLosses}/${tradeSettings.maxConsecutiveLosses}). Trading PAUSED.`);
      overlay?.setTradeStatus(`PAUSED: ${consecutiveLosses} consecutive losses`);
    }
  }

  saveTradeState();

  // Notify background
  chrome.runtime.sendMessage({
    type: "TRADE_RESULT",
    outcome,
  } as ExtensionMessage).catch(() => {});

  console.log(`[AutoTrade] Result: ${outcome} | Streak: ${consecutiveLosses} losses | W:${tradeWins} L:${tradeLosses}`);
}

function saveTradeState(): void {
  const state = {
    consecutiveLosses,
    tradingPaused,
    totalTrades,
    wins: tradeWins,
    losses: tradeLosses,
  };
  chrome.storage.local.set({ tradeState: state });
}

// ============================================================================
// WS INTERCEPTOR
// ============================================================================
function injectWsInterceptor(): void {
  try {
    const extScript = document.createElement("script");
    extScript.src = chrome.runtime.getURL("ws-interceptor.js");
    extScript.onload = () => {
      console.log("[AlertMonitor] WS interceptor loaded via src");
      extScript.remove();
    };
    extScript.onerror = () => {
      console.log("[AlertMonitor] External script failed, trying inline...");
      injectInline();
    };
    (document.head || document.documentElement).appendChild(extScript);
  } catch {
    injectInline();
  }
}

function injectInline(): void {
  try {
    const script = document.createElement("script");
    script.textContent = `(function(){
      if(window.__QAM__)return;window.__QAM__=true;
      var O=window.WebSocket;
      window.WebSocket=function(u,p){
        console.log("[QAM] WS open:",u);
        var w=p?new O(u,p):new O(u);
        w.addEventListener("message",function(e){try{
          var d=e.data;
          if(typeof d==="string"&&d.length>3)window.postMessage({s:"QAM",t:"str",d:d},"*");
          else if(d instanceof ArrayBuffer)try{window.postMessage({s:"QAM",t:"bin",d:new TextDecoder().decode(d)},"*")}catch(x){}
          else if(d instanceof Blob)d.text().then(function(t){window.postMessage({s:"QAM",t:"blob",d:t},"*")}).catch(function(){});
        }catch(x){}});
        return w;
      };
      window.WebSocket.prototype=O.prototype;
      window.WebSocket.CONNECTING=O.CONNECTING;
      window.WebSocket.OPEN=O.OPEN;
      window.WebSocket.CLOSING=O.CLOSING;
      window.WebSocket.CLOSED=O.CLOSED;
      console.log("[QAM] WS hook installed (inline)");
    })();`;
    (document.head || document.documentElement).appendChild(script);
    script.remove();
  } catch (e) {
    console.error("[AlertMonitor] Both injection methods failed:", e);
  }
}

// ============================================================================
// WS MESSAGE PROCESSING
// ============================================================================
let wsLogCount = 0;

function listenForWsData(): void {
  window.addEventListener("message", (event) => {
    if (!event.data || event.data.s !== "QAM") return;
    const raw: string = event.data.d;
    if (!raw || raw.length < 3) return;
    wsLogCount++;
    if (wsLogCount <= 100) {
      console.log(`[AlertMonitor WS] #${wsLogCount} (${raw.length}):`, raw.substring(0, 400));
    }
    processWsMessage(raw);
  });
}

let pendingBinaryEvent: string | null = null;

function processWsMessage(raw: string): void {
  if (raw === "2" || raw === "3") return;

  if (raw.startsWith("42")) {
    try {
      const parsed = JSON.parse(raw.substring(2));
      if (Array.isArray(parsed) && parsed.length >= 1) {
        if (wsLogCount <= 50) {
          console.log(`[AlertMonitor WS] Event: "${parsed[0]}"`);
        }
      }
    } catch {}
    return;
  }

  const binHeaderMatch = raw.match(/^45\d*-\["([^"]+)"/);
  if (binHeaderMatch) {
    pendingBinaryEvent = binHeaderMatch[1];
    return;
  }

  const eventName = pendingBinaryEvent;
  pendingBinaryEvent = null;

  if (eventName === "quotes/stream") {
    parseQuotesStream(raw);
  } else if (eventName === "history/list/v2") {
    parseHistoryData(raw);
  } else if (eventName === "s_chart_notification/get") {
    parseChartNotification(raw);
  } else if (eventName === "orders/closed/list" || eventName === "orders/opened/list") {
    parseOrderEvents(raw, eventName);
  } else if (eventName === "instruments/list") {
    // Skip
  } else {
    tryGenericParse(raw, eventName);
  }
}

function parseQuotesStream(raw: string): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (Array.isArray(data)) {
      for (const tick of data) {
        if (Array.isArray(tick) && tick.length >= 3) {
          const asset = tick[0]; // e.g. "AUDUSD_otc" or "GBPJPY"
          const price = tick[2];
          if (typeof price === "number" && price > 0 && price < 1000000) {
            // Update the WS-detected asset name (most reliable source)
            if (typeof asset === "string" && asset.length > 2) {
              wsAssetName = asset;
            }
            feedPrice(price);
          }
        }
      }
    }
  } catch {}
}

function parseHistoryData(raw: string): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (!data || !data.history || !Array.isArray(data.history)) return;

    // Capture asset name from history data (e.g. "AUDUSD_otc")
    if (data.asset && typeof data.asset === "string") {
      wsAssetName = data.asset;
    }

    const history: [number, number, number][] = data.history;
    if (history.length === 0) return;

    const candleMap = new Map<number, { open: number; high: number; low: number; close: number; ts: number }>();

    for (const [ts, price] of history) {
      if (typeof price !== "number" || price <= 0 || price > 100000) continue;
      const minuteKey = Math.floor(ts / 60) * 60;
      if (!candleMap.has(minuteKey)) {
        candleMap.set(minuteKey, { open: price, high: price, low: price, close: price, ts: minuteKey });
      } else {
        const c = candleMap.get(minuteKey)!;
        c.high = Math.max(c.high, price);
        c.low = Math.min(c.low, price);
        c.close = price;
      }
      lastPrice = price;
    }

    const builtCandles = Array.from(candleMap.values()).sort((a, b) => a.ts - b.ts);
    if (builtCandles.length > 0) {
      historicalCandles = builtCandles.map(c => ({
        open: c.open, high: c.high, low: c.low, close: c.close, timestamp: c.ts,
      }));
      console.log(`[AlertMonitor] Built ${historicalCandles.length} candles from ${history.length} history ticks`);
      feedPrice(builtCandles[builtCandles.length - 1].close);
    }
  } catch (e) {
    console.warn("[AlertMonitor] History parse error:", e);
  }
}

function parseChartNotification(raw: string): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (Array.isArray(data)) {
      for (const item of data) {
        if (item && typeof item.price === "number" && item.price > 0) feedPrice(item.price);
      }
    }
  } catch {}
}

/** Parse order events to detect trade outcomes (WIN/LOSS) */
function parseOrderEvents(raw: string, eventName: string): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (!Array.isArray(data)) return;

    for (const order of data) {
      if (!order || typeof order !== "object") continue;

      // Quotex order fields: profit, status, close_reason, etc.
      const profit = order.profit ?? order.pnl ?? order.win;
      const status = order.status ?? order.close_reason;

      if (typeof profit === "number" && status) {
        if (profit > 0) {
          recordTradeResult("WIN");
        } else if (profit <= 0 && status !== "opened") {
          recordTradeResult("LOSS");
        }
      }
    }
  } catch {}
}

function tryGenericParse(raw: string, eventName: string | null): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (data && typeof data === "object") {
      const priceFields = ["price", "value", "close", "bid", "ask", "rate"];
      for (const f of priceFields) {
        if (typeof data[f] === "number" && data[f] > 0 && data[f] < 100000) {
          feedPrice(data[f]);
          return;
        }
      }
    }
  } catch {}
}

// ============================================================================
// DOM PRICE SCAN (fallback)
// ============================================================================
let domScanLogCount = 0;

function scanDomForPrice(): number | null {
  try {
    const all = document.querySelectorAll<HTMLElement>("*");
    for (const el of all) {
      if (el.id === "quotex-alert-monitor-overlay" || el.closest("#quotex-alert-monitor-overlay")) continue;
      if (el.children.length > 2) continue;
      const text = el.textContent?.trim();
      if (!text || text.length > 15 || text.length < 3) continue;
      const match = text.match(/^(\d{1,6}\.\d{2,6})$/);
      if (match) {
        const p = parseFloat(match[1]);
        if (p > 0.0001 && p < 1_000_000) {
          domScanLogCount++;
          if (domScanLogCount <= 5) {
            console.log(`[AlertMonitor DOM] Found price: ${p} in <${el.tagName}>`);
          }
          return p;
        }
      }
    }
  } catch {}
  return null;
}

// ============================================================================
// PRICE FEED + ASSET NAME
// ============================================================================
function feedPrice(price: number): void {
  if (price <= 0 || price > 1_000_000 || !isFinite(price)) return;
  lastPrice = price;
  tickCount++;
  if (priceCollector && monitoring) priceCollector.tick(price);
  if (tickCount % 10 === 0) overlay?.setPrice(price);
  if (tickCount <= 5 || tickCount % 100 === 0) {
    console.log(`[AlertMonitor] Price #${tickCount}: ${price}`);
  }
}

function readAssetName(): string {
  // Priority 1: Use asset name from WebSocket data (most reliable)
  if (wsAssetName) {
    // Convert "AUDUSD_otc" -> "AUD/USD (OTC)", "GBPJPY" -> "GBP/JPY"
    let name = wsAssetName;
    const isOtc = name.endsWith("_otc");
    if (isOtc) name = name.replace("_otc", "");
    // Insert "/" between currency codes (e.g. AUDUSD -> AUD/USD)
    if (name.length >= 6 && !name.includes("/")) {
      name = name.slice(0, 3) + "/" + name.slice(3);
    }
    if (isOtc) name += " (OTC)";
    return name;
  }

  // Priority 2: DOM scan fallback
  try {
    const all = document.querySelectorAll<HTMLElement>("span, div, a, button");
    for (const el of all) {
      const text = el.textContent?.trim();
      if (!text || text.length > 40) continue;
      const match = text.match(/([A-Z]{2,6}\s*\/\s*[A-Z]{2,6}(\s*\(OTC\))?)/);
      if (match) return match[1].replace(/\s/g, "");
    }
  } catch {}
  return "Unknown";
}

// ============================================================================
// BACKEND COMMUNICATION
// ============================================================================
async function sendCandles(): Promise<void> {
  if (!priceCollector) return;

  let candles = [...historicalCandles];
  const rtCandles = priceCollector.getCandles(CANDLES_TO_SEND);
  for (const c of rtCandles) {
    if (!candles.some(h => h.timestamp === c.timestamp)) candles.push(c);
  }
  const current = priceCollector.getCurrentCandle();
  if (current && !candles.some(h => h.timestamp === current.timestamp)) {
    candles.push({ ...current });
  }
  candles.sort((a, b) => a.timestamp - b.timestamp);
  candles = candles.slice(-CANDLES_TO_SEND);

  if (candles.length === 0 && lastPrice !== null) {
    candles = [{ open: lastPrice, high: lastPrice, low: lastPrice, close: lastPrice, timestamp: Date.now() / 1000 }];
  }
  if (candles.length === 0) return;

  const assetName = readAssetName();
  const marketType = PriceCollector.detectMarketType(assetName);

  const payload: any = {
    candles,
    market_type: marketType,
    asset_name: assetName.replace(/\s*\(OTC\)\s*/, "").trim(),
    expiry_profile: DEFAULT_EXPIRY_PROFILE,
    parse_mode: DEFAULT_PARSE_MODE,
    chart_read_confidence: DEFAULT_CHART_READ_CONFIDENCE,
    current_price: lastPrice,  // Real-time tick price for accurate evaluation
  };

  try {
    const response = await fetch(`${BACKEND_URL}${INGEST_ENDPOINT}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      if (!backendConnected) { backendConnected = true; overlay?.setConnected(true); }
      const data = await response.json() as Record<string, any>;
      if (data.prediction_direction && data.prediction_direction !== "NO_TRADE") {
        const signal: Signal = {
          id: data.signal_id || "",
          asset: data.asset_name || assetName,
          direction: data.prediction_direction,
          confidence: data.confidence || 0,
          timestamp: data.created_at || new Date().toISOString(),
        };
        handleSignal(signal);
      }
    } else {
      backendConnected = false;
      overlay?.setConnected(false);
    }

    chrome.runtime.sendMessage({
      type: "CONTENT_STATUS",
      payload: { active: backendConnected, asset: assetName, market: marketType, candleCount: priceCollector.getCandleCount() },
    } as ExtensionMessage).catch(() => {});
  } catch {
    backendConnected = false;
    overlay?.setConnected(false);
  }
}

function handleSignal(signal: Signal): void {
  console.log(`[AlertMonitor] SIGNAL: ${signal.direction} ${signal.asset} ${signal.confidence}%`);
  overlay?.setLastDirection(signal.direction);
  chrome.runtime.sendMessage({ type: "NEW_SIGNAL", payload: signal } as ExtensionMessage).catch(() => {});

  // AUTO-TRADE: Execute trade if enabled
  if (tradeSettings.autoTradeEnabled && !tradingPaused) {
    console.log(`[AutoTrade] Signal received, executing ${signal.direction} trade...`);
    executeTrade(signal.direction);
  } else if (tradingPaused) {
    console.log(`[AutoTrade] Signal received but trading PAUSED (${consecutiveLosses} consecutive losses)`);
    overlay?.setTradeStatus(`PAUSED: ${consecutiveLosses} losses`);
  }
}

// ============================================================================
// MONITORING
// ============================================================================
function startMonitoring(): void {
  if (monitoring) return;
  monitoring = true;
  console.log("[AlertMonitor] Starting monitoring");

  priceCollector = new PriceCollector();
  overlay?.setStatus("Active");

  domScanTimer = setInterval(() => {
    const price = scanDomForPrice();
    if (price !== null) feedPrice(price);
  }, 1000);

  sendTimer = setInterval(() => sendCandles(), SEND_INTERVAL_MS);
  setTimeout(() => { if (monitoring) sendCandles(); }, 3000);
}

function stopMonitoring(): void {
  if (!monitoring) return;
  monitoring = false;
  if (sendTimer) { clearInterval(sendTimer); sendTimer = null; }
  if (domScanTimer) { clearInterval(domScanTimer); domScanTimer = null; }
  priceCollector = null;
  overlay?.setStatus("Stopped");
  overlay?.setConnected(false);
}

// ============================================================================
// MESSAGE HANDLING
// ============================================================================
chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
  switch (message.type) {
    case "TOGGLE_MONITORING":
      if (message.enabled) startMonitoring(); else stopMonitoring();
      sendResponse({ ok: true }); break;

    case "STATE_UPDATE":
      if (message.payload.monitoring && !monitoring) startMonitoring();
      else if (!message.payload.monitoring && monitoring) stopMonitoring();
      sendResponse({ ok: true }); break;

    case "NEW_SIGNAL":
      overlay?.setLastDirection(message.payload.direction);
      sendResponse({ ok: true }); break;

    case "SET_TRADE_SETTINGS":
      tradeSettings = message.payload;
      chrome.storage.local.set({ tradeSettings });
      // If re-enabling, check if we should unpause
      if (tradeSettings.autoTradeEnabled && consecutiveLosses < tradeSettings.maxConsecutiveLosses) {
        tradingPaused = false;
      }
      console.log("[AutoTrade] Settings updated:", tradeSettings);
      sendResponse({ ok: true }); break;

    case "GET_TRADE_STATE":
      sendResponse({
        consecutiveLosses,
        totalTrades,
        wins: tradeWins,
        losses: tradeLosses,
        tradingPaused,
        autoTradeEnabled: tradeSettings.autoTradeEnabled,
        maxConsecutiveLosses: tradeSettings.maxConsecutiveLosses,
      }); break;

    case "RESET_TRADE_STATE":
      consecutiveLosses = 0;
      tradingPaused = false;
      totalTrades = 0;
      tradeWins = 0;
      tradeLosses = 0;
      saveTradeState();
      console.log("[AutoTrade] State reset");
      sendResponse({ ok: true }); break;

    case "EXECUTE_TRADE":
      const success = executeTrade(message.direction);
      sendResponse({ ok: success }); break;

    default:
      sendResponse({ ok: true });
  }
  return true;
});

// ============================================================================
// INIT
// ============================================================================
if (isQuotexPage()) {
  injectWsInterceptor();
  listenForWsData();
}

function fullInit(): void {
  if (!isQuotexPage()) return;
  console.log("[AlertMonitor] Quotex detected:", window.location.href);

  overlay = new OverlayRenderer();
  overlay.mount();
  overlay.setStatus("Connecting...");

  fetch(`${BACKEND_URL}/health`)
    .then(r => r.json())
    .then(d => {
      backendConnected = true;
      overlay?.setConnected(true);
      overlay?.setStatus("Active");
      chrome.runtime.sendMessage({
        type: "CONTENT_STATUS",
        payload: { active: true, asset: readAssetName(), market: "LIVE", candleCount: 0 },
      } as ExtensionMessage).catch(() => {});
    })
    .catch(e => {
      overlay?.setStatus("Backend offline!");
    });

  startMonitoring();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", fullInit);
} else {
  fullInit();
}

window.addEventListener("unload", () => { stopMonitoring(); overlay?.unmount(); });
