// ============================================================
// Quotex Alert Intelligence - Chart Observer
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { MarketType, CandleData, IngestPayload } from "@shared/types";
import { QuoteParser } from "./quote-parser";

const DEFAULT_PARSE_INTERVAL = 5000;

const MARKET_TYPE_SELECTORS = [
  '[class*="otc"]',
  '[class*="OTC"]',
  '[data-market-type]',
  '.asset-name',
  '[class*="asset"]',
];

const ASSET_NAME_SELECTORS = [
  '.asset-name',
  '[class*="pair-name"]',
  '[class*="asset-title"]',
  '[class*="instrument"]',
  '[data-asset]',
];

export class ChartObserver {
  private chartElement: HTMLElement;
  private mutationObserver: MutationObserver | null = null;
  private parseTimer: ReturnType<typeof setInterval> | null = null;
  private quoteParser: QuoteParser;
  private isObserving = false;

  constructor(chartElement: HTMLElement) {
    this.chartElement = chartElement;
    this.quoteParser = new QuoteParser();
  }

  observe(intervalMs: number = DEFAULT_PARSE_INTERVAL): void {
    if (this.isObserving) return;
    this.isObserving = true;

    // MutationObserver for DOM changes on the chart
    this.mutationObserver = new MutationObserver((_mutations) => {
      // Chart updated - capture will happen on the next interval tick
    });

    this.mutationObserver.observe(this.chartElement, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    });

    // Periodic capture
    this.parseTimer = setInterval(() => {
      this.captureChartData();
    }, intervalMs);

    // Immediate first capture
    this.captureChartData();
  }

  stop(): void {
    this.isObserving = false;

    if (this.mutationObserver) {
      this.mutationObserver.disconnect();
      this.mutationObserver = null;
    }

    if (this.parseTimer) {
      clearInterval(this.parseTimer);
      this.parseTimer = null;
    }
  }

  detectChartElement(): HTMLElement | null {
    const selectors = [
      ".chart-area",
      "#chart-container",
      '[class*="chart-wrap"]',
      '[class*="trading-chart"]',
      "canvas",
    ];

    for (const selector of selectors) {
      const el = document.querySelector<HTMLElement>(selector);
      if (el) return el;
    }
    return null;
  }

  async captureChartData(): Promise<void> {
    if (!this.isObserving) return;

    try {
      // Try DOM extraction first
      let candles: CandleData[] = this.quoteParser.parseFromDOM(this.chartElement);

      // If DOM parse failed, try canvas extraction
      if (candles.length === 0) {
        const canvas = this.chartElement.querySelector("canvas") || this.chartElement as unknown as HTMLCanvasElement;
        if (canvas instanceof HTMLCanvasElement) {
          candles = this.quoteParser.parseFromCanvas(canvas);
        }
      }

      // If still no data, try screenshot-based capture
      if (candles.length === 0) {
        candles = await this.quoteParser.captureScreenshot();
      }

      if (candles.length === 0) return;

      const confidence = this.quoteParser.estimateParseConfidence(candles);
      if (confidence < 0.3) return; // Too low confidence, skip

      const marketType = this.getMarketType();
      const assetName = this.getAssetName();

      const payload: IngestPayload = {
        market_type: marketType || "otc",
        asset_name: assetName || "UNKNOWN",
        expiry_profile: "short",
        candles,
      };

      await this.sendToBackend(payload);
    } catch (err) {
      console.warn("[QAI] Chart capture error:", err);
    }
  }

  getMarketType(): MarketType | null {
    for (const selector of MARKET_TYPE_SELECTORS) {
      const el = document.querySelector(selector);
      if (!el) continue;

      const text = (el.textContent || "").toLowerCase();
      const dataAttr = el.getAttribute("data-market-type");

      if (dataAttr) {
        return dataAttr === "otc" ? "otc" : "real";
      }
      if (text.includes("otc")) return "otc";
      if (text.includes("live") || text.includes("real")) return "real";
    }

    // Fallback: check URL
    const url = window.location.href.toLowerCase();
    if (url.includes("otc")) return "otc";

    return null;
  }

  getAssetName(): string | null {
    for (const selector of ASSET_NAME_SELECTORS) {
      const el = document.querySelector(selector);
      if (!el) continue;

      const text = (el.textContent || "").trim();
      const dataAttr = el.getAttribute("data-asset");

      if (dataAttr) return dataAttr;
      if (text.length > 0 && text.length < 30) return text;
    }

    // Fallback: look for common pair patterns in the page
    const body = document.body.innerText;
    const pairMatch = body.match(/\b([A-Z]{3}\/[A-Z]{3})\b/);
    if (pairMatch) return pairMatch[1];

    return null;
  }

  async sendToBackend(data: IngestPayload): Promise<void> {
    try {
      await chrome.runtime.sendMessage({
        type: "INGEST_DATA",
        payload: data,
      });
    } catch (err) {
      console.warn("[QAI] Failed to send data to background:", err);
    }
  }
}
