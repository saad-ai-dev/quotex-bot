/**
 * Quotex Alert Monitor - Content Script
 * ALERT-ONLY: Captures price from Quotex via WS interception + DOM scan.
 * Sends candles to backend every 5s. Does NOT execute trades.
 */

import type { IngestPayload, ExtensionMessage, Signal } from "../shared/types";
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

// ---- Page Detection ----
function isQuotexPage(): boolean {
  const url = window.location.href;
  return url.includes("quotex.io") || url.includes("qxbroker.com") || url.includes("market-qx.trade");
}

// ---- WS Interceptor ----
// Try TWO methods to inject into page MAIN WORLD:
// 1. External script src (works if CSP blocks inline but allows extension URLs)
// 2. Inline script.textContent (works if CSP allows inline or unsafe-eval)
function injectWsInterceptor(): void {
  // Method 1: External file (more reliable, worked in earlier builds)
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
    console.log("[AlertMonitor] WS interceptor injected (inline)");
  } catch (e) {
    console.error("[AlertMonitor] Both injection methods failed:", e);
  }
}

// ---- Process intercepted WS data in content script ----
let wsLogCount = 0;

function listenForWsData(): void {
  window.addEventListener("message", (event) => {
    // Don't check event.source - cross-world postMessage may have different refs
    if (!event.data || event.data.s !== "QAM") return;

    const raw: string = event.data.d;
    if (!raw || raw.length < 3) return;

    wsLogCount++;
    if (wsLogCount <= 100) {
      console.log(`[AlertMonitor WS] #${wsLogCount} (${raw.length}):`, raw.substring(0, 400));
    }

    // Parse Socket.IO messages
    processWsMessage(raw);
  });
}

// Track the pending binary event name from Socket.IO "451-" headers
let pendingBinaryEvent: string | null = null;

function processWsMessage(raw: string): void {
  if (raw === "2" || raw === "3") return; // ping/pong

  // Socket.IO event: "42[event_name, data]"
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

  // Socket.IO binary event header: "451-[event_name, {_placeholder}]"
  const binHeaderMatch = raw.match(/^45\d*-\["([^"]+)"/);
  if (binHeaderMatch) {
    pendingBinaryEvent = binHeaderMatch[1];
    return;
  }

  // Binary data (starts with ␄ control char or raw data after binary header)
  const eventName = pendingBinaryEvent;
  pendingBinaryEvent = null;

  // Parse based on event type
  if (eventName === "quotes/stream") {
    // Format: ␄[["AUDUSD_otc", 1775325425.923, 0.69627, 1]]
    parseQuotesStream(raw);
  } else if (eventName === "history/list/v2") {
    // Format: ␄{"asset":"X","period":60,"history":[[ts,price,flag],...]}
    parseHistoryData(raw);
  } else if (eventName === "s_chart_notification/get") {
    // Format: ␄[{"id":"...","price":0.69675,"asset":"AUDUSD_otc"}]
    parseChartNotification(raw);
  } else if (eventName === "instruments/list") {
    // Skip - too much data, not needed for price tracking
  } else {
    // For unknown events, try generic parsing
    tryGenericParse(raw, eventName);
  }
}

/** Parse quotes/stream: real-time price ticks
 *  Format: [["ASSET", timestamp, price, flag], ...]
 */
function parseQuotesStream(raw: string): void {
  // Strip leading control char
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (Array.isArray(data)) {
      for (const tick of data) {
        if (Array.isArray(tick) && tick.length >= 3) {
          const asset = tick[0];   // e.g. "AUDUSD_otc"
          const ts = tick[1];      // e.g. 1775325425.923
          const price = tick[2];   // e.g. 0.69627
          if (typeof price === "number" && price > 0 && price < 100000) {
            feedPrice(price);
          }
        }
      }
    }
  } catch {}
}

