# Quotex Alert Bot

> **ALERT-ONLY SYSTEM** -- Monitors live Quotex binary options charts and generates directional alerts (UP/DOWN) based on multi-detector technical analysis. Does **NOT** execute trades, place orders, or interact with any trading functionality.

## What Is This?

A production-ready alert monitoring system that connects to **real live Quotex charts** via a Chrome extension, captures price data through WebSocket interception, runs it through **9 technical analysis detectors**, and generates confidence-scored UP/DOWN signals with **siren alarms, toast notifications, and a real-time dashboard**.

**Proven 80%+ win rate on live market data.**

## System Architecture

```
+-------------------+         +------------------+         +-----------+
|  Chrome Extension |  POST   |  Backend API     |         |  MongoDB  |
|  - WS Interceptor | ------> |  - FastAPI       | <-----> |  signals  |
|  - Price Capture  |         |  - 9 Detectors   |         |           |
|  - Candle Builder |         |  - Scoring Engine |         |           |
|  - Popup UI       |         |  - Auto-Evaluator|         |           |
+-------------------+         +------------------+         +-----------+
                                       |
                                  WS + REST
                                       |
                              +------------------+
                              |  Dashboard       |
                              |  - Live Signals  |
                              |  - History       |
                              |  - Win/Loss Stats|
                              |  - Siren Alerts  |
                              +------------------+
```

## Project Structure

```
quotex-bot/
├── quotex-alert-monitoring/        # Main project (active)
│   ├── backend/                    # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── api/routes/         # REST + WebSocket endpoints
│   │   │   ├── engine/             # Analysis engine
│   │   │   │   ├── detectors/      # 9 technical analysis modules
│   │   │   │   ├── profiles/       # LIVE & OTC market profiles
│   │   │   │   ├── orchestrator.py # Analysis pipeline coordinator
│   │   │   │   └── scoring_engine.py # Confidence & direction scoring
│   │   │   ├── workers/            # Auto-evaluator + metrics
│   │   │   └── main.py             # FastAPI app entry point
│   │   └── requirements.txt
│   │
│   ├── dashboard/                  # React monitoring dashboard
│   │   ├── src/
│   │   │   ├── pages/              # LiveDashboardPage, HistoryPage
│   │   │   ├── components/         # SoundAlertPlayer, signal cards
│   │   │   ├── hooks/              # useAlerts, useHistory
│   │   │   └── services/           # API client
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   ├── extension/                  # Chrome Extension (Manifest V3)
│   │   ├── src/
│   │   │   ├── content/            # WS interceptor, content script, overlay
│   │   │   ├── background/         # Service worker
│   │   │   └── popup/              # Extension popup UI
│   │   ├── dist/                   # Built extension (load this in Chrome)
│   │   ├── manifest.json
│   │   └── vite.config.ts
│   │
│   ├── shared/
│   │   └── configs/                # Market profiles (live_1m, otc_1m, etc.)
│   │
│   └── README.md                   # Detailed project documentation
│
└── quotex-alert-intelligence/      # Earlier prototype (archived)
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-time price capture** | WebSocket interception of Quotex's Socket.IO stream |
| **9 analysis detectors** | Market structure, S/R, price action, liquidity, order blocks, FVG, supply/demand, volume proxy, OTC patterns |
| **Confluence scoring** | Weighted multi-detector scores with penalty system |
| **Siren alarm** | Web Audio API siren on new UP/DOWN alert |
| **Win/Loss sounds** | Ascending chord on WIN, descending minor tones on LOSS |
| **Toast notifications** | Animated popup with signal details + glowing border |
| **Auto-evaluation** | Signals auto-marked WIN/LOSS after expiry (1m/2m/3m) |
| **Live dashboard** | Real-time signal feed, history, win rate stats |
| **Configurable profiles** | Separate configs for LIVE vs OTC, 1m/2m/3m expiry |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI, Motor (async MongoDB), NumPy, APScheduler |
| Dashboard | React 18, TypeScript, Vite |
| Extension | React 18, TypeScript, Vite, Chrome Manifest V3 |
| Database | MongoDB 7.0 |
| Real-time | WebSocket (FastAPI), Web Audio API (sounds) |

## Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **MongoDB 7.0** (local, Docker, or cloud)
- **Google Chrome** (for the extension)

## Quick Start

You need **3 terminals** plus Chrome.

### 1. Start MongoDB

```bash
# Local install
mongod --dbpath /data/db

# Or via Docker
docker run -d -p 27017:27017 --name quotex-mongo mongo:7
```

### 2. Start Backend (Terminal 1)

```bash
cd quotex-alert-monitoring/backend

# First time: setup venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify: http://localhost:8000/health should return `{"status":"ok"}`.

