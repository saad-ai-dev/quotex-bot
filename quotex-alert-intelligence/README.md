# Quotex Alert Intelligence

**ALERT-ONLY chart observation system. This software does NOT execute trades, manage funds, or interact with any trading platform. It observes chart data, runs scoring analysis, and generates informational alerts.**

## Overview

Quotex Alert Intelligence is a probabilistic chart analysis system that observes price action data from the Quotex platform and generates directional alerts (CALL/PUT) with confidence scores. It is designed as an educational and informational tool to help users understand market structure, price action patterns, and technical analysis concepts.

The system consists of two components:

1. **Backend (Python/FastAPI)** - Scoring engine, signal storage, REST/WebSocket API
2. **Chrome Extension** - Chart data extraction, alert display, settings management

## Architecture

```
Chrome Extension (Chart Observer)
        |
        | Parsed candle data via REST/WebSocket
        v
FastAPI Backend (Scoring Engine)
        |
        | Store signals, compute analytics
        v
MongoDB (Signal Storage + History)
```

The extension observes chart DOM elements, parses candle data, and sends it to the backend. The backend runs the scoring engine across multiple analysis dimensions (market structure, support/resistance, price action, liquidity, order blocks, FVG, supply/demand, volume proxy, and OTC patterns), applies penalty adjustments, and produces a directional alert with a confidence percentage.

## Features

- Multi-dimensional scoring engine with 9 analysis components
- Separate LIVE and OTC market profiles with distinct weight configurations
- Support for 1-minute, 2-minute, and 3-minute expiry windows
- Real-time alerts via WebSocket
- Signal history tracking with win/loss/neutral outcome recording
- Configurable confidence thresholds and penalty weights
- Analytics and performance statistics
- Chrome extension with popup UI for alert display
- MongoDB-backed persistence with TTL-based cleanup

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Motor (async MongoDB), Pydantic
- **Extension**: TypeScript, Chrome Extensions Manifest V3
- **Database**: MongoDB 7
- **Infrastructure**: Docker, Docker Compose

## Prerequisites

- Python 3.11 or higher
- Node.js 18+ and npm (for the extension)
- MongoDB 7 (local install or Docker)
- Docker and Docker Compose (optional, for containerized setup)

## Setup

### Quick Start with Docker

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

### Manual Setup

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Chrome Extension

```bash
cd extension
npm install
npm run build
```

Then load the `extension/dist` directory as an unpacked extension in Chrome.

#### Database Initialization

```bash
# Ensure MongoDB is running
python scripts/init_indexes.py
python scripts/seed_settings.py
```

#### Development Mode

```bash
# All-in-one development startup
bash scripts/dev_run.sh
```

Or using Make:

```bash
make install-backend
make init-db
make seed-settings
make run-backend
```

## API Reference Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/signals` | Submit chart data for analysis |
| GET | `/api/v1/signals` | List recent signals |
| GET | `/api/v1/signals/{id}` | Get signal details |
| PATCH | `/api/v1/signals/{id}/resolve` | Record signal outcome |
| GET | `/api/v1/history` | Get signal history |
| GET | `/api/v1/analytics` | Get performance analytics |
| GET | `/api/v1/settings` | Get current settings |
| PUT | `/api/v1/settings` | Update settings |
| GET | `/api/v1/profiles` | List available scoring profiles |
| GET | `/api/v1/health` | Health check |
| WS | `/ws/signals` | Real-time signal stream |

See [docs/api-reference.md](docs/api-reference.md) for full details.

## Signal Lifecycle

1. **Observation**: The Chrome extension observes chart DOM and parses candle data
2. **Submission**: Parsed data is sent to the backend via POST `/api/v1/signals`
3. **Scoring**: The engine evaluates all 9 analysis dimensions using the active profile
4. **Penalty Application**: Conflict, chop, weak data, parsing quality, and timing penalties are applied
5. **Direction Decision**: Bullish vs bearish scores are compared against thresholds
6. **Alert Generation**: If confidence exceeds the minimum threshold, an alert is emitted
7. **Broadcast**: The alert is stored in MongoDB and broadcast via WebSocket
8. **Resolution** (optional): After expiry, the outcome can be recorded for tracking

## Configuration Guide

Scoring profiles are stored in `shared/configs/` as JSON files. Each profile defines:

- **weights**: Relative importance of each analysis dimension (must sum to 100 for LIVE, 100 for OTC)
- **thresholds**: Minimum confidence and directional margins required to emit an alert
- **penalties**: Multipliers for various quality and conflict deductions
- **timing**: Expiry duration and minimum lead time

Available profiles: `live_1m`, `live_2m`, `live_3m`, `otc_1m`, `otc_2m`, `otc_3m`

See [docs/scoring-engine.md](docs/scoring-engine.md) for detailed scoring documentation.

## Key Limitations

- **Probabilistic, not predictive**: Confidence scores represent analytical weight, not probability of profit
- **No trade execution**: This system generates informational alerts only
- **No financial guarantees**: Past signal accuracy does not predict future results
- **Parsing dependent**: Alert quality depends entirely on the accuracy of chart data parsing from the DOM
- **Latency sensitive**: Real-time chart changes may not be captured instantly
- **OTC limitations**: OTC markets have synthetic pricing; traditional technical analysis has reduced applicability

See [docs/limitations.md](docs/limitations.md) for comprehensive details.

## Future Roadmap

- Multi-timeframe confluence analysis
- Machine learning-based weight optimization from historical outcomes
- Additional asset class support
- Advanced pattern recognition (harmonics, Elliott Wave overlay)
- Performance dashboard with equity curve visualization
- Alert export to Telegram/Discord webhooks
- Backtesting framework using historical chart data
- Mobile companion app for alert notifications

## License

This project is for educational and informational purposes only. Not financial advice.
