/**
 * Quotex Alert Monitor - PriceCollector
 * ALERT-ONLY: Samples price every second, builds 1-minute OHLC candles.
 * Does NOT interact with trade UI.
 */

import type { CandleData } from "../shared/types";
import { CANDLE_DURATION_MS } from "../shared/constants";

export class PriceCollector {
  private candles: CandleData[] = [];
  private currentCandle: CandleData | null = null;
  private candleStartTime: number = 0;
  private _onCandleClose: (() => void) | null = null;

  /** Register a callback that fires when a candle closes (minute boundary crossed). */
  onCandleClose(cb: () => void): void {
    this._onCandleClose = cb;
  }

  /**
   * Called every ~1 second with the current price.
   * Builds OHLC candles from individual price ticks.
   */
  tick(price: number): void {
    const now = Date.now();
    // Align candle start to the minute boundary
    const minuteStart = Math.floor(now / CANDLE_DURATION_MS) * CANDLE_DURATION_MS;

    if (this.currentCandle === null || minuteStart !== this.candleStartTime) {
      // Close previous candle if it exists
      const hadPreviousCandle = this.currentCandle !== null;
      if (this.currentCandle !== null) {
        this.candles.push({ ...this.currentCandle });
      }

      // Start a new candle
      this.candleStartTime = minuteStart;
      this.currentCandle = {
        open: price,
        high: price,
        low: price,
        close: price,
        timestamp: minuteStart / 1000, // seconds as float
      };

      // Fire candle-close callback — the best moment to send data to backend
      // because all candles are now finalized (no incomplete data).
      if (hadPreviousCandle && this._onCandleClose) {
        this._onCandleClose();
      }
    } else {
      // Update current candle
      this.currentCandle.high = Math.max(this.currentCandle.high, price);
      this.currentCandle.low = Math.min(this.currentCandle.low, price);
      this.currentCandle.close = price;
    }
  }

  /**
   * Returns the last N closed candles.
   * Does not include the currently forming candle.
   */
  getCandles(count: number): CandleData[] {
    const startIdx = Math.max(0, this.candles.length - count);
    return this.candles.slice(startIdx);
  }

  /** Returns the number of closed candles available */
  getCandleCount(): number {
    return this.candles.length;
  }

  /** Returns the current (unclosed) candle or null */
  getCurrentCandle(): CandleData | null {
    return this.currentCandle;
  }

  /**
   * Detect market type from the asset name.
   * OTC if the name contains "(OTC)", otherwise LIVE.
   */
  static detectMarketType(assetName: string): "LIVE" | "OTC" {
    return assetName.includes("(OTC)") ? "OTC" : "LIVE";
  }
}
