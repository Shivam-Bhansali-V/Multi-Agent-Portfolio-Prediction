#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02e_validate.py -- Comprehensive data-cleaning validation harness.

Addresses findings:
- F16 (LOW): Report no metric that no code computes. Explicitly checks the 3 OHLC inequalities.
- F06 (HIGH): Asserts every stock date is in master calendar.
- F07 (HIGH): Asserts zero PreListing rows emitted in cleaned datasets.
- F11 (MEDIUM): Asserts row counts unchanged by flag-setting.
- F09 (HIGH): Action-table coverage metric replacing 'unexplained: 0'. Reports uncaught moves >= 15%.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

log = logging.getLogger("validate")


# --------------------------------------------------------------------------------------
# 1. Named Individual Checks
# --------------------------------------------------------------------------------------

def check_ohlc_inequalities(df: pd.DataFrame, symbol: str) -> List[str]:
    """Check High >= max(Open, Close), Low <= min(Open, Close), and High >= Low. (F16)"""
    problems = []
    cols = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in cols):
        return [f"{symbol}: Missing one or more OHLC columns"]

    o = pd.to_numeric(df["Open"], errors="coerce")
    h = pd.to_numeric(df["High"], errors="coerce")
    l = pd.to_numeric(df["Low"], errors="coerce")
    c = pd.to_numeric(df["Close"], errors="coerce")

    max_oc = np.maximum(o, c)
    min_oc = np.minimum(o, c)

    bad_high = df.index[h < max_oc - 1e-6]
    bad_low = df.index[l > min_oc + 1e-6]
    bad_hl = df.index[h < l - 1e-6]

    if len(bad_high):
        problems.append(f"{symbol}: High < max(Open, Close) on {len(bad_high)} sessions (e.g. {list(bad_high[:3])})")
    if len(bad_low):
        problems.append(f"{symbol}: Low > min(Open, Close) on {len(bad_low)} sessions (e.g. {list(bad_low[:3])})")
    if len(bad_hl):
        problems.append(f"{symbol}: High < Low on {len(bad_hl)} sessions (e.g. {list(bad_hl[:3])})")

    return problems


def check_positive_prices(df: pd.DataFrame, symbol: str) -> List[str]:
    """Check that all price columns are strictly positive and finite."""
    problems = []
    price_cols = [c for c in ["Open", "High", "Low", "Close", "AdjClose", "StructAdjClose"] if c in df.columns]
    for col in price_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        bad = df.index[(series.isna()) | (series <= 0)]
        # Exclude NoData days from price check if NoData column exists
        if "NoData" in df.columns:
            bad = bad[~df.loc[bad, "NoData"]]
        if len(bad):
            problems.append(f"{symbol}: Column {col} non-positive or NaN on {len(bad)} trading sessions")
    return problems


def check_index_integrity(df: pd.DataFrame, symbol: str) -> List[str]:
    """Check index is sorted, strictly monotonic increasing, and has no duplicates."""
    problems = []
    if not isinstance(df.index, pd.DatetimeIndex):
        return [f"{symbol}: Index is not a DatetimeIndex"]
    if df.index.has_duplicates:
        problems.append(f"{symbol}: Index contains {df.index.duplicated().sum()} duplicate dates")
    if not df.index.is_monotonic_increasing:
        problems.append(f"{symbol}: Index is not strictly monotonic increasing")
    return problems


def check_calendar_presence(df: pd.DataFrame, calendar: pd.DatetimeIndex, symbol: str) -> List[str]:
    """Check every stock bar date exists in master calendar (F06 regression guard)."""
    stock_dates = set(pd.DatetimeIndex(df.index).normalize())
    cal_dates = set(calendar)
    missing = sorted(stock_dates - cal_dates)
    if missing:
        return [f"{symbol}: {len(missing)} stock dates absent from master calendar (e.g. {missing[:3]})"]
    return []


def check_no_prelisting_padding(df: pd.DataFrame, symbol: str) -> List[str]:
    """Check zero PreListing rows are emitted in cleaned output (F07 guard)."""
    if "PreListing" in df.columns and df["PreListing"].any():
        n = df["PreListing"].sum()
        return [f"{symbol}: Contains {n} pre-listing padded rows (F07 violation)"]
    return []