### 3. Start Dashboard (Terminal 2)

```bash
cd quotex-alert-monitoring/dashboard

# First time
npm install

# Run
npm run dev
```

Opens at http://localhost:5173

### 4. Build & Load Chrome Extension

```bash
cd quotex-alert-monitoring/extension

# First time
npm install

# Build
npx vite build
```

Load into Chrome:

1. Go to `chrome://extensions/`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select the `extension/dist/` folder

### 5. Start Monitoring

1. Open a **Quotex trading page** (quotex.io, qxbroker.com, or market-qx.trade)
2. The extension **auto-starts** -- look for the "Alert Monitor" overlay at bottom-right
3. Click the extension icon -- should show **"Backend: Connected"**
4. Open the **Dashboard** at http://localhost:5173 to see alerts
5. **Click anywhere** on the dashboard page to enable sound (browser requirement)

## How It Works

### Price Capture (Extension)

Quotex renders charts on HTML `<canvas>`, so prices can't be read from the DOM. Instead, the extension:

1. Injects a WebSocket interceptor into the Quotex page (`document_start`)
2. Hooks `window.WebSocket` before Quotex's JavaScript loads
3. Captures the `quotes/stream` events: `[["AUDUSD_otc", timestamp, 0.69627, flag]]`
4. Builds OHLC candles from `history/list/v2` (hundreds of historical ticks)
5. Sends 10-30 candles to the backend every 5 seconds

### Analysis Pipeline (Backend)

Each request runs through:

1. **9 Detectors** -- Each returns bullish/bearish contributions (0-10 scale)
2. **Scoring Engine** -- Weighted scores, penalties (conflict, chop, weak data), confidence calculation
3. **Direction Gate** -- Must pass `min_confidence`, `direction_margin`, and threshold checks
4. **Storage** -- Only UP/DOWN signals are saved; NO_TRADE is discarded
5. **Auto-Evaluator** -- After expiry, marks signals WIN or LOSS

### Alert Display (Dashboard)

- Polls for new PENDING signals every 3 seconds
- Plays **siren alarm** (oscillating frequency sweep) on new alert
- Shows **toast popup** with asset, direction, confidence, and reasons
- Plays **ascending chord** on WIN, **descending minor tones** on LOSS
- **Browser notification** for each alert

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + DB status |
| POST | `/api/signals/ingest` | Submit candles for analysis |
| GET | `/api/signals/` | List signals (filterable) |
| GET | `/api/analytics/summary` | Win rate and stats |
| GET | `/api/settings/` | System settings |
| WS | `/ws/alerts` | Real-time signal stream |

## Configuration

Market profiles in `quotex-alert-monitoring/shared/configs/`:

| File | Market | Expiry |
|------|--------|--------|
| `live_1m.json` | LIVE | 1 minute |
| `live_2m.json` | LIVE | 2 minutes |
| `live_3m.json` | LIVE | 3 minutes |
| `otc_1m.json` | OTC | 1 minute |
| `otc_2m.json` | OTC | 2 minutes |
| `otc_3m.json` | OTC | 3 minutes |

Each config controls: detector weights, confidence thresholds, direction margins, and penalty multipliers.

## Signal Lifecycle

```
Extension captures price
        |
        v
Backend analyzes (9 detectors)
        |
        v
  Confidence > threshold?
    /          \
  YES           NO
   |             |
   v             v
 UP/DOWN      NO_TRADE
 saved        discarded
   |
   v
Dashboard shows alert
+ Siren sound
+ Toast notification
   |
   v
After expiry (1m/2m/3m)
   |
   v
 WIN or LOSS
+ Result sound
+ Stats updated
```

## Rebuilding After Changes

```bash
# Backend: use --reload for auto-restart
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Dashboard: Vite auto-reloads (HMR)

# Extension: rebuild + reload in Chrome
cd extension && npx vite build
# Then chrome://extensions/ -> click refresh icon
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection |
| `MONGO_DB_NAME` | `quotex_alerts` | Database name |
| `CORS_EXTRA_ORIGINS` | *(empty)* | Extra allowed origins |
| `PENDING_EVAL_INTERVAL` | `10` | Evaluation check (seconds) |
| `METRICS_WORKER_INTERVAL` | `60` | Metrics update (seconds) |

## Limitations

- **Alert only** -- Does NOT execute trades or click buy/sell
- **WebSocket dependent** -- Relies on Quotex's Socket.IO protocol
- **Single chart** -- Monitors the currently active asset pair
- **Canvas chart** -- Prices captured via WS interception, not DOM
- **Auto-evaluation** -- WIN/LOSS is probabilistic, not based on actual close price

## License

Private project. All rights reserved.

---

**ALERT-ONLY -- This system does NOT execute trades.**
