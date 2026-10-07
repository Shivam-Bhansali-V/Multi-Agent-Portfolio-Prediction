"""
Checkpoint 1.1 - first price pull from Yahoo Finance.

Same method as the old Multi_Agent/data_loader.py (yfinance.download), with:
  - all NIFTY 100 stocks instead of one ticker
  - no hardcoded paths (everything is relative to this project folder)
  - raw AND adjusted prices kept (auto_adjust=False)
  - a log of rows / date range / failures per stock

No API key is needed for Yahoo Finance.

KNOWN LIMITS (do not hide these in the paper):
  - Uses TODAY's NIFTY 100 list -> survivorship bias until historical
    constituents are added.
  - Yahoo has no delivery-percentage data. NSE daily files come in a later script.

Run from the project folder:
    pip install yfinance pandas requests
    python scripts/01_download_prices.py
"""
import io
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "yahoo"
REF_DIR = ROOT / "data" / "reference"
LOG_DIR = ROOT / "reports" / "phase1"
START_DATE = "2015-01-01"
NIFTY100_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv"
INDEX_TICKERS = {"NIFTY50": "^NSEI", "NIFTY100": "^CNX100", "INDIAVIX": "^INDIAVIX"}
EXPECTED_COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def get_constituents() -> pd.DataFrame:
    """NIFTY 100 list from NSE. Falls back to a manually saved copy."""
    path = REF_DIR / "ind_nifty100list.csv"
    try:
        r = requests.get(NIFTY100_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.to_csv(path, index=False)
        print(f"[OK] NIFTY 100 list downloaded from NSE: {len(df)} stocks")
    except Exception as e:
        print(f"[WARN] Could not download the list from NSE ({e}).")
        if not path.exists():
            sys.exit(
                "[STOP] No constituent list available.\n"
                f"Open {NIFTY100_URL} in a browser, save the file as\n{path}\nand run again."
            )
        df = pd.read_csv(path)
        print(f"[OK] Using saved copy: {path} ({len(df)} stocks)")
    df.columns = [c.strip() for c in df.columns]
    if "Symbol" not in df.columns:
        sys.exit(f"[STOP] 'Symbol' column missing in constituent list. Columns: {list(df.columns)}")
    return df


def fetch(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, start=START_DATE, auto_adjust=False, progress=False, threads=False)
    if df is None or len(df) == 0:
        raise ValueError("empty result from Yahoo")
    if isinstance(df.columns, pd.MultiIndex):          # newer yfinance versions
        df.columns = df.columns.get_level_values(0)
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns {missing}")
    df = df[EXPECTED_COLS].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"
    return df[~df.index.duplicated(keep="last")].sort_index()


def main():
    for d in (RAW_DIR, REF_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
    cons = get_constituents()
    jobs = [(s.strip(), s.strip() + ".NS", "stock") for s in cons["Symbol"].astype(str)]
    jobs += [(name, tkr, "index") for name, tkr in INDEX_TICKERS.items()]

    rows = []
    for i, (name, ticker, kind) in enumerate(jobs, 1):
        rec = {"name": name, "ticker": ticker, "kind": kind, "status": "FAILED",
               "rows": 0, "first_date": "", "last_date": "", "nan_rows": 0,
               "zero_volume_days": 0, "error": ""}
        for attempt in (1, 2, 3):
            try:
                df = fetch(ticker)
                df.to_csv(RAW_DIR / f"{name}.csv")
                rec.update(status="OK", rows=len(df),
                           first_date=str(df.index[0].date()), last_date=str(df.index[-1].date()),
                           nan_rows=int(df[["Open", "High", "Low", "Close"]].isna().any(axis=1).sum()),
                           zero_volume_days=int((df["Volume"] == 0).sum()), error="")
                break
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"[:200]
                time.sleep(2 * attempt)
        print(f"[{i:3d}/{len(jobs)}] {ticker:16s} {rec['status']:6s} rows={rec['rows']:5d} "
              f"{rec['first_date']} -> {rec['last_date']} {rec['error']}")
        rows.append(rec)
        time.sleep(0.4)

    log = pd.DataFrame(rows)
    log_path = LOG_DIR / "01_download_log.csv"
    log.to_csv(log_path, index=False)
    ok = (log["status"] == "OK").sum()
    late = log[(log["status"] == "OK") & (log["first_date"] > "2015-01-10") & (log["kind"] == "stock")]
    summary = [
        f"Run time: {datetime.now():%Y-%m-%d %H:%M}",
        f"yfinance version: {yf.__version__}",
        f"Requested: {len(log)}  OK: {ok}  FAILED: {len(log) - ok}",
        f"Failed: {', '.join(log.loc[log['status'] != 'OK', 'ticker']) or 'none'}",
        f"Stocks whose history starts after 2015-01-10 (listed later): {len(late)}",
        f"  {', '.join(late['name'])}" if len(late) else "",
        f"Latest data date (most common): {log.loc[log['status'] == 'OK', 'last_date'].mode().iat[0] if ok else 'n/a'}",
    ]
    (LOG_DIR / "01_download_summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print("\n" + "\n".join(summary))
    print(f"\nLog saved: {log_path}")


if __name__ == "__main__":
    main()
