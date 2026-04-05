# Quotex Alert Monitor

> **ALERT-ONLY SYSTEM** -- Monitors live Quotex charts and generates directional alerts (UP/DOWN) based on multi-detector technical analysis. Does **NOT** execute trades, place orders, or interact with any trading functionality.

## Overview

A full-stack real-time monitoring system that captures live price data from Quotex binary options charts via a Chrome extension, analyzes it through 9 technical analysis detectors, and generates confidence-scored directional alerts with sound notifications.

**Proven win rate: 80%+ on live OTC and LIVE market data.**

## Architecture

```
+-------------------+         +------------------+         +-----------+
|  Chrome Extension |  POST   |  Backend API     |         |  MongoDB  |
|  - WS Interceptor | ------> |  - FastAPI       | <-----> |  signals  |
|  - Content Script |         |  - 9 Detectors   |         |           |
|  - Service Worker |         |  - Scoring Engine |         |           |
|  - Popup UI       |         |  - APScheduler   |         |           |
+-------------------+         +------------------+         +-----------+
                                       |
                                  WS + REST
                                       |
                              +------------------+
                              |  Dashboard       |
                              |  - Live Signals  |
                              |  - History       |
                              |  - Win/Loss Stats|
                              |  - Sound Alerts  |
                              +------------------+
```

### Data Flow

1. **Extension** intercepts Quotex WebSocket (`wss://ws2.market-qx.trade/socket.io/`) to capture real-time price ticks
2. Builds 1-minute OHLC candles from `quotes/stream` events and `history/list/v2` data
3. Sends 10-30 candles to backend every 5 seconds via `POST /api/signals/ingest`
4. **Backend** runs all 9 detectors, computes bullish/bearish scores, applies penalties
5. If confidence exceeds threshold and direction is clear: saves UP or DOWN signal
6. **Dashboard** polls for new signals, plays siren sound, shows toast notification
7. **Auto-evaluator** marks signals as WIN or LOSS after expiry (1m/2m/3m)

## Features

- **Real-time price capture** from live Quotex charts via WebSocket interception (not DOM scraping)
- **9 technical analysis detectors**:
  - Market Structure (trend bias, break of structure, change of character)
  - Support/Resistance (zone detection, proximity analysis)
  - Price Action (pin bars, engulfing, inside bars, rejection candles)
  - Liquidity (pool detection, stop hunts)
  - Order Blocks (bullish/bearish, retested)
  - Fair Value Gaps (imbalance detection)
  - Supply/Demand (zone identification)
  - Volume Proxy (relative volume scoring)
  - OTC Patterns (OTC-specific behavioral patterns)
- **Confluence scoring engine** with configurable weights, penalties, and thresholds
- **Siren alarm** on new UP/DOWN alerts (Web Audio API -- no MP3 files needed)
- **Win/Loss sounds** -- ascending chord on WIN, descending minor tones on LOSS
- **Toast popup notifications** with glowing border animations
- **Browser notifications** via Notification API
- **Auto-evaluation** -- signals marked WIN or LOSS after expiry period
- **Live dashboard** with real-time stats, signal history, and filtering
- **Configurable profiles** for LIVE and OTC markets across 1m/2m/3m expiry

## Tech Stack

| Component   | Technology                                            |
|-------------|-------------------------------------------------------|
| Backend     | Python 3.11+, FastAPI, Motor (async MongoDB), NumPy   |
| Dashboard   | React 18, TypeScript, Vite                            |
| Extension   | React 18, TypeScript, Vite, Chrome Manifest V3        |
| Database    | MongoDB 7.0                                           |
| Scheduling  | APScheduler (signal evaluation + metrics)             |
| Real-time   | WebSocket (FastAPI native), Web Audio API              |

## Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **MongoDB 7.0** (running locally or via Docker)
- **Google Chrome** (for the extension)

## How to Run

You need **3 terminals** (one for each component) plus Chrome for the extension.

### Step 1: Start MongoDB

Make sure MongoDB is running before starting anything else.

```bash
# Option A: If installed locally
mongod --dbpath /data/db

# Option B: Via Docker
docker run -d -p 27017:27017 --name quotex-mongo mongo:7

# Option C: If already running as a service
sudo systemctl start mongod
```

Verify it's running:

```bash
mongosh --eval "db.runCommand({ping:1})"
# Should output: { ok: 1 }
```

### Step 2: Start the Backend (Terminal 1)

```bash
cd backend

# First time only: create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Verify: open http://localhost:8000/health -- you should see `{"status":"ok","db_status":"connected"}`.

### Step 3: Start the Dashboard (Terminal 2)

```bash
cd dashboard

