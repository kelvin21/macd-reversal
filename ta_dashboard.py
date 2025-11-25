import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import os

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
    st.warning("⚠️ build_price_db module not found. TCBS refresh will be disabled.")

# OPTIMIZED: Make ticker_manager optional
try:
    import ticker_manager as tm
    HAS_TM = True
except ImportError:
    tm = None
    HAS_TM = False

st.set_page_config(page_title="MACD Reversal Dashboard", layout="wide", page_icon="📊")
st.markdown("#### MACD Histogram Reversal — Overview")  # Changed from st.title() to smaller heading

# Initialize session state for selected ticker (must be before any code that references it)
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = None

# --- Helpers -----------------------------------------------------------------
@st.cache_data(ttl=300)
def get_all_tickers(db_path=DB_PATH, debug=False):
    # OPTIMIZED: Fallback implementation if bdb not available
    if HAS_BDB:
        try:
            return bdb._get_distinct_tickers_from_db(db_path, debug=debug)
        except Exception as e:
            if debug:
                st.write(f"[DEBUG] Error in get_all_tickers: {e}")
    
    # Fallback: direct DB query
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT ticker FROM price_data WHERE ticker IS NOT NULL ORDER BY ticker")
        tickers = [r[0] for r in cur.fetchall()]
        conn.close()
        return tickers
    except Exception as e:
        if debug:
            st.write(f"[DEBUG] Fallback ticker query error: {e}")
        return []