/** Parse history/list/v2: Build OHLC candles from historical tick data
 *  Format: {"asset":"X","period":60,"history":[[ts,price,flag],...]}
 *  This gives us 10-30+ minute candles for proper analysis
 */
function parseHistoryData(raw: string): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (!data || !data.history || !Array.isArray(data.history)) return;

    const history: [number, number, number][] = data.history;
    if (history.length === 0) return;

    // Build 1-minute OHLC candles from tick data
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

      // Also feed the latest price for real-time display
      lastPrice = price;
    }

    // Store built candles
    const builtCandles = Array.from(candleMap.values())
      .sort((a, b) => a.ts - b.ts);

    if (builtCandles.length > 0) {
      historicalCandles = builtCandles.map(c => ({
        open: c.open, high: c.high, low: c.low, close: c.close,
        timestamp: c.ts,
      }));
      console.log(`[AlertMonitor] Built ${historicalCandles.length} candles from ${history.length} history ticks for ${data.asset}`);
      // Feed last price for tick display
      feedPrice(builtCandles[builtCandles.length - 1].close);
    }
  } catch (e) {
    console.warn("[AlertMonitor] History parse error:", e);
  }
}

/** Parse chart notification: price alerts
 *  Format: [{"id":"...","price":0.69675,"asset":"AUDUSD_otc"}]
 */
function parseChartNotification(raw: string): void {
  const cleaned = raw.replace(/^[\x00-\x1f]+/, "");
  try {
    const data = JSON.parse(cleaned);
    if (Array.isArray(data)) {
      for (const item of data) {
        if (item && typeof item.price === "number" && item.price > 0) {
          feedPrice(item.price);
        }
      }
    }
  } catch {}
}

/** Generic parse for unknown events */
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

// ---- DOM Price Scan (fallback) ----
let domScanLogCount = 0;

function scanDomForPrice(): number | null {
  try {
    // Strategy 1: Walk ALL elements on the page looking for price text
    const all = document.querySelectorAll<HTMLElement>("*");
    for (const el of all) {
      // Skip our own overlay
      if (el.id === "quotex-alert-monitor-overlay" || el.closest("#quotex-alert-monitor-overlay")) continue;

      // Only check leaf-ish elements (0-2 children)
      if (el.children.length > 2) continue;

      const text = el.textContent?.trim();
      if (!text || text.length > 15 || text.length < 3) continue;

      // Match price pattern: digits.digits
      const match = text.match(/^(\d{1,6}\.\d{2,6})$/);
      if (match) {
        const p = parseFloat(match[1]);
        if (p > 0.0001 && p < 1_000_000) {
          // Log first few DOM price finds
          domScanLogCount++;
          if (domScanLogCount <= 5) {
            console.log(`[AlertMonitor DOM] Found price: ${p} in <${el.tagName}> class="${el.className}"`);
          }
          return p;
        }
      }
    }
  } catch {}
  return null;
}

// ---- Price Feed ----
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

