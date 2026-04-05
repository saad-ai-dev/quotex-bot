# Scoring Engine

> **ALERT-ONLY** -- The scoring engine calculates confidence scores for informational alerts. Scores are not used to trigger trades.

## Overview

The scoring engine evaluates raw candle data through multiple technical indicators, then combines their signals into a weighted confidence score. The score determines the confidence tier (high/medium/low) of the alert.

## Scoring Categories

### 1. Trend Score (default weight: 25%)

Evaluates the overall price trend direction and strength.

**Indicators used:**
- **EMA Crossover** -- Short-period EMA (9) vs long-period EMA (21) position and slope
- **Price vs EMA** -- Current price position relative to EMA lines
- **Higher highs / Lower lows** -- Sequential candle pattern analysis

**Scoring logic:**
- Strong trend alignment with signal direction: 20-25 points
- Moderate trend alignment: 10-19 points
- Weak or conflicting trend: 0-9 points

### 2. Momentum Score (default weight: 25%)

Measures the speed and strength of price movement.

**Indicators used:**
- **RSI (14)** -- Oversold (<30) for UP signals, overbought (>70) for DOWN signals
- **Stochastic Oscillator (K/D)** -- Crossover signals and extreme zones
- **MACD Histogram** -- Direction and magnitude of histogram bars

**Scoring logic:**
- RSI in extreme zone matching direction: 8-10 points
- Stochastic crossover confirmation: 5-8 points
- MACD histogram direction matching: 5-7 points
- Convergence of all momentum indicators: bonus 2-3 points

### 3. Volatility Score (default weight: 20%)

Assesses market volatility conditions.

**Indicators used:**
- **Bollinger Bands** -- Price position within bands (0 = lower, 1 = upper)
- **ATR (14)** -- Average True Range for volatility magnitude
- **Band width** -- Bollinger Band squeeze/expansion detection

**Scoring logic:**
- Price near lower band + UP signal: 15-20 points (bounce potential)
- Price near upper band + DOWN signal: 15-20 points (reversal potential)
- Normal volatility with clear direction: 8-14 points
- Excessive volatility (unclear direction): 0-7 points

### 4. Volume Score (default weight: 15%)

Evaluates volume confirmation of the signal.

**Indicators used:**
- **Volume Ratio** -- Current volume vs average volume (20 periods)
- **Volume trend** -- Increasing or decreasing volume direction

**Scoring logic:**
- Volume above 1.5x average with matching direction: 12-15 points
- Volume above average (1.0-1.5x): 8-11 points
- Normal volume: 4-7 points
- Below average volume: 0-3 points

### 5. Pattern Score (default weight: 15%)

Identifies candlestick patterns and price formations.

**Patterns detected:**
- Engulfing patterns (bullish/bearish)
- Doji / hammer / shooting star
- Three consecutive candles in direction
- Pin bar formations

**Scoring logic:**
- Strong reversal pattern matching direction: 12-15 points
- Moderate pattern signal: 6-11 points
- Weak or no pattern: 0-5 points

## Confidence Calculation

```
total_score = (trend_score * trend_weight / 100)
            + (momentum_score * momentum_weight / 100)
            + (volatility_score * volatility_weight / 100)
            + (volume_score * volume_weight / 100)
            + (pattern_score * pattern_weight / 100)

confidence = (total_score / max_possible_score) * 100
```

## Confidence Tiers

| Tier | Threshold | Chrome Notification | Sound |
|------|-----------|-------------------|-------|
| High | 75%+ | Priority 2, requires interaction | Direction-specific alert |
| Medium | 50-74% | Priority 1, auto-dismiss | Direction-specific alert |
| Low | Below 50% | Not shown (configurable) | None (configurable) |

## Customization

All weights and thresholds are configurable via the Settings API:

```json
{
  "scoring_weights": {
    "trend": 25,
    "momentum": 25,
    "volatility": 20,
    "volume": 15,
    "pattern": 15
  },
  "confidence_tiers": {
    "high": 75,
    "medium": 50,
    "low": 0
  }
}
```

Weights must sum to 100. The minimum confidence for alerts is separately configurable (default: 60%).

## Limitations

- Indicators are calculated on available data only (may be limited by DOM scraping)
- Pattern detection is basic compared to specialized charting libraries
- No machine learning or adaptive weighting
- Historical accuracy is not tracked (no backtesting)
- Volume data may be unavailable depending on chart scraping success
