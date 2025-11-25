# Installation Guide - Windows

## 🐳 Docker Setup (Recommended for Deployment)

### Install Docker Desktop for Windows

1. **Download Docker Desktop**
   - Visit: https://www.docker.com/products/docker-desktop/
   - Click "Download for Windows"
   - File: Docker Desktop Installer.exe (~500MB)

2. **Install Docker Desktop**
   - Run the installer
   - Check "Use WSL 2 instead of Hyper-V" (recommended)
   - Restart computer when prompted

3. **Verify Installation**
   ```powershell
   docker --version
   # Should show: Docker version 24.x.x
   
   docker compose version
   # Should show: Docker Compose version v2.x.x
   ```

### Important: Docker Compose v2

Modern Docker Desktop includes Compose V2 as a plugin. Use:
```powershell
# NEW syntax (Docker Compose V2)
docker compose up

# OLD syntax (deprecated)
docker-compose up
```

If you get "docker-compose not recognized", use `docker compose` (space, not hyphen).

## 🐍 Python Setup (Alternative to Docker)

### Install Python 3.11+

1. **Download Python**
   - Visit: https://www.python.org/downloads/
   - Download Python 3.11 or 3.12 (Windows installer)

2. **Run Installer**
   - ✅ Check "Add Python to PATH"
   - Click "Install Now"

3. **Verify Installation**
   ```powershell
   python --version
   # Should show: Python 3.11.x or 3.12.x
   
   pip --version
   # Should show: pip 23.x.x
   ```

### Install Dependencies

```powershell
# Navigate to project directory
cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Install required packages
pip install -r requirements.txt
```

## 🚀 Running the Dashboard

### Option 1: Python (Local Development)

```powershell
# Activate virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run dashboard
streamlit run macd_reversal_dashboard.py
```

Visit: http://localhost:8501

### Option 2: Docker Compose (Production-like)

```powershell
# Ensure Docker Desktop is running (system tray icon)

# Navigate to project directory
cd c:\Users\hadao\OneDrive\Documents\Programming\amidata\ta-dashboard-deploy

# Start services (V2 syntax - note the SPACE)
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

Visit: http://localhost:8501

### Option 3: Docker CLI (Manual)

```powershell
# Build image
docker build -t ta-dashboard .

# Run container
docker run -d `
  --name ta-dashboard `
  -p 8501:8501 `
  -v ${PWD}/data:/app/data `
  ta-dashboard

# View logs
docker logs -f ta-dashboard

# Stop container
docker stop ta-dashboard
docker rm ta-dashboard
```

## 🗄️ Database Setup

### Copy Existing Database

```powershell
# Create data directory
mkdir data

# Copy your database
copy "C:\path\to\price_data.db" data\

# Copy reference database (optional)
copy "C:\path\to\analysis_results.db" data\
```

### Create Empty Database

```powershell
# Install sqlite3 (comes with Python)
python -c "import sqlite3; conn = sqlite3.connect('data/price_data.db'); conn.execute('CREATE TABLE IF NOT EXISTS price_data (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'); conn.commit(); conn.close()"
```

### Import Data from CSV

```powershell
# Using ticker_manager
python ticker_manager.py import amidata_export.csv --source amibroker

# Or using AmiBroker export
python ami2py_export_csv.py --watchlist 0 --output ami_export.csv
python ticker_manager.py import ami_export.csv --source amibroker
```

## 🔧 Troubleshooting

### Docker Issues

#### "docker-compose not recognized"
**Solution**: Use `docker compose` (space) instead of `docker-compose` (hyphen)

Docker Compose V2 is a plugin, not a standalone command.

#### "Docker daemon not running"
**Solution**: 
1. Open Docker Desktop from Start Menu
2. Wait for "Docker Desktop is running" message
3. Try command again

#### "Port 8501 already in use"
**Solution**:
```powershell
# Find process using port
netstat -ano | findstr :8501

# Kill process (replace PID with actual number)
taskkill /PID <PID> /F

# Or use different port
docker run -p 8502:8501 ta-dashboard
```

### Python Issues

#### "python not recognized"
**Solution**: 
1. Reinstall Python with "Add to PATH" checked
2. Or add manually: System Properties > Environment Variables > Path > Add `C:\Python311\`

#### "pip install fails"
**Solution**:
```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Install with --user flag
pip install --user -r requirements.txt

# Or use virtual environment
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

#### "Module not found: streamlit"
**Solution**:
```powershell
# Ensure you're in correct environment
pip list | findstr streamlit

# Reinstall if missing
pip install streamlit
```

### Database Issues

#### "Database is locked"
**Solution**:
```powershell
# Close all programs accessing the database
# Check for AmiBroker, Excel, or other SQLite tools

# Force unlock (use cautiously)
fuser -k data/price_data.db  # Linux
# Windows: restart computer or use Process Explorer
```

#### "No data available"
**Solution**:
1. Check database exists: `dir data\price_data.db`
2. Check it has data: `python ticker_manager.py list`
3. Import data if empty: see "Import Data from CSV" above

## 📊 Quick Start Checklist

- [ ] Install Docker Desktop OR Python 3.11+
- [ ] Clone/download ta-dashboard-deploy folder
- [ ] Copy database files to `data/` folder
- [ ] Configure `.env` file (copy from `.env.example`)
- [ ] Run dashboard: `streamlit run ta_dashboard.py` OR `docker compose up`
- [ ] Open browser: http://localhost:8501
- [ ] Test TCBS refresh (if build_price_db.py included)
- [ ] Add/remove tickers via Admin panel

## 🆘 Still Having Issues?

1. **Check system requirements**
   - Windows 10/11 (64-bit)
   - 4GB+ RAM
   - Docker: WSL 2 enabled
   - Python: 3.11 or higher

2. **Enable verbose logging**
   ```powershell
   # Python
   streamlit run ta_dashboard.py --logger.level=debug
   
   # Docker
   docker compose up  # (without -d flag)
   ```

3. **Check firewall/antivirus**
   - Allow Docker Desktop
   - Allow Python.exe
   - Allow port 8501

4. **Verify file paths**
   - Use forward slashes: `data/price_data.db`
   - Or double backslashes: `data\\price_data.db`
   - Avoid spaces in folder names

## 🔗 Useful Links

- Docker Desktop: https://www.docker.com/products/docker-desktop/
- Python Downloads: https://www.python.org/downloads/
- Streamlit Docs: https://docs.streamlit.io/
- SQLite Browser: https://sqlitebrowser.org/
