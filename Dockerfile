FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for healthcheck)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY macd_reversal_dashboard.py .
COPY ticker_manager.py .
COPY build_price_db.py .

# Create data directory
RUN mkdir -p /app/data /app/logs

# Environment variables (can be overridden)
ENV PRICE_DB_PATH=/app/data/price_data.db
ENV REF_DB_PATH=/app/data/analysis_results.db
ENV PYTHONUNBUFFERED=1

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "macd_reversal_dashboard.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true", \
     "--server.fileWatcherType", "none"]
