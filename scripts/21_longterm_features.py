"""
21_longterm_features.py -- Phase 3.7 (add-on): long-term trend/regime features.

WHY: checkpoint 4.5's backtest lost to buy-and-hold mainly by trading too little
during a multi-year bull run. checkpoint 2.4's own baseline numbers already hinted
at this: `momentum_252d` (a pure 252-day time-series-momentum rule) scored Sharpe
0.84 standalone, the closest any single rule got to buy-and-hold's 1.02 -- far ahead
of any short-horizon oscillator rule (RSI-based rules scored much lower). The frozen
Phase 3 feature set has EMA20/50 and ADX -- medium-term at best -- but nothing that
directly tells the model "is this stock in a long-running uptrend." This adds that.

Features (all causal -- use AdjClose through t only):
  - ret_252d: trailing 252-session (~1yr) return -- the same lookback as the
    momentum_252d baseline that scored 0.84.
  - above_sma200: 1 if Close > 200-day SMA (classic long-term trend filter), else 0.
  - dist_sma200_pct: (Close - SMA200) / SMA200 -- how far above/below, not just a flag.
  - golden_cross_state: 1 if SMA50 > SMA200 ("golden cross" regime), -1 if SMA50 <
    SMA200 ("death cross" regime), 0 if within 0.1% (effectively equal).

CAUSALITY: same pattern as 20_sector_features.py's `_check_causality` -- truncating
history at an arbitrary date must reproduce the same feature value at that date.

NOTE ON WARM-UP: SMA200/ret_252d need 252 sessions of history before they're not NaN
-- roughly 1 trading year. This is a longer warm-up than any Phase 3 feature (which
used WARMUP_SESSIONS=60), stated here rather than silently shortened.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "clean"
OUT_DIR = ROOT / "data" / "features_longterm"
REPORTS_DIR = ROOT / "reports" / "phase3"

PILOT_SYMBOLS = ["TCS", "RELIANCE", "HDFCBANK", "ITC",
                 "SIEMENS", "TATASTEEL", "BHARTIARTL", "ULTRACEMCO"]
HOLDOUT_START = pd.Timestamp("2025-04-01")
LONG_WARMUP = 252


def _load_close(symbol: str) -> pd.Series:
    path = CLEAN_DIR / f"{symbol}.csv"
    df = pd.read_csv(path, usecols=["Date", "AdjClose"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.set_index("Date").sort_index()
    df = df.loc[df.index < HOLDOUT_START]
    return df["AdjClose"]


def build_longterm_features(close: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame(index=close.index)
    out["ret_252d"] = close / close.shift(252) - 1.0

    sma50 = close.rolling(50, min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()

    out["above_sma200"] = (close > sma200).astype(float)
    out.loc[sma200.isna(), "above_sma200"] = np.nan
    out["dist_sma200_pct"] = (close - sma200) / sma200

    gap = (sma50 - sma200) / sma200
    state = pd.Series(0.0, index=close.index)
    state[gap > 0.001] = 1.0
    state[gap < -0.001] = -1.0
    state[sma50.isna() | sma200.isna()] = np.nan
    out["golden_cross_state"] = state

    out.index.name = "Date"
    return out.reset_index()


def _check_causality(check) -> None:
    for symbol in ["ITC", "TATASTEEL"]:
        close = _load_close(symbol)
        full = build_longterm_features(close).set_index("Date")
        cut_date = full.index[400]
        trunc = build_longterm_features(close.loc[close.index <= cut_date]).set_index("Date")
        if cut_date not in trunc.index:
            check(f"causality check has data for {symbol}", False, "truncated series too short")
            continue
        row_full, row_trunc = full.loc[cut_date], trunc.loc[cut_date]
        same = all(
            (pd.isna(row_full[c]) and pd.isna(row_trunc[c])) or np.isclose(row_full[c], row_trunc[c], equal_nan=True)
            for c in full.columns
        )
        check(f"{symbol}: truncated-history recompute matches full-history value at an interior date",
              same, f"mismatch at {cut_date.date()}")


def run(symbols: Optional[Sequence[str]] = None) -> Dict[str, pd.DataFrame]:
    symbols = list(symbols or PILOT_SYMBOLS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for sym in symbols:
        feat = build_longterm_features(_load_close(sym))
        feat["symbol"] = sym
        feat.to_csv(OUT_DIR / f"{sym}.csv", index=False)
        out[sym] = feat
    return out


def _selftest() -> int:
    n_pass, n_fail, failures = 0, 0, []

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal n_pass, n_fail
        if cond:
            n_pass += 1
            print(f"PASS  {name}")
        else:
            n_fail += 1
            failures.append(f"{name} -- {detail}")
            print(f"FAIL  {name}" + (f"  -- {detail}" if detail else ""))

    print("=" * 78)
    print("21_longterm_features.py -- Phase 3.7: long-term trend/regime features")
    print("=" * 78)

    out = run(PILOT_SYMBOLS)
    for sym in PILOT_SYMBOLS:
        f = out[sym]
        n_valid = f["above_sma200"].notna().sum()
        check(f"{sym}: has real (non-NaN) long-term features after the 252-session warm-up",
              n_valid > 0, f"0 valid rows")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _check_causality(check)

    manifest_rows = [{"symbol": s, "n_rows": len(out[s]),
                       "n_valid_above_sma200": int(out[s]["above_sma200"].notna().sum()),
                       "first_date": str(out[s]["Date"].min().date()),
                       "last_date": str(out[s]["Date"].max().date())} for s in PILOT_SYMBOLS]
    pd.DataFrame(manifest_rows).to_csv(REPORTS_DIR / "checkpoint_3_7_longterm_feature_manifest.csv", index=False)

    print(f"\nwrote data/features_longterm/<symbol>.csv for {len(PILOT_SYMBOLS)} symbols")
    print(f"wrote reports/phase3/checkpoint_3_7_longterm_feature_manifest.csv")
    print("\n" + "-" * 78)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
