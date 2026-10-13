"""
01b_download_sector_indices.py -- Phase 1.3 (sector mapping / sector index data).

MUST BE RUN ON A MACHINE WITH REAL INTERNET ACCESS TO YAHOO FINANCE -- not in a
sandboxed/proxied environment. (Confirmed empirically: a sandboxed run of this exact
yfinance call returns a 403 from the network proxy, not a Yahoo error. Run this on your
own PC, same way you ran 01_download_prices.py.)

HONESTY NOTE -- read before running: I could not confirm most of these Yahoo tickers
from where I'm working. I tried fetching several Yahoo Finance quote pages directly:
    ^NSEBANK      -> CONFIRMED real (NIFTY BANK), via a live Yahoo Finance page fetch.
    ^CNXMETAL     -> 404 on Yahoo Finance (not this symbol, or delisted there).
    ^CNXFMCG      -> 404 on Yahoo Finance.
    NIFTY_FIN_SERVICE.NS -> 404 on Yahoo Finance.
I did NOT get to test every candidate below (budget/search limits) -- most of the
tickers in CANDIDATE_TICKERS past ^NSEBANK are UNVERIFIED GUESSES based on common
yfinance/NSE-project naming patterns, not confirmed facts. Rather than assert a ticker
is correct when I have not checked it, this script tries a short list of candidates per
sector and logs exactly which one(s) actually return data -- so the fetch log, not my
guess, is the source of truth once you run this.

Sector -> candidate tickers mapping is scoped to the 8 stocks' sectors (from
data/reference/ind_nifty100list.csv, read directly, not assumed):
    TCS         -> Information Technology
    RELIANCE    -> Oil Gas & Consumable Fuels
    BAJAJFINSV  -> Financial Services
    ITC         -> Fast Moving Consumer Goods
    SIEMENS     -> Capital Goods
    VEDL        -> Metals & Mining
    ADANIENT    -> Metals & Mining
    IDEA        -> Telecommunication
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("FATAL: yfinance not installed. Run: pip install yfinance", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "yahoo_sector"
LOG_PATH = ROOT / "reports" / "phase1" / "sector_index_fetch_log.csv"

START = "2015-01-01"
END = None  # defaults to today in yfinance

# sector label (matches ind_nifty100list.csv "Industry" column) -> ordered list of
# candidate Yahoo tickers to try. First one that returns non-empty data wins; all
# attempts are logged either way. CONFIRMED tickers are marked; everything else is an
# unverified guess -- the log tells you which guess (if any) actually worked.
CANDIDATE_TICKERS: dict[str, list[str]] = {
    "Information Technology": ["^CNXIT", "^NIFTYIT", "NIFTY_IT.NS"],          # all unverified
    "Oil Gas & Consumable Fuels": ["^CNXENERGY", "^NIFTYENERGY", "NIFTY_OIL_AND_GAS.NS"],  # unverified
    "Financial Services": ["^CNXFIN", "NIFTY_FIN_SERVICE.NS", "^NIFTYFINSERVICE"],  # unverified (NIFTY_FIN_SERVICE.NS already confirmed 404)
    "Fast Moving Consumer Goods": ["^CNXFMCG", "NIFTY_FMCG.NS"],  # unverified (^CNXFMCG already confirmed 404)
    "Capital Goods": ["^CNXINFRA", "NIFTY_CAPITAL_GOODS.NS", "NIFTY_INFRA.NS"],  # unverified; NIFTY Capital Goods is a newer NSE index (2024), may not exist on Yahoo at all
    "Metals & Mining": ["^CNXMETAL", "NIFTY_METAL.NS"],  # unverified (^CNXMETAL already confirmed 404)
    "Telecommunication": ["^CNXMEDIA", "NIFTY_MEDIA.NS"],  # unverified; NSE may not publish a dedicated telecom sector index at all -- flag to the user if nothing resolves
    "NIFTY BANK (reference, not one of the 8 stocks' sectors)": ["^NSEBANK"],  # CONFIRMED real on Yahoo
}


def try_download(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, start=START, end=END, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    log_rows = []
    for sector, candidates in CANDIDATE_TICKERS.items():
        resolved = False
        for ticker in candidates:
            try:
                df = try_download(ticker)
            except Exception as e:
                log_rows.append({"sector": sector, "ticker": ticker, "status": "ERROR",
                                  "rows": 0, "detail": f"{type(e).__name__}: {e}"})
                continue
            if df is None or df.empty:
                log_rows.append({"sector": sector, "ticker": ticker, "status": "EMPTY",
                                  "rows": 0, "detail": "download returned 0 rows"})
                continue
            out_name = ticker.replace("^", "").replace(".", "_")
            out_path = OUT_DIR / f"{out_name}.csv"
            df.to_csv(out_path)
            log_rows.append({"sector": sector, "ticker": ticker, "status": "OK",
                              "rows": len(df), "detail": str(out_path)})
            resolved = True
            break  # first working candidate for this sector is enough
        if not resolved:
            log_rows.append({"sector": sector, "ticker": "(none)", "status": "ALL_FAILED",
                              "rows": 0, "detail": "no candidate ticker returned data -- "
                                                    "needs manual research, do not guess a replacement"})

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, index=False)
    print(log_df.to_string(index=False))
    print(f"\nFull log written to {LOG_PATH}")
    n_failed = (log_df["status"] != "OK").sum()
    if n_failed:
        print(f"\n{n_failed} sector(s) did not resolve to a working ticker. "
              f"Report these back rather than inventing a ticker for them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
