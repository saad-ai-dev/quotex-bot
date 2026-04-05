# Scoring Engine

## Overview

The scoring engine is the core analytical component of Quotex Alert Intelligence. It evaluates parsed chart data across 9 independent analysis dimensions, applies weighted scoring based on the active profile, computes penalty deductions, and produces a final directional alert with a confidence percentage.

**Important**: Confidence scores represent the weighted analytical assessment, not a probability of profit. See [limitations.md](limitations.md) for details.

## Analysis Dimensions

Each dimension receives the parsed candle data and produces:
- **raw_score** (0-100): How strongly the dimension supports a directional view
- **direction**: `bullish`, `bearish`, or `neutral`
- **details**: Human-readable explanation of the assessment

### 1. Market Structure (market_structure)

Analyzes the trend context using swing highs and swing lows.

- Identifies higher highs / higher lows (bullish structure)
- Identifies lower highs / lower lows (bearish structure)
- Detects structure breaks (Break of Structure / BOS)
- Detects changes of character (CHoCH)
- Assesses trend strength and consistency

Higher weight in longer expiry profiles where trend matters more.

### 2. Support and Resistance (support_resistance)

Identifies key horizontal price levels and evaluates proximity and reaction.

- Detects significant support and resistance levels from recent price action
- Measures distance from current price to nearest levels
- Evaluates bounce/rejection quality at levels
- Considers level strength based on number of touches
- Assesses whether price is approaching or departing from a level

### 3. Price Action (price_action)

Evaluates candlestick patterns and immediate momentum.

- Single candle patterns: engulfing, pin bar, doji, hammer, shooting star
- Multi-candle patterns: morning/evening star, three soldiers/crows
- Momentum assessment: candle body sizes, consecutive directional candles
- Rejection patterns: long wicks, failed breakouts
- Current candle formation assessment

Highest weight in short-expiry (1m) profiles where immediate price action dominates.

### 4. Liquidity (liquidity)

Analyzes liquidity sweeps and stop hunts.

- Detects sweeps of recent highs/lows
- Identifies liquidity pools (clusters of equal highs/lows)
- Evaluates post-sweep reversal quality
- Assesses whether current price is near liquidity targets
- Detects stop hunt patterns

### 5. Order Blocks (order_blocks)

Identifies institutional order flow zones.

- Detects bullish order blocks (last bearish candle before a strong bullish move)
- Detects bearish order blocks (last bullish candle before a strong bearish move)
- Evaluates order block freshness (untested vs. tested)
- Measures price proximity to active order blocks
- Assesses order block strength based on the move that followed

### 6. Fair Value Gaps (fvg)

Identifies price imbalances (Fair Value Gaps / FVGs).

- Detects bullish FVGs (gap between candle 1 high and candle 3 low)
- Detects bearish FVGs (gap between candle 1 low and candle 3 high)
- Evaluates FVG fill status (unfilled, partially filled, fully filled)
- Measures proximity of current price to open FVGs
- Assesses FVG size relative to average range

### 7. Supply and Demand (supply_demand)

Maps supply and demand zones and evaluates zone interactions.

- Identifies demand zones (strong bullish departures)
- Identifies supply zones (strong bearish departures)
- Evaluates zone freshness and strength
- Detects price entering or departing zones
- Assesses zone overlap with other structural levels

### 8. Volume Proxy (volume_proxy)

Since direct volume data is not available from the chart DOM, this dimension uses candle characteristics as volume proxies.

- Body-to-wick ratio (larger bodies suggest stronger conviction)
- Body size relative to recent average (expansion = increased activity)
- Consecutive body size changes (increasing = momentum, decreasing = exhaustion)
- Wick direction and size patterns
- Candle range expansion/contraction

### 9. OTC Patterns (otc_patterns)

Specialized analysis for OTC (Over-The-Counter) markets which have synthetic pricing.

- Cycle detection: OTC markets often exhibit repetitive patterns
- Mean reversion tendency: OTC prices tend to oscillate around a mean
- Pattern repetition: detection of recurring candle sequences
- Timing patterns: cycle duration and phase estimation
- Anomaly detection: identification of pattern breaks

This dimension has zero weight in LIVE profiles and significant weight (20-25) in OTC profiles.

## Weight Profiles

Weights determine the relative importance of each dimension. They must sum to 100.

### LIVE Market Profiles

| Dimension | 1m | 2m | 3m |
|-----------|-----|-----|-----|
| market_structure | 12 | 15 | 18 |
| support_resistance | 15 | 15 | 15 |
| price_action | 25 | 20 | 18 |
| liquidity | 10 | 10 | 9 |
| order_blocks | 10 | 10 | 9 |
| fvg | 8 | 8 | 7 |
| supply_demand | 10 | 10 | 12 |
| volume_proxy | 10 | 12 | 12 |
| otc_patterns | 0 | 0 | 0 |

Key observations:
- **1m**: Heavily weighted toward price_action (25) since immediate candle patterns are most relevant for 60-second windows.
- **2m**: More balanced, with increased market_structure weight as trend context becomes more relevant.
- **3m**: Highest market_structure (18) and supply_demand (12) weights, as structural levels have more time to play out.