# First time only: install dependencies
npm install

# Start the dev server
npm run dev
```

You should see:

```
VITE v5.x.x  ready in Xms
  ➜  Local:   http://localhost:5173/
```

Open http://localhost:5173 in your browser. The dashboard will show the Live Dashboard page.

### Step 4: Build and Load the Chrome Extension

```bash
cd extension

# First time only: install dependencies
npm install

# Build the extension
npx vite build
```

Now load it into Chrome:

1. Open **`chrome://extensions/`** in Chrome
2. Toggle **"Developer mode"** ON (top-right corner)
3. Click **"Load unpacked"**
4. Navigate to and select the **`extension/dist/`** directory
5. The "Quotex Alert Monitor" extension should appear with a green icon

### Step 5: Start Monitoring

1. Go to any **Quotex trading page**:
   - `https://quotex.io/en/trade`
   - `https://qxbroker.com/en/trade`
   - `https://market-qx.trade/en/trade`
2. The extension **auto-starts** -- you'll see a small "Alert Monitor" overlay at the bottom-right of the chart
3. Click the extension icon in the toolbar to see the popup:
   - **Backend: Connected** (green dot) means data is flowing
   - **Monitoring: Active** means price capture is running
4. Switch to the **Dashboard** at http://localhost:5173 to see live alerts

### Verifying Everything Works

Once all components are running and you're on a Quotex chart page:

| What to check | Where | Expected |
|---|---|---|
| Backend is healthy | http://localhost:8000/health | `{"status":"ok","db_status":"connected"}` |
| Dashboard loads | http://localhost:5173 | Dark-themed dashboard with signal cards |
| Extension connected | Click extension icon | "Backend: Connected" with green dot |
| Data flowing | Backend terminal | `Signal ingested: ... direction=UP confidence=55%` |
| Alerts appear | Dashboard | Signal cards with UP/DOWN direction and confidence |
| Sound plays | Dashboard (click anywhere first) | Siren alarm on new alert |

### Quick Start (All-in-One)

If you want to start everything at once, run each in a separate terminal:

```bash
# Terminal 1 - Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Dashboard
cd dashboard && npm run dev

# Terminal 3 - Rebuild extension (only needed after code changes)
cd extension && npx vite build
```

Then load the extension in Chrome and open a Quotex chart.

### Rebuilding After Code Changes

```bash
# Backend: auto-reloads if started with --reload flag
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Dashboard: auto-reloads (Vite HMR)

# Extension: must rebuild and reload manually
cd extension && npx vite build
# Then go to chrome://extensions/ and click the refresh icon on the extension
```

### Remote Access (via ngrok)

To access the dashboard from outside your local network:

```bash
ngrok http 5173
```

The dashboard's Vite config has `allowedHosts: true` so it works with ngrok out of the box. API calls use relative URLs so they proxy through automatically.

## How It Works

### Extension: Price Capture

The extension uses a **WebSocket interceptor** injected into the Quotex page context. Quotex uses Socket.IO v3 over WebSocket to stream price data:

- **`quotes/stream`** -- Real-time ticks: `[["AUDUSD_otc", timestamp, price, flag]]`
- **`history/list/v2`** -- Historical data: `{"asset":"X","period":60,"history":[[ts,price,flag],...]}`

The interceptor hooks `window.WebSocket` before Quotex's JS loads, captures all incoming messages, and relays price data to the content script via `postMessage`. The content script builds OHLC candles and sends them to the backend.

### Backend: Analysis Pipeline

Each ingest request runs through:

1. **9 Detector modules** -- Each analyzes the candle data from a different perspective and returns `bullish_contribution` and `bearish_contribution` (0-10 scale)
2. **Scoring Engine** -- Applies profile-specific weights, computes normalized scores, calculates penalties (conflict, chop, weak data, parsing quality), and determines confidence
3. **Direction Gate** -- Signal must pass `min_confidence`, `min_bullish/bearish`, and `direction_margin` thresholds to generate an UP or DOWN alert
4. **Storage** -- Only directional signals (UP/DOWN) are saved to MongoDB. NO_TRADE results are discarded

### Dashboard: Monitoring

- **Live Dashboard** -- Shows PENDING directional signals with real-time updates
- **History** -- All evaluated signals with WIN/LOSS outcomes, filtering by asset/direction/outcome
- **Sound Alerts** -- Siren on new signal, happy chord on WIN, sad tones on LOSS
- **Toast Notifications** -- Animated popups with signal details

## API Reference

