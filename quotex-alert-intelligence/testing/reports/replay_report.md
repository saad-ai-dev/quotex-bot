# Historical Replay Validation Report
**Date:** 2026-04-04T11:17:09.507968+00:00
**Total Alerts:** 150

## Summary Metrics
- Wins: 67
- Losses: 7
- Neutral: 0
- Unknown: 0
- No-Trade: 76
- **Win Rate (excl. neutral/unknown):** 90.54%
- **Avg Confidence:** 44.04
- **No-Trade Rate:** 50.67%

## Directional Precision
- UP Precision: 83.72%
- DOWN Precision: 100.0%

## Confidence Calibration
- 50-60: 92.0% win rate
- 60-70: 89.8% win rate

## High-Confidence Signals (>=70)
- Total: 0
- Wins: 0
- Losses: 0
- Win Rate: 0.0%

## Market Breakdown
### LIVE: total=108, wins=59, losses=2, win_rate=96.72%, avg_conf=49.39
### OTC: total=42, wins=8, losses=5, win_rate=61.54%, avg_conf=30.29

## Expiry Breakdown
### 1m: total=50, wins=24, losses=3, win_rate=88.89%
### 2m: total=50, wins=21, losses=2, win_rate=91.3%
### 3m: total=50, wins=22, losses=2, win_rate=91.67%

## Failure Analysis
### otc_overfit (4 occurrences)
  - replay_958ad4aa: conf=64.92, predicted=UP, actual=bearish
  - replay_f37f475f: conf=65.76, predicted=UP, actual=bearish
  - replay_f6cd90bc: conf=63.92, predicted=UP, actual=bearish

### alert_in_chop_conditions (3 occurrences)
  - replay_0dbe0d86: conf=51.79, predicted=UP, actual=bearish
  - replay_4534834d: conf=66.54, predicted=UP, actual=bearish
  - replay_313f271d: conf=59.75, predicted=UP, actual=bearish
