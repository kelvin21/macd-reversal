#!/bin/bash
# Quick start script for TA Dashboard

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}TA Dashboard - Quick Start${NC}"
echo "=================================================="

# Parse arguments
METHOD=""
STOP=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --docker) METHOD="docker"; shift ;;
        --python) METHOD="python"; shift ;;
        --stop) STOP=true; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

# Stop services
if [ "$STOP" = true ]; then
    echo -e "\n${YELLOW}Stopping services...${NC}"
    docker compose down 2>/dev/null || true
    docker stop ta-dashboard 2>/dev/null || true
    docker rm ta-dashboard 2>/dev/null || true
    pkill -f streamlit || true
    echo -e "${GREEN}Stopped.${NC}"
    exit 0
fi

# Auto-detect method
if [ -z "$METHOD" ]; then
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}Docker detected - using containerized deployment${NC}"
        METHOD="docker"
    elif command -v python3 &> /dev/null; then
        echo -e "${GREEN}Python detected - using local development mode${NC}"
        METHOD="python"
    else
        echo -e "${RED}Error: Neither Docker nor Python found!${NC}"
        echo -e "${YELLOW}Please install Docker or Python 3.11+${NC}"
        exit 1
    fi
fi

# Check database
if [ ! -f "data/price_data.db" ]; then
    echo -e "\n${YELLOW}Warning: data/price_data.db not found${NC}"
    read -p "Create empty database? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p data
        python3 -c "import sqlite3; conn = sqlite3.connect('data/price_data.db'); conn.execute('CREATE TABLE IF NOT EXISTS price_data (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'); conn.commit(); conn.close()"
        echo -e "${GREEN}Empty database created.${NC}"
    fi
fi

# Run
if [ "$METHOD" = "docker" ]; then
    echo -e "\n${CYAN}Starting with Docker Compose...${NC}"
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}Error: Docker daemon is not running${NC}"
        echo -e "${YELLOW}Please start Docker and try again${NC}"
        exit 1
    fi
    
    docker compose up -d
    
    echo -e "\n${GREEN}✓ Dashboard started successfully!${NC}"
    echo -e "   ${CYAN}Visit: http://localhost:8501${NC}"
    echo -e "\nView logs:  docker compose logs -f"
    echo -e "Stop:       docker compose down"
    
elif [ "$METHOD" = "python" ]; then
    echo -e "\n${CYAN}Starting with Python...${NC}"
    
    if ! python3 -c "import streamlit" &> /dev/null; then
        echo -e "${YELLOW}Installing dependencies...${NC}"
        pip3 install -r requirements.txt
    fi
    
    echo -e "\n${GREEN}✓ Starting dashboard...${NC}"
    echo -e "   ${CYAN}Visit: http://localhost:8501${NC}"
    echo -e "\nPress Ctrl+C to stop"
    
    streamlit run macd_reversal_dashboard.py
fi
