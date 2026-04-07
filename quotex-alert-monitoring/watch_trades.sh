#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/quotex-trade-monitor.log"

cd "$DIR"
nohup python3 scripts/monitor_executed_trades.py > "$LOG" 2>&1 &
echo "Trade monitor started. Log: $LOG"
echo "Recorded trade summaries: $DIR/runtime/executed_trade_monitor.log"