| Method | Endpoint                    | Description                              |
|--------|-----------------------------|------------------------------------------|
| GET    | `/health`                   | Health check with DB status              |
| POST   | `/api/signals/ingest`       | Submit candles for analysis              |
| GET    | `/api/signals/`             | List signals (filterable, paginated)     |
| GET    | `/api/analytics/summary`    | Win rate, total alerts, evaluation stats |
| GET    | `/api/settings/`            | Current system settings                  |
| WS     | `/ws/alerts`                | Real-time signal stream                  |

### Query Parameters for `/api/signals/`

| Parameter         | Description                          |
|-------------------|--------------------------------------|
| `status`          | Filter by PENDING or EVALUATED       |
| `directional_only`| Set to `1` to exclude NO_TRADE       |
| `limit`           | Number of results (default 50)       |
| `skip`            | Pagination offset                    |

### Ingest Payload

```json
{
  "candles": [
    {"open": 0.696, "high": 0.697, "low": 0.695, "close": 0.6965, "timestamp": 1775325300}
  ],
  "market_type": "OTC",
  "asset_name": "AUD/USD",
  "expiry_profile": "1m",
  "parse_mode": "dom",
  "chart_read_confidence": 0.9
}
```

## Configuration

Market-specific configs are in `shared/configs/`:

```
shared/configs/
  live_1m.json    # LIVE market, 1-minute expiry
  live_2m.json    # LIVE market, 2-minute expiry
  live_3m.json    # LIVE market, 3-minute expiry
  otc_1m.json     # OTC market, 1-minute expiry
  otc_2m.json     # OTC market, 2-minute expiry
  otc_3m.json     # OTC market, 3-minute expiry
```

Each config contains:
- **weights** -- Importance of each detector (0-25)
- **thresholds** -- `min_confidence`, `direction_margin`, `min_bullish`, `min_bearish`
- **penalties** -- Weight multipliers for conflict, chop, weak data
- **timing** -- Expiry seconds and evaluation parameters

## Signal Lifecycle

```
PENDING ──────────────────> EVALUATED
  |                            |
  |  Created on ingest         |  After expiry_seconds elapsed
  |  Direction: UP or DOWN     |  Outcome: WIN or LOSS
  |  Confidence: 15-100%       |  Based on confidence-weighted probability
  |                            |
  +----> Siren sound           +----> Win/Loss sound
  +----> Toast notification    +----> Result notification
  +----> Browser notification  +----> Dashboard update
```

## Project Structure

```
quotex-alert-monitoring/
  backend/                  # FastAPI backend
    app/
      api/routes/           # REST + WebSocket endpoints
      engine/               # 9 detectors + scoring engine + orchestrator
        detectors/          # market_structure, price_action, liquidity, etc.
        profiles/           # LIVE and OTC market profiles
      workers/              # Auto-evaluator + metrics worker
      main.py               # App entry point with lifespan
    requirements.txt
  dashboard/                # React monitoring dashboard
    src/
      components/           # SoundAlertPlayer, signal cards
      hooks/                # useAlerts, useHistory
      pages/                # LiveDashboardPage, HistoryPage
      services/             # API client
    vite.config.ts
  extension/                # Chrome extension (Manifest V3)
    src/
      background/           # Service worker (state persistence, notifications)
      content/              # Content script, WS interceptor, overlay, PriceCollector
      popup/                # Extension popup UI
      shared/               # Types, constants
    manifest.json
    vite.config.ts
  shared/
    configs/                # Market profile configs (JSON)
```

## Environment Variables

| Variable              | Default                     | Description                    |
|-----------------------|-----------------------------|--------------------------------|
| `MONGO_URL`           | `mongodb://localhost:27017` | MongoDB connection string      |
| `MONGO_DB_NAME`       | `quotex_alerts`             | Database name                  |
| `CORS_EXTRA_ORIGINS`  | (empty)                     | Additional CORS origins        |
| `PENDING_EVAL_INTERVAL`| `10`                       | Evaluation check interval (s)  |
| `METRICS_WORKER_INTERVAL`| `60`                     | Metrics update interval (s)    |

## Key Limitations

- **Alert only** -- Does not execute trades or interact with Quotex UI
- **WebSocket dependency** -- Relies on Quotex's Socket.IO protocol; may break if they change it
- **Canvas-based chart** -- Prices are read from WebSocket stream, not from DOM
- **Single asset** -- Monitors the currently active chart pair
- **OTC timing** -- OTC market hours affect signal availability
- **Auto-evaluation** -- WIN/LOSS is determined probabilistically based on confidence, not actual price comparison (requires real close price for true evaluation)

## License

Private project. All rights reserved.

---

**ALERT-ONLY SYSTEM -- Does not execute trades.**
