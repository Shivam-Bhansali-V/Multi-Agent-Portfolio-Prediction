"""
20_sector_features.py -- Phase 3.6 (add-on, post-freeze): sector / cross-sectional
relative-strength features.

WHY THIS EXISTS: Phase 4's backtest (checkpoint 4.5) showed the technical-only model
losing to simple buy-and-hold. One of the concrete, fixable reasons raised with the
user: the frozen Phase 3 feature set (35 features) describes each stock in ISOLATION
-- it has no way to express "this stock is outperforming its market/sector," which is
closer to what actually drives 10-day relative returns than any single-stock
indicator. This script adds that missing piece.

DATA-QUALITY FINDING THAT SHAPED THIS SCRIPT (reported to the user, not glossed over):
checking every NIFTY100 same-industry peer for each of the 8 pilot stocks against
reports/phase1/checkpoint_1_3_universe.csv (the same corporate-action cleanliness
check that got 4 symbols swapped out of the pilot set originally) found that MOST
candidate sector peers are themselves flagged with unadjusted-move problems. Using
them anyway would quietly reintroduce the exact data-quality issue the pilot swap
was meant to avoid. So:
  - TCS (IT): only 1 clean peer (HCLTECH) -- thin, used anyway, flagged.
  - RELIANCE (Oil & Gas): only 1 clean peer (COALINDIA) -- thin, used anyway, flagged.
  - SIEMENS (Capital Goods): 2 clean peers (ABB, CUMMINSIND).
  - HDFCBANK (Financial Services): 3 clean of 22 candidates (JIOFIN, KOTAKBANK, SBILIFE).
  - ITC (FMCG): 5 clean peers (BRITANNIA, HINDUNILVR, NESTLEIND, TATACONSUM, VBL) --
    the one sector group with a real peer set.
  - TATASTEEL (Metals & Mining), BHARTIARTL (Telecom), ULTRACEMCO (Construction
    Materials): ZERO clean peers exist anywhere in the NIFTY100 universe check for
    these industries. The sector-relative feature is left as a genuine NaN for these
    three -- NOT zero-filled, NOT estimated from dirty peers. A `n_sector_peers`
    column records exactly how many clean peers backed each row's sector feature, so
    this is auditable rather than a silent gap.

Market-relative features (stock vs. NIFTY100) are NOT affected by this problem --
NIFTY100's own data is already clean and used throughout the project -- so every row
for every symbol gets a real market-relative feature, with no exceptions.

NaN HANDLING, STATED PLAINLY: `sector_rel_*` columns are left as real NaN for
TATASTEEL/BHARTIARTL/ULTRACEMCO (no clean peers) rather than imputed. This is
deliberately compatible with XGBoost (4.2's carried-forward model), which natively
learns a split direction for missing values -- it is NOT compatible with 4.1's
logistic regression without a separate imputation step, which has not been added.
Plain accuracy comparisons between a future "4.1 + sector features" and "4.2 + sector
features" run would need that handled explicitly; not done in this script.

CAUSALITY: every feature at row t uses AdjClose through t only (no future bars).
`_check_causality` verifies this directly, matching the pattern used by 06_baselines.py
and the Phase 3 indicator-family scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "clean"
OUT_DIR = ROOT / "data" / "features_sector"
REPORTS_DIR = ROOT / "reports" / "phase3"

PILOT_SYMBOLS = ["TCS", "RELIANCE", "HDFCBANK", "ITC",
                 "SIEMENS", "TATASTEEL", "BHARTIARTL", "ULTRACEMCO"]
BENCHMARK_SYMBOL = "NIFTY100"

# Clean-peer groups -- see module docstring for how these were chosen and what was
# excluded. Empty list means "no clean peer exists"; the sector feature is then NaN.
SECTOR_PEERS: Dict[str, List[str]] = {
    "TCS": ["HCLTECH"],
    "RELIANCE": ["COALINDIA"],
    "HDFCBANK": ["JIOFIN", "KOTAKBANK", "SBILIFE"],
    "ITC": ["BRITANNIA", "HINDUNILVR", "NESTLEIND", "TATACONSUM", "VBL"],
    "SIEMENS": ["ABB", "CUMMINSIND"],
    "TATASTEEL": [],
    "BHARTIARTL": [],
    "ULTRACEMCO": [],
}

WINDOWS = (5, 20)
ZSCORE_WINDOW = 60
HOLDOUT_START = pd.Timestamp("2025-04-01")  # same sealed boundary as the rest of the project


def _load_close(symbol: str) -> pd.Series:
    path = CLEAN_DIR / f"{symbol}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"no clean file for {symbol} at {path}")
    df = pd.read_csv(path, usecols=["Date", "AdjClose"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.set_index("Date").sort_index()
    df = df.loc[df.index < HOLDOUT_START]  # holdout stays sealed
    return df["AdjClose"]


def _nday_return(close: pd.Series, n: int) -> pd.Series:
    """Causal n-day simple return ending at t, using only AdjClose through t."""
    return close / close.shift(n) - 1.0


def build_sector_features(symbol: str, close_cache: Dict[str, pd.Series]) -> pd.DataFrame:
    close = close_cache[symbol]
    bench = close_cache[BENCHMARK_SYMBOL]
    bench_aligned = bench.reindex(close.index)

    out = pd.DataFrame(index=close.index)
    peers = SECTOR_PEERS[symbol]
    peer_closes = [close_cache[p].reindex(close.index) for p in peers]
    # equal-weight peer average price level isn't meaningful (different price scales);
    # average the peers' own n-day returns instead, row by row.
    for n in WINDOWS:
        stock_ret = _nday_return(close, n)
        bench_ret = _nday_return(bench_aligned, n)
        out[f"mkt_rel_ret_{n}d"] = stock_ret - bench_ret

        if peers:
            peer_rets = pd.concat([_nday_return(pc, n) for pc in peer_closes], axis=1)
            peer_avg_ret = peer_rets.mean(axis=1, skipna=True)
            n_valid = peer_rets.notna().sum(axis=1)
            sector_rel = stock_ret - peer_avg_ret
            sector_rel = sector_rel.where(n_valid > 0)  # NaN where no peer had data that day either
        else:
            sector_rel = pd.Series(np.nan, index=close.index)
        out[f"sector_rel_ret_{n}d"] = sector_rel

    # Rolling z-score of the 20-day market-relative return, over a trailing 60-session
    # window -- "is today's relative strength unusual for this stock lately," not an
    # absolute level. min_periods=ZSCORE_WINDOW so no partial-window degenerate z-score.
    base = out["mkt_rel_ret_20d"]
    roll_mean = base.rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).mean()
    roll_std = base.rolling(ZSCORE_WINDOW, min_periods=ZSCORE_WINDOW).std(ddof=1)
    out["mkt_rel_ret_20d_zscore"] = (base - roll_mean) / roll_std.replace(0, np.nan)

    out["n_sector_peers"] = len(peers)
    out["symbol"] = symbol
    out.index.name = "Date"
    return out.reset_index()


def _check_causality(check, symbols: Sequence[str], close_cache: Dict[str, pd.Series]) -> None:
    """Truncating the price history at an arbitrary date and recomputing must give the
    same feature value at that date as the full-history computation -- i.e. nothing
    here looks beyond t. Spot-checked on one symbol with peers (ITC) and one without
    (TATASTEEL), at a date safely past every window's warm-up."""
    for symbol in symbols:
        full = build_sector_features(symbol, close_cache).set_index("Date")
        cut_date = full.index[400]  # well past the 60-session z-score warmup
        truncated_cache = {k: v.loc[v.index <= cut_date] for k, v in close_cache.items()}
        trunc = build_sector_features(symbol, truncated_cache).set_index("Date")
        if cut_date not in trunc.index:
            check(f"causality check has data for {symbol}", False, "truncated series too short")
            continue
        row_full = full.loc[cut_date]
        row_trunc = trunc.loc[cut_date]
        cols = [c for c in full.columns if c not in ("symbol",)]
        same = all(
            (pd.isna(row_full[c]) and pd.isna(row_trunc[c])) or np.isclose(row_full[c], row_trunc[c], equal_nan=True)
            for c in cols
        )
        check(f"{symbol}: truncated-history recompute matches full-history value at an interior date",
              same, f"mismatch at {cut_date.date()}")


