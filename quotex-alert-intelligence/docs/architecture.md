# Architecture Overview

## System Design

Quotex Alert Intelligence follows a client-server architecture with three main components communicating over HTTP/WebSocket.

## Component Diagram

```
+---------------------------+
|    Chrome Extension        |
|  (Manifest V3)            |
|                           |
|  +---------------------+ |
|  | Content Script       | |    Observes DOM
|  | (Chart Observer)     |-----> Parses candle data
|  +---------------------+ |
|  | Popup UI             | |    Displays alerts
|  | (Alert Dashboard)    | |    Manages settings
|  +---------------------+ |
|  | Background Worker    | |    Manages connections
|  | (Service Worker)     |-----> WebSocket client
|  +---------------------+ |
+------------||--------------+
             ||
             || REST API (POST /api/v1/signals)
             || WebSocket (/ws/signals)
             ||
+------------||--------------+
|    FastAPI Backend          |
|                            |
|  +----------------------+  |
|  | API Layer            |  |   REST endpoints
|  | (Routes + WS)       |  |   WebSocket broadcast
|  +----------------------+  |
|  | Scoring Engine       |  |   9-dimension analysis
|  | (Core Logic)         |  |   Penalty computation
|  +----------------------+  |
|  | Profile Manager      |  |   Load/switch configs
|  | (Config Loader)      |  |   Weight management
|  +----------------------+  |
|  | Data Access Layer    |  |   Motor (async MongoDB)
|  | (Repositories)       |  |   CRUD operations
|  +----------------------+  |
+------------||--------------+
             ||
             ||  Motor (async driver)
             ||
+------------||--------------+
|    MongoDB 7               |
|                            |
|  - signals (active)       |
|  - signal_history         |
|  - settings               |
|  - analytics              |
+----------------------------+
```

## Data Flow

### Signal Generation Flow

1. The **Content Script** runs on the Quotex chart page, observing DOM mutations and extracting candle OHLC data, timestamps, and chart metadata.

2. Parsed candle arrays are sent to the **Background Worker** via Chrome messaging.

3. The Background Worker sends the data to the **Backend API** via `POST /api/v1/signals` with the current market type and expiry profile.

4. The **Scoring Engine** loads the appropriate profile configuration and evaluates the candle data across all 9 analysis dimensions:
   - Market Structure (trend, structure breaks)
   - Support/Resistance (key levels, bounces)
   - Price Action (candle patterns, momentum)
   - Liquidity (sweeps, traps)
   - Order Blocks (institutional zones)
   - Fair Value Gaps (imbalances)
   - Supply/Demand (zones, reactions)
   - Volume Proxy (body/wick ratios as volume substitute)
   - OTC Patterns (cycle detection, synthetic patterns - OTC only)

5. Each dimension produces a raw score (0-100), a directional bias (bullish/neutral/bearish), and explanatory details.

6. Raw scores are multiplied by profile weights to produce weighted scores.

7. The **Penalty Engine** computes deductions for:
   - Conflicting signals across dimensions
   - Choppy/ranging market conditions
   - Weak or insufficient data
   - Parsing quality issues
   - Timing proximity to candle close

8. Final confidence = sum of weighted scores - total penalties.

9. If confidence exceeds the profile threshold and directional margin is sufficient, a signal document is created with direction (CALL/PUT).

10. The signal is stored in MongoDB and broadcast via **WebSocket** to all connected clients.

### Alert Display Flow

1. The Background Worker receives the signal via WebSocket.
2. It forwards the signal to the Popup UI via Chrome messaging.
3. The Popup renders the alert with confidence, direction, component breakdown, and expiry countdown.
4. Optional browser notification and sound alert are triggered based on settings.

### Resolution Flow

1. After the expiry window passes, the extension observes the chart price.
2. It compares the price at expiry to the price at signal generation.
3. A `PATCH /api/v1/signals/{id}/resolve` call records the outcome (WIN/LOSS/NEUTRAL).
4. The signal is moved to the `signal_history` collection for long-term tracking.
5. Analytics aggregations are updated.

## Technology Choices

### FastAPI (Backend)
- Async-first framework with native WebSocket support
- Automatic OpenAPI documentation
- Pydantic for request/response validation
- High performance for real-time signal processing

### MongoDB (Database)
- Flexible document schema fits the variable structure of scoring results
- TTL indexes for automatic signal cleanup
- Good performance for time-series-like signal data
- Motor driver provides native async support for FastAPI

### Chrome Extension Manifest V3 (Frontend)
- Direct access to page DOM for chart observation
- Service Worker for persistent WebSocket connections
- Popup UI for compact alert display
- Chrome storage API for local settings cache

### Docker (Infrastructure)
- Consistent development and deployment environment
- Simple MongoDB provisioning
- Single `docker compose up` for full stack
