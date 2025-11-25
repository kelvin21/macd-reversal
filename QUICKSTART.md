# Quick Start Reference

## 🏁 First Time Setup

### 1. Install Prerequisites

**Windows:**
- Install Docker Desktop: https://www.docker.com/products/docker-desktop/
- OR install Python 3.11+: https://www.python.org/downloads/

**Linux/Mac:**
```bash
# Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Python
sudo apt install python3.11 python3-pip
```

### 2. Get the Code

```bash
git clone https://github.com/your-username/ta-dashboard.git
cd ta-dashboard
```

### 3. Prepare Database

```bash
# Copy your existing database
cp /path/to/price_data.db data/

# OR create empty database
mkdir data
python -c "import sqlite3; conn = sqlite3.connect('data/price_data.db'); conn.execute('CREATE TABLE IF NOT EXISTS price_data (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'); conn.commit(); conn.close()"
```

### 4. Run Dashboard

**Windows:**
```powershell
.\run.ps1
```

**Linux/Mac:**
```bash
bash run.sh
```

**Manual (Docker):**
```bash
docker compose up -d
```

**Manual (Python):**
```bash
pip install -r requirements.txt
streamlit run macd_reversal_dashboard.py
```

## 🎯 Common Commands

### Start
```bash
# Using script
./run.ps1                  # Windows
bash run.sh                # Linux/Mac

# Docker
docker compose up -d

# Python
streamlit run ta_dashboard.py
```

### Stop
```bash
# Using script
./run.ps1 --stop           # Windows
bash run.sh --stop         # Linux/Mac

# Docker
docker compose down

# Python
Ctrl + C
```

### View Logs
```bash
# Docker
docker compose logs -f

# Python
# Logs shown in terminal
```

### Restart
```bash
docker compose restart
# OR
docker compose down && docker compose up -d
```

## 🔧 Manage Tickers

### CLI
```bash
# List all tickers
python ticker_manager.py list

# Add ticker
python ticker_manager.py add VIC --source manual

# Remove ticker
python ticker_manager.py remove VIC --confirm

# Import CSV
python ticker_manager.py import data.csv
```

### Dashboard UI
1. Open dashboard in browser
2. Expand "🔧 Admin: Manage Tickers" in sidebar
3. Add/remove/import tickers

## 📊 Access Dashboard

- Local: http://localhost:8501
- Network: http://YOUR_IP:8501

## ⚡ Troubleshooting

| Issue | Solution |
|-------|----------|
| `docker-compose not recognized` | Use `docker compose` (space not hyphen) |
| `Docker daemon not running` | Start Docker Desktop |
| `Port 8501 already in use` | `netstat -ano | findstr :8501` then kill process |
| `No data available` | Check `data/price_data.db` exists and has data |
| `Module not found` | `pip install -r requirements.txt` |

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for detailed troubleshooting.

## 🌐 Deploy to Cloud

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for:
- AWS EC2
- Google Cloud Run
- Azure
- Streamlit Cloud
- Heroku

## 📚 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Ticker Management](docs/TICKER_MANAGEMENT.md)
