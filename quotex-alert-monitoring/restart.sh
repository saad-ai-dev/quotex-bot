#!/bin/bash
# Quotex Alert Monitoring - Full System Restart
# Usage: ./restart.sh

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_LOG="/tmp/quotex-backend.log"
DASHBOARD_LOG="/tmp/quotex-dashboard.log"

echo "=== Quotex Alert Monitoring - Restarting ==="

# Kill existing processes
echo "[1/4] Stopping existing processes..."
pkill -f "python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000" 2>/dev/null && echo "  Backend stopped" || echo "  Backend was not running"
pkill -f "vite --host 0.0.0.0" 2>/dev/null && echo "  Dashboard stopped" || echo "  Dashboard was not running"
sleep 1

# Build extension
echo "[2/4] Building extension..."
cd "$DIR/extension"
npm run build >/dev/null
echo "  Extension built"

# Start backend
echo "[3/4] Starting backend..."
cd "$DIR/backend"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
sleep 3
if curl -s http://localhost:8000/health | python3 -c "import json,sys;d=json.load(sys.stdin);exit(0 if d['status']=='ok' else 1)" 2>/dev/null; then
    echo "  Backend running (PID: $BACKEND_PID) - http://localhost:8000"
else
    echo "  ERROR: Backend failed to start! Check $BACKEND_LOG"
    exit 1
fi

# Start dashboard
echo "[4/4] Starting dashboard..."
cd "$DIR/dashboard"
nohup npx vite --host 0.0.0.0 > "$DASHBOARD_LOG" 2>&1 &
DASH_PID=$!
sleep 3
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "  Dashboard running (PID: $DASH_PID) - http://localhost:5173"
else
    echo "  ERROR: Dashboard failed to start! Check $DASHBOARD_LOG"
fi

echo ""
echo "=== System Ready ==="
echo "  Backend:   http://localhost:8000"
echo "  Dashboard: http://localhost:5173"
echo "  Backend log:   tail -f $BACKEND_LOG"
echo "  Dashboard log: tail -f $DASHBOARD_LOG"
echo ""
echo "Next: Reload extension in chrome://extensions, then refresh Quotex page"