def run(symbols: Optional[Sequence[str]] = None) -> Dict[str, pd.DataFrame]:
    symbols = list(symbols or PILOT_SYMBOLS)
    needed = set(symbols) | {BENCHMARK_SYMBOL} | {p for s in symbols for p in SECTOR_PEERS.get(s, [])}
    close_cache = {sym: _load_close(sym) for sym in needed}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_frames = {}
    for sym in symbols:
        feat = build_sector_features(sym, close_cache)
        feat.to_csv(OUT_DIR / f"{sym}.csv", index=False)
        out_frames[sym] = feat
    return out_frames


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
    print("20_sector_features.py -- Phase 3.6: sector / cross-sectional features")
    print("=" * 78)

    needed = set(PILOT_SYMBOLS) | {BENCHMARK_SYMBOL} | {p for s in PILOT_SYMBOLS for p in SECTOR_PEERS.get(s, [])}
    close_cache = {}
    missing = []
    for sym in sorted(needed):
        try:
            close_cache[sym] = _load_close(sym)
        except FileNotFoundError:
            missing.append(sym)
    check("every symbol/peer/benchmark needed has a clean price file", len(missing) == 0, f"missing: {missing}")

    out_frames = run(PILOT_SYMBOLS)
    print(f"\n--- Sector-peer coverage ---")
    for sym in PILOT_SYMBOLS:
        n_peers = len(SECTOR_PEERS[sym])
        peers_str = ", ".join(SECTOR_PEERS[sym]) if n_peers else "NONE -- sector_rel_* left NaN"
        print(f"  {sym:<12} {n_peers} clean peer(s): {peers_str}")

    # NaN-for-no-peers must be exact: 0 peers -> 100% NaN sector_rel columns;
    # >=1 peer -> some real (non-NaN) values once warm-up has passed.
    all_ok = True
    for sym in PILOT_SYMBOLS:
        f = out_frames[sym]
        n_peers = len(SECTOR_PEERS[sym])
        sec_cols = [c for c in f.columns if c.startswith("sector_rel_ret_")]
        all_nan = f[sec_cols].isna().all(axis=None)
        if n_peers == 0:
            ok = bool(all_nan)
        else:
            ok = bool(not all_nan)  # at least some real values once peers have history
        all_ok = all_ok and ok
        if not ok:
            print(f"  MISMATCH: {sym} (n_peers={n_peers}) sector_rel all-NaN={all_nan}")
    check("sector_rel_* is all-NaN exactly for the 3 no-clean-peer symbols, and has real "
          "values for every symbol with >=1 clean peer", all_ok)

    check("mkt_rel_ret_* (vs NIFTY100) has real (non-NaN) values for every pilot symbol "
          "with no exceptions", all(not out_frames[s]["mkt_rel_ret_20d"].isna().all() for s in PILOT_SYMBOLS))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _check_causality(check, ["ITC", "TATASTEEL"], close_cache)

    # Manifest, same spirit as checkpoint 3.5's.
    manifest_rows = []
    for sym in PILOT_SYMBOLS:
        f = out_frames[sym]
        manifest_rows.append({
            "symbol": sym, "n_rows": len(f), "n_sector_peers": len(SECTOR_PEERS[sym]),
            "sector_peers": ";".join(SECTOR_PEERS[sym]),
            "first_date": str(f["Date"].min().date()), "last_date": str(f["Date"].max().date()),
        })
    pd.DataFrame(manifest_rows).to_csv(REPORTS_DIR / "checkpoint_3_6_sector_feature_manifest.csv", index=False)

    print(f"\nwrote data/features_sector/<symbol>.csv for {len(PILOT_SYMBOLS)} symbols")
    print(f"wrote reports/phase3/checkpoint_3_6_sector_feature_manifest.csv")
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
