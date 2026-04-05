# MongoDB Schema Reference

## Database

Default database name: `quotex_alerts` (configurable via `MONGODB_DB_NAME` environment variable).

## Collections

### signals

Active signals that have not yet expired or been resolved. Documents are automatically removed after 7 days via TTL index.

#### Document Shape

```json
{
  "_id": "sig_20260404_EURUSD_1m_001",
  "asset": "EUR/USD",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "direction": "CALL",
  "confidence": 72.5,
  "timestamp": "2026-04-04T14:30:00.000Z",
  "expiry_at": "2026-04-04T14:31:00.000Z",
  "status": "PENDING",
  "scores": {
    "market_structure": {
      "raw_score": 75,
      "weighted_score": 9.0,
      "direction": "bullish",
      "details": "Higher highs and higher lows confirmed."
    },
    "support_resistance": {
      "raw_score": 80,
      "weighted_score": 12.0,
      "direction": "bullish",
      "details": "Price bounced off key support at 1.0842."
    },
    "price_action": {
      "raw_score": 70,
      "weighted_score": 17.5,
      "direction": "bullish",
      "details": "Bullish engulfing candle at support."
    },
    "liquidity": {
      "raw_score": 65,
      "weighted_score": 6.5,
      "direction": "bullish",
      "details": "Liquidity sweep below recent low."
    },
    "order_blocks": {
      "raw_score": 60,
      "weighted_score": 6.0,
      "direction": "neutral",
      "details": "Minor bullish order block nearby."
    },
    "fvg": {
      "raw_score": 55,
      "weighted_score": 4.4,
      "direction": "bullish",
      "details": "Small FVG partially filled."
    },
    "supply_demand": {
      "raw_score": 72,
      "weighted_score": 7.2,
      "direction": "bullish",
      "details": "In demand zone."
    },
    "volume_proxy": {
      "raw_score": 68,
      "weighted_score": 6.8,
      "direction": "bullish",
      "details": "Increasing body sizes suggest buying pressure."
    },
    "otc_patterns": {
      "raw_score": 0,
      "weighted_score": 0,
      "direction": "neutral",
      "details": "Not applicable for LIVE market."
    }
  },
  "penalties": {
    "conflict_penalty": 2.1,
    "chop_penalty": 0.0,
    "weak_data_penalty": 1.5,
    "parsing_quality_penalty": 0.8,
    "timing_penalty": 0.0,
    "total_penalty": 4.4
  },
  "raw_confidence": 76.9,
  "bullish_score": 72.5,
  "bearish_score": 27.5,
  "parsing_metadata": {
    "candles_parsed": 60,
    "parsing_errors": 0,
    "data_quality": "good",
    "source": "chart_observation"
  },
  "alert_text": "CALL EUR/USD | Confidence: 72.5% | Expiry: 1m | Bullish engulfing at support",
  "created_at": "2026-04-04T14:30:00.000Z",
  "updated_at": "2026-04-04T14:30:00.000Z"
}
```

#### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | Unique signal identifier (format: `sig_{date}_{asset}_{expiry}_{seq}`) |
| `asset` | string | Trading pair name (e.g., "EUR/USD", "EUR/USD (OTC)") |
| `market_type` | string | `"LIVE"` or `"OTC"` |
| `expiry_profile` | string | `"1m"`, `"2m"`, or `"3m"` |
| `direction` | string | `"CALL"` or `"PUT"` |
| `confidence` | number | Final confidence score after penalties (0-100) |
| `timestamp` | datetime | When the signal was generated |
| `expiry_at` | datetime | When the signal expires |
| `status` | string | `"PENDING"`, `"WIN"`, `"LOSS"`, or `"NEUTRAL"` |
| `scores` | object | Per-dimension scoring breakdown |
| `penalties` | object | Penalty breakdown |
| `raw_confidence` | number | Confidence before penalty deductions |
| `bullish_score` | number | Total bullish weighted score |
| `bearish_score` | number | Total bearish weighted score |
| `parsing_metadata` | object | Information about the source data quality |
| `alert_text` | string | Human-readable alert summary |
| `created_at` | datetime | Document creation time |
| `updated_at` | datetime | Last update time |

#### Indexes

| Name | Keys | Options |
|------|------|---------|
| `idx_timestamp_desc` | `{ timestamp: -1 }` | |
| `idx_asset_market_timestamp` | `{ asset: 1, market_type: 1, timestamp: -1 }` | |
| `idx_status_timestamp` | `{ status: 1, timestamp: -1 }` | |
| `idx_direction_confidence` | `{ direction: 1, confidence: -1 }` | |
| `idx_expiry_status` | `{ expiry_at: 1, status: 1 }` | |
| `idx_market_expiry_timestamp` | `{ market_type: 1, expiry_profile: 1, timestamp: -1 }` | |
| `idx_confidence_timestamp` | `{ confidence: -1, timestamp: -1 }` | |
| `idx_ttl_created` | `{ created_at: 1 }` | `expireAfterSeconds: 604800` (7 days) |

