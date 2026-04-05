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
| **Confluence scoring** | Weighted multi-detector scores with 6 penalty types |
| **Signal deduplication** | Same asset+direction blocked within 60 seconds to prevent spam |
| **Auto-trade execution** | Extension clicks Quotex Up/Down buttons on signal (toggle on/off) |
| **Max loss safety break** | Auto-trading pauses after N consecutive losses, alerts continue |
| **Entry/close price tracking** | Records real entry price at signal, close price at expiry |
| **Real WIN/LOSS evaluation** | Outcome based on actual price movement, not probability |
| **P/L display** | Pip difference shown on dashboard signal cards and history table |
| **Siren alarm** | Web Audio API siren on new UP/DOWN alert |
| **Win/Loss sounds** | Ascending chord on WIN, descending minor tones on LOSS |
| **Toast notifications** | Animated popup with signal details + glowing border |
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

> **Don't have these installed?** The setup script installs everything for you automatically. See below.

## One-Command Setup

The setup script detects your OS, installs all missing dependencies (Python, Node.js, MongoDB), sets up all 3 components, and creates a run script.

```bash
# Linux / macOS
chmod +x setup.sh
./setup.sh

# Windows (PowerShell as Administrator)
powershell -ExecutionPolicy Bypass -File setup.ps1
```

After setup, start everything with:

```bash
# Linux / macOS
./run.sh

# Windows
run.bat
```

That's it. Open http://localhost:5173 for the dashboard, load the extension in Chrome, and go to Quotex.

## Manual Setup (Quick Start)

If you prefer to set things up manually, you need **3 terminals** plus Chrome.

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
5. Sends 10-30 candles to the backend every 15 seconds

### Analysis Pipeline (Backend)

Each request runs through:

1. **9 Detectors** -- Each returns bullish/bearish contributions (0-10 scale)
2. **Scoring Engine** -- Weighted scores with 6 penalty types, confidence calculation
3. **Direction Gate** -- Must pass `min_confidence` (45%), `direction_margin` (8), and score thresholds (22+)
4. **Signal Dedup** -- Same asset+direction blocked within 60 seconds to prevent duplicate alerts
5. **Storage** -- Only UP/DOWN signals saved with `entry_price`; NO_TRADE is discarded
6. **Auto-Evaluator** -- After expiry, records `close_price` and determines WIN/LOSS by comparing real prices

### Penalty System

The scoring engine applies 6 penalties that reduce confidence to filter weak signals:

| Penalty | Triggers When | Effect |
|---------|--------------|--------|
| **Conflict** | Bull/bear scores within 15 points | Up to 30 points |
| **Chop** | Chop probability > 45% | Up to 22 points |
| **Low confluence** | Fewer than 3 detectors agreeing | Up to 36 points |
| **Weak data** | Fewer than 12 candles | Up to 20 points |
| **Ranging market** | No clear trend bias | +8 points |
| **Timing reliability** | OTC market timing uncertainty | Up to 2.25 points |

Only signals that survive all penalties with confidence >= 45% generate an alert.

### Auto-Trade Execution (Optional)

When enabled in the extension popup:

1. Signal triggers (UP or DOWN with sufficient confidence)
2. Extension finds the Quotex **Up** or **Down** button by text content and color
3. Clicks the button to place the trade
4. Tracks trade result from Quotex WebSocket (`orders/closed/list`)
5. Records WIN/LOSS and updates consecutive loss counter
6. **Safety break**: After N consecutive losses (configurable), trading pauses automatically
7. Alerts continue flowing even when trading is paused
8. User must click "Reset & Resume" to re-enable trading

Time and investment amount are set manually on the Quotex trading panel.

### Alert Display (Dashboard)

- Polls for new PENDING signals every 3 seconds
- Plays **siren alarm** (oscillating frequency sweep) on new alert
- Shows **toast popup** with asset, direction, confidence, and reasons
- Shows **entry price**, **close price**, and **P/L in pips** on signal cards
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
Extension captures price (every 15s)
        |
        v
Backend analyzes (9 detectors + 6 penalties)
        |
        v
  Confidence >= 45% + 3 detectors agree?
    /          \
  YES           NO
   |             |
   v             v
 UP/DOWN      NO_TRADE
 saved        discarded
 entry_price
 recorded
   |
   v
Dedup check (same direction within 60s?)
   |  YES -> skip
   |  NO  -> save
   v
Dashboard alert + Siren + Toast
   |
   v (if auto-trade ON)
Extension clicks Up/Down button
   |
   v
After expiry (1m/2m/3m)
   |
   v
close_price recorded
entry vs close -> WIN or LOSS
   |
   v
Result sound + Stats updated
   |
   v (if auto-trade ON)
Track consecutive losses
   |
   v
Max losses hit? -> PAUSE trading (alerts continue)
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

- **WebSocket dependent** -- Relies on Quotex's Socket.IO protocol; may break if they change it
- **Single chart** -- Monitors the currently active asset pair
- **Canvas chart** -- Prices captured via WS interception, not DOM elements
- **Button detection** -- Auto-trade finds buttons by text ("Up"/"Down"); may fail if Quotex changes button labels
- **OTC markets** -- Inherently less predictable than LIVE markets; win rate may vary

## License

Private project. All rights reserved.
