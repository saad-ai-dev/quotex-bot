#!/usr/bin/env bash
# =============================================================================
# Quotex Alert Intelligence - Development Runner
#
# This script:
#   1. Checks that MongoDB is accessible
#   2. Runs index initialization
#   3. Seeds default settings
#   4. Starts the FastAPI backend with uvicorn in reload mode
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo " Quotex Alert Intelligence - Dev Runner"
echo " ALERT-ONLY System - No Trade Execution"
echo "=============================================="
echo ""

# Load .env if present
if [ -f "$PROJECT_DIR/.env" ]; then
    echo -e "${GREEN}Loading .env file...${NC}"
    set -a
    source "$PROJECT_DIR/.env"
    set +a
else
    echo -e "${YELLOW}No .env file found. Using defaults.${NC}"
    echo "  Tip: Copy .env.example to .env and configure it."
fi

MONGODB_URL="${MONGODB_URL:-mongodb://localhost:27017}"

# Step 1: Check MongoDB connectivity
echo ""
echo "Step 1: Checking MongoDB connectivity..."
if command -v mongosh &> /dev/null; then
    if mongosh "$MONGODB_URL" --quiet --eval "db.adminCommand('ping')" &> /dev/null; then
        echo -e "  ${GREEN}MongoDB is reachable at $MONGODB_URL${NC}"
    else
        echo -e "  ${RED}ERROR: Cannot connect to MongoDB at $MONGODB_URL${NC}"
        echo "  Make sure MongoDB is running. Try: docker compose up -d mongodb"
        exit 1
    fi
elif command -v python3 &> /dev/null; then
    if python3 -c "
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
try:
    client = MongoClient('$MONGODB_URL', serverSelectionTimeoutMS=3000)
    client.admin.command('ping')
    print('  MongoDB is reachable')
except Exception as e:
    print(f'  ERROR: {e}')
    exit(1)
" 2>/dev/null; then
        echo -e "  ${GREEN}MongoDB connectivity verified via pymongo.${NC}"
    else
        echo -e "  ${RED}ERROR: Cannot connect to MongoDB at $MONGODB_URL${NC}"
        echo "  Make sure MongoDB is running. Try: docker compose up -d mongodb"
        exit 1
    fi
else
    echo -e "  ${YELLOW}WARNING: Cannot verify MongoDB (no mongosh or python3 found).${NC}"
    echo "  Proceeding anyway..."
fi

# Step 2: Initialize database indexes
echo ""
echo "Step 2: Initializing database indexes..."
cd "$PROJECT_DIR"
python3 scripts/init_indexes.py
echo -e "  ${GREEN}Indexes initialized.${NC}"

# Step 3: Seed default settings
echo ""
echo "Step 3: Seeding default settings..."
python3 scripts/seed_settings.py
echo -e "  ${GREEN}Settings seeded.${NC}"

# Step 4: Start the backend
echo ""
echo "Step 4: Starting FastAPI backend..."
echo "  Backend will be available at http://localhost:8000"
echo "  API docs at http://localhost:8000/docs"
echo "  Press Ctrl+C to stop."
echo ""

cd "$PROJECT_DIR/backend"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
