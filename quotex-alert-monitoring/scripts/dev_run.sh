#!/bin/bash
# Quotex Alert Monitor - Development Runner
# ALERT-ONLY: Starts all services for local development.
# This script does NOT enable any trade execution features.

set -e

echo "=============================================="
echo "Quotex Alert Monitor - Development Setup"
echo "ALERT-ONLY: No trade execution"
echo "=============================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ---- Check MongoDB ----
echo -e "\n${YELLOW}[1/4] Checking MongoDB...${NC}"

if command -v mongosh &> /dev/null; then
    if mongosh --quiet --eval "db.adminCommand('ping')" &> /dev/null; then
        echo -e "${GREEN}  MongoDB is running${NC}"
    else
        echo -e "${RED}  MongoDB is not running. Starting with Docker...${NC}"
        docker-compose up -d mongodb
        echo "  Waiting for MongoDB to be ready..."
        sleep 5
        if mongosh --quiet --eval "db.adminCommand('ping')" &> /dev/null; then
            echo -e "${GREEN}  MongoDB is now running${NC}"
        else
            echo -e "${RED}  ERROR: Could not start MongoDB${NC}"
            exit 1
        fi
    fi
elif command -v docker &> /dev/null; then
    echo "  mongosh not found, using Docker..."
    docker-compose up -d mongodb
    sleep 5
    echo -e "${GREEN}  MongoDB container started${NC}"
else
    echo -e "${RED}  ERROR: Neither mongosh nor docker found. Install MongoDB or Docker.${NC}"
    exit 1
fi

# ---- Initialize Indexes ----
echo -e "\n${YELLOW}[2/4] Initializing database indexes...${NC}"
python scripts/init_indexes.py

# ---- Seed Settings ----
echo -e "\n${YELLOW}[3/4] Seeding default settings...${NC}"
python scripts/seed_settings.py

# ---- Start Backend ----
echo -e "\n${YELLOW}[4/4] Starting backend server...${NC}"
echo -e "${GREEN}  Backend starting on http://localhost:8000${NC}"
echo -e "${GREEN}  API docs: http://localhost:8000/docs${NC}"
echo ""
echo "=============================================="
echo "ALERT-ONLY monitoring system is starting."
echo "No trades will be executed."
echo "=============================================="
echo ""

cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
