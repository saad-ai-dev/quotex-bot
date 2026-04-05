# Architecture Overview

> **ALERT-ONLY** -- All components are designed for monitoring and alerting. No trade execution exists in any layer.

## System Components

### 1. Chrome Extension (Manifest V3)

The extension is the user-facing entry point. It runs on Quotex pages and provides the alert interface.

**Content Script** (`content-script.ts`)
- Injected into Quotex pages at `document_idle`
- Detects the chart container using heuristic DOM selectors
- Mounts a transparent overlay for alert display
- Delegates data capture to `ChartObserver`

**Chart Observer** (`chart-observer.ts`)
- Periodic timer-based capture (default 5s interval)
- Three extraction strategies: window globals, data attributes, DOM text
- Sends captured `CandleData[]` to the service worker via `chrome.runtime.sendMessage`

**Overlay Renderer** (`overlay-renderer.ts`)
- Positioned absolutely within the chart container
- Shows: status dot, alert direction/confidence, countdown timer
- Auto-dismisses alerts after 30 seconds
- Configurable position (four corners)

**Service Worker** (`service-worker.ts`)
- Maintains WebSocket connection to backend
- Routes messages between popup, content scripts, and backend
- Manages Chrome notifications and alarms
- Persists settings and alert history in `chrome.storage.local`

**Popup** (`App.tsx`)
- React app with three tabs: Status, Alerts, Settings
- Zustand store synced with service worker state
- No trade controls -- monitoring toggle and alert management only

### 2. Backend API (Python/FastAPI)

The backend performs analysis and stores results.

**REST API**
- Signal CRUD with pagination and filtering
- Settings management
- Chart data ingestion endpoint
- Statistics aggregation

**Scoring Engine**
- Receives raw candle data
- Calculates technical indicators (RSI, MACD, Bollinger, EMA, Stochastic, ATR)
- Applies weighted scoring across five categories
- Produces confidence score (0-100) and tier classification

**WebSocket Server**
- Endpoint: `/ws/signals`
- Broadcasts new signals to all connected clients
- Heartbeat mechanism for connection health
- Supports multiple concurrent connections (extension + dashboard)

**Static File Server**
- Serves alert sound MP3 files from `/static/sounds/`

### 3. Dashboard (React)

Web application for historical analysis and configuration.

- Signal list with real-time updates
- Filtering by asset, direction, confidence, status
- Daily/hourly statistics charts
- Settings editor with live preview

### 4. MongoDB

Document store for all persistent data.

**Collections:**
- `signals` -- Detected signals with full indicator/scoring data (24h TTL on expiry)
- `alert_events` -- Record of alerts shown to user
- `chart_data` -- Raw captured candle data (1h TTL)
- `settings` -- Configuration documents
- `daily_stats` -- Aggregated daily statistics

## Data Flow

```
[Quotex Page DOM]
       |
       v (DOM scraping)
[Content Script / ChartObserver]
       |
       v (chrome.runtime.sendMessage)
[Service Worker]
       |
       v (REST POST /api/v1/chart/data)
[Backend API]
       |
       v (scoring engine)
[Signal Generated]
       |
       +---> MongoDB (persist)
       |
       +---> WebSocket broadcast
              |
              +---> Service Worker
              |        |
              |        +---> Chrome Notification
              |        +---> Content Script (overlay)
              |        +---> Popup (state update)
              |
              +---> Dashboard (live update)
```

## Communication Protocols

| Path | Protocol | Format |
|------|----------|--------|
| Extension <-> Backend | REST (HTTPS) | JSON |
| Extension <-> Backend | WebSocket | JSON messages with type field |
| Content Script <-> Service Worker | `chrome.runtime.sendMessage` | `ExtensionMessage` union type |
| Service Worker <-> Popup | `chrome.runtime.sendMessage` | `ExtensionMessage` union type |
| Service Worker <-> Storage | `chrome.storage.local` | Serialized JSON |

## Security Considerations

- API key authentication via `X-API-Key` header
- CORS restricted to known origins (localhost, chrome-extension)
- No sensitive data stored in extension (API key in chrome.storage)
- All signals are read-only from the extension's perspective
- No trade execution capabilities exist in any component
