# MACD Reversal Dashboard - Production Deployment

MACD Histogram Reversal Dashboard with multi-timeframe analysis and TCBS integration.

## 🚀 Quick Start

### Local Development
```bash
pip install -r requirements.txt
streamlit run macd_reversal_dashboard.py
```

### Docker Deployment
```bash
docker-compose up -d
# Visit http://localhost:8501
```

## 📋 Prerequisites

Choose ONE of the following:

- **Docker Desktop** - Recommended for production
  - Download: https://www.docker.com/products/docker-desktop/
  
- **Python 3.11+** - For local development
  - Download: https://www.python.org/downloads/

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for detailed setup instructions.

## ⚠️ Important Note for Windows Users

If you see:
```
docker-compose : The term 'docker-compose' is not recognized...
```

**Solution**: Use `docker compose` (space) instead of `docker-compose` (hyphen)

Docker Compose V2 is included in Docker Desktop as a plugin, not a standalone command.

## 📋 Features

- **Multi-timeframe MACD analysis** (Daily, Weekly, Monthly)
- **TCBS data integration** with auto-scaling
- **Quick commentary** with velocity-based cross prediction
- **Ticker management** (add/remove/import CSV)
- **Real-time volume analysis** (adjusted for trading hours)
- **Auto-refresh** with scale mismatch detection

## 🗂️ Project Structure

```
ta-dashboard-deploy/
├── macd_reversal_dashboard.py  # Main dashboard application
├── ticker_manager.py            # Ticker add/remove/import utility
├── build_price_db.py           # TCBS integration & scaling (optional)
├── requirements.txt            # Python dependencies
├── Dockerfile                 # Container configuration
├── docker-compose.yml         # Multi-container setup
├── .env.example              # Environment variable template
├── .gitignore                # Git ignore rules
├── data/                     # Database files (gitignored)
│   ├── price_data.db
│   └── analysis_results.db
└── docs/                     # Documentation
    ├── DEPLOYMENT.md
    ├── TICKER_MANAGEMENT.md
    └── API.md
```

## 📦 Dependencies

### Core (Required)
- `streamlit>=1.28.0` - Web framework
- `pandas>=2.0.0` - Data manipulation
- `numpy>=1.24.0` - Numerical computing
- `plotly>=5.17.0` - Interactive charts
- `python-dotenv>=1.0.0` - Environment variables

### Optional
- `requests>=2.31.0` - TCBS API calls (if build_price_db.py included)

## ⚙️ Configuration

### Environment Variables
Create `.env` file (see `.env.example`):
```bash
PRICE_DB_PATH=data/price_data.db
REF_DB_PATH=data/analysis_results.db
```

### Modules
- **With build_price_db.py**: Full TCBS refresh capability
- **Without build_price_db.py**: Read-only mode (view existing data only)

## 🌐 Deployment Options

### Streamlit Cloud
1. Push to GitHub
2. Connect at https://share.streamlit.io
3. Add secrets in dashboard settings

### Docker (AWS/GCP/Azure)
```bash
docker build -t ta-dashboard .
docker run -p 8501:8501 -v $(pwd)/data:/app/data ta-dashboard
```

### Heroku
```bash
heroku create ta-dashboard
git push heroku main
```

## 🔒 Security

### Production Checklist
- [ ] Enable authentication (Streamlit auth or reverse proxy)
- [ ] Set up HTTPS/SSL
- [ ] Restrict admin panel access
- [ ] Configure rate limiting for TCBS API
- [ ] Set up database backups
- [ ] Use secrets manager for API keys

### File Permissions
- Database files need write access for TCBS refresh
- CSV uploads validated for size/format
- Admin operations require confirmation

## 📊 Usage

### View Dashboard
- Navigate to overview table
- Click ticker or use dropdown to view detailed charts
- Enable "Vol ≥1.5x" filter for high-volume signals

### TCBS Refresh
1. Enable TCBS module (include build_price_db.py)
2. Set refresh interval (5-60 min)
3. Check confirmation box
4. Click "Force refresh ALL tickers now"
5. Wait for progress bar (auto-reloads after completion)

### Manage Tickers
1. Expand "🔧 Admin: Manage Tickers" in sidebar
2. Add individual tickers or upload CSV
3. Remove with source filtering
4. View ticker list with row counts

## 🐛 Troubleshooting

### "No data available"
- Check DB_PATH environment variable
- Ensure price_data.db exists with data
- Run `python ticker_manager.py list` to verify

### "TCBS refresh disabled"
- Include build_price_db.py in deployment
- Check TCBS API access (Vietnam servers)
- Verify requests package installed

### Slow performance
- Reduce "Days back" in sidebar (default: 365)
- Limit tickers in database
- Increase cache TTL (edit @st.cache_data(ttl=...))

## 📝 License

Proprietary - Internal Use Only

## 🤝 Contributing

Internal project - contact maintainer for access.

## 📧 Support

For issues or questions, open GitHub issue or contact: [your-email]