### OTC Market Profiles

| Dimension | 1m | 2m | 3m |
|-----------|-----|-----|-----|
| market_structure | 8 | 10 | 12 |
| support_resistance | 12 | 13 | 14 |
| price_action | 18 | 15 | 13 |
| liquidity | 8 | 8 | 7 |
| order_blocks | 8 | 8 | 7 |
| fvg | 6 | 6 | 6 |
| supply_demand | 8 | 10 | 12 |
| volume_proxy | 7 | 8 | 9 |
| otc_patterns | 25 | 22 | 20 |

Key observations:
- **otc_patterns** carries the highest weight (20-25) since OTC markets have synthetic pricing with detectable cycles.
- Traditional technical analysis dimensions have reduced weights since they are less reliable on synthetic data.
- Lower confidence thresholds reflect the inherently lower predictability of OTC markets.

## Scoring Computation

### Step 1: Raw Score Calculation

Each dimension independently analyzes the candle data and produces a `raw_score` from 0 to 100:
- 0-20: Strong opposing signal
- 21-40: Weak opposing signal
- 41-60: Neutral / insufficient data
- 61-80: Moderate supporting signal
- 81-100: Strong supporting signal

### Step 2: Weighted Score Calculation

```
weighted_score = raw_score * (weight / 100)
```

For example, if price_action raw_score is 75 and its weight is 25:
```
weighted_score = 75 * (25 / 100) = 18.75
```

### Step 3: Direction Aggregation

Bullish and bearish scores are aggregated separately:

```
bullish_total = sum of weighted_scores where direction == "bullish"
bearish_total = sum of weighted_scores where direction == "bearish"
neutral_total = sum of weighted_scores where direction == "neutral"
```

Neutral scores are distributed proportionally:
```
bullish_share = neutral_total * (bullish_total / (bullish_total + bearish_total))
bearish_share = neutral_total * (bearish_total / (bullish_total + bearish_total))
```

### Step 4: Direction Decision

```
if bullish_total > bearish_total + direction_margin:
    direction = "CALL"
    raw_confidence = bullish_total + bullish_share
elif bearish_total > bullish_total + direction_margin:
    direction = "PUT"
    raw_confidence = bearish_total + bearish_share
else:
    direction = None  # No signal - too close to call
```

### Step 5: Penalty Application

See the Penalties section below.

### Step 6: Final Confidence

```
final_confidence = raw_confidence - total_penalty
```

If `final_confidence < min_confidence`, no alert is generated.

## Penalties

Penalties reduce the confidence score to account for various risk factors. Each penalty type has a weight multiplier that controls its impact.

### Conflict Penalty (conflict_weight)

Applied when dimensions disagree on direction.

```
conflict_count = number of dimensions with opposite direction to the majority
conflict_ratio = conflict_count / total_active_dimensions
conflict_penalty = conflict_ratio * 20 * conflict_weight
```

A `conflict_weight` of 1.2 (LIVE) amplifies this penalty because conflicting signals in real markets are a strong warning sign.

### Chop Penalty (chop_weight)

Applied when the market appears to be ranging/choppy.

```
chop_score = measure of price oscillation without clear direction
chop_penalty = chop_score * 15 * chop_weight
```

Indicators: small candle bodies, alternating directions, narrow range, many doji candles.

### Weak Data Penalty (weak_data_weight)

Applied when there is insufficient candle data for reliable analysis.

```
data_completeness = candles_available / candles_expected
weak_penalty = (1 - data_completeness) * 10 * weak_data_weight
```

### Parsing Quality Penalty (parsing_quality_weight)

Applied when the chart data parsing had errors or quality issues.

```
error_ratio = parsing_errors / candles_parsed
quality_penalty = error_ratio * 15 * parsing_quality_weight
```

### Timing Penalty (timing_weight)

Applied when the signal is generated too close to the candle close.

```
seconds_remaining = expiry_seconds - elapsed_since_candle_open
if seconds_remaining < min_seconds_before_close:
    timing_penalty = 10 * timing_weight
```

### Total Penalty

```
total_penalty = conflict_penalty + chop_penalty + weak_penalty + quality_penalty + timing_penalty
```

## Thresholds

| Parameter | Description | Typical LIVE | Typical OTC |
|-----------|-------------|-------------|-------------|
| min_confidence | Minimum final confidence to emit an alert | 60-65 | 55-60 |
| direction_margin | Minimum gap between bull/bear scores | 15 | 12 |
| min_bullish | Minimum bullish score for a CALL alert | 55 | 50 |
| min_bearish | Minimum bearish score for a PUT alert | 55 | 50 |

## Custom Profiles

Users can override weights, thresholds, and penalties through the settings API. Custom overrides are stored in the `scoring_overrides` field of the settings document.

When custom overrides are active, they are merged with the base profile:

```python
effective_weights = {**base_profile.weights, **custom_overrides.custom_weights}
```

This allows partial overrides - you can change just one or two weights without specifying all of them.