// ---- Asset Name ----
function readAssetName(): string {
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

// ---- Backend Communication ----
async function sendCandles(): Promise<void> {
  if (!priceCollector) return;

  // Start with historical candles (from Quotex history/list/v2)
  let candles = [...historicalCandles];

  // Add real-time candles from PriceCollector
  const rtCandles = priceCollector.getCandles(CANDLES_TO_SEND);
  for (const c of rtCandles) {
    if (!candles.some(h => h.timestamp === c.timestamp)) {
      candles.push(c);
    }
  }

  // Add current forming candle
  const current = priceCollector.getCurrentCandle();
  if (current && !candles.some(h => h.timestamp === current.timestamp)) {
    candles.push({ ...current });
  }

  // Sort and take last 30
  candles.sort((a, b) => a.timestamp - b.timestamp);
  candles = candles.slice(-CANDLES_TO_SEND);

  // Fallback: synthetic candle from last known price
  if (candles.length === 0 && lastPrice !== null) {
    candles = [{
      open: lastPrice, high: lastPrice,
      low: lastPrice, close: lastPrice,
      timestamp: Date.now() / 1000,
    }];
  }

  if (candles.length === 0) {
    console.log("[AlertMonitor] No price data yet, skipping send");
    return;
  }

  const assetName = readAssetName();
  const marketType = PriceCollector.detectMarketType(assetName);

  const payload: IngestPayload = {
    candles,
    market_type: marketType,
    asset_name: assetName.replace(/\s*\(OTC\)\s*/, "").trim(),
    expiry_profile: DEFAULT_EXPIRY_PROFILE,
    parse_mode: DEFAULT_PARSE_MODE,
    chart_read_confidence: DEFAULT_CHART_READ_CONFIDENCE,
  };

  console.log(`[AlertMonitor] Sending ${candles.length} candles for ${assetName} | price: ${candles[candles.length - 1].close} | ticks: ${tickCount}`);

  try {
    const response = await fetch(`${BACKEND_URL}${INGEST_ENDPOINT}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      if (!backendConnected) {
        backendConnected = true;
        overlay?.setConnected(true);
      }
      const data = await response.json() as Record<string, any>;
      if (data.prediction_direction && data.prediction_direction !== "NO_TRADE") {
        handleSignal({
          id: data.signal_id || "",
          asset: data.asset_name || assetName,
          direction: data.prediction_direction,
          confidence: data.confidence || 0,
          timestamp: data.created_at || new Date().toISOString(),
        } as any);
      }
    } else {
      console.warn("[AlertMonitor] Backend error:", response.status);
      backendConnected = false;
      overlay?.setConnected(false);
    }

    chrome.runtime.sendMessage({
      type: "CONTENT_STATUS",
      payload: { active: backendConnected, asset: assetName, market: marketType, candleCount: priceCollector.getCandleCount() },
    } as ExtensionMessage).catch(() => {});
  } catch (err) {
    console.warn("[AlertMonitor] Send failed:", err);
    backendConnected = false;
    overlay?.setConnected(false);
  }
}

function handleSignal(signal: Signal): void {
  console.log(`[AlertMonitor] SIGNAL: ${signal.direction} ${signal.asset} ${signal.confidence}%`);
  overlay?.setLastDirection(signal.direction);
  chrome.runtime.sendMessage({ type: "NEW_SIGNAL", payload: signal } as ExtensionMessage).catch(() => {});
}

// ---- Monitoring ----
function startMonitoring(): void {
  if (monitoring) return;
  monitoring = true;
  console.log("[AlertMonitor] Starting monitoring");

  priceCollector = new PriceCollector();
  overlay?.setStatus("Active");

  // DOM scan every 1s as fallback
  domScanTimer = setInterval(() => {
    const price = scanDomForPrice();
    if (price !== null) feedPrice(price);
  }, 1000);

  // Send to backend
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

// ---- Messages ----
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
    default: sendResponse({ ok: true });
  }
  return true;
});

// ---- Init ----
// STEP 1: Inject WS hook immediately
if (isQuotexPage()) {
  injectWsInterceptor();
  listenForWsData();
}

// STEP 2: Full init when DOM ready
function fullInit(): void {
  if (!isQuotexPage()) return;
  console.log("[AlertMonitor] Quotex detected:", window.location.href);

  overlay = new OverlayRenderer();
  overlay.mount();
  overlay.setStatus("Connecting...");

  fetch(`${BACKEND_URL}/health`)
    .then(r => r.json())
    .then(d => {
      console.log("[AlertMonitor] Backend health:", d.status);
      backendConnected = true;
      overlay?.setConnected(true);
      overlay?.setStatus("Active");
      chrome.runtime.sendMessage({
        type: "CONTENT_STATUS",
        payload: { active: true, asset: readAssetName(), market: "LIVE", candleCount: 0 },
      } as ExtensionMessage).catch(() => {});
    })
    .catch(e => {
      console.error("[AlertMonitor] Backend unreachable:", e);
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