---

### signal_history

Resolved signals with outcome data. Used for performance tracking and analytics.

#### Document Shape

Same as `signals` but with an additional `result` field:

```json
{
  "_id": "sig_20260404_EURUSD_1m_001",
  "asset": "EUR/USD",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "direction": "CALL",
  "confidence": 72.5,
  "timestamp": "2026-04-04T14:30:00.000Z",
  "expiry_at": "2026-04-04T14:31:00.000Z",
  "status": "WIN",
  "result": {
    "entry_price": 1.0842,
    "exit_price": 1.0849,
    "outcome": "WIN",
    "resolved_at": "2026-04-04T14:31:00.000Z"
  },
  "scores": { "..." : "..." },
  "penalties": { "..." : "..." },
  "raw_confidence": 76.9,
  "bullish_score": 72.5,
  "bearish_score": 27.5,
  "alert_text": "CALL EUR/USD | Confidence: 72.5% | Expiry: 1m",
  "created_at": "2026-04-04T14:30:00.000Z"
}
```

#### Result Field

| Field | Type | Description |
|-------|------|-------------|
| `result.entry_price` | number | Price at signal generation |
| `result.exit_price` | number | Price at expiry |
| `result.outcome` | string | `"WIN"`, `"LOSS"`, or `"NEUTRAL"` |
| `result.resolved_at` | datetime | When the outcome was recorded |

#### Indexes

| Name | Keys |
|------|------|
| `idx_history_timestamp` | `{ timestamp: -1 }` |
| `idx_history_asset_timestamp` | `{ asset: 1, timestamp: -1 }` |
| `idx_history_outcome_timestamp` | `{ "result.outcome": 1, timestamp: -1 }` |
| `idx_history_market_expiry_timestamp` | `{ market_type: 1, expiry_profile: 1, timestamp: -1 }` |
| `idx_history_confidence` | `{ confidence: -1 }` |

---

### settings

User configuration and preferences. Typically contains a single document with `_id: "default_settings"`.

#### Document Shape

```json
{
  "_id": "default_settings",
  "active_profile": "live_1m",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "alerts_enabled": true,
  "sound_enabled": true,
  "notification_enabled": true,
  "auto_refresh_interval_ms": 5000,
  "max_signals_displayed": 50,
  "signal_retention_hours": 24,
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
    "show_component_scores": true,
    "show_parsing_metadata": false
  },
  "scoring_overrides": {
    "custom_weights": null,
    "custom_thresholds": null,
    "custom_penalties": null
  },
  "history": {
    "track_results": true,
    "max_history_entries": 1000,
    "export_format": "json"
  },
  "created_at": "2026-04-04T00:00:00.000Z",
  "updated_at": "2026-04-04T00:00:00.000Z"
}
```

#### Indexes

| Name | Keys | Options |
|------|------|---------|
| `idx_settings_id` | `{ _id: 1 }` | `unique: true` |

---

### analytics

Pre-computed analytics and performance statistics.

#### Document Shape

```json
{
  "_id": "analytics_live_1m_2026-04-04",
  "period": "daily",
  "date": "2026-04-04",
  "market_type": "LIVE",
  "expiry_profile": "1m",
  "asset": "ALL",
  "stats": {
    "total_signals": 45,
    "wins": 28,
    "losses": 14,
    "neutrals": 3,
    "win_rate": 62.2,
    "avg_confidence": 68.4,
    "avg_confidence_wins": 72.1,
    "avg_confidence_losses": 63.8,
    "highest_confidence": 82.3,
    "lowest_confidence": 60.1,
    "calls": 26,
    "puts": 19,
    "call_win_rate": 65.4,
    "put_win_rate": 57.9
  },
  "penalty_stats": {
    "avg_total_penalty": 4.2,
    "avg_conflict_penalty": 1.8,
    "avg_chop_penalty": 0.9,
    "avg_weak_data_penalty": 0.8,
    "avg_parsing_penalty": 0.5,
    "avg_timing_penalty": 0.2
  },
  "calculated_at": "2026-04-04T23:59:59.000Z"
}
```

#### Indexes

| Name | Keys |
|------|------|
| `idx_analytics_period_market` | `{ period: 1, market_type: 1 }` |
| `idx_analytics_asset_period` | `{ asset: 1, period: 1 }` |
| `idx_analytics_calculated_at` | `{ calculated_at: -1 }` |

## Data Lifecycle

1. **Signal Creation**: New signals are inserted into `signals` with status `"PENDING"`.
2. **Signal Resolution**: When resolved, status is updated to `"WIN"`, `"LOSS"`, or `"NEUTRAL"` and a `result` field is added.
3. **History Migration**: Resolved signals are copied to `signal_history` for permanent storage.
4. **TTL Cleanup**: The TTL index on `signals.created_at` automatically removes documents older than 7 days.
5. **Analytics Update**: Analytics documents are computed periodically from `signal_history` data.
