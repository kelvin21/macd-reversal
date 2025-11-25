# Redirect for backward compatibility
# This file redirects to the renamed macd_reversal_dashboard.py

import os
import sys

print("Note: ta_dashboard.py has been renamed to macd_reversal_dashboard.py")
print("Redirecting...")

# Import and run the main dashboard
import macd_reversal_dashboard

import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import os

# STARTUP DIAGNOSTICS - Add at very beginning
print("=" * 50)
print("MACD Reversal Dashboard - Starting...")
print(f"Current directory: {os.getcwd()}")
print(f"Files in current dir: {os.listdir('.')}")
print(f"Data directory exists: {os.path.exists('data')}")
if os.path.exists('data'):
    print(f"Files in data/: {os.listdir('data')}")
print("=" * 50)

# Show loading message while checking dependencies
with st.spinner("Initializing dashboard..."):
    # Check critical dependencies
    missing_deps = []
    try:
        import streamlit
    except ImportError:
        missing_deps.append("streamlit")
    
    try:
        import plotly
    except ImportError:
        missing_deps.append("plotly")
    
    if missing_deps:
        st.error(f"Missing dependencies: {', '.join(missing_deps)}")
        st.stop()

# OPTIMIZED: Make build_price_db optional and use environment variables
try:
    import build_price_db as bdb
    DB_PATH = os.getenv("PRICE_DB_PATH", bdb.NEW_DB_PATH)
    DEFAULT_LOCAL_DB = os.getenv("REF_DB_PATH", bdb.DEFAULT_LOCAL_DB)
    HAS_BDB = True
except ImportError:
    bdb = None
    DB_PATH = os.getenv("PRICE_DB_PATH", "price_data.db")
    DEFAULT_LOCAL_DB = os.getenv("REF_DB_PATH", "analysis_results.db")
    HAS_BDB = False
    print("Warning: build_price_db module not found. TCBS refresh will be disabled.")

# Check if database exists, if not create empty one
if not os.path.exists(DB_PATH):
    st.warning(f"⚠️ Database not found: {DB_PATH}")
    
    # Show import options
    st.info("""
    **Options to populate database:**
    
    1. **Upload CSV via Admin Panel** (recommended for Streamlit Cloud)
       - Expand "🔧 Admin: Manage Tickers" in sidebar
       - Use "Bulk Import CSV" section
       - Upload your AmiBroker export
    
    2. **TCBS Refresh** (if build_price_db.py included)
       - Add tickers manually via Admin Panel
       - Use "Force refresh ALL tickers" to fetch from TCBS
    
    3. **Local Database** (for local development)
       - Copy price_data.db to data/ directory
    """)
    
    st.info("Creating empty database structure...")
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                ticker TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, date, source)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON price_data(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON price_data(date)")
        conn.commit()
        conn.close()
        st.success("✓ Empty database created. Add tickers using Admin Panel below.")
    except Exception as e:
        st.error(f"Failed to create database: {e}")
        st.stop()

st.set_page_config(page_title="MACD Reversal Dashboard", layout="wide", page_icon="📊")
st.markdown("#### MACD Histogram Reversal — Overview")
