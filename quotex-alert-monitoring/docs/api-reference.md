# API Reference

> **ALERT-ONLY** -- All endpoints are for monitoring and alerting. No trade execution endpoints exist.

Base URL: `http://localhost:8000`

## Authentication

Optional API key via header:

```
X-API-Key: your-api-key
```

## Endpoints

---

### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-04-04T14:30:00.000Z",
  "version": "1.0.0"
}
```

---

### List Signals

```
GET /api/v1/signals
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| page_size | int | 20 | Items per page (max 100) |
| asset | string | - | Filter by asset name |
| direction | string | - | Filter: "UP" or "DOWN" |
| min_confidence | float | - | Minimum confidence score |
| status | string | - | Filter by status |

**Response:**
```json
{
  "items": [
    {
      "id": "sig_20260404_143025_eurusd_a7b3c",
      "asset": "EUR/USD",
      "direction": "UP",
      "confidence": 78.5,
      "confidence_tier": "high",
      "entry_price": 1.08245,
      "timestamp": "2026-04-04T14:30:25.000Z",
      "expiry_seconds": 300,
      "expiry_time": "2026-04-04T14:35:25.000Z",
      "status": "active",
      "indicators": { ... },
      "scoring_breakdown": { ... }
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 20
}
```

---

### Get Latest Signals

```
GET /api/v1/signals/latest?limit=10
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 20 | Number of signals (max 100) |

**Response:** Array of Signal objects (same structure as items above).

---

### Get Active Signals

```
GET /api/v1/signals/active
```

Returns signals with status "active" that have not yet expired.

**Response:** Array of Signal objects.

---

### Get Single Signal

```
GET /api/v1/signals/{signal_id}
```

**Response:** Single Signal object or 404.

---

### Submit Chart Data

```
POST /api/v1/chart/data
```

Submit captured candle data for analysis. The scoring engine processes the data and may generate a signal alert.

**Request Body:**
```json
{
  "candles": [
    {
      "timestamp": "2026-04-04T14:30:00.000Z",
      "open": 1.08230,
      "high": 1.08260,
      "low": 1.08215,
      "close": 1.08245,
      "volume": 1523,
      "asset": "EUR/USD",
      "timeframe": "1m"
    }
  ]
}
```

**Response:**
```json
{
  "signal": {
    "id": "sig_20260404_143025_eurusd_a7b3c",
    "asset": "EUR/USD",
    "direction": "UP",
    "confidence": 78.5,
    ...
  }
}
```

If no signal is generated (insufficient data or low confidence), `signal` is `null`.

---

### Get Settings

```
GET /api/v1/settings
```

**Response:**
```json
{
  "backend_url": "http://localhost:8000",
  "ws_url": "ws://localhost:8000/ws/signals",
  "monitoring_enabled": false,
  "sound_enabled": true,
  "notifications_enabled": true,
  "min_confidence": 60,
  "alert_assets": [],
  "capture_interval_ms": 5000,
  "overlay_enabled": true,
  "overlay_position": "top-right",
  "theme": "dark"
}
```

---

### Update Settings

```
PUT /api/v1/settings
```

**Request Body:** Partial settings object (only include fields to update).

```json
{
  "min_confidence": 70,
  "sound_enabled": false
}
```

**Response:** Updated full settings object.

---

### Get Statistics

```
GET /api/v1/stats
```

**Response:**
```json
{
  "total_signals": 1247,
  "signals_by_direction": { "UP": 634, "DOWN": 613 },
  "signals_by_confidence": { "high": 312, "medium": 589, "low": 346 },
  "average_confidence": 58.3,
  "assets_monitored": ["EUR/USD", "GBP/USD", "BTC/USD"]
}
```

---

### Get Daily Statistics

```
GET /api/v1/stats/daily?date=2026-04-04
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| date | string | today | Date in YYYY-MM-DD format |

**Response:**
```json
{
  "date": "2026-04-04",
  "total_signals": 42,
  "signals_by_hour": {
    "09": 3, "10": 5, "11": 8, "12": 4, "13": 6, "14": 7, "15": 9
  },
  "top_assets": [
    { "asset": "EUR/USD", "count": 18 },
    { "asset": "GBP/USD", "count": 12 },
    { "asset": "BTC/USD", "count": 8 }
  ]
}
```

---

### WebSocket: Signal Stream

```
WS /ws/signals
```

Connects to the real-time signal stream. All new signals are broadcast to connected clients.

**Incoming Messages (server to client):**

Signal:
```json
{
  "type": "signal",
  "data": { "id": "...", "asset": "EUR/USD", ... },
  "timestamp": "2026-04-04T14:30:25.000Z"
}
```

Heartbeat:
```json
{
  "type": "heartbeat",
  "data": null,
  "timestamp": "2026-04-04T14:30:00.000Z"
}
```

Status:
```json
{
  "type": "status",
  "data": { "connected_clients": 3 },
  "timestamp": "2026-04-04T14:30:00.000Z"
}
```

**Outgoing Messages (client to server):**

Ping:
```json
{
  "type": "ping",
  "timestamp": "2026-04-04T14:30:00.000Z"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error description",
  "status_code": 404
}
```

| Status Code | Meaning |
|------------|---------|
| 400 | Bad request / invalid parameters |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Resource not found |
| 422 | Validation error |
| 500 | Internal server error |

## Static Files

| Path | Description |
|------|-------------|
| `/static/sounds/alert-up.mp3` | UP alert sound |
| `/static/sounds/alert-down.mp3` | DOWN alert sound |
| `/static/sounds/alert-generic.mp3` | Generic alert sound |
