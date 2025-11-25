# Quick start script for TA Dashboard on Windows

param(
    [switch]$Docker,
    [switch]$Python,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

Write-Host "TA Dashboard - Quick Start" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Detect what's available
$hasDocker = Get-Command docker -ErrorAction SilentlyContinue
$hasPython = Get-Command python -ErrorAction SilentlyContinue

if ($Stop) {
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    if ($hasDocker) {
        docker compose down 2>$null
        docker stop ta-dashboard 2>$null
        docker rm ta-dashboard 2>$null
    }
    Stop-Process -Name streamlit -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor Green
    exit 0
}

# Determine run method - PRIORITIZE PYTHON FIRST
if ($Python) {
    $method = "python"
} elseif ($Docker) {
    $method = "docker"
} else {
    # Auto-detect - Python first, Docker second
    if ($hasPython) {
        Write-Host "Python detected - using local development mode (recommended)" -ForegroundColor Green
        $method = "python"
    } elseif ($hasDocker) {
        Write-Host "Docker detected - using containerized deployment" -ForegroundColor Green
        $method = "docker"
    } else {
        Write-Host "Error: Neither Python nor Docker found!" -ForegroundColor Red
        Write-Host "Please install Python 3.11+ (recommended)" -ForegroundColor Yellow
        Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Cyan
        Write-Host "`nOr install Docker Desktop (optional)" -ForegroundColor Yellow
        Write-Host "Download: https://www.docker.com/products/docker-desktop/" -ForegroundColor Cyan
        exit 1
    }
}

# Check database exists
if (-not (Test-Path "data\price_data.db")) {
    Write-Host "`nWarning: data\price_data.db not found" -ForegroundColor Yellow
    Write-Host "Create empty database? (Y/N): " -NoNewline
    $response = Read-Host
    if ($response -eq "Y" -or $response -eq "y") {
        New-Item -ItemType Directory -Force -Path "data" | Out-Null
        python -c "import sqlite3; conn = sqlite3.connect('data/price_data.db'); conn.execute('CREATE TABLE IF NOT EXISTS price_data (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'); conn.commit(); conn.close()"
        Write-Host "Empty database created." -ForegroundColor Green
    }
}

# Run with PYTHON (prioritized)
if ($method -eq "python") {
    Write-Host "`nStarting with Python..." -ForegroundColor Cyan
    
    # Check if Python is available
    if (-not $hasPython) {
        Write-Host "Error: Python not found!" -ForegroundColor Red
        Write-Host "Install Python 3.11+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
    
    # Check if requirements installed
    python -c "import streamlit" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing dependencies..." -ForegroundColor Yellow
        pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to install dependencies" -ForegroundColor Red
            Write-Host "Try manually: pip install -r requirements.txt" -ForegroundColor Yellow
            exit 1
        }
    }
    
    Write-Host "`n✓ Starting dashboard..." -ForegroundColor Green
    Write-Host "   Visit: http://localhost:8501" -ForegroundColor Cyan
    Write-Host "`nPress Ctrl+C to stop" -ForegroundColor Gray
    Write-Host ""
    
    streamlit run macd_reversal_dashboard.py
}

# Run with DOCKER (optional fallback)
if ($method -eq "docker") {
    Write-Host "`nStarting with Docker Compose..." -ForegroundColor Cyan
    
    # Check if Docker is available
    if (-not $hasDocker) {
        Write-Host "Error: Docker not found!" -ForegroundColor Red
        Write-Host "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        Write-Host "`nOr use Python instead: .\run.ps1 --python" -ForegroundColor Cyan
        exit 1
    }
    
    # Check if Docker Desktop is running
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Docker Desktop is not running" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
        Write-Host "`nOr use Python instead: .\run.ps1 --python" -ForegroundColor Cyan
        exit 1
    }
    
    # Use Docker Compose V2 syntax (space, not hyphen)
    docker compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Dashboard started successfully!" -ForegroundColor Green
        Write-Host "   Visit: http://localhost:8501" -ForegroundColor Cyan
        Write-Host "`nView logs:  docker compose logs -f" -ForegroundColor Gray
        Write-Host "Stop:       docker compose down" -ForegroundColor Gray
    } else {
        Write-Host "`n✗ Failed to start Docker container" -ForegroundColor Red
        Write-Host "Try: docker compose logs" -ForegroundColor Yellow
        Write-Host "`nOr use Python instead: .\run.ps1 --python" -ForegroundColor Cyan
    }

