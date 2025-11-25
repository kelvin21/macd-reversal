# Deployment Guide

## 📦 Prerequisites

- Python 3.11+ (local) or Docker (containerized)
- Git (for version control)
- Database files: `price_data.db` (required), `analysis_results.db` (optional)

## 🚀 Deployment Steps

### 1. Local Development

```bash
# Clone repository
git clone https://github.com/your-username/ta-dashboard.git
cd ta-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your paths

# Prepare data directory
mkdir -p data
# Copy your price_data.db to data/

# Run dashboard
streamlit run macd_reversal_dashboard.py
```

Visit http://localhost:8501

### 2. Docker Deployment

```bash
# Build image
docker build -t ta-dashboard .

# Run container
docker run -d \
  --name ta-dashboard \
  -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  ta-dashboard

# Or use docker-compose
docker-compose up -d

# View logs
docker logs -f ta-dashboard
```

### 3. Streamlit Cloud

```bash
# Go to https://share.streamlit.io
# Click "New app"
# Select repository: your-username/ta-dashboard
# Main file: macd_reversal_dashboard.py
# Click "Deploy"

# Add secrets (Settings > Secrets):
PRICE_DB_PATH = "data/price_data.db"
REF_DB_PATH = "data/analysis_results.db"
```

**Note**: Upload `data/price_data.db` via GitHub or Streamlit file uploader.

### 4. AWS EC2

```bash
# SSH into EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Docker
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
# Log out and back in

# Clone repo
git clone https://github.com/your-username/ta-dashboard.git
cd ta-dashboard

# Copy database files
scp -i your-key.pem data/price_data.db ubuntu@your-ec2-ip:~/ta-dashboard/data/

# Run
docker-compose up -d

# Configure security group: allow port 8501
```

Access via http://your-ec2-ip:8501

### 5. Google Cloud Run

```bash
# Install gcloud CLI
# Authenticate: gcloud auth login

# Build and push to GCR
gcloud builds submit --tag gcr.io/your-project/ta-dashboard

# Deploy to Cloud Run
gcloud run deploy ta-dashboard \
  --image gcr.io/your-project/ta-dashboard \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8501 \
  --memory 2Gi

# Note: For database persistence, use Cloud SQL or mounted volumes
```

### 6. Heroku

Create `Procfile`:
```
web: streamlit run ta_dashboard.py --server.port=$PORT --server.address=0.0.0.0
```

Deploy:
```bash
heroku login
heroku create ta-dashboard
git push heroku main
```

## 🔧 Post-Deployment

### Database Setup
```bash
# Local: Copy DB files
cp /path/to/price_data.db data/

# Docker: Volume mount
docker cp price_data.db ta-dashboard:/app/data/

# Cloud: Upload via dashboard admin panel or SCP
```

### Initial Data Load
```bash
# Option 1: Import from CSV
python ticker_manager.py import amidata_export.csv

# Option 2: TCBS refresh (if build_price_db.py included)
# Use dashboard: Force refresh ALL tickers

# Option 3: Copy from existing DB
python build_price_db.py --copy-existing
```

### SSL/HTTPS Setup (Production)

**Nginx reverse proxy:**
```nginx
server {
    listen 443 ssl;
    server_name ta-dashboard.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Authentication (Optional)

Add to `ta_dashboard.py`:
```python
import streamlit_authenticator as stauth

# Load users from secrets
authenticator = stauth.Authenticate(
    credentials,
    cookie_name='ta_dashboard',
    key='random_secret_key'
)

name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    # Show dashboard
    pass
elif authentication_status == False:
    st.error('Username/password is incorrect')
elif authentication_status == None:
    st.warning('Please enter username and password')
```

## 📊 Monitoring

### Healthcheck Endpoint
```bash
curl http://localhost:8501/_stcore/health
# Returns 200 OK if healthy
```

### Resource Usage
```bash
# Docker stats
docker stats ta-dashboard

# Disk usage
df -h data/

# Database size
ls -lh data/price_data.db
```

### Logs
```bash
# Docker logs
docker logs -f ta-dashboard

# Streamlit logs location
tail -f logs/streamlit.log
```

## 🔄 Updates

```bash
# Pull latest changes
git pull origin main

# Rebuild Docker image
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Or for running container
docker exec ta-dashboard git pull
docker restart ta-dashboard
```

## 🆘 Troubleshooting

### Port already in use
```bash
# Find process
lsof -i :8501
# Kill it
kill -9 <PID>
```

### Database locked
```bash
# Check for zombie connections
fuser data/price_data.db
# Kill if needed
```

### Out of memory
```bash
# Increase Docker memory limit
docker update --memory 2g ta-dashboard

# Or in docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 2G
```

### Slow TCBS refresh
- Reduce pause_between to 0.1s
- Use async/parallel fetching (future enhancement)
- Cache TCBS responses

## 🔐 Security Best Practices

1. **Never commit DB files** (use .gitignore)
2. **Use environment variables** for secrets
3. **Enable authentication** for production
4. **Regular backups** of price_data.db
5. **Rate limit** TCBS API calls
6. **Validate CSV uploads** (size/format)
7. **Use HTTPS** in production
8. **Restrict admin panel** to authorized users
