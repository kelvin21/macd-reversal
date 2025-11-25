import os
import sqlite3
import argparse
import json
from datetime import datetime, timedelta
import time

import pandas as pd
import numpy as np
import requests

# Optional dependency for SFTP upload
try:
    import paramiko
except Exception:
    paramiko = None

DEFAULT_LOCAL_DB = "analysis_results.db"       # existing DB to copy from
NEW_DB_PATH = "price_data.db"                  # new DB to build/store OHLCV
TCBS_URL = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
CHUNK = 500

# NEW: lookback window used by median/ autoscaling helpers
LOOKBACK_DAYS = 60


def create_db(db_path=NEW_DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date DATE NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            source TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_ticker_date ON price_data(ticker, date)")
    # NEW: table to remember TCBS scaling per ticker
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tcbs_scaling (
            ticker TEXT PRIMARY KEY,
            scale INTEGER,
            detected_by TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"✅ Created/ensured schema in {db_path}")


def copy_existing_market_data(source_db=DEFAULT_LOCAL_DB, target_db=NEW_DB_PATH, limit=None):
    """Copy market_data from current analysis_results.db into new DB (initial load)."""
    if not os.path.exists(source_db):
        raise FileNotFoundError(f"Source DB not found: {source_db}")
    create_db(target_db)
    src_conn = sqlite3.connect(source_db)
    tgt_conn = sqlite3.connect(target_db)

    # attempt to read available columns from source
    query = "SELECT ticker, date, open, high, low, close, volume FROM market_data"
    if limit:
        query += f" LIMIT {limit}"
    df = pd.read_sql_query(query, src_conn)
    src_conn.close()
    if df.empty:
        print("No market_data rows found in source DB")
        tgt_conn.close()
        return 0

    # Normalize columns
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"date": "date"})
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    df['source'] = 'local_copy'
    df = df[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'source']]

    # upsert in batches
    cursor = tgt_conn.cursor()
    total = 0
    insert_sql = """
        INSERT OR REPLACE INTO price_data
        (ticker, date, open, high, low, close, volume, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    for start in range(0, len(df), CHUNK):
        chunk = df.iloc[start:start + CHUNK]
        params = [(
            row.ticker, row.date, _safe(row.open), _safe(row.high),
            _safe(row.low), _safe(row.close), int(_safe_int(row.volume)),
            row.source
        ) for row in chunk.itertuples()]
        cursor.executemany(insert_sql, params)
        tgt_conn.commit()
        total += len(params)
        print(f"  ↳ Copied {total}/{len(df)}")
    tgt_conn.close()
    print(f"✅ Copied {total} rows into {target_db}")
    return total


def _safe(x):
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass
    return float(x) if x is not None else None


def _safe_int(x):
    try:
        if pd.isna(x):
            return 0
    except Exception:
        pass
    try:
        return int(x)
    except Exception:
        return 0


def fetch_historical_price(ticker: str, days: int = 365, resolution: str = "D", timeout=15) -> pd.DataFrame:
    """Fetch stock historical price and volume data from TCBS API.
    Returns DataFrame with columns: tradingDate(datetime), open, high, low, close, volume
    """
    to_timestamp = int(datetime.now().timestamp())
    from_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())

    params = {
        "ticker": ticker,
        "type": "stock",
        "resolution": resolution,
        "from": str(from_timestamp),
        "to": str(to_timestamp)
    }

    headers = {
        "User-Agent": "ami2py/1.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(TCBS_URL, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        payload = r.json()
        data = payload.get('data') or payload.get('bars') or payload
        if not data:
            print(f"⚠️ No data returned for {ticker}")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        # Normalize trading date column
        if 'tradingDate' in df.columns:
            # tradingDate might be ISO string or epoch ms
            sample = df['tradingDate'].iloc[0]
            if isinstance(sample, str) and 'T' in sample:
                df['tradingDate'] = pd.to_datetime(df['tradingDate'])
            else:
                df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms', errors='coerce')
        else:
            # try common columns
            for col in ('datetime', 'timestamp', 'date'):
                if col in df.columns:
                    try:
                        df['tradingDate'] = pd.to_datetime(df[col], unit='ms', errors='coerce') \
                            if np.issubdtype(df[col].dtype, np.number) else pd.to_datetime(df[col], errors='coerce')
                        break
                    except Exception:
                        continue

        # keep relevant columns
        cols_map = {}
        for c in df.columns:
            lc = c.lower()
            if lc in ('open', 'high', 'low', 'close', 'volume'):
                cols_map[c] = lc
        df = df.rename(columns=cols_map)
        if 'tradingDate' not in df.columns:
            print(f"⚠️ No date column for {ticker} - skipping")
            return pd.DataFrame()
        df = df[['tradingDate'] + [c for c in ['open', 'high', 'low', 'close', 'volume'] if c in df.columns]]
        df = df.dropna(subset=['tradingDate'])
        df = df.sort_values('tradingDate').reset_index(drop=True)
        return df
    except requests.RequestException as e:
        print(f"❌ HTTP error fetching {ticker}: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Unexpected error fetching {ticker}: {e}")
        return pd.DataFrame()


def upsert_prices_from_df(df: pd.DataFrame, db_path=NEW_DB_PATH, ticker=None, source='api'):
    """Upsert normalized DataFrame into price_data table. df must have tradingDate, open, high, low, close, volume."""
    if df.empty:
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    insert_sql = """
        INSERT OR REPLACE INTO price_data
        (ticker, date, open, high, low, close, volume, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    df = df.copy()
    if 'tradingDate' in df.columns:
        df['date'] = pd.to_datetime(df['tradingDate']).dt.strftime('%Y-%m-%d')
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    else:
        raise ValueError("DataFrame missing date/tradingDate column")

    df['ticker'] = ticker if ticker else df.get('ticker', None)
    if df['ticker'].isnull().any():
        raise ValueError("Ticker not provided and not present in DataFrame")

    rows = []
    for row in df.itertuples(index=False):
        rows.append((
            row.ticker if hasattr(row, 'ticker') else ticker,
            row.date,
            _safe(getattr(row, 'open', None)),
            _safe(getattr(row, 'high', None)),
            _safe(getattr(row, 'low', None)),
            _safe(getattr(row, 'close', None)),
            _safe_int(getattr(row, 'volume', 0)),
            source
        ))
    total = 0
    for i in range(0, len(rows), CHUNK):
        batch = rows[i:i+CHUNK]
        cursor.executemany(insert_sql, batch)
        conn.commit()
        total += len(batch)
        print(f"  ↳ Upserted {total}/{len(rows)}")
    conn.close()
    return total


# NEW helper: get local DB median for a ticker (used by fetch_and_scale / autoscaling)
def _get_local_db_median(ticker, db_paths=None, lookback_days=LOOKBACK_DAYS):
    """
    Return median close for ticker from first available DB in db_paths using recent lookback.
    Default search order: NEW_DB_PATH (price_data.db), then DEFAULT_LOCAL_DB (analysis_results.db).
    """
    if db_paths is None:
        db_paths = [NEW_DB_PATH, DEFAULT_LOCAL_DB]
    for db_path in db_paths:
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            # prefer market_data table if present, else price_data
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('market_data','price_data')")
            tables = [r[0] for r in cur.fetchall()]
            if 'market_data' in tables:
                q = "SELECT close FROM market_data WHERE ticker = ? AND date >= date('now', ? || ' day')"
            elif 'price_data' in tables:
                q = "SELECT close FROM price_data WHERE ticker = ? AND date >= date('now', ? || ' day')"
            else:
                conn.close()
                continue
            cur.execute(q, (ticker, f"-{lookback_days}"))
            rows = [r[0] for r in cur.fetchall() if r[0] is not None]
            conn.close()
            if rows:
                return float(pd.Series(rows).median())
        except Exception:
            # ignore DB errors and try next DB
            continue
    return None


def fetch_and_scale(ticker: str, days: int = 365, resolution: str = "D", timeout=15, db_path=NEW_DB_PATH) -> pd.DataFrame:
    """Fetch and auto-scale TCBS data for a ticker.
    If a saved scale exists in db_path.tcbs_scaling, apply it immediately.
    Otherwise detect autoscale and save the detected scale for future runs.
    If no local median is available, apply default 1000 when TCBS values are large (except VNINDEX).
    """
    df = fetch_historical_price(ticker, days=days, resolution=resolution, timeout=timeout)
    if df is None or df.empty:
        return df

    t_up = (ticker or "").upper()
    # Exclude VNINDEX from autoscaling/default scaling
    if t_up == "VNINDEX":
        return df

    # 1) Check saved scale first
    saved = get_saved_scale(t_up, db_path=db_path)
    if saved:
        try:
            applied_cols = []
            for col in ('open','high','low','close'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce') / saved
                    applied_cols.append(col)
            print(f"[tcbs_api] Applied saved scale /{saved} for {ticker} (cols: {', '.join(applied_cols)})")
        except Exception as e:
            print(f"[tcbs_api] Warning applying saved scale for {ticker}: {e}")
        return df

    # 2) No saved scale — perform detection like before
    try:
        tcbs_median = float(pd.to_numeric(df['close'], errors='coerce').median(skipna=True))
    except Exception:
        tcbs_median = None
    if tcbs_median is None or tcbs_median <= 0:
        return df

    db_median = _get_local_db_median(ticker)
    scale_to_apply = None

    if db_median is not None and db_median > 0:
        ratio = tcbs_median / db_median
        if ratio > THRESHOLD_RATIO:
            for candidate in SCALE_CANDIDATES:
                if abs(ratio - candidate) / candidate < 0.2:
                    scale_to_apply = candidate
                    break
    else:
        # default heuristic when no reference
        if tcbs_median > 1000:
            scale_to_apply = 1000

    if scale_to_apply:
        try:
            for col in ('open','high','low','close'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce') / scale_to_apply
            # persist detected scale for future runs
            save_scale(ticker, scale_to_apply, db_path=db_path, detected_by='autoscale', note=f"tcbs_median={tcbs_median}, db_median={db_median}")
            print(f"⚙️ Scaling {ticker} data by factor of {scale_to_apply} (TCBS median: {tcbs_median}, DB median: {db_median})")
        except Exception as e:
            print(f"⚠️ Error applying detected scale for {ticker}: {e}")

    return df


# NEW: helpers to persist/read saved scaling
def get_saved_scale(ticker, db_path=NEW_DB_PATH):
    """Return saved integer scale for ticker (e.g., 1000) or None."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT scale FROM tcbs_scaling WHERE ticker = ?", (ticker.upper(),))
        row = cur.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None

def save_scale(ticker, scale, db_path=NEW_DB_PATH, detected_by='autoscale', note=None):
    """Insert or update scale for ticker."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tcbs_scaling (ticker, scale, detected_by, detected_at, note)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(ticker) DO UPDATE SET scale=excluded.scale, detected_by=excluded.detected_by, detected_at=excluded.detected_at, note=excluded.note
        """, (ticker.upper(), int(scale), detected_by, note))
        conn.commit()
        conn.close()
        print(f"[tcbs_scaling] Saved scale {scale} for {ticker} in {db_path}")
    except Exception as e:
        print(f"[tcbs_scaling] Failed to save scale for {ticker}: {e}")


def update_from_api(tickers, days=365, db_path=NEW_DB_PATH, source='tcbs'):
    """Fetch + upsert with autoscaling/default-scaling for TCBS data."""
    create_db(db_path)
    total = 0
    for t in tickers:
        print(f"🔎 Fetching {t} ({days} days)...")
        # Pass db_path so fetched scale is read/saved in the correct DB
        df = fetch_and_scale(t, days=days, db_path=db_path)
        if df is None or df.empty:
            print(f"  ⚠️ No data for {t}")
            continue

        upserted = upsert_prices_from_df(df.assign(ticker=t), db_path=db_path, ticker=t, source=source)
        print(f"  ✅ {t}: upserted {upserted} rows")
        total += upserted
        time.sleep(0.5)
    print(f"✅ API update complete. Total rows upserted: {total}")
    return total


def update_all_tickers_via_api(target_db=NEW_DB_PATH, source_db=DEFAULT_LOCAL_DB, days=365, pause=0.25, start_index=0):
    """
    Fetch historical prices for all tickers found in source_db and upsert into target_db.
    Returns number of tickers processed.
    """
    tickers = _get_distinct_tickers_from_db(source_db)
    if not tickers:
        print("No tickers found in source DB.")
        return 0

    create_db(target_db)
    total = 0               # total rows upserted
    processed = 0           # tickers processed
    n = len(tickers)
    print(f"Updating {n} tickers from {source_db} -> {target_db} (days={days})")

    for idx, ticker in enumerate(tickers[start_index:], start=start_index+1):
        try:
            print(f"[{idx}/{n}] Fetching {ticker} ...")
            # Use fetch_and_scale with target_db so scale is saved there
            df = fetch_and_scale(ticker, days=days, db_path=target_db)
            if df is None or df.empty:
                print(f"[{idx}/{n}] {ticker}: no data")
            else:
                # ensure 'tradingDate' present
                if 'tradingDate' not in df.columns and 'date' in df.columns:
                    df = df.rename(columns={'date': 'tradingDate'})
                upserted = upsert_prices_from_df(df.assign(ticker=ticker), db_path=target_db, ticker=ticker, source='tcbs')
                print(f"[{idx}/{n}] {ticker}: upserted {upserted} rows")
                total += upserted
            processed += 1

        except KeyboardInterrupt:
            print("\nInterrupted by user")
            break
        except Exception as e:
            print(f"[{idx}/{n}] {ticker}: error {e}")

        time.sleep(pause)
    print(f"Finished updating {processed} tickers; {total} rows upserted.")
    return processed


def _get_distinct_tickers_from_db(source_db, debug=False):
    """Return list of distinct tickers from an existing DB (market_data or price_data).
    If the provided source_db has no tickers, try DEFAULT_LOCAL_DB as a fallback.
    If debug=True, print detailed table/schema info.
    """
    if not os.path.exists(source_db):
        if debug:
            print(f"[DEBUG] Source DB not found: {source_db}")
        # fallback directly to DEFAULT_LOCAL_DB if available
        source_db = DEFAULT_LOCAL_DB

    try:
        conn = sqlite3.connect(source_db)
        cursor = conn.cursor()
        
        # List ALL tables in the DB (debug)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [r[0] for r in cursor.fetchall()]
        if debug:
            print(f"[DEBUG] {source_db} contains tables: {all_tables}")
        
        # Try market_data first (older DB), then price_data (new DB)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('market_data','price_data')")
        tables = [r[0] for r in cursor.fetchall()]
        tickers = []
        
        if 'market_data' in tables:
            cursor.execute("SELECT DISTINCT ticker FROM market_data")
            tickers = [r[0] for r in cursor.fetchall() if r[0]]
            if debug:
                print(f"[DEBUG] Found {len(tickers)} tickers in market_data table")
        elif 'price_data' in tables:
            cursor.execute("SELECT DISTINCT ticker FROM price_data")
            tickers = [r[0] for r in cursor.fetchall() if r[0]]
            if debug:
                print(f"[DEBUG] Found {len(tickers)} tickers in price_data table")
        else:
            # Neither standard table found — try to find ANY table with a 'ticker' column
            if debug:
                print(f"[DEBUG] Standard tables (market_data/price_data) not found. Checking all tables for 'ticker' column...")
            for tbl in all_tables:
                try:
                    cursor.execute(f"PRAGMA table_info({tbl})")
                    cols = [r[1] for r in cursor.fetchall()]
                    if debug:
                        print(f"[DEBUG] Table {tbl} has columns: {cols}")
                    if 'ticker' in cols:
                        cursor.execute(f"SELECT DISTINCT ticker FROM {tbl}")
                        tickers = [r[0] for r in cursor.fetchall() if r[0]]
                        if debug:
                            print(f"[DEBUG] Found {len(tickers)} tickers in table {tbl}")
                        if tickers:
                            break
                except Exception as e:
                    if debug:
                        print(f"[DEBUG] Error reading table {tbl}: {e}")
        
        conn.close()

        # If no tickers found in the requested DB, attempt fallback to DEFAULT_LOCAL_DB (if different)
        if not tickers and source_db != DEFAULT_LOCAL_DB and os.path.exists(DEFAULT_LOCAL_DB):
            if debug:
                print(f"[DEBUG] No tickers in {source_db}, trying fallback to {DEFAULT_LOCAL_DB}")
            try:
                conn2 = sqlite3.connect(DEFAULT_LOCAL_DB)
                cur2 = conn2.cursor()
                cur2.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('market_data','price_data')")
                tables2 = [r[0] for r in cur2.fetchall()]
                if 'market_data' in tables2:
                    cur2.execute("SELECT DISTINCT ticker FROM market_data")
                    tickers = [r[0] for r in cur2.fetchall() if r[0]]
                elif 'price_data' in tables2:
                    cur2.execute("SELECT DISTINCT ticker FROM price_data")
                    tickers = [r[0] for r in cur2.fetchall() if r[0]]
                conn2.close()
                if tickers and debug:
                    print(f"[DEBUG] Fallback: loaded {len(tickers)} tickers from {DEFAULT_LOCAL_DB}")
            except Exception as e:
                if debug:
                    print(f"[DEBUG] Error reading fallback DB {DEFAULT_LOCAL_DB}: {e}")

        return tickers
    except Exception as e:
        if debug:
            print(f"[DEBUG] Error reading tickers from {source_db}: {e}")
        return []


# --- START: Price unit cleaning utilities ---
SCALE_CANDIDATES = [1000, 100, 10, 10000]
THRESHOLD_RATIO = 5.0  # LOWERED from 10.0 to catch more subtle mismatches

def _get_recent_median_from_db(db_path, table, ticker, lookback_days=LOOKBACK_DAYS, since_date=None):
	"""Return median close for ticker from db_path.
	If since_date is provided (YYYY-MM-DD), use rows with date >= since_date.
	Otherwise use the lookback_days window relative to today.
	"""
	if not os.path.exists(db_path):
		return None
	try:
		conn = sqlite3.connect(db_path)
		cur = conn.cursor()
		if since_date:
			q = f"SELECT close FROM {table} WHERE ticker = ? AND date >= ?"
			cur.execute(q, (ticker, since_date))
		else:
			q = f"SELECT close FROM {table} WHERE ticker = ? AND date >= date('now', ? || ' day')"
			cur.execute(q, (ticker, f"-{lookback_days}"))
		rows = [r[0] for r in cur.fetchall() if r[0] is not None]
		conn.close()
		if rows:
			return float(pd.Series(rows).median())
	except Exception:
		return None
	return None

def _detect_scale(price_median, ref_median):
    """Detect scale mismatch between price_median and ref_median.
    Returns (scale, operation) where:
      - scale: integer factor (1000, 100, 10, etc.)
      - operation: 'divide' if price_median is too large, 'multiply' if too small, None if no mismatch
    """
    if ref_median is None or ref_median <= 0:
        return None, None
    
    ratio = price_median / ref_median
    
    # Case 1: TCBS is too large (normal case: divide by 1000/100/10)
    if ratio > THRESHOLD_RATIO:
        best = min(SCALE_CANDIDATES, key=lambda s: abs(ratio - s))
        if abs(ratio - best) / best < 0.2:
            return best, 'divide'
    
    # Case 2: TCBS is too small (inverse case: multiply by 1000/100/10)
    if ratio < (1.0 / THRESHOLD_RATIO):  # e.g., ratio < 0.2 when THRESHOLD_RATIO=5
        inverse_ratio = ref_median / price_median
        best = min(SCALE_CANDIDATES, key=lambda s: abs(inverse_ratio - s))
        if abs(inverse_ratio - best) / best < 0.2:
            return best, 'multiply'
    
    return None, None

def scan_and_fix(db_path="price_data.db", ref_db="analysis_results.db", dry_run=True, since_date=None):
    """
    Scan price_data.db for tickers whose most recent close (tcbs source) appears scaled relative to local/reference data.
    Only compares when TCBS and local data have overlapping or very recent dates (within 7 days tolerance).
    If dates don't overlap, falls back to median-based comparison over recent window.
    Uses ONLY the latest matching date to determine scale, then applies that scale to ALL TCBS rows for the ticker.
    Reference priority:
      1. Non-TCBS rows in price_data.db (e.g., source='local_copy' or 'amibroker')
      2. market_data in ref_db (analysis_results.db)
    If a scale is detected, divide open/high/low/close by scale (applied only when dry_run=False).
    Only applies fix to rows where source='tcbs'.
    If since_date is provided, only TCBS rows with date >= since_date are fixed (but detection still uses latest overlapping date).
    Returns list of fixes: [(ticker, tcbs_close, ref_close, scale, date_used), ...]
    """
    fixes = []
    if not os.path.exists(db_path):
        print(f"Price DB not found: {db_path}")
        return fixes

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM price_data")
    tickers = [r[0] for r in cur.fetchall() if r[0]]
    print(f"Found {len(tickers)} tickers in {db_path}")

    DATE_TOLERANCE_DAYS = 7  # allow up to 7 days difference for "overlapping"

    for t in tickers:
        # Get LATEST close from TCBS source
        cur.execute("SELECT close, date FROM price_data WHERE ticker = ? AND source = 'tcbs' ORDER BY date DESC LIMIT 1", (t,))
        tcbs_row = cur.fetchone()
        if not tcbs_row or tcbs_row[0] is None:
            continue
        tcbs_latest_close = float(tcbs_row[0])
        tcbs_latest_date_str = tcbs_row[1]
        tcbs_latest_date = pd.to_datetime(tcbs_latest_date_str).date()

        # Get LATEST close from NON-TCBS source (local_copy, amibroker, etc.)
        cur.execute("SELECT close, date FROM price_data WHERE ticker = ? AND source != 'tcbs' ORDER BY date DESC LIMIT 1", (t,))
        local_row = cur.fetchone()
        
        ref_close = None
        ref_date = None
        comparison_method = None
        
        if local_row and local_row[0] is not None:
            local_close = float(local_row[0])
            local_date_str = local_row[1]
            local_date = pd.to_datetime(local_date_str).date()
            
            # Check if dates are close enough (within tolerance)
            date_diff_days = abs((tcbs_latest_date - local_date).days)
            
            if date_diff_days <= DATE_TOLERANCE_DAYS:
                # Dates overlap or are very recent — use latest close comparison
                ref_close = local_close
                ref_date = local_date
                comparison_method = "latest_close"
                print(f"[scan_and_fix] {t}: tcbs_latest={tcbs_latest_close:.2f} ({tcbs_latest_date_str}), local_latest={local_close:.2f} ({local_date_str}), date_diff={date_diff_days} days")
            else:
                # Dates don't overlap — fall back to median-based comparison over recent window
                print(f"[scan_and_fix] {t}: dates don't overlap (tcbs={tcbs_latest_date_str}, local={local_date_str}, diff={date_diff_days} days). Using median fallback.")
                # Compute TCBS median over last LOOKBACK_DAYS
                cur.execute("SELECT close FROM price_data WHERE ticker = ? AND source = 'tcbs' AND date >= date('now', ? || ' day')", (t, f"-{60}"))
                tcbs_closes = [r[0] for r in cur.fetchall() if r[0] is not None]
                tcbs_median = float(pd.Series(tcbs_closes).median()) if tcbs_closes else None
                
                # Compute local median over last LOOKBACK_DAYS
                cur.execute("SELECT close FROM price_data WHERE ticker = ? AND source != 'tcbs' AND date >= date('now', ? || ' day')", (t, f"-{60}"))
                local_closes = [r[0] for r in cur.fetchall() if r[0] is not None]
                local_median = float(pd.Series(local_closes).median()) if local_closes else None
                
                if tcbs_median and local_median and local_median > 0:
                    ref_close = local_median
                    tcbs_latest_close = tcbs_median  # use median for comparison
                    comparison_method = "median_fallback"
                    print(f"[scan_and_fix] {t}: tcbs_median={tcbs_median:.2f}, local_median={local_median:.2f}")
                else:
                    ref_close = None
        
        # If still no local reference, try external ref_db (market_data)
        if ref_close is None:
            if os.path.exists(ref_db):
                try:
                    conn_ref = sqlite3.connect(ref_db)
                    cur_ref = conn_ref.cursor()
                    cur_ref.execute("SELECT close, date FROM market_data WHERE ticker = ? ORDER BY date DESC LIMIT 1", (t,))
                    ref_row = cur_ref.fetchone()
                    if ref_row and ref_row[0] is not None:
                        ref_close = float(ref_row[0])
                        ref_date = pd.to_datetime(ref_row[1]).date()
                        comparison_method = "ref_db_latest"
                    conn_ref.close()
                except Exception:
                    pass
        
        if ref_close is None or ref_close <= 0:
            continue

        # Detect scale using close values (now returns scale AND operation)
        scale, operation = _detect_scale(tcbs_latest_close, ref_close)
        
        if scale and operation:
            fixes.append((t, tcbs_latest_close, ref_close, scale, operation, comparison_method))
            print(f"Ticker {t}: tcbs_close={tcbs_latest_close:.2f}, ref_close={ref_close:.2f}, detected scale={scale}, operation={operation} (method={comparison_method})")
            if not dry_run:
                # Apply fix to ALL TCBS rows for this ticker
                if operation == 'divide':
                    scale_sql = """
                        UPDATE price_data
                        SET open = CASE WHEN open IS NOT NULL THEN open / ? ELSE NULL END,
                            high = CASE WHEN high IS NOT NULL THEN high / ? ELSE NULL END,
                            low = CASE WHEN low IS NOT NULL THEN low / ? ELSE NULL END,
                            close = CASE WHEN close IS NOT NULL THEN close / ? ELSE NULL END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE ticker = ? {date_filter} AND source = 'tcbs'
                    """
                else:  # multiply
                    scale_sql = """
                        UPDATE price_data
                        SET open = CASE WHEN open IS NOT NULL THEN open * ? ELSE NULL END,
                            high = CASE WHEN high IS NOT NULL THEN high * ? ELSE NULL END,
                            low = CASE WHEN low IS NOT NULL THEN low * ? ELSE NULL END,
                            close = CASE WHEN close IS NOT NULL THEN close * ? ELSE NULL END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE ticker = ? {date_filter} AND source = 'tcbs'
                    """
                
                if since_date:
                    date_filter = "AND date >= ?"
                    print(f"  Applying {operation} by {scale} to tcbs rows on/after {since_date} for {t}")
                    cur.execute(scale_sql.format(date_filter=date_filter), (scale, scale, scale, scale, t, since_date))
                else:
                    date_filter = ""
                    print(f"  Applying {operation} by {scale} to ALL tcbs rows for {t}")
                    cur.execute(scale_sql.format(date_filter=date_filter), (scale, scale, scale, scale, t))
                conn.commit()

    conn.close()
    print(f"Scan complete. {len(fixes)} tickers flagged. Dry run: {dry_run}")
    if fixes:
        print("Flagged tickers summary (ticker, tcbs_close, ref_close, scale, operation, method):")
        for f in fixes:
            print(f)
    return fixes

def force_rescale_tcbs(db_path="price_data.db", scale=1000, since_date=None, tickers=None):
    """
    Force-rescale all TCBS data by dividing OHLC by a fixed scale factor.
    This is a fallback when scan_and_fix doesn't detect mismatches but you know TCBS data is unscaled.
    Optionally restrict to specific tickers and/or since_date.
    Returns number of rows updated.
    """
    if not os.path.exists(db_path):
        print(f"Price DB not found: {db_path}")
        return 0
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Build WHERE clause
    where_parts = ["source = 'tcbs'"]
    params = []
    if tickers:
        tickers_list = [t.strip().upper() for t in tickers if t.strip()]
        where_parts.append(f"ticker IN ({','.join('?' for _ in tickers_list)})")
        params.extend(tickers_list)
    if since_date:
        where_parts.append("date >= ?")
        params.append(since_date)
    
    where_clause = " AND ".join(where_parts)
    
    # Count affected rows first
    count_sql = f"SELECT COUNT(*) FROM price_data WHERE {where_clause}"
    cur.execute(count_sql, params)
    count = cur.fetchone()[0]
    
    if count == 0:
        print("No TCBS rows match the criteria.")
        conn.close()
        return 0
    
    print(f"Force-rescaling {count} TCBS rows by dividing OHLC by {scale}...")
    
    # Apply rescale
    update_sql = f"""
        UPDATE price_data
        SET open = CASE WHEN open IS NOT NULL THEN open / ? ELSE NULL END,
            high = CASE WHEN high IS NOT NULL THEN high / ? ELSE NULL END,
            low = CASE WHEN low IS NOT NULL THEN low / ? ELSE NULL END,
            close = CASE WHEN close IS NOT NULL THEN close / ? ELSE NULL END,
            updated_at = CURRENT_TIMESTAMP
        WHERE {where_clause}
    """
    cur.execute(update_sql, [scale, scale, scale, scale] + params)
    affected = cur.rowcount
    conn.commit()
    conn.close()
    
    print(f"Force-rescaled {affected} TCBS rows.")
    return affected


def remove_tcbs_data(db_path="price_data.db", since_date=None, tickers=None):
    """
    Remove all rows from price_data where source='tcbs'.
    Optionally restrict to tickers and/or since_date.
    """
    if not os.path.exists(db_path):
        print(f"Price DB not found: {db_path}")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    base_sql = "DELETE FROM price_data WHERE source = 'tcbs'"
    params = []
    if tickers:
        tickers = [t.strip().upper() for t in tickers if t.strip()]
        base_sql += " AND ticker IN ({})".format(",".join("?" for _ in tickers))
        params.extend(tickers)
    if since_date:
        base_sql += " AND date >= ?"
        params.append(since_date)
    print(f"Executing: {base_sql} with params {params}")
    cur.execute(base_sql, params)
    affected = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Removed {affected} tcbs rows from price_data.")
    return affected


def main():
    parser = argparse.ArgumentParser(description="Build / update price_data SQLite DB from API and CSVs")
    parser.add_argument("--create", action="store_true", help="Create new DB schema")
    parser.add_argument("--copy-existing", action="store_true", help="Copy market_data from existing analysis_results.db")
    parser.add_argument("--source-db", type=str, default=DEFAULT_LOCAL_DB, help="Existing DB to copy from")
    parser.add_argument("--db", type=str, default=NEW_DB_PATH, help="Target DB path")
    parser.add_argument("--update-api", nargs='?', const='', type=str,
                        help="Comma separated tickers to fetch from API. If flag provided without value, update all tickers found in source DB.")
    parser.add_argument("--api-days", type=int, default=365, help="Days to fetch per ticker from API")
    parser.add_argument("--days", type=int, default=None, help="Alias for --api-days (accepts same value)")
    parser.add_argument("--api-pause", type=float, default=0.25, help="Pause (s) between API calls")
    parser.add_argument("--upload-sftp", action="store_true", help="Upload DB to remote via SFTP")
    parser.add_argument("--sftp-host", type=str, default=None)
    parser.add_argument("--sftp-user", type=str, default=None)
    parser.add_argument("--sftp-pass", type=str, default=None)
    parser.add_argument("--sftp-key", type=str, default=None)
    parser.add_argument("--sftp-path", type=str, default='.', help="Remote path for uploaded DB")
    parser.add_argument("--update-all-api", action="store_true", help="Fetch and upsert historical prices for all tickers found in source DB")
    parser.add_argument("--clean-price-units", action="store_true",
                        help="Run price unit inconsistency scan on price_data.db (dry-run by default)")
    parser.add_argument("--apply-clean", action="store_true",
                        help="Apply fixes when running --clean-price-units")
    parser.add_argument("--autoclean", action="store_true",
                        help="Automatically run clean after data-updating operations and apply fixes if --apply-clean is provided")
    parser.add_argument("--clean-ref-db", type=str, default="analysis_results.db",
                        help="Reference DB for unit comparison (default: analysis_results.db)")
    parser.add_argument("--run-clean", action="store_true",
                        help="Run the cleaner immediately and exit (alias for --clean-price-units)")
    parser.add_argument("--fix-from-date", type=str, default=None,
                        help="When running cleaner, only inspect and (optionally) fix rows on/after this date (YYYY-MM-DD)")
    parser.add_argument("--remove-tcbs", action="store_true",
                        help="Remove all rows from price_data where source='tcbs'")
    parser.add_argument("--remove-tcbs-since", type=str, default=None,
                        help="Remove tcbs rows only on/after this date (YYYY-MM-DD)")
    parser.add_argument("--remove-tcbs-tickers", type=str, default=None,
                        help="Comma-separated tickers to restrict tcbs removal")
    # NEW: force-rescale option
    parser.add_argument("--force-rescale-tcbs", action="store_true",
                        help="Force-rescale TCBS data by a fixed factor (use with --scale)")
    parser.add_argument("--scale", type=int, default=1000,
                        help="Scale factor for force-rescale (default: 1000)")
    parser.add_argument("--rescale-since", type=str, default=None,
                        help="Force-rescale TCBS rows only on/after this date (YYYY-MM-DD)")
    parser.add_argument("--rescale-tickers", type=str, default=None,
                        help="Comma-separated tickers to restrict force-rescale")

    args = parser.parse_args()

    # map legacy --days -> api_days if present
    if getattr(args, "days", None) is not None:
        args.api_days = args.days

    target_db = args.db
    data_changed = False

    # If user requested immediate run-clean, perform now and exit
    if args.run_clean or args.clean_price_units:
        dry_run = not args.apply_clean
        print("Running price unit scan on target DB:", target_db)
        print(f"Dry run: {dry_run}. Reference DB: {args.clean_ref_db}. Since date: {args.fix_from_date}")
        fixes = scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=dry_run, since_date=args.fix_from_date)
        if fixes and not dry_run:
            print(f"Applied fixes for {len(fixes)} tickers.")
        elif fixes:
            print(f"Detected {len(fixes)} potential fixes (dry-run). Run with --apply-clean to apply.")
        else:
            print("No unit inconsistencies detected.")
        return

    if args.create:
        create_db(target_db)

    if args.copy_existing:
        copied = copy_existing_market_data(source_db=args.source_db, target_db=target_db)
        if copied and copied > 0:
            data_changed = True

    # NEW: support optional --update-api
    if args.update_api is not None:
        # flag provided without value -> args.update_api == '' -> use tickers from source DB
        if args.update_api == '':
            tickers = _get_distinct_tickers_from_db(args.source_db)
            if not tickers:
                print(f"No tickers found in source DB ({args.source_db}). Nothing to update.")
            else:
                print(f"Updating {len(tickers)} tickers from source DB ({args.source_db}) via API...")
                processed = update_all_tickers_via_api(target_db, source_db=args.source_db, days=args.api_days, pause=args.api_pause)
                if processed:
                    data_changed = True
        else:
            # user provided comma-separated tickers
            tickers = [t.strip().upper() for t in args.update_api.split(",") if t.strip()]
            if tickers:
                updated = update_from_api(tickers, days=args.api_days, db_path=target_db)
                if updated:
                    data_changed = True
        # done with update-api processing
        # after update-api we may want to run cleaning if autoclean requested
        if args.autoclean and data_changed:
            print("Autoclean requested: running dry-run cleaning now...")
            fixes = scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=True)
            if fixes and args.apply_clean:
                print("Applying fixes as requested...")
                scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=False)
        return

    if args.update_all_api:
        processed = update_all_tickers_via_api(
            target_db=target_db,
            source_db=args.source_db,
            days=args.api_days,
            pause=args.api_pause
        )
        if processed:
            data_changed = True
        if args.autoclean and data_changed:
            fixes = scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=True)
            if fixes and args.apply_clean:
                scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=False)
        return

    # SAFELY handle optional update_csv flag (avoid AttributeError)
    if getattr(args, 'update_csv', None):
        up_csv_count = update_from_csv(args.update_csv, db_path=target_db)
        if up_csv_count:
            data_changed = True

    # After any manual update operations (copy, api, csv), if autoclean requested run the cleaner
    if args.autoclean and data_changed:
        print("Autoclean requested: running dry-run cleaning now...")
        fixes = scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=True)
        if fixes:
            print(f"Detected {len(fixes)} fixable tickers.")
            if args.apply_clean:
                print("Applying fixes...")
                scan_and_fix(db_path=target_db, ref_db=args.clean_ref_db, dry_run=False)
            else:
                print("Run with --apply-clean to apply the fixes.")
        else:
            print("No unit inconsistency detected.")

    if args.upload_sftp:
        if not args.sftp_host or not args.sftp_user:
            print("SFTP host/user required (--sftp-host, --sftp-user)")
        else:
            upload_db_sftp(target_db, args.sftp_host, args.sftp_user, password=args.sftp_pass, keyfile=args.sftp_key, remote_path=args.sftp_path)

    # If cleaning requested, run and exit
    if args.clean_price_units:
        dry_run = not args.apply_clean
        print("Running price unit scan on price_data.db")
        print(f"Dry run: {dry_run}. Reference DB: {args.clean_ref_db}")
        scan_and_fix(db_path=args.db, ref_db=args.clean_ref_db, dry_run=dry_run)
        return

    # Remove tcbs data if requested
    if args.remove_tcbs:
        tickers = None
        if args.remove_tcbs_tickers:
            tickers = [t.strip().upper() for t in args.remove_tcbs_tickers.split(",") if t.strip()]
        remove_tcbs_data(db_path=args.db, since_date=args.remove_tcbs_since, tickers=tickers)
        return
    
    # NEW: Force-rescale TCBS data
    if args.force_rescale_tcbs:
        tickers = None
        if args.rescale_tickers:
            tickers = [t.strip().upper() for t in args.rescale_tickers.split(",") if t.strip()]
        force_rescale_tcbs(db_path=args.db, scale=args.scale, since_date=args.rescale_since, tickers=tickers)
        return


if __name__ == "__main__":
    main()
