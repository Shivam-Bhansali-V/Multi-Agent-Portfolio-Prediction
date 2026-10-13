"""Download one NSE stock from Yahoo and run the pattern scanner on it.

usage: python fetch_and_scan.py ABCAPITAL [lookback_candles]
Saves pattern_study/scan_data/<SYMBOL>.csv (same format as the project's raw Yahoo files: raw and adjusted
prices, auto_adjust=False; kept apart so a fresh download never overwrites the study's frozen raw data),
then runs scan_stock.py and writes results/scan_<SYMBOL>.md.
If run while NSE is open (before 16:00 IST), today's still-forming candle is dropped: a pattern must
complete on a closed candle.
"""
import sys, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf

HERE = Path(__file__).resolve().parent
SYM = (sys.argv[1] if len(sys.argv) > 1 else "ABCAPITAL").upper()
LOOK = sys.argv[2] if len(sys.argv) > 2 else "5"
RAW = HERE / "scan_data"; RAW.mkdir(parents=True, exist_ok=True)
COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

df = yf.download(f"{SYM}.NS", start="2015-01-01", auto_adjust=False, progress=False, threads=False)
if isinstance(df.columns, pd.MultiIndex):
    lvl = next((i for i in range(df.columns.nlevels) if "Close" in df.columns.get_level_values(i)), 0)
    df.columns = df.columns.get_level_values(lvl)
missing = [c for c in COLS if c not in df.columns]
if df.empty or missing:
    sys.exit(f"[STOP] download failed for {SYM}.NS (empty={df.empty}, missing={missing}). "
             "Check the internet connection or the symbol.")
df = df[COLS].dropna(subset=["Close"])
df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
df.index.name = "Date"
now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
if now_ist.hour < 16 and len(df) and df.index[-1].date() >= now_ist.date():
    print(f"dropping today's unfinished candle ({df.index[-1].date()}); market not closed yet")
    df = df[df.index.date < now_ist.date()]
out = RAW / f"{SYM}.csv"
df.to_csv(out)
print(f"saved {out}  rows={len(df)}  first={df.index[0].date()}  last={df.index[-1].date()}")
r = subprocess.run([sys.executable, str(HERE / "scan_stock.py"), str(out), SYM, LOOK], cwd=str(HERE))
sys.exit(r.returncode)
