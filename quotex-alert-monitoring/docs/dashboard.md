# Dashboard Pages Documentation

> **ALERT-ONLY** -- The dashboard displays monitoring data. It does not provide trade execution controls.

## Overview

The dashboard is a React web application that connects to the backend API. It provides historical signal data, statistics, and configuration management.

## Pages

### Signals Page

The primary view for reviewing detected signals.

**Features:**
- Real-time signal feed via WebSocket subscription
- Paginated signal list (default 20 per page)
- Sortable by timestamp, confidence, asset, direction
- Status badges: pending, active, expired, confirmed, rejected

**Filters:**
- Asset name (dropdown or search)
- Direction: UP, DOWN, or All
- Confidence tier: High, Medium, Low, or All
- Minimum confidence percentage (slider)
- Status filter
- Date range picker

**Signal Card Content:**
- Asset name and direction arrow
- Confidence score and tier badge
- Entry price at signal time
- Timestamp and expiry countdown
- Indicator summary (RSI, MACD, Bollinger position)
- Scoring breakdown (expandable)

### Statistics Page

Aggregated analytics of monitoring activity.

**Daily Overview:**
- Total signals detected
- Signals by direction (UP vs DOWN pie chart)
- Signals by confidence tier (bar chart)
- Average confidence score
- Hourly distribution (heatmap or line chart)

**Asset Breakdown:**
- Top monitored assets by signal count
- Per-asset confidence averages
- Direction distribution per asset

**Trend Analysis:**
- 7-day rolling signal count
- Confidence trend over time
- Detection rate by hour of day

### Settings Page

Configuration for the monitoring system.

**Backend Configuration:**
- API URL
- WebSocket URL
- API key (masked input)

**Alert Configuration:**
- Minimum confidence threshold (0-100 slider)
- Alert asset filter (multi-select)
- Sound enable/disable
- Notification enable/disable

**Scoring Engine Weights:**
- Trend weight (0-100)
- Momentum weight (0-100)
- Volatility weight (0-100)
- Volume weight (0-100)
- Pattern weight (0-100)
- Live preview of how weight changes affect scoring

**Confidence Tiers:**
- High threshold (default 75)
- Medium threshold (default 50)

**Display Settings:**
- Theme (dark/light)
- Default page size
- Auto-refresh interval

## Real-Time Updates

The dashboard maintains a WebSocket connection to receive live signals. When a new signal is detected:

1. A toast notification appears in the top-right
2. The signals list prepends the new entry (if on the Signals page)
3. Statistics counters increment
4. The latest signal card highlights briefly

## API Integration

The dashboard consumes the following endpoints:

| Page | Endpoints Used |
|------|---------------|
| Signals | `GET /api/v1/signals`, `GET /api/v1/signals/{id}` |
| Statistics | `GET /api/v1/stats`, `GET /api/v1/stats/daily` |
| Settings | `GET /api/v1/settings`, `PUT /api/v1/settings` |
| All | `WS /ws/signals` |