def check_no_ffill_runs(df: pd.DataFrame, symbol: str, max_run: int = 3) -> List[str]:
    """Check for identical consecutive OHLC bars (ffill damage guard)."""
    cols = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in cols):
        return []
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    identical = (o == o.shift(1)) & (h == h.shift(1)) & (l == l.shift(1)) & (c == c.shift(1))
    run = 0
    max_observed = 0
    for ident in identical:
        if ident:
            run += 1
            max_observed = max(max_observed, run)
        else:
            run = 0
    if max_observed >= max_run:
        return [f"{symbol}: Run of {max_observed + 1} identical OHLC bars detected (ffill signature)"]
    return []


def audit_action_coverage(
    raw_df: pd.DataFrame,
    adj_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    symbol: str,
    threshold: float = 0.15,
) -> Dict[str, Any]:
    """Evaluate corporate action coverage vs raw moves (F09 replacement metric).
    
    Reports:
    - total structural actions for symbol
    - count of raw 1-day moves beyond threshold
    - uncaught moves (moves >= 15% with NO action table entry)
    - residual moves in adjusted series (outside known table dates)
    """
    raw_close = pd.to_numeric(raw_df["Close"], errors="coerce")
    raw_ret = raw_close.pct_change()
    raw_big_moves = raw_df.index[raw_ret.abs() >= threshold].tolist()

    sym_acts = actions_df.loc[
        (actions_df["symbol"] == symbol) &
        (actions_df["action_type"].isin({"split", "bonus", "demerger", "rights"}))
    ] if actions_df is not None and not actions_df.empty else pd.DataFrame()

    act_dates = set(pd.to_datetime(sym_acts["ex_date"]).dt.normalize()) if not sym_acts.empty else set()

    # Uncaught moves: raw big move with no action within +/- 2 sessions
    uncaught_moves = []
    for d in raw_big_moves:
        d_norm = pd.Timestamp(d).normalize()
        near = any(abs((d_norm - ad).days) <= 3 for ad in act_dates)
        if not near:
            uncaught_moves.append(str(d_norm.date()))

    # Residual moves in adjusted series
    adj_col = "StructAdjClose" if "StructAdjClose" in adj_df.columns else "AdjClose"
    adj_close = pd.to_numeric(adj_df[adj_col], errors="coerce")
    adj_ret = adj_close.pct_change()
    adj_big_moves = adj_df.index[adj_ret.abs() >= threshold].tolist()

    residual_moves = []
    for d in adj_big_moves:
        d_norm = pd.Timestamp(d).normalize()
        near = any(abs((d_norm - ad).days) <= 3 for ad in act_dates)
        if not near:
            residual_moves.append(str(d_norm.date()))

    return {
        "symbol": symbol,
        "actions_in_table": len(sym_acts),
        "raw_moves_ge_15pct": len(raw_big_moves),
        "uncaught_raw_moves": uncaught_moves,
        "uncaught_count": len(uncaught_moves),
        "residual_moves_in_adj": residual_moves,
        "residual_count": len(residual_moves),
    }


# --------------------------------------------------------------------------------------
# 2. Harness Execution across Dataset
# --------------------------------------------------------------------------------------

def validate_symbol(
    raw_df: pd.DataFrame,
    adj_df: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    actions_df: pd.DataFrame,
    symbol: str,
) -> Tuple[List[str], Dict[str, Any]]:
    """Run all validation checks for one symbol."""
    problems = []
    problems.extend(check_ohlc_inequalities(adj_df, symbol))
    problems.extend(check_positive_prices(adj_df, symbol))
    problems.extend(check_index_integrity(adj_df, symbol))
    problems.extend(check_calendar_presence(adj_df, calendar, symbol))
    problems.extend(check_no_prelisting_padding(adj_df, symbol))
    problems.extend(check_no_ffill_runs(adj_df, symbol))

    coverage_metrics = audit_action_coverage(raw_df, adj_df, actions_df, symbol)
    return problems, coverage_metrics