@st.cache_data(ttl=300)
def load_price_range(ticker, start_date, end_date, db_path=DB_PATH):
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        # Ensure dates are strings in YYYY-MM-DD format for SQLite string comparison
        start_str = start_date if isinstance(start_date, str) else start_date.strftime("%Y-%m-%d")
        end_str = end_date if isinstance(end_date, str) else end_date.strftime("%Y-%m-%d")
        
        q = """
            SELECT date, open, high, low, close, volume
            FROM price_data
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        df = pd.read_sql_query(q, conn, params=(ticker, start_str, end_str))
        if df.empty:
            return df
        df['date'] = pd.to_datetime(df['date'])
        return df
    finally:
        conn.close()

def macd_hist(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - macd_signal
    return macd_line, macd_signal, hist

def detect_stage(hist: pd.Series, lookback=20):
    """
    Return one of six stages for the latest bar with numeric prefix for sorting:
    '1. Troughing', '2. Confirmed Trough', '3. Rising above Zero', '4. Peaking',
    '5. Confirmed Peak', '6. Falling below Zero'
    
    Improved logic:
      - cross_up (prev<0, last>=0) => Confirmed Trough
      - cross_down (prev>0, last<=0) => Confirmed Peak
      - For Troughing: histogram is negative, there's a clear local minimum in the window since last cross-down,
        and histogram is rising from that minimum.
      - For Peaking: histogram is positive, there's a clear local maximum in the window since last cross-up,
        and histogram is falling from that maximum.
      - Otherwise classify as Rising above Zero or Falling below Zero based on sign and recent slope.
    """
    s = hist.dropna().reset_index(drop=True)
    if s.empty or len(s) < 3:
        return "N/A"
    last = float(s.iat[-1])
    prev = float(s.iat[-2])
    
    # Detect zero-crosses
    cross_up = (prev < 0 and last >= 0)
    cross_down = (prev > 0 and last <= 0)
    
    # Immediate zero-cross states
    if cross_up:
        return "2. Confirmed Trough"
    if cross_down:
        return "5. Confirmed Peak"
    
    # Find the index of the last zero-cross (either direction) to define the window
    # Search backwards for the most recent bar where sign changed
    last_cross_idx = len(s) - 1
    for i in range(len(s)-2, max(0, len(s)-lookback-1), -1):
        if (s[i] < 0 and s[i+1] >= 0) or (s[i] > 0 and s[i+1] <= 0):
            last_cross_idx = i + 1
            break
    
    # Window from last cross to current
    window_start = max(0, last_cross_idx)
    window = s.iloc[window_start:]
    
    if last < 0:
        # Negative histogram: check for Troughing vs Falling below Zero
        # Troughing: there's a clear local min in window and we're rising from it
        if len(window) >= 3:
            min_idx_in_window = int(window.idxmin())
            min_val = float(window.min())
            # Check if the minimum is not at the very end (allow some recovery)
            if min_idx_in_window < len(s) - 1:
                # Check if we're rising from that min (compare last few bars to min)
                recent_vals = s.iloc[min_idx_in_window:]
                if len(recent_vals) >= 2:
                    # Confirm upward trend from min
                    slope = np.polyfit(range(len(recent_vals)), recent_vals.values, 1)[0] if len(recent_vals) > 1 else (last - min_val)
                    if slope > 0:
                        return "1. Troughing"
        # Otherwise falling below zero
        return "6. Falling below Zero"
    else:
        # Positive histogram: check for Peaking vs Rising above Zero
        # Peaking: there's a clear local max in window and we're falling from it
        if len(window) >= 3:
            max_idx_in_window = int(window.idxmax())
            max_val = float(window.max())
            # Check if the maximum is not at the very end (allow some decline)
            if max_idx_in_window < len(s) - 1:
                # Check if we're falling from that max
                recent_vals = s.iloc[max_idx_in_window:]
                if len(recent_vals) >= 2:
                    slope = np.polyfit(range(len(recent_vals)), recent_vals.values, 1)[0] if len(recent_vals) > 1 else (last - max_val)
                    if slope < 0:
                        return "4. Peaking"
        # Otherwise rising above zero
        return "3. Rising above Zero"

def stage_score(stage):
    # numeric scores: Confirmed Trough +3, Troughing +2, Rising +1, Peaking -2, Confirmed Peak -3, Falling -1
    # Now stages have prefixes, extract base name or use full match
    if "Confirmed Trough" in stage:
        return 3
    if "Troughing" in stage:
        return 2
    if "Rising above Zero" in stage:
        return 1
    if "Peaking" in stage:
        return -2
    if "Confirmed Peak" in stage:
        return -3
    if "Falling below Zero" in stage:
        return -1
    return 0

def build_overview(tickers, start_date, end_date, lookback=20, max_rows=200):
    rows = []
    skipped = 0
    
    # Get current time for volume adjustment
    now = datetime.now()
    current_time = now.time()
    
    # Trading hours: 9:00-11:30 and 13:00-14:45
    morning_start = datetime.strptime("09:00", "%H:%M").time()
    morning_end = datetime.strptime("11:30", "%H:%M").time()
    afternoon_start = datetime.strptime("13:00", "%H:%M").time()
    afternoon_end = datetime.strptime("14:45", "%H:%M").time()
    
    # Calculate elapsed trading minutes today
    elapsed_trading_minutes = 0
    if morning_start <= current_time <= morning_end:
        # Currently in morning session
        elapsed_trading_minutes = (datetime.combine(datetime.today(), current_time) - datetime.combine(datetime.today(), morning_start)).seconds / 60
    elif afternoon_start <= current_time <= afternoon_end:
        # Currently in afternoon session (morning session complete + partial afternoon)
        morning_minutes = 150  # 09:00 to 11:30 = 2.5 hours
        elapsed_afternoon = (datetime.combine(datetime.today(), current_time) - datetime.combine(datetime.today(), afternoon_start)).seconds / 60
        elapsed_trading_minutes = morning_minutes + elapsed_afternoon
    elif current_time > afternoon_end:
        # Market closed - full day
        elapsed_trading_minutes = 255  # 150 morning + 105 afternoon (13:00-14:45)
    # else: before market open, elapsed_trading_minutes = 0
    
    total_trading_minutes = 255  # Full trading day
    time_factor = elapsed_trading_minutes / total_trading_minutes if total_trading_minutes > 0 else 1.0
    
    for t in tickers[:max_rows]:
        df = load_price_range(t, start_date, end_date)
        if df.empty:
            skipped += 1
            continue
        latest = df.iloc[-1]
        close = float(latest['close'])
        latest_date = latest['date']
        current_vol = float(latest['volume'])
        
        # Daily
        _, _, histD = macd_hist(df['close'].astype(float))
        stageD = detect_stage(histD, lookback=lookback)
        histD_val = float(histD.iat[-1])
        # Weekly
        df_w = df.set_index('date').resample('W').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
        if df_w.empty:
            stageW = "N/A"
            histW_val = np.nan
        else:
            _, _, histW = macd_hist(df_w['close'].astype(float))
            stageW = detect_stage(histW, lookback=lookback)
            histW_val = float(histW.iat[-1])
        # Monthly
        df_m = df.set_index('date').resample('M').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
        if df_m.empty:
            stageM = "N/A"
            histM_val = np.nan
        else:
            _, _, histM = macd_hist(df_m['close'].astype(float))
            stageM = detect_stage(histM, lookback=lookback)
            histM_val = float(histM.iat[-1])
        
        # AvgVol (daily lookback, excluding today) and calculate ratio
        df_hist = df[df['date'] < latest_date]  # exclude today
        if len(df_hist) >= 20:
            avg_vol = float(df_hist['volume'].tail(20).mean())
        elif len(df_hist) > 0:
            avg_vol = float(df_hist['volume'].mean())
        else:
            avg_vol = current_vol  # fallback
        
        # Adjust current volume by time factor if market is still open
        adjusted_current_vol = current_vol / time_factor if time_factor > 0 else current_vol
        vol_ratio = adjusted_current_vol / avg_vol if avg_vol > 0 else 1.0
        
        score = 0.5*stage_score(stageD) + 0.3*stage_score(stageW) + 0.2*stage_score(stageM)
        rows.append({
            "Ticker": t,
            "Close": f"{close:.1f}",
            "Trend (Daily)": stageD,
            "Trend (Weekly)": stageW,
            "Trend (Monthly)": stageM,
            "Score": int(np.round(score)),
            "MACD_Hist_Daily": f"{histD_val:.2f}" if not np.isnan(histD_val) else "",
            "MACD_Hist_Weekly": f"{histW_val:.2f}" if not np.isnan(histW_val) else "",
            "MACD_Hist_Monthly": f"{histM_val:.2f}" if not np.isnan(histM_val) else "",
            "Vol/AvgVol": f"{vol_ratio:.1f}x"  # Format as ratio with 1 decimal
        })
    df_out = pd.DataFrame(rows)
    if debug_flag:
        st.write(f"[DEBUG] build_overview: processed {len(tickers[:max_rows])} tickers, skipped {skipped} (no data in range), built {len(df_out)} rows")
        st.write(f"[DEBUG] Current time: {now.strftime('%H:%M:%S')}, elapsed trading minutes: {elapsed_trading_minutes:.0f}, time factor: {time_factor:.2f}")
    
    # Sort by daily stage, then by MACD_Hist_Daily
    if not df_out.empty:
        df_out['_sort_macd'] = df_out['MACD_Hist_Daily'].replace('', np.nan).astype(float)
        df_out = df_out.sort_values(['Trend (Daily)', '_sort_macd'], ascending=[True, True]).drop(columns=['_sort_macd']).reset_index(drop=True)
    return df_out

def _get_db_stats(db_path):
    """Return diagnostic info for a sqlite DB: existence, size, mtime, table row counts and sample rows."""
    info = {
        "path": db_path,
        "exists": os.path.exists(db_path),
        "size_bytes": None,
        "modified": None,
        "tables": {},
        "errors": []
    }
    if not info["exists"]:
        return info
    try:
        info["size_bytes"] = os.path.getsize(db_path)
        info["modified"] = datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
    except Exception as e:
        info["errors"].append(f"fs-error: {e}")

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        for tbl in ("price_data", "market_data", "tcbs_scaling"):
            if tbl in tables:
                try:
                    cur.execute(f"SELECT COUNT(1) FROM {tbl}")
                    cnt = cur.fetchone()[0]
                except Exception as e:
                    cnt = f"err:{e}"
                sample = []
                try:
                    cur.execute(f"SELECT * FROM {tbl} LIMIT 5")
                    cols = [d[0] for d in cur.description] if cur.description else []
                    rows = cur.fetchall()
                    sample = [dict(zip(cols, r)) for r in rows]
                except Exception as e:
                    sample = [f"sample-error: {e}"]
                info["tables"][tbl] = {"count": cnt, "sample": sample}
            else:
                info["tables"][tbl] = {"count": 0, "sample": []}
        conn.close()
    except Exception as e:
        info["errors"].append(f"db-error: {e}")
    return info

# NEW: Move style_stage_column here (top-level helper)
def style_stage_column(val):
    """Return CSS style for a stage cell based on numeric prefix (1-6)."""
    # Extract numeric prefix (e.g., "1. Troughing" -> 1)
    try:
        prefix = int(val.split('.')[0])
    except Exception:
        return ""
    # Green shades for stages 1-3, red shades for 4-6
    colors = {
        1: "background-color: #c8e6c9; color: black",        # Pale green (Troughing)
        2: "background-color: #39ff14; color: black",        # Neon green (Confirmed Trough)
        3: "background-color: #2e7d32; color: white",        # Dark green (Rising above Zero)
        4: "background-color: #ffccbc; color: black",        # Pale red/orange (Peaking)
        5: "background-color: #ff5252; color: white",        # Bright red (Confirmed Peak)
        6: "background-color: #c62828; color: white"         # Dark red (Falling below Zero)
    }
    return colors.get(prefix, "")

# NEW: Style functions for different columns
def style_vol_ratio(val):
    """Style Vol/AvgVol cell - green for high volume, gray for low."""
    try:
        ratio = float(val.rstrip('x'))
    except Exception:
        return ""
    # Green gradient for high volume (>1.5x), gray for low (<0.8x), white for normal
    if ratio >= 1.5:
        return "background-color: #66bb6a; color: white"  # Green
    elif ratio >= 1.2:
        return "background-color: #aed581; color: black"  # Light green
    elif ratio >= 1.0:
        return "background-color: #e8f5e9; color: black"  # Very light green
    elif ratio >= 0.8:
        return "background-color: #f5f5f5; color: black"  # Light gray
    else:
        return "background-color: #bdbdbd; color: black"  # Gray

def style_by_score(val, score):
    """Style Ticker/Close cells based on score value."""
    # Green for positive scores, red for negative
    if score >= 2:
        return "background-color: #66bb6a; color: white"  # Strong green
    elif score >= 1:
        return "background-color: #aed581; color: black"  # Light green
    elif score >= 0:
        return "background-color: #e8f5e9; color: black"  # Very light green
    elif score >= -1:
        return "background-color: #ffccbc; color: black"  # Light red
    elif score >= -2:
        return "background-color: #ff8a80; color: white"  # Medium red
    else:
        return "background-color: #ff5252; color: white"  # Strong red

def style_macd_by_trend(val, trend):
    """Style MACD hist cells based on their corresponding trend stage."""
    # Reuse stage_score colors but extract from trend string
    try:
        prefix = int(trend.split('.')[0])
    except Exception:
        return ""
    colors = {
        1: "background-color: #c8e6c9; color: black",
        2: "background-color: #39ff14; color: black",
        3: "background-color: #2e7d32; color: white",
        4: "background-color: #ffccbc; color: black",
        5: "background-color: #ff5252; color: white",
        6: "background-color: #c62828; color: white"
    }
    return colors.get(prefix, "")

def plot_multi_tf_macd(ticker, start_date, end_date, lookback, db_path=DB_PATH):
    """Plot candlestick + MACD histograms for daily/weekly/monthly in subplots."""
    df = load_price_range(ticker, start_date, end_date, db_path=db_path)
    if df.empty:
        st.warning(f"No data for {ticker}")
        return
    df = df.sort_values('date').reset_index(drop=True)
    close = df['close'].astype(float)
    
    # Compute daily MACD
    _, _, histD = macd_hist(close)
    stageD = detect_stage(histD, lookback=lookback)
    
    # Resample for weekly
    df_w = df.set_index('date').resample('W').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index()
    if not df_w.empty:
        _, _, histW = macd_hist(df_w['close'].astype(float))
        stageW = detect_stage(histW, lookback=lookback)
    else:
        histW = pd.Series([])
        stageW = "N/A"
    
    # Resample for monthly
    df_m = df.set_index('date').resample('M').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index()
    if not df_m.empty:
        _, _, histM = macd_hist(df_m['close'].astype(float))
        stageM = detect_stage(histM, lookback=lookback)
    else:
        histM = pd.Series([])
        stageM = "N/A"
    
    # Build subplots: candlestick + 3 MACD hists
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        row_heights=[0.5, 0.16, 0.17, 0.17], vertical_spacing=0.02,
                        subplot_titles=("Price", f"MACD Hist (Daily) - {stageD}", f"MACD Hist (Weekly) - {stageW}", f"MACD Hist (Monthly) - {stageM}"))
    
    # Candlestick
    fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
    
    # Daily MACD hist
    df['histD'] = histD.values
    fig.add_trace(go.Bar(x=df['date'], y=df['histD'], name='Daily', marker_color=['#1f77b4' if v>=0 else '#ff7f0e' for v in df['histD']]), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['date'], y=[0]*len(df), mode='lines', line=dict(color='black', width=1), showlegend=False), row=2, col=1)
    
    # Weekly MACD hist
    if not df_w.empty:
        df_w['histW'] = histW.values
        fig.add_trace(go.Bar(x=df_w['date'], y=df_w['histW'], name='Weekly', marker_color=['#1f77b4' if v>=0 else '#ff7f0e' for v in df_w['histW']]), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_w['date'], y=[0]*len(df_w), mode='lines', line=dict(color='black', width=1), showlegend=False), row=3, col=1)
    
    # Monthly MACD hist
    if not df_m.empty:
        df_m['histM'] = histM.values
        fig.add_trace(go.Bar(x=df_m['date'], y=df_m['histM'], name='Monthly', marker_color=['#1f77b4' if v>=0 else '#ff7f0e' for v in df_m['histM']]), row=4, col=1)
        fig.add_trace(go.Scatter(x=df_m['date'], y=[0]*len(df_m), mode='lines', line=dict(color='black', width=1), showlegend=False), row=4, col=1)
    
    fig.update_layout(title=f"{ticker} — Multi-Timeframe MACD", xaxis_rangeslider_visible=False, template='plotly_white', height=900)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="MACD Hist", row=2, col=1)
    fig.update_yaxes(title_text="MACD Hist", row=3, col=1)
    fig.update_yaxes(title_text="MACD Hist", row=4, col=1)
    
    st.plotly_chart(fig, use_container_width=True)

# --- UI layout ---------------------------------------------------------------
sidebar = st.sidebar
sidebar.header("Overview Controls")

# OPTIMIZED: Show DB path and module status
if sidebar.checkbox("Show system info", value=False):
    st.sidebar.markdown("---")
    st.sidebar.caption(f"**DB Path:** `{DB_PATH}`")
    st.sidebar.caption(f"**Ref DB:** `{DEFAULT_LOCAL_DB}`")
    st.sidebar.caption(f"**TCBS Module:** {'✓ Available' if HAS_BDB else '✗ Not Available'}")
    st.sidebar.caption(f"**Ticker Manager:** {'✓ Available' if HAS_TM else '✗ Not Available'}")

debug = sidebar.checkbox("Show debug info (DB diagnostics)", value=False)
debug_flag = debug

# OPTIMIZED: Cache clear button
if sidebar.button("Clear cache & reload"):
    try:
        load_price_range.clear()
        get_all_tickers.clear()
        st.success("Cache cleared")
    except Exception:
        pass

all_tickers = get_all_tickers(debug=debug)

days_back = sidebar.number_input("Days back for analysis", min_value=60, max_value=3650, value=365)
lookback = sidebar.slider("Lookback (bars) for trough/peak detection", 5, 60, 20)

# OPTIMIZED: TCBS refresh only if module available
if HAS_BDB:
    sidebar.markdown("### TCBS refresh (all tickers)")
    refresh_interval_min = sidebar.number_input("Refresh interval (minutes)", min_value=5, max_value=60, value=10, step=1)
    pause_between = sidebar.number_input("Pause between calls (s)", min_value=0.0, max_value=5.0, value=0.25, step=0.05)
    confirm_all = sidebar.checkbox("I confirm: refresh ALL tickers from TCBS", value=False)
    force_all_btn = sidebar.button("Force refresh ALL tickers now")
else:
    force_all_btn = False
    st.sidebar.warning("TCBS refresh disabled (build_price_db not available)")

# date range
end_date = datetime.now().date()
start_date = end_date - timedelta(days=int(days_back))

if debug:
    st.sidebar.write(f"[DEBUG] Date range: {start_date} to {end_date}")
    st.sidebar.write(f"[DEBUG] Total tickers: {len(all_tickers)}")

# OPTIMIZED: Force refresh ALL tickers (only if HAS_BDB)
if force_all_btn and HAS_BDB:
    if not confirm_all:
        st.warning("Check the confirmation checkbox before refreshing all tickers.")
    else:
        tickers_to_refresh = all_tickers[:]
        if not tickers_to_refresh:
            st.warning("No tickers found to refresh.")
        else:
            st.info(f"Starting TCBS refresh for {len(tickers_to_refresh)} tickers (REPLACE mode)...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            updated_count = 0
            error_count = 0
            
            for i, tk in enumerate(tickers_to_refresh, start=1):
                status_text.text(f"Refreshing {tk} ({i}/{len(tickers_to_refresh)})...")
                try:
                    days_to_fetch = 365
                    df_new = bdb.fetch_and_scale(tk, days=days_to_fetch, db_path=DB_PATH)
                    
                    if df_new is not None and not df_new.empty:
                        if 'tradingDate' in df_new.columns:
                            df_new['date'] = pd.to_datetime(df_new['tradingDate']).dt.strftime('%Y-%m-%d')
                        elif 'date' in df_new.columns:
                            df_new['date'] = pd.to_datetime(df_new['date']).dt.strftime('%Y-%m-%d')
                        
                        conn = sqlite3.connect(DB_PATH)
                        cur = conn.cursor()
                        cur.execute("DELETE FROM price_data WHERE ticker = ? AND source = 'tcbs'", (tk,))
                        deleted_rows = cur.rowcount
                        conn.commit()
                        conn.close()
                        
                        bdb.upsert_prices_from_df(df_new.assign(ticker=tk), db_path=DB_PATH, ticker=tk, source="tcbs")
                        updated_count += 1
                        status_text.text(f"✓ {tk}: replaced {deleted_rows} old rows with {len(df_new)} new rows")
                    else:
                        status_text.text(f"⚠ {tk}: no data from TCBS")
                        
                except Exception as e:
                    error_count += 1
                    status_text.text(f"✗ {tk}: {str(e)[:50]}")
                    time.sleep(0.5)
                
                progress_bar.progress(int(i / len(tickers_to_refresh) * 100))
                time.sleep(float(pause_between))
            
            try:
                load_price_range.clear()
                get_all_tickers.clear()
            except Exception:
                pass
            
            status_text.empty()
            progress_bar.empty()
            
            st.success(f"✓ Refresh complete: {updated_count} replaced, {error_count} errors")
            
            # OPTIMIZED: Run unit cleaner after refresh
            st.info("Running unit cleaner to fix scale mismatches...")
            try:
                fixes = bdb.scan_and_fix(
                    db_path=DB_PATH, 
                    ref_db=DEFAULT_LOCAL_DB,
                    dry_run=False,
                    since_date=None
                )
                if fixes:
                    st.success(f"✓ Applied {len(fixes)} scale fixes:")
                    fixed_summary = {}
                    for ticker, tcbs_close, ref_close, scale, operation, method in fixes:
                        if operation not in fixed_summary:
                            fixed_summary[operation] = []
                        fixed_summary[operation].append(f"{ticker}(x{scale if operation=='multiply' else f'÷{scale}'})")
                    
                    for op, tickers_list in fixed_summary.items():
                        st.write(f"  {op.upper()}: {', '.join(tickers_list[:10])}" + (f" +{len(tickers_list) - 10} more" if len(tickers_list) > 10 else ""))
                else:
                    st.success("✓ No scale issues detected - all data is clean")
            except Exception as e:
                st.warning(f"⚠ Unit cleaner error: {e}")
            
            # Show debug sample data if debug mode enabled
            if debug:
                st.markdown("#### Debug: Sample price data after refresh")
                conn = sqlite3.connect(DB_PATH)
                try:
                    # Show sample data for first 3 tickers
                    sample_tickers = all_tickers[:3]
                    for tk in sample_tickers:
                        st.markdown(f"**{tk}** — Last 5 rows:")
                        df_sample = pd.read_sql_query(
                            "SELECT date, open, high, low, close, volume, source FROM price_data WHERE ticker = ? ORDER BY date DESC LIMIT 5",
                            conn,
                            params=(tk,)
                        )
                        if not df_sample.empty:
                            st.dataframe(df_sample, use_container_width=True)
                        else:
                            st.caption(f"No data for {tk}")
                    
                    # Show today's TCBS data for GMD specifically
                    st.markdown("---")
                    st.markdown("**GMD (Sample Ticker)** — Today's TCBS Data:")
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    # Try to fetch fresh TCBS data for GMD
                    try:
                        st.caption(f"Fetching live TCBS data for GMD...")
                        df_gmd_tcbs = bdb.fetch_and_scale("GMD", days=5, db_path=DB_PATH)
                        
                        if df_gmd_tcbs is not None and not df_gmd_tcbs.empty:
                            # Normalize column names
                            if 'tradingDate' in df_gmd_tcbs.columns:
                                df_gmd_tcbs['date'] = pd.to_datetime(df_gmd_tcbs['tradingDate']).dt.strftime('%Y-%m-%d')
                            elif 'date' in df_gmd_tcbs.columns:
                                df_gmd_tcbs['date'] = pd.to_datetime(df_gmd_tcbs['date']).dt.strftime('%Y-%m-%d')
                            
                            # Show last 3 rows from TCBS (including today if available)
                            display_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                            available_cols = [c for c in display_cols if c in df_gmd_tcbs.columns]
                            st.dataframe(df_gmd_tcbs[available_cols].tail(3), use_container_width=True)
                            
                            # Check if today's data exists
                            today_data = df_gmd_tcbs[df_gmd_tcbs['date'] == today_str]
                            if not today_data.empty:
                                st.success(f"✓ Today's data ({today_str}) is present in TCBS feed")
                            else:
                                st.warning(f"⚠ Today's data ({today_str}) not yet available from TCBS")
                        else:
                            st.warning("No data returned from TCBS for GMD")
                    except Exception as e:
                        st.error(f"Error fetching GMD from TCBS: {e}")
                    
                    # Show what's in the database for GMD
                    st.markdown("**GMD** — Data in price_data.db:")
                    df_gmd_db = pd.read_sql_query(
                        "SELECT date, open, high, low, close, volume, source FROM price_data WHERE ticker = 'GMD' ORDER BY date DESC LIMIT 5",
                        conn
                    )
                    if not df_gmd_db.empty:
                        st.dataframe(df_gmd_db, use_container_width=True)
                        
                        # Compare DB vs today
                        latest_db_date = df_gmd_db['date'].iloc[0]
                        if latest_db_date == today_str:
                            st.success(f"✓ Database has today's data ({today_str})")
                        else:
                            st.info(f"ℹ Database latest date: {latest_db_date} (today is {today_str})")
                    else:
                        st.caption("No GMD data in database")
                        
                except Exception as e:
                    st.error(f"Error loading sample data: {e}")
                finally:
                    conn.close()
            
            st.info("Dashboard will reload with fresh data...")
            time.sleep(2)
            st.rerun()

# --- Admin: Manage Tickers (if HAS_TM) --------------------------------------
# NEW: Admin Panel (expandable section)
with sidebar.expander("🔧 Admin: Manage Tickers", expanded=False):
    if not HAS_TM:
        st.warning("Ticker manager not available")
    else:
        st.markdown("**Add Ticker**")
        new_ticker = st.text_input("Ticker symbol", key="add_ticker_input", placeholder="e.g., VIC")
        new_source = st.selectbox("Data source", ["manual", "tcbs", "local_copy", "amibroker"], key="add_source")
        if st.button("➕ Add Ticker"):
            if new_ticker:
                if tm.add_ticker(new_ticker.upper(), db_path=DB_PATH, source=new_source):
                    st.success(f"✓ Added {new_ticker.upper()}")
                    # Clear cache to reload ticker list
                    try:
                        get_all_tickers.clear()
                    except:
                        pass
                else:
                    st.warning(f"Ticker {new_ticker.upper()} already exists")
            else:
                st.error("Enter a ticker symbol")
        
        st.markdown("---")
        st.markdown("**Remove Ticker**")
        
        # Get current tickers for dropdown
        current_tickers_df = tm.get_all_tickers(db_path=DB_PATH)
        if not current_tickers_df.empty:
            unique_tickers = sorted(current_tickers_df['ticker'].unique())
            remove_ticker = st.selectbox("Select ticker to remove", unique_tickers, key="remove_ticker_select")
            remove_source = st.selectbox("Source (or all)", ["all"] + list(current_tickers_df['source'].unique()), key="remove_source")
            confirm_remove = st.checkbox("I confirm deletion", key="confirm_remove")
            
            if st.button("🗑️ Remove Ticker"):
                if confirm_remove:
                    source_filter = None if remove_source == "all" else remove_source
                    deleted = tm.remove_ticker(remove_ticker, db_path=DB_PATH, source=source_filter, confirm=True)
                    if deleted > 0:
                        st.success(f"✓ Deleted {deleted} rows for {remove_ticker}")
                        try:
                            get_all_tickers.clear()
                            load_price_range.clear()
                        except:
                            pass
                        st.rerun()
                    else:
                        st.warning("No rows deleted")
                else:
                    st.error("Check confirmation box to delete")
        else:
            st.info("No tickers in database")
        
        st.markdown("---")
        st.markdown("**Bulk Import CSV**")
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"], key="csv_upload")
        import_source = st.text_input("Source label", value="csv_import", key="import_source")
        
        if uploaded_file is not None:
            if st.button("📥 Import CSV"):
                # Save uploaded file temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                inserted, errors = tm.import_tickers_from_csv(tmp_path, db_path=DB_PATH, source=import_source)
                os.unlink(tmp_path)
                
                if inserted > 0:
                    st.success(f"✓ Imported {inserted} rows ({errors} errors)")
                    try:
                        get_all_tickers.clear()
                        load_price_range.clear()
                    except:
                        pass
                else:
                    st.error(f"Import failed: {errors} errors")
        
        st.markdown("---")
        st.markdown("**View All Tickers**")
        if st.button("📋 Show Ticker List"):
            df_tickers = tm.get_all_tickers(db_path=DB_PATH)
            if not df_tickers.empty:
                st.dataframe(df_tickers, use_container_width=True)
            else:
                st.info("No tickers in database")

# Always build overview
with st.spinner("Building overview for tickers in DB..."):
    tickers = all_tickers
    if not tickers:
        df_over = pd.DataFrame()
    else:
        df_over = build_overview(tickers, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), lookback=lookback, max_rows=len(tickers))

# Main view: always show today/overview table with current date in header
current_date_str = datetime.now().strftime("%Y-%m-%d")
st.markdown(f"##### Overview — latest bar per ticker ({current_date_str})")  # Changed from st.subheader() to smaller heading

if df_over is None or df_over.empty:
    st.warning("No data available to build overview. Ensure price_data.db or analysis_results.db has rows; you can import or run API updates.")
    if not all_tickers:
        st.info("No tickers found in price_data.db or analysis_results.db. Run: `python build_price_db.py --copy-existing` to seed data.")
    else:
        st.info(f"Found {len(all_tickers)} tickers but no data in date range [{start_date} to {end_date}]. Try increasing 'Days back' or run API updates.")
else:
    # NEW: Add quick commentary section - ultra-simplified with improved velocity prediction
    st.markdown("###### 🎯 Quick Commentary")  # Changed from ##### to ###### (even smaller)
    vol_filter = st.checkbox("Vol ≥1.5x only", value=False)
    
    # Extract numeric values for filtering
    df_analysis = df_over.copy()
    df_analysis['macd_d_num'] = df_analysis['MACD_Hist_Daily'].replace('', np.nan).astype(float)
    df_analysis['vol_ratio_num'] = df_analysis['Vol/AvgVol'].str.rstrip('x').astype(float)
    
    # IMPROVED: Calculate velocity with multiple lookback periods for better detection
    @st.cache_data(ttl=60)
    def estimate_days_to_cross(ticker, current_hist):
        """Estimate days until zero-cross based on recent velocity. Returns None if >5 days or moving away."""
        df_hist = load_price_range(ticker, (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d"))
        if len(df_hist) < 10:
            return None
        _, _, hist_series = macd_hist(df_hist['close'].astype(float))
        
        # Try multiple velocity calculations (recent 3, 5, 10 bars)
        velocities = []
        for lookback in [3, 5, 10]:
            recent_hist = hist_series.tail(lookback).values
            if len(recent_hist) >= 2:
                velocity = np.mean(np.diff(recent_hist))
                if abs(velocity) > 0.005:  # lower threshold from 0.01
                    velocities.append(velocity)
        
        if not velocities:
            return None
        
        # Use median velocity to be more robust
        velocity = np.median(velocities)
        
        if abs(velocity) < 0.005:  # still too slow
            return None
        
        days = abs(current_hist / velocity)
        
        # Include if moving toward zero and will cross in 1-5 days (increased from 1-3)
        if current_hist < 0 and velocity > 0 and 0.5 <= days <= 5:
            return days
        if current_hist > 0 and velocity < 0 and 0.5 <= days <= 5:
            return days
        return None
    
    # Confirmed crosses
    just_crossed_up = df_analysis[df_analysis['Trend (Daily)'].str.contains('Confirmed Trough', na=False)]
    just_crossed_down = df_analysis[df_analysis['Trend (Daily)'].str.contains('Confirmed Peak', na=False)]
    
    # IMPROVED: Broader near cross candidates (include more negative/positive values)
    near_cross_up_candidates = df_analysis[
        (df_analysis['Trend (Daily)'].str.contains('Troughing|Falling', na=False)) &
        (df_analysis['macd_d_num'] < 0) &
        (df_analysis['macd_d_num'] > -0.5)  # wider range
    ]
    near_cross_down_candidates = df_analysis[
        (df_analysis['Trend (Daily)'].str.contains('Peaking|Rising', na=False)) &
        (df_analysis['macd_d_num'] > 0) &
        (df_analysis['macd_d_num'] < 0.5)  # wider range
    ]
    
    # Filter by velocity (1-5 days to cross)
    near_cross_up = []
    for idx, row in near_cross_up_candidates.iterrows():
        try:
            days = estimate_days_to_cross(row['Ticker'], row['macd_d_num'])
            if days and days <= 3:  # only show 1-3 days in display
                near_cross_up.append((row['Ticker'], days))
        except Exception:
            pass
    
    near_cross_down = []
    for idx, row in near_cross_down_candidates.iterrows():
        try:
            days = estimate_days_to_cross(row['Ticker'], row['macd_d_num'])
            if days and days <= 3:  # only show 1-3 days in display
                near_cross_down.append((row['Ticker'], days))
        except Exception:
            pass
    
    # Apply volume filter
    if vol_filter:
        just_crossed_up = just_crossed_up[just_crossed_up['vol_ratio_num'] >= 1.5]
        just_crossed_down = just_crossed_down[just_crossed_down['vol_ratio_num'] >= 1.5]
        near_cross_up = [(t, d) for t, d in near_cross_up if df_analysis[df_analysis['Ticker'] == t]['vol_ratio_num'].values[0] >= 1.5]
        near_cross_down = [(t, d) for t, d in near_cross_down if df_analysis[df_analysis['Ticker'] == t]['vol_ratio_num'].values[0] >= 1.5]
    
    # Sort by days (ascending)
    near_cross_up = sorted(near_cross_up, key=lambda x: x[1])
    near_cross_down = sorted(near_cross_down, key=lambda x: x[1])
    
    # Display in compact format
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🟢 Bullish**")
        if not just_crossed_up.empty:
            st.caption(f"✓ Crossed: {', '.join(just_crossed_up.head(8)['Ticker'].tolist())} ({len(just_crossed_up)})")
        if near_cross_up:
            tickers_with_days = [f"{t}({int(d)}d)" for t, d in near_cross_up[:8]]
            st.caption(f"→ Near (1-3d): {', '.join(tickers_with_days)}")
        if just_crossed_up.empty and not near_cross_up:
            st.caption("None")
    
    with col2:
        st.markdown("**🔴 Bearish**")
        if not just_crossed_down.empty:
            st.caption(f"✓ Crossed: {', '.join(just_crossed_down.head(8)['Ticker'].tolist())} ({len(just_crossed_down)})")
        if near_cross_down:
            tickers_with_days = [f"{t}({int(d)}d)" for t, d in near_cross_down[:8]]
            st.caption(f"→ Near (1-3d): {', '.join(tickers_with_days)}")
        if just_crossed_down.empty and not near_cross_down:
            st.caption("None")
    
    st.markdown("---")
    
    # Display main overview table
    display_cols = ["Ticker","Close","Trend (Daily)","Trend (Weekly)","Trend (Monthly)","Score","MACD_Hist_Daily","MACD_Hist_Weekly","MACD_Hist_Monthly","Vol/AvgVol"]
    
    # Apply complex conditional styling - fixed approach
    styled = df_over[display_cols].style
    
    # Style Trend columns
    styled = styled.applymap(style_stage_column, subset=["Trend (Daily)", "Trend (Weekly)", "Trend (Monthly)"])
    
    # Style Vol/AvgVol
    styled = styled.applymap(style_vol_ratio, subset=["Vol/AvgVol"])
    
    # Style Ticker and Close based on Score - use full row apply without subset
    def style_row_by_score(row):
        score = row["Score"]
        ticker_style = style_by_score(row["Ticker"], score)
        close_style = style_by_score(row["Close"], score)
        # Return style for each column - empty string for columns we don't want to style
        return pd.Series([
            ticker_style,  # Ticker
            close_style,   # Close
            '',            # Trend (Daily)
            '',            # Trend (Weekly)
            '',            # Trend (Monthly)
            '',            # Score
            '',            # MACD_Hist_Daily
            '',            # MACD_Hist_Weekly
            '',            # MACD_Hist_Monthly
            ''             # Vol/AvgVol
        ], index=display_cols)
    
    styled = styled.apply(style_row_by_score, axis=1)
    
    # Style MACD hist columns based on their respective trends
    def style_macd_by_trends(row):
        daily_trend = row["Trend (Daily)"]
        weekly_trend = row["Trend (Weekly)"]
        monthly_trend = row["Trend (Monthly)"]
        
        macd_d_style = style_macd_by_trend(row["MACD_Hist_Daily"], daily_trend)
        macd_w_style = style_macd_by_trend(row["MACD_Hist_Weekly"], weekly_trend)
        macd_m_style = style_macd_by_trend(row["MACD_Hist_Monthly"], monthly_trend)
        
        # Return style for each column
        return pd.Series([
            '',            # Ticker
            '',            # Close
            '',            # Trend (Daily)
            '',            # Trend (Weekly)
            '',            # Trend (Monthly)
            '',            # Score
            macd_d_style,  # MACD_Hist_Daily
            macd_w_style,  # MACD_Hist_Weekly
            macd_m_style,  # MACD_Hist_Monthly
            ''             # Vol/AvgVol
        ], index=display_cols)
    
    styled = styled.apply(style_macd_by_trends, axis=1)
    
    # Display styled dataframe
    st.dataframe(styled, height=700, use_container_width=True)
    
    st.markdown("### 💡 Click a ticker in the table above to view detailed charts")
    st.markdown("Select a ticker from the dropdown or type to search:")
    selected_ticker_input = st.selectbox("Select ticker for detailed view", options=[""] + df_over['Ticker'].tolist(), index=0, key="ticker_selector")
    
    if selected_ticker_input:
        st.session_state.selected_ticker = selected_ticker_input
    
    st.download_button("Download overview CSV", data=df_over.to_csv(index=False).encode('utf-8'), file_name=f"macd_overview_{current_date_str}.csv", mime="text/csv")
    
    if debug:
        st.markdown("### Debug diagnostics (overview built successfully)")
        pstats = _get_db_stats(DB_PATH)
        st.write(f"Tickers in DB: {len(all_tickers)}, Rows in overview: {len(df_over)}")
        st.json({"price_data": pstats})

# --- Detailed chart view (for selected ticker) --------------------------------
if st.session_state.selected_ticker:
    ticker = st.session_state.selected_ticker
    
    st.subheader(f"Detailed MACD Analysis — {ticker}")
    
    # --- Price and MACD histograms (multi-timeframe) ---------------------------
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown("#### 📈 Price Chart")
        # --- Price chart with MACD histograms --------------------------------
        df = load_price_range(ticker, start_date, end_date)
        if df.empty:
            st.warning(f"No price data found for {ticker} in the selected date range.")
        else:
            # --- Candlestick chart with MACD histograms ------------------------
            plot_multi_tf_macd(ticker, start_date, end_date, lookback=lookback)
    
    with col2:
        st.markdown("#### 📊 MACD Histogram Analysis")
        # --- MACD histogram analysis (daily/weekly/monthly) ----------------
        df = load_price_range(ticker, start_date, end_date)
        if df.empty:
            st.warning(f"No price data found for {ticker} in the selected date range.")
        else:
            # Calculate MACD histograms
            df['macd_line'], df['macd_signal'], df['macd_hist'] = macd_hist(df['close'].astype(float))
            
            # Resample for weekly and monthly
            df_w = df.set_index('date').resample('W').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
            df_m = df.set_index('date').resample('M').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
            
            # Calculate MACD for resampled data
            if not df_w.empty:
                df_w['macd_line'], df_w['macd_signal'], df_w['macd_hist'] = macd_hist(df_w['close'].astype(float))
            if not df_m.empty:
                df_m['macd_line'], df_m['macd_signal'], df_m['macd_hist'] = macd_hist(df_m['close'].astype(float))
            
            # --- Multi-timeframe MACD histogram plot ----------------------------
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.02,
                                subplot_titles=("Price", "MACD Histogram (Daily)", "MACD Histogram (Weekly)"))
            
            # Price
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
            
            # Daily MACD hist
            df['histD'] = df['macd_hist']
            fig.add_trace(go.Bar(x=df['date'], y=df['histD'], name='Daily', marker_color=['#1f77b4' if v>=0 else '#ff7f0e' for v in df['histD']]), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=[0]*len(df), mode='lines', line=dict(color='black', width=1), showlegend=False), row=2, col=1)
            
            # Weekly MACD hist
            if not df_w.empty:
                df_w['histW'] = df_w['macd_hist']
                fig.add_trace(go.Bar(x=df_w['date'], y=df_w['histW'], name='Weekly', marker_color=['#1f77b4' if v>=0 else '#ff7f0e' for v in df_w['histW']]), row=3, col=1)
                fig.add_trace(go.Scatter(x=df_w['date'], y=[0]*len(df_w), mode='lines', line=dict(color='black', width=1), showlegend=False), row=3, col=1)
            
            fig.update_layout(title=f"{ticker} — MACD Histogram Analysis", xaxis_rangeslider_visible=False, template='plotly_white', height=800)
            fig.update_yaxes(title_text="Price", row=1, col=1)
            fig.update_yaxes(title_text="MACD Histogram", row=2, col=1)
            fig.update_yaxes(title_text="MACD Histogram", row=3, col=1)
            
            st.plotly_chart(fig, use_container_width=True)
    
    # --- Download and debug info --------------------------------------------
    st.markdown("---")
    st.markdown("### Data and Diagnostics")
    
    # Download links for raw data
    df_full = load_price_range(ticker, "2000-01-01", end_date)
    if not df_full.empty:
        csv = df_full.to_csv(index=False).encode('utf-8')
        st.download_button("Download full data CSV", data=csv, file_name=f"{ticker}_full_data.csv", mime="text/csv")
    else:
        st.warning("No full data available for download.")
    
    # Debug diagnostics
    if debug:
        st.markdown("#### Debug Diagnostics")
        pstats = _get_db_stats(DB_PATH)
        st.json({"price_data": pstats})
        st.write(f"Processed {len(df_full)} rows of price data for {ticker}.")
        if not df_full.empty:
            st.write(f"Date range in data: {df_full['date'].min()} to {df_full['date'].max()}")
        else:
            st.write("No price data found.")
    
    # --- End of detailed view ----------------------------------------------
    st.markdown("---")
    st.markdown("### Return to Overview")
    if st.button("Back to Overview"):
        st.session_state.selected_ticker = None
        st.experimental_rerun()
