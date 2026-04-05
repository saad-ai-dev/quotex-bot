# API Reference

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

If `API_KEY` is set in the environment, all requests must include the header:

```
X-API-Key: your-api-key
```

If `API_KEY` is empty or not set, authentication is disabled.

## Endpoints

---

### Health Check

#### `GET /api/v1/health`

Returns the health status of the backend and database connection.

**Request:**
```
GET /api/v1/health
```

**Response (200):**
```json
{
  "status": "ok",
  "database": "connected",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

**Response (503):**
```json
{
  "status": "error",
  "database": "disconnected",
  "version": "1.0.0",
  "error": "Cannot connect to MongoDB"
}
```

---

### Signals

#### `POST /api/v1/signals`

Submit chart data for scoring analysis. The scoring engine evaluates the data and returns a signal (or no signal if thresholds are not met).

**Request:**
```json
{
  "asset": "EUR/USD",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "candles": [
    {
      "timestamp": "2026-04-04T14:29:00.000Z",
      "open": 1.0840,
      "high": 1.0845,
      "low": 1.0838,
      "close": 1.0843
    },
    {
      "timestamp": "2026-04-04T14:30:00.000Z",
      "open": 1.0843,
      "high": 1.0850,
      "low": 1.0841,
      "close": 1.0848
    }
  ],
  "metadata": {
    "source": "chart_observation",
    "parsing_errors": 0,
    "candles_expected": 60
  }
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `asset` | string | yes | Trading pair name |
| `market_type` | string | yes | `"LIVE"` or `"OTC"` |
| `expiry_profile` | string | yes | `"1m"`, `"2m"`, or `"3m"` |
| `candles` | array | yes | Array of OHLC candle objects |
| `candles[].timestamp` | string | yes | ISO 8601 datetime |
| `candles[].open` | number | yes | Open price |
| `candles[].high` | number | yes | High price |
| `candles[].low` | number | yes | Low price |
| `candles[].close` | number | yes | Close price |
| `metadata` | object | no | Parsing quality metadata |

**Response (201) - Signal Generated:**
```json
{
  "signal_generated": true,
  "signal": {
    "_id": "sig_20260404_EURUSD_1m_001",
    "asset": "EUR/USD",
    "market_type": "LIVE",
    "expiry_profile": "1m",
    "direction": "CALL",
    "confidence": 72.5,
    "timestamp": "2026-04-04T14:30:00.000Z",
    "expiry_at": "2026-04-04T14:31:00.000Z",
    "status": "PENDING",
    "scores": { "...": "..." },
    "penalties": { "...": "..." },
    "raw_confidence": 76.9,
    "bullish_score": 72.5,
    "bearish_score": 27.5,
    "alert_text": "CALL EUR/USD | Confidence: 72.5% | Expiry: 1m"
  }
}
```

**Response (200) - No Signal (thresholds not met):**
```json
{
  "signal_generated": false,
  "reason": "confidence_below_threshold",
  "details": {
    "raw_confidence": 52.3,
    "min_confidence": 65,
    "bullish_score": 52.3,
    "bearish_score": 47.7,
    "direction_margin_required": 15,
    "actual_margin": 4.6
  }
}
```

**Response (422) - Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "candles"],
      "msg": "ensure this value has at least 5 items",
      "type": "value_error.list.min_items"
    }
  ]
}
```

---

#### `GET /api/v1/signals`

List recent signals with optional filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max signals to return (1-100) |
| `offset` | int | 0 | Pagination offset |
| `asset` | string | null | Filter by asset |
| `market_type` | string | null | Filter by LIVE or OTC |
| `expiry_profile` | string | null | Filter by expiry profile |
| `direction` | string | null | Filter by CALL or PUT |
| `min_confidence` | float | null | Minimum confidence filter |
| `status` | string | null | Filter by status |

**Request:**
```
GET /api/v1/signals?limit=10&market_type=LIVE&min_confidence=65
```

**Response (200):**
```json
{
  "signals": [
    {
      "_id": "sig_20260404_EURUSD_1m_001",
      "asset": "EUR/USD",
      "direction": "CALL",
      "confidence": 72.5,
      "timestamp": "2026-04-04T14:30:00.000Z",
      "status": "PENDING",
      "alert_text": "CALL EUR/USD | Confidence: 72.5% | Expiry: 1m"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

#### `GET /api/v1/signals/{signal_id}`

Get full details of a specific signal including all scores and penalties.

**Request:**
```
GET /api/v1/signals/sig_20260404_EURUSD_1m_001
```

**Response (200):**
```json
{
  "_id": "sig_20260404_EURUSD_1m_001",
  "asset": "EUR/USD",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "direction": "CALL",
  "confidence": 72.5,
  "scores": { "...": "full breakdown" },
  "penalties": { "...": "full breakdown" },
  "raw_confidence": 76.9,
  "bullish_score": 72.5,
  "bearish_score": 27.5,
  "parsing_metadata": { "...": "..." },
  "alert_text": "CALL EUR/USD | Confidence: 72.5% | Expiry: 1m",
  "created_at": "2026-04-04T14:30:00.000Z"
}
```

**Response (404):**
```json
{
  "detail": "Signal not found"
}
```

---

#### `PATCH /api/v1/signals/{signal_id}/resolve`

Record the outcome of a signal after its expiry window has passed.

**Request:**
```json
{
  "entry_price": 1.0842,
  "exit_price": 1.0849,
  "outcome": "WIN"
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `entry_price` | number | yes | Price when signal was generated |
| `exit_price` | number | yes | Price at expiry |
| `outcome` | string | yes | `"WIN"`, `"LOSS"`, or `"NEUTRAL"` |

**Response (200):**
```json
{
  "signal_id": "sig_20260404_EURUSD_1m_001",
  "status": "WIN",
  "result": {
    "entry_price": 1.0842,
    "exit_price": 1.0849,
    "outcome": "WIN",
    "resolved_at": "2026-04-04T14:31:05.000Z"
  }
}
```

**Response (400):**
```json
{
  "detail": "Signal already resolved"
}
```

---

### History

#### `GET /api/v1/history`

Get resolved signal history with optional filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max entries to return (1-500) |
| `offset` | int | 0 | Pagination offset |
| `asset` | string | null | Filter by asset |
| `market_type` | string | null | Filter by LIVE or OTC |
| `outcome` | string | null | Filter by WIN, LOSS, or NEUTRAL |
| `min_confidence` | float | null | Minimum confidence filter |
| `start_date` | string | null | ISO 8601 start date |
| `end_date` | string | null | ISO 8601 end date |

**Request:**
```
GET /api/v1/history?limit=20&outcome=WIN&market_type=LIVE
```

**Response (200):**
```json
{
  "history": [
    {
      "_id": "sig_20260404_EURUSD_1m_001",
      "asset": "EUR/USD",
      "direction": "CALL",
      "confidence": 72.5,
      "result": {
        "outcome": "WIN",
        "entry_price": 1.0842,
        "exit_price": 1.0849
      },
      "timestamp": "2026-04-04T14:30:00.000Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### Analytics

#### `GET /api/v1/analytics`

Get performance analytics and statistics.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | "daily" | `"daily"`, `"weekly"`, or `"monthly"` |
| `market_type` | string | null | Filter by LIVE or OTC |
| `asset` | string | null | Filter by specific asset |
| `start_date` | string | null | ISO 8601 start date |
| `end_date` | string | null | ISO 8601 end date |

**Request:**
```
GET /api/v1/analytics?period=daily&market_type=LIVE
```

**Response (200):**
```json
{
  "analytics": {
    "period": "daily",
    "date": "2026-04-04",
    "market_type": "LIVE",
    "stats": {
      "total_signals": 45,
      "wins": 28,
      "losses": 14,
      "neutrals": 3,
      "win_rate": 62.2,
      "avg_confidence": 68.4,
      "avg_confidence_wins": 72.1,
      "avg_confidence_losses": 63.8,
      "calls": 26,
      "puts": 19,
      "call_win_rate": 65.4,
      "put_win_rate": 57.9
    },
    "penalty_stats": {
      "avg_total_penalty": 4.2,
      "avg_conflict_penalty": 1.8,
      "avg_chop_penalty": 0.9
    }
  }
}
```

---

### Settings

#### `GET /api/v1/settings`

Get current settings.

**Request:**
```
GET /api/v1/settings
```

**Response (200):**
```json
{
  "_id": "default_settings",
  "active_profile": "live_1m",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "alerts_enabled": true,
  "sound_enabled": true,
  "notification_enabled": true,
  "filters": {
    "min_confidence": 60,
    "assets": [],
    "directions": ["CALL", "PUT"],
    "market_types": ["LIVE", "OTC"]
  },
  "display": {
    "theme": "dark",
    "compact_mode": false,
    "show_penalties": true,
    "show_component_scores": true
  }
}
```

---

#### `PUT /api/v1/settings`

Update settings. Supports partial updates (only provided fields are changed).

**Request:**
```json
{
  "active_profile": "live_2m",
  "market_type": "LIVE",
  "expiry_profile": "2m",
  "filters": {
    "min_confidence": 70
  }
}
```

**Response (200):**
```json
{
  "message": "Settings updated",
  "settings": {
    "_id": "default_settings",
    "active_profile": "live_2m",
    "market_type": "LIVE",
    "expiry_profile": "2m",
    "filters": {
      "min_confidence": 70,
      "assets": [],
      "directions": ["CALL", "PUT"],
      "market_types": ["LIVE", "OTC"]
    }
  }
}
```

---

### Profiles

#### `GET /api/v1/profiles`

List all available scoring profiles.

**Request:**
```
GET /api/v1/profiles
```

**Response (200):**
```json
{
  "profiles": [
    {
      "name": "live_1m",
      "market_type": "LIVE",
      "expiry_profile": "1m",
      "weights": { "...": "..." },
      "thresholds": { "...": "..." }
    },
    {
      "name": "live_2m",
      "market_type": "LIVE",
      "expiry_profile": "2m",
      "weights": { "...": "..." },
      "thresholds": { "...": "..." }
    },
    {
      "name": "live_3m",
      "market_type": "LIVE",
      "expiry_profile": "3m",
      "weights": { "...": "..." },
      "thresholds": { "...": "..." }
    },
    {
      "name": "otc_1m",
      "market_type": "OTC",
      "expiry_profile": "1m",
      "weights": { "...": "..." },
      "thresholds": { "...": "..." }
    },
    {
      "name": "otc_2m",
      "market_type": "OTC",
      "expiry_profile": "2m",
      "weights": { "...": "..." },
      "thresholds": { "...": "..." }
    },
    {
      "name": "otc_3m",
      "market_type": "OTC",
      "expiry_profile": "3m",
      "weights": { "...": "..." },
      "thresholds": { "...": "..." }
    }
  ]
}
```

---

### WebSocket

#### `WS /ws/signals`

Real-time signal stream. The server pushes new signals to all connected clients as they are generated.

**Connection:**
```
ws://localhost:8000/ws/signals
```

If authentication is enabled, pass the API key as a query parameter:
```
ws://localhost:8000/ws/signals?api_key=your-key
```

**Server Messages:**

New signal:
```json
{
  "type": "new_signal",
  "data": {
    "_id": "sig_20260404_EURUSD_1m_001",
    "asset": "EUR/USD",
    "direction": "CALL",
    "confidence": 72.5,
    "expiry_profile": "1m",
    "timestamp": "2026-04-04T14:30:00.000Z",
    "alert_text": "CALL EUR/USD | Confidence: 72.5% | Expiry: 1m"
  }
}
```

Signal resolved:
```json
{
  "type": "signal_resolved",
  "data": {
    "_id": "sig_20260404_EURUSD_1m_001",
    "status": "WIN",
    "result": {
      "outcome": "WIN",
      "entry_price": 1.0842,
      "exit_price": 1.0849
    }
  }
}
```

Heartbeat (every 30 seconds):
```json
{
  "type": "heartbeat",
  "timestamp": "2026-04-04T14:30:30.000Z"
}
```

**Client Messages:**

Subscribe to specific assets (optional):
```json
{
  "type": "subscribe",
  "assets": ["EUR/USD", "GBP/USD"]
}
```

Unsubscribe:
```json
{
  "type": "unsubscribe",
  "assets": ["GBP/USD"]
}
```

## Error Responses

All error responses follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created (new signal) |
| 400 | Bad request (invalid input or state) |
| 401 | Unauthorized (missing or invalid API key) |
| 404 | Not found |
| 422 | Validation error (Pydantic) |
| 500 | Internal server error |
| 503 | Service unavailable (database down) |

## Rate Limiting

Currently no rate limiting is implemented. This is intended for local/personal use. If deploying publicly, add rate limiting middleware.
