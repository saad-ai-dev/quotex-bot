// ============================================================
// Quotex Alert Intelligence - Quote Parser
// ALERT-ONLY system - NO trade execution
// ============================================================

import type { CandleData } from "@shared/types";

type ParseMode = "dom" | "canvas" | "screenshot" | "none";

export class QuoteParser {
  private lastParseMode: ParseMode = "none";

  /**
   * Try to extract candle/price data from DOM nodes within the chart element.
   */
  parseFromDOM(chartElement: HTMLElement): CandleData[] {
    const candles: CandleData[] = [];

    // Strategy 1: Look for data attributes on chart elements
    const dataElements = chartElement.querySelectorAll(
      '[data-open], [data-close], [data-high], [data-low], [data-price], [data-value]'
    );

    if (dataElements.length > 0) {
      for (const el of dataElements) {
        const open = parseFloat(el.getAttribute("data-open") || "0");
        const close = parseFloat(el.getAttribute("data-close") || "0");
        const high = parseFloat(el.getAttribute("data-high") || "0");
        const low = parseFloat(el.getAttribute("data-low") || "0");
        const timestamp = parseInt(el.getAttribute("data-timestamp") || "0", 10);

        if (open > 0 && close > 0) {
          candles.push({ open, high: high || Math.max(open, close), low: low || Math.min(open, close), close, timestamp: timestamp || Date.now() });
        }
      }

      if (candles.length > 0) {
        this.lastParseMode = "dom";
        return candles;
      }
    }

    // Strategy 2: Look for price text nodes (tooltip, price labels, axis)
    const priceLabels = chartElement.querySelectorAll(
      '[class*="price"], [class*="value"], [class*="label"], [class*="tooltip"], [class*="ohlc"]'
    );

    const prices: number[] = [];
    for (const label of priceLabels) {
      const text = (label.textContent || "").trim();
      const match = text.match(/[\d]+\.[\d]+/);
      if (match) {
        prices.push(parseFloat(match[0]));
      }
    }

    // Strategy 3: Look for SVG elements (some charting libs use SVG)
    const svgRects = chartElement.querySelectorAll("svg rect, svg line, svg path");
    if (svgRects.length > 0 && prices.length >= 4) {
      // Attempt to reconstruct candles from price labels
      for (let i = 0; i + 3 < prices.length; i += 4) {
        candles.push({
          open: prices[i],
          high: prices[i + 1],
          low: prices[i + 2],
          close: prices[i + 3],
          timestamp: Date.now() - (prices.length - i) * 1000,
        });
      }
      if (candles.length > 0) {
        this.lastParseMode = "dom";
        return candles;
      }
    }

    // Strategy 4: Look for table-like structures
    const rows = chartElement.querySelectorAll("tr, [class*='row']");
    for (const row of rows) {
      const cells = row.querySelectorAll("td, [class*='cell'], span");
      const nums: number[] = [];
      for (const cell of cells) {
        const val = parseFloat((cell.textContent || "").trim());
        if (!isNaN(val) && val > 0) nums.push(val);
      }
      if (nums.length >= 4) {
        candles.push({
          open: nums[0],
          high: nums[1],
          low: nums[2],
          close: nums[3],
          timestamp: Date.now(),
        });
      }
    }

    if (candles.length > 0) {
      this.lastParseMode = "dom";
    }

    return candles;
  }

