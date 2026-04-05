# Limitations

> **ALERT-ONLY** -- This document covers limitations of the monitoring and alerting system. Trade execution is intentionally excluded from the project scope.

## Fundamental Limitations

### No Trade Execution
This system generates alerts only. It does not:
- Place orders on Quotex or any other platform
- Interact with trade buttons, amount inputs, or expiry selectors
- Manage positions or account balances
- Provide risk management or position sizing

### No Guaranteed Accuracy
Signal confidence scores are heuristic estimates based on technical indicators. They are not predictions of market outcomes. High-confidence signals can and will be wrong.

## Technical Limitations

### Chart Detection (DOM Scraping)

**Fragile selectors.** The extension detects the Quotex chart using CSS selectors that may break if Quotex updates their page structure. When selectors fail, no chart data is captured and no alerts are generated.

**Limited data extraction.** Three strategies are attempted:
1. Global window objects (may not be exposed)
2. Data attributes on chart elements (may not exist)
3. DOM text content (only gives current price, no OHLC)

In many cases, only strategy 3 succeeds, providing a single current price rather than full candle data. This significantly limits indicator calculation accuracy.

**No canvas reading.** If the chart renders on a `<canvas>` element without exposing data, pixel-level analysis is not performed. The observer cannot read price data from rendered pixels.

### Data Quality

**Missing OHLC data.** When only the current price is available (DOM text strategy), open/high/low values are set equal to close. This makes candle-based indicators (patterns, Bollinger Bands) unreliable.

**No historical data.** The system analyzes data captured during the session only. It does not fetch historical candles from an external data provider. Short sessions produce insufficient data for reliable indicator calculation.

**Volume data.** Volume is frequently unavailable from DOM scraping. When volume is zero, the volume scoring category produces minimal points, reducing overall confidence.

### Timing and Latency

**Capture interval.** Default 5-second capture interval means up to 5 seconds of price movement may be missed between captures.

**Processing pipeline.** Data flows: DOM capture -> service worker -> REST POST -> backend analysis -> WebSocket broadcast -> notification. Total latency is typically 1-5 seconds.

**Expiry precision.** Signal expiry times are estimated and may not align precisely with Quotex's actual option expiry windows.

### Browser and Extension

**Single instance.** The extension runs in one Chrome browser. Multiple Chrome profiles or browsers are not coordinated.

**Service worker lifecycle.** Manifest V3 service workers may be terminated by Chrome after 30 seconds of inactivity. The extension uses alarms to keep the worker alive during monitoring, but gaps can occur.

**Storage limits.** `chrome.storage.local` has a 10MB limit. Alert history is capped at 200 entries to stay well within this.

**Cross-origin restrictions.** Content scripts cannot access all page data due to browser security policies. Some Quotex globals may be inaccessible.

### Scoring Engine

**No adaptive learning.** Scoring weights are static (configurable but not self-tuning). The engine does not learn from signal outcomes.

**No backtesting.** There is no facility to test scoring parameters against historical data.

**Limited patterns.** Pattern detection covers basic candlestick patterns. Complex formations (head and shoulders, triangles, etc.) are not detected.

**Indicator calculation.** With limited candle data (especially from DOM-only capture), indicators like RSI (needs 14+ periods) and MACD (needs 26+ periods) may not have enough data points. The engine degrades gracefully but with reduced accuracy.

### Network and Infrastructure

**Backend dependency.** The extension requires the backend API to be running. Without the backend, no signals are generated (only chart observation occurs).

**MongoDB dependency.** The backend requires MongoDB for persistence. Without MongoDB, the backend will not start.

**No offline mode.** The extension cannot generate alerts independently. It relies on the backend for all analysis.

**WebSocket disconnections.** Network interruptions cause the WebSocket to disconnect. Auto-reconnect with exponential backoff is implemented, but alerts are missed during disconnection periods.

### Dashboard

**No real-time charting.** The dashboard shows signal data but does not render price charts. Historical price data is not retained long enough for chart display (1-hour TTL on chart_data collection).

**No export.** Signal data cannot currently be exported to CSV or JSON from the dashboard.

## Known Issues

1. Quotex may serve different DOM structures for different regions or account types
2. Chart overlay may overlap with Quotex's own UI elements
3. Sound playback may be blocked by Chrome's autoplay policy until user interacts with the page
4. Chrome notifications may be suppressed by OS-level Do Not Disturb settings
5. Extension popup state may briefly show stale data after service worker restart

## Mitigations

- The extension retries chart detection up to 30 times (2-second intervals) to handle slow page loads
- WebSocket reconnects with exponential backoff up to 50 attempts
- Health checks run every minute to detect backend outages
- Alert history persists across service worker restarts via chrome.storage
- Fallback audio (Web Audio API oscillator) works when MP3 files are unavailable