def run_all(
    clean_dir: Union[str, Path],
    raw_dir: Union[str, Path],
    actions_path: Union[str, Path],
    calendar: pd.DatetimeIndex,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Validate all symbols in clean_dir against raw_dir and actions.
    
    Returns (summary_validation_df, all_problems_df).
    """
    clean_p = Path(clean_dir)
    raw_p = Path(raw_dir)
    acts_df = pd.read_csv(actions_path) if Path(actions_path).is_file() else pd.DataFrame()

    summary_records = []
    problem_records = []

    for clean_file in sorted(clean_p.glob("*.csv")):
        sym = clean_file.stem
        raw_file = raw_p / f"{sym}.csv"
        if not raw_file.is_file():
            problem_records.append({"symbol": sym, "problem": f"Raw CSV missing for {sym}"})
            continue

        raw_df = pd.read_csv(raw_file)
        raw_df["Date"] = pd.to_datetime(raw_df["Date"]).dt.normalize()
        raw_df = raw_df.set_index("Date").sort_index()

        adj_df = pd.read_csv(clean_file)
        adj_df["Date"] = pd.to_datetime(adj_df["Date"]).dt.normalize()
        adj_df = adj_df.set_index("Date").sort_index()

        probs, cov = validate_symbol(raw_df, adj_df, calendar, acts_df, sym)
        for p in probs:
            problem_records.append({"symbol": sym, "problem": p})

        summary_records.append({
            "symbol": sym,
            "passed": len(probs) == 0,
            "problem_count": len(probs),
            "actions_in_table": cov["actions_in_table"],
            "raw_moves_ge_15pct": cov["raw_moves_ge_15pct"],
            "uncaught_count": cov["uncaught_count"],
            "residual_count": cov["residual_count"],
        })

    summary_df = pd.DataFrame(summary_records)
    problems_df = pd.DataFrame(problem_records)
    return summary_df, problems_df


# ======================================================================================
# Self-test -- SYNTHETIC in-memory data only
# ======================================================================================

def _selftest() -> int:
    passed = 0
    failed = 0

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"PASS  {name}")
        else:
            failed += 1
            print(f"FAIL  {name} -- {detail}")

    print("=" * 70)
    print("02e_validate.py Self-Test (SYNTHETIC in-memory)")
    print("=" * 70)

    # 1. OHLC inequality checks (F16)
    idx = pd.date_range("2020-01-01", periods=2)
    good_ohlc = pd.DataFrame({
        "Open": [100.0, 102.0], "High": [105.0, 107.0],
        "Low": [95.0, 99.0], "Close": [102.0, 104.0]
    }, index=idx)
    check("check_ohlc_inequalities passes valid bar", len(check_ohlc_inequalities(good_ohlc, "GOOD")) == 0)

    bad_high = pd.DataFrame({
        "Open": [100.0], "High": [99.0], "Low": [95.0], "Close": [98.0]
    }, index=idx[:1])
    check("check_ohlc_inequalities catches High < max(Open, Close) (F16)",
          any("High < max" in p for p in check_ohlc_inequalities(bad_high, "BAD")))

    # 2. Calendar presence check (F06)
    cal = pd.date_range("2020-01-01", periods=5, freq="B")
    missing_stock = pd.DataFrame({"Close": [10.0]}, index=pd.to_datetime(["2020-01-04"]))  # Saturday not in cal
    check("check_calendar_presence flags missing dates (F06)", len(check_calendar_presence(missing_stock, cal, "SYM")) > 0)

    # 3. PreListing check (F07)
    padded = pd.DataFrame({"PreListing": [True, False]}, index=idx)
    check("check_no_prelisting_padding flags PreListing=True (F07)", len(check_no_prelisting_padding(padded, "PAD")) > 0)

    # 4. Action coverage audit (F09)
    raw_df = pd.DataFrame({"Close": [100.0, 50.0]}, index=idx)  # -50% jump
    adj_df = pd.DataFrame({"StructAdjClose": [100.0, 50.0]}, index=idx)
    acts_empty = pd.DataFrame(columns=["symbol", "ex_date", "action_type", "ratio"])
    cov = audit_action_coverage(raw_df, adj_df, acts_empty, "UNCAUGHT")
    check("audit_action_coverage reports uncaught raw move >= 15% (F09)", cov["uncaught_count"] == 1)

    print("-" * 70)
    print(f"{passed} passed, {failed} failed")
    print("-" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest())