  /**
   * Extract pixel data from a canvas element and try to infer price data.
   * This is a heuristic approach - canvas data is opaque.
   */
  parseFromCanvas(canvas: HTMLCanvasElement): CandleData[] {
    const candles: CandleData[] = [];

    try {
      const ctx = canvas.getContext("2d");
      if (!ctx) return candles;

      const width = canvas.width;
      const height = canvas.height;

      if (width === 0 || height === 0) return candles;

      const imageData = ctx.getImageData(0, 0, width, height);
      const data = imageData.data;

      // Scan for vertical green/red bars (candlestick bodies)
      // Green candles: close > open, Red candles: close < open
      const columns = new Map<number, { greenPixels: number; redPixels: number; topY: number; bottomY: number }>();

      const step = 4; // sample every 4th column for performance
      for (let x = 0; x < width; x += step) {
        let greenCount = 0;
        let redCount = 0;
        let topY = height;
        let bottomY = 0;

        for (let y = 0; y < height; y++) {
          const idx = (y * width + x) * 4;
          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];
          const a = data[idx + 3];

          if (a < 128) continue;

          // Detect green candle body (various shades of green)
          if (g > 100 && g > r * 1.5 && g > b * 1.5) {
            greenCount++;
            topY = Math.min(topY, y);
            bottomY = Math.max(bottomY, y);
          }
          // Detect red candle body
          if (r > 100 && r > g * 1.5 && r > b * 1.5) {
            redCount++;
            topY = Math.min(topY, y);
            bottomY = Math.max(bottomY, y);
          }
        }

        if (greenCount > 5 || redCount > 5) {
          columns.set(x, { greenPixels: greenCount, redPixels: redCount, topY, bottomY });
        }
      }

      // Group adjacent columns into candle regions
      const sortedCols = [...columns.entries()].sort((a, b) => a[0] - b[0]);
      let currentGroup: typeof sortedCols = [];
      const groups: (typeof sortedCols)[] = [];

      for (const entry of sortedCols) {
        if (currentGroup.length === 0 || entry[0] - currentGroup[currentGroup.length - 1][0] <= step * 2) {
          currentGroup.push(entry);
        } else {
          if (currentGroup.length > 0) groups.push(currentGroup);
          currentGroup = [entry];
        }
      }
      if (currentGroup.length > 0) groups.push(currentGroup);

      // Convert each group to a pseudo-candle
      for (let i = 0; i < groups.length; i++) {
        const group = groups[i];
        let totalGreen = 0;
        let totalRed = 0;
        let minY = height;
        let maxY = 0;

        for (const [, col] of group) {
          totalGreen += col.greenPixels;
          totalRed += col.redPixels;
          minY = Math.min(minY, col.topY);
          maxY = Math.max(maxY, col.bottomY);
        }

        const isBullish = totalGreen > totalRed;
        // Normalize Y to pseudo-price (inverted since canvas Y grows downward)
        const high = 1 - minY / height;
        const low = 1 - maxY / height;
        const bodyTop = 1 - (minY + (maxY - minY) * 0.2) / height;
        const bodyBottom = 1 - (maxY - (maxY - minY) * 0.2) / height;

        candles.push({
          open: isBullish ? bodyBottom : bodyTop,
          close: isBullish ? bodyTop : bodyBottom,
          high,
          low,
          timestamp: Date.now() - (groups.length - i) * 60000,
        });
      }

      if (candles.length > 0) {
        this.lastParseMode = "canvas";
      }
    } catch (err) {
      console.warn("[QAI] Canvas parse error:", err);
    }

    return candles;
  }

  /**
   * Capture a screenshot of the visible tab via background script.
   * Returns empty candles - the backend will process the image.
   */
  async captureScreenshot(): Promise<CandleData[]> {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "CAPTURE_SCREENSHOT",
      });

      if (response && response.dataUrl) {
        this.lastParseMode = "screenshot";
        // Screenshot data will be processed by backend
        // Return a placeholder candle to signal that data was captured
        return [{
          open: 0,
          close: 0,
          high: 0,
          low: 0,
          timestamp: Date.now(),
        }];
      }
    } catch {
      // Screenshot capture not available
    }

    this.lastParseMode = "none";
    return [];
  }

  /**
   * Build a normalized candle sequence from raw parsed data.
   */
  buildCandleSequence(rawData: CandleData[]): CandleData[] {
    if (rawData.length === 0) return [];

    // Sort by timestamp
    const sorted = [...rawData].sort((a, b) => a.timestamp - b.timestamp);

    // Remove duplicates (same timestamp)
    const unique: CandleData[] = [];
    let prevTs = -1;
    for (const candle of sorted) {
      if (candle.timestamp !== prevTs) {
        unique.push(candle);
        prevTs = candle.timestamp;
      }
    }

    // Validate: high >= max(open, close), low <= min(open, close)
    return unique.map((c) => ({
      open: c.open,
      close: c.close,
      high: Math.max(c.high, c.open, c.close),
      low: Math.min(c.low, c.open, c.close),
      timestamp: c.timestamp,
    }));
  }

  /**
   * Estimate confidence that the parsed candles are valid data.
   * Returns 0.0 - 1.0
   */
  estimateParseConfidence(candles: CandleData[]): number {
    if (candles.length === 0) return 0;

    let score = 0;
    const total = candles.length;

    // Check: non-zero values
    let nonZero = 0;
    for (const c of candles) {
      if (c.open > 0 && c.close > 0 && c.high > 0 && c.low > 0) nonZero++;
    }
    score += (nonZero / total) * 0.3;

    // Check: OHLC consistency (high >= open/close, low <= open/close)
    let consistent = 0;
    for (const c of candles) {
      if (c.high >= c.open && c.high >= c.close && c.low <= c.open && c.low <= c.close) {
        consistent++;
      }
    }
    score += (consistent / total) * 0.3;

    // Check: reasonable price variance (not all same value)
    const closes = candles.map((c) => c.close).filter((v) => v > 0);
    if (closes.length > 1) {
      const mean = closes.reduce((a, b) => a + b, 0) / closes.length;
      const variance = closes.reduce((a, b) => a + (b - mean) ** 2, 0) / closes.length;
      const cv = mean > 0 ? Math.sqrt(variance) / mean : 0;
      // Reasonable CV for financial data: 0.0001 - 0.1
      if (cv > 0.00001 && cv < 0.5) score += 0.2;
    }

    // Check: enough candles
    if (total >= 5) score += 0.1;
    if (total >= 10) score += 0.1;

    return Math.min(score, 1.0);
  }

  /**
   * Get the current parse mode used.
   */
  getParseMode(): ParseMode {
    return this.lastParseMode;
  }
}
