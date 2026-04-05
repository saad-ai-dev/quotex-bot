# Limitations

This document outlines the known limitations, constraints, and caveats of the Quotex Alert Intelligence system. Understanding these limitations is essential for appropriate use of the system.

## Fundamental Limitations

### Probabilistic, Not Predictive

The confidence scores produced by the scoring engine represent a weighted assessment of technical analysis factors. They are **not** probabilities of a particular outcome. A signal with 75% confidence does not mean there is a 75% chance the price will move in the indicated direction. It means that 75% of the analytical weight (after penalties) supports that direction.

### No Financial Guarantees

This system provides informational alerts only. Past signal accuracy, even if tracked over extended periods, does not predict future results. Markets are inherently unpredictable, and no technical analysis system can consistently predict short-term price movements with reliability.

### Alert-Only System

This system does **not**:
- Execute trades on any platform
- Manage funds or account balances
- Interact with the Quotex platform API
- Place orders of any kind
- Access or store financial account credentials

It is purely an observation and analysis tool that generates informational alerts.

## Technical Limitations

### DOM-Based Parsing

The Chrome extension extracts chart data by observing the DOM (Document Object Model) of the Quotex chart page. This approach has several inherent limitations:

1. **DOM changes**: If Quotex updates their chart rendering code, CSS class names, or DOM structure, the parser may break or produce incorrect data without warning.

2. **Parsing accuracy**: DOM-based extraction is less precise than direct API data access. Small rendering differences, anti-aliasing, or canvas-based charts may introduce parsing errors.

3. **Missing data**: Not all data visible on the chart may be accessible via DOM inspection. Some data may be rendered on HTML5 canvas elements that cannot be parsed from the DOM.

4. **Timing gaps**: There is an inherent delay between when a candle forms on the chart and when the parser extracts and processes it. For 1-minute expiry windows, even sub-second delays affect the relevance of the analysis.

5. **Browser dependency**: The extension runs within Chrome's extension sandbox. Browser performance, tab suspension, and resource constraints can affect parsing reliability.

### No Direct Volume Data

The Quotex chart does not expose volume data in a DOM-accessible format. The `volume_proxy` scoring dimension uses candle body/wick characteristics as a substitute for volume analysis. This is a significantly less reliable indicator than actual volume data:

- Body size correlates weakly with volume
- Wick patterns are ambiguous without volume context
- Volume proxy cannot distinguish between low-volume breakouts and high-volume breakouts

### Single Timeframe Analysis

The system currently analyzes only the displayed timeframe. It does not perform multi-timeframe analysis (e.g., checking the 5-minute trend while analyzing 1-minute candles). Multi-timeframe confluence is one of the most important aspects of technical analysis, and its absence reduces signal quality.

### Limited Candle History

The parser can only extract candles currently visible on the chart. Depending on the chart zoom level and window size, this may be as few as 30-60 candles for 1-minute charts. Many technical analysis concepts require longer lookback periods for reliable assessment:

- Support/resistance identification benefits from hundreds of candles of history
- Market structure analysis needs sufficient swing points to establish trend
- Pattern recognition accuracy improves with larger sample sizes

### Latency Constraints

The signal generation pipeline introduces latency at multiple points:

1. Chart rendering delay (platform side)
2. DOM observation and parsing delay (extension side)
3. HTTP request to backend (network latency)
4. Scoring engine computation time
5. WebSocket broadcast delay
6. Alert rendering in the popup

For 1-minute expiry windows, cumulative latency of even 2-3 seconds reduces the actionable time window significantly.

## Scoring Engine Limitations

### Weight Subjectivity

The weights assigned to each scoring dimension are based on practitioner judgment, not empirical optimization. Different weight configurations could produce meaningfully different results. There is no guarantee that the default weights are optimal for any particular market condition.

### Static Profiles

Scoring profiles are static configurations. They do not adapt to changing market conditions within a session. A profile optimized for trending conditions will underperform in ranging conditions, and vice versa. The system does not detect regime changes or automatically switch profiles.

### Independence Assumption

The scoring engine treats each dimension as independent, but they are not. For example:
- Support/resistance and supply/demand zones often overlap
- Market structure and price action are inherently correlated
- Order blocks are a subset of supply/demand concepts

This overlap means some directional evidence is effectively double-counted, potentially inflating confidence scores.

### Penalty Calibration

Penalty weights and formulas are heuristic. The conflict penalty, for example, uses a linear formula that may not accurately capture the nonlinear relationship between signal conflict and prediction reliability.

### No Fundamental Analysis

The system performs purely technical analysis. It does not account for:
- Economic news releases and their impact
- Central bank decisions
- Geopolitical events
- Market sentiment shifts
- Correlation between currency pairs
- Session transitions (London/New York/Tokyo)

High-impact news events can cause price movements that completely override technical patterns.

## OTC-Specific Limitations

### Synthetic Pricing

OTC market prices are generated by the platform's algorithms, not by real market supply and demand. This fundamentally undermines the theoretical basis of technical analysis, which assumes that price patterns emerge from aggregate participant behavior.

### Algorithm Opacity

The OTC price generation algorithm is proprietary and opaque. It may change at any time without notice, invalidating any detected patterns.

### Non-Stationarity

Even if OTC patterns are detected accurately, they may not persist. The algorithm may:
- Change cycle lengths during a session
- Introduce randomness periodically
- Adjust behavior based on aggregate user positions
- Update between sessions

### No External Validation

OTC prices cannot be verified against external data sources. There is no way to confirm that the prices displayed are consistent with any external benchmark.

## Operational Limitations

### Single User Design

The system is designed for single-user, local deployment. It does not include:
- User authentication (beyond optional API key)
- Multi-tenant isolation
- Rate limiting
- Audit logging
- Data encryption at rest

### No High Availability

The backend runs as a single process. There is no clustering, failover, or load balancing. If the backend crashes, signals are not generated until it restarts.

### Storage Growth

The `signal_history` collection grows indefinitely. While active signals are cleaned up via TTL index, historical data accumulates without automatic pruning. Long-running deployments should monitor database size.

### No Backup

The system does not include automated database backup. Users are responsible for backing up their MongoDB data.

## Interpretation Guidelines

Given these limitations, signals should be interpreted as:

- **Informational observations**, not trading recommendations
- **One input among many**, not a sole decision source
- **Time-sensitive assessments** that decay rapidly after generation
- **Condition-dependent** - accuracy varies significantly with market regime
- **Profile-dependent** - different profiles produce different signals for the same data

The system is most useful as a structured way to observe and organize chart information, not as a prediction tool.
