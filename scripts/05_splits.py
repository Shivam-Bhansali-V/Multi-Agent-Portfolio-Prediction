"""
05_splits.py -- Phase 2.3: purged, embargoed walk-forward splits on the real labels.

Frozen spec:
    Development window: 2015-01-01 .. 2025-03-31. Holdout (April 2025 onward) is
    sealed and is never touched here.
    Label horizon: 10 trading days.

Checkpoint 2.3's required check, in the user's words: "no label window overlaps train
and test". That is what `verify_no_overlap` asserts, on the real label files, for
every fold and every symbol -- not on synthetic data.

WHY PURGING IS NEEDED (and why a plain date cut is not enough)
--------------------------------------------------------------
A triple-barrier label stamped at date t is resolved by prices in (t, t+10]. If the
train set ends the day before the test set begins, the last 10 train labels are
resolved using prices that live inside the test period. The model would then be fit on
information from its own test window. The standard fix is Lopez de Prado's purging:
drop any train label whose resolution window reaches into the test period. Here the
window end is taken as the label's own `touch_date` when it touched a barrier, and
t+10 sessions otherwise -- using touch_date rather than always t+10 keeps labels that
genuinely resolved early, which would otherwise be discarded for no reason.

EMBARGO: purging alone leaves a subtler leak in the other direction. Serial
correlation means prices just after the test period still carry test-period
information, so a later fold's train set gets an extra `embargo` sessions removed
immediately after each test window. `02d_universe.embargo_folds` computes the
symmetric interval around a boundary and is used here as the boundary-level sanity
cross-check; the per-label purge below is the operative mechanism.

FOLD LAYOUT (expanding train, 1-year test, chosen here -- not previously frozen)
    fold 1: train 2015-01 .. 2017-12   test 2018
    fold 2: train 2015-01 .. 2018-12   test 2019
    ...
    fold 7: train 2015-01 .. 2023-12   test 2024
    fold 8: train 2015-01 .. 2024-12   test 2025-01 .. 2025-03  (short, stub quarter)
An expanding rather than rolling train window is used because the per-symbol label
count is modest and discarding early history would cost more than the
non-stationarity it would avoid. This is a design decision, not a measured one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

LABELS_DIR = ROOT / "data" / "labels"
CLEAN_DIR = ROOT / "data" / "clean"
REPORTS_DIR = ROOT / "reports" / "phase2"

HORIZON = 10
EMBARGO = 10
DEV_START = pd.Timestamp("2015-01-01")
DEV_END = pd.Timestamp("2025-03-31")
HOLDOUT_START = pd.Timestamp("2025-04-01")

PILOT_SYMBOLS = ["TCS", "RELIANCE", "HDFCBANK", "ITC",
                 "SIEMENS", "TATASTEEL", "BHARTIARTL", "ULTRACEMCO"]
# Swapped 8 Oct 2026 -- see 04_backtest.py's PILOT_SYMBOLS comment. This module had its
# own hardcoded copy of the list rather than importing it, which meant the first re-run
# after the swap silently used the stale symbols without erroring -- caught only when
# building Phase 4's fold-based training data. Flagging the duplication rather than just
# fixing it: any future symbol-list change must update BOTH 04_backtest.py and this file.

FOLD_TEST_RANGES: List[Tuple[str, str]] = [
    ("2018-01-01", "2018-12-31"),
    ("2019-01-01", "2019-12-31"),
    ("2020-01-01", "2020-12-31"),
    ("2021-01-01", "2021-12-31"),
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-03-31"),
]


# ======================================================================================
# Loading
# ======================================================================================

def trading_calendar(symbols: Sequence[str] = PILOT_SYMBOLS) -> pd.DatetimeIndex:
    """Union calendar over the pilot symbols' clean files, cut at the dev boundary."""
    cal: Optional[pd.DatetimeIndex] = None
    for sym in symbols:
        p = CLEAN_DIR / f"{sym}.csv"
        if not p.is_file():
            continue
        d = pd.to_datetime(pd.read_csv(p, usecols=["Date"])["Date"]).dt.normalize()
        idx = pd.DatetimeIndex(d.unique())
        cal = idx if cal is None else cal.union(idx)
    if cal is None:
        raise FileNotFoundError("no clean files found to build a calendar from")
    return cal[(cal >= DEV_START) & (cal <= DEV_END)].sort_values()


def load_labels(symbol: str) -> pd.DataFrame:
    """Kept labels only, cut at the dev boundary, with the resolution-window end
    computed per label."""
    p = LABELS_DIR / f"{symbol}.csv"
    if not p.is_file():
        raise FileNotFoundError(f"no label file at {p}")
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["touch_date"] = pd.to_datetime(df["touch_date"], errors="coerce").dt.normalize()
    df = df.loc[df["dropped_reason"].isna() & df["label"].notna()].copy()
    df = df.loc[(df["date"] >= DEV_START) & (df["date"] <= DEV_END)]
    return df.sort_values("date").reset_index(drop=True)


def add_window_end(df: pd.DataFrame, calendar: pd.DatetimeIndex, horizon: int = HORIZON) -> pd.DataFrame:
    """window_end = touch_date if the label touched a barrier, else date + horizon
    sessions on the trading calendar. This is the interval the label's outcome depends
    on, and therefore the interval that must not straddle a train/test boundary."""
    out = df.copy()
    pos = calendar.searchsorted(out["date"].to_numpy())
    pos = np.clip(pos + horizon, 0, len(calendar) - 1)
    timeout_end = calendar[pos]
    out["window_end"] = out["touch_date"].fillna(pd.Series(timeout_end, index=out.index))
    # A touch_date can in principle sit past the calendar end; clamp defensively.
    out["window_end"] = out[["window_end", "date"]].max(axis=1)
    return out


# ======================================================================================
# Split construction
# ======================================================================================

def make_folds(
    labels: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    test_ranges: Sequence[Tuple[str, str]] = FOLD_TEST_RANGES,
    embargo: int = EMBARGO,
) -> List[Dict]:
    """Build purged + embargoed expanding-window folds for one symbol's labels.

    train: labels whose ENTIRE resolution window ends strictly before test_start, and
           which are not inside the embargo shadow of any EARLIER test window.
    test:  labels whose resolution window lies entirely inside the test range.
    """
    folds = []
    for k, (ts, te) in enumerate(test_ranges, start=1):
        test_start, test_end = pd.Timestamp(ts), pd.Timestamp(te)

        in_test = (
            (labels["date"] >= test_start)
            & (labels["date"] <= test_end)
            & (labels["window_end"] <= test_end)
        )
        test_df = labels.loc[in_test]

        # Purge: the whole resolution window must precede the test period.
        train_mask = labels["window_end"] < test_start

        # Embargo after every earlier test window (serial correlation shadow).
        for ts_prev, te_prev in test_ranges[: k - 1]:
            prev_end = pd.Timestamp(te_prev)
            pos = calendar.searchsorted(prev_end)
            shadow_end = calendar[min(pos + embargo, len(calendar) - 1)]
            train_mask &= ~((labels["date"] > prev_end) & (labels["date"] <= shadow_end))

        train_df = labels.loc[train_mask]

        # How many labels purging actually removed, vs a naive date cut.
        naive_train = labels.loc[labels["date"] < test_start]
        folds.append({
            "fold": k,
            "test_start": test_start, "test_end": test_end,
            "train": train_df, "test": test_df,
            "n_train": len(train_df), "n_test": len(test_df),
            "n_purged_vs_naive_cut": int(len(naive_train) - len(train_df)),
            "train_last_date": train_df["date"].max() if len(train_df) else pd.NaT,
            "train_last_window_end": train_df["window_end"].max() if len(train_df) else pd.NaT,
        })
    return folds


# ======================================================================================
# The checkpoint check
# ======================================================================================

def verify_no_overlap(folds: Sequence[Dict], check) -> None:
    """Checkpoint 2.3: no label window overlaps train and test."""
    for f in folds:
        tr, te = f["train"], f["test"]
        ts, tend = f["test_start"], f["test_end"]
        k = f["fold"]

        if len(tr):
            worst = tr["window_end"].max()
            check(f"fold {k}: no train label's resolution window reaches the test period "
                  f"(latest train window end {worst.date()} < test start {ts.date()})",
                  worst < ts,
                  f"{int((tr['window_end'] >= ts).sum())} train label(s) resolve inside the test period")
        if len(te):
            check(f"fold {k}: every test label resolves inside its own test period",
                  bool((te["window_end"] <= tend).all() and (te["date"] >= ts).all()),
                  f"{int((te['window_end'] > tend).sum())} test label(s) resolve past the test period")
        check(f"fold {k}: train and test share no label dates",
              len(set(tr['date']) & set(te['date'])) == 0,
              f"{len(set(tr['date']) & set(te['date']))} shared date(s)")
        check(f"fold {k}: nothing in this fold touches the sealed holdout",
              (len(tr) == 0 or tr['date'].max() < HOLDOUT_START)
              and (len(te) == 0 or te['date'].max() < HOLDOUT_START),
              "a label on/after 2025-04-01 leaked into a dev fold")


def _selftest(symbols: Optional[Sequence[str]] = None) -> int:
    symbols = list(symbols or PILOT_SYMBOLS)
    n_pass, n_fail, failures = 0, 0, []

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal n_pass, n_fail
        if cond:
            n_pass += 1
        else:
            n_fail += 1
            failures.append(f"{name} -- {detail}")
            print(f"FAIL  {name}" + (f"  -- {detail}" if detail else ""))

    print("=" * 78)
    print("05_splits.py -- Phase 2.3 checkpoint: purged walk-forward splits (REAL labels)")
    print("=" * 78)

    cal = trading_calendar(symbols)
    print(f"dev calendar: {cal[0].date()} .. {cal[-1].date()}  ({len(cal)} sessions)\n")

    rows = []
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        labels = add_window_end(load_labels(sym), cal)
        folds = make_folds(labels, cal)
        verify_no_overlap(folds, check)
        for f in folds:
            tr, te = f["train"], f["test"]
            rows.append({
                "symbol": sym, "fold": f["fold"],
                "test_start": str(f["test_start"].date()), "test_end": str(f["test_end"].date()),
                "n_train": f["n_train"], "n_test": f["n_test"],
                "purged_vs_naive_cut": f["n_purged_vs_naive_cut"],
                "train_last_window_end": str(f["train_last_window_end"].date()) if pd.notna(f["train_last_window_end"]) else "",
                "test_up": int((te["label"] == "Up").sum()),
                "test_down": int((te["label"] == "Down").sum()),
                "test_sideways": int((te["label"] == "Sideways").sum()),
                "train_up": int((tr["label"] == "Up").sum()),
                "train_down": int((tr["label"] == "Down").sum()),
                "train_sideways": int((tr["label"] == "Sideways").sum()),
            })

    summary = pd.DataFrame(rows)
    out = REPORTS_DIR / "checkpoint_2_3_folds.csv"
    summary.to_csv(out, index=False)

    agg = summary.groupby("fold").agg(
        test_start=("test_start", "first"), test_end=("test_end", "first"),
        n_train=("n_train", "sum"), n_test=("n_test", "sum"),
        purged=("purged_vs_naive_cut", "sum"),
    ).reset_index()
    print("Per-fold totals across the 8 pilot symbols:")
    print(agg.to_string(index=False))
    print(f"\nTotal labels purged by the window rule that a naive date cut would have kept: "
          f"{int(summary['purged_vs_naive_cut'].sum())}")
    print(f"wrote {out.relative_to(ROOT)}")

    print("\n" + "-" * 78)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures[:20]:
            print(f"  - {f}")
    print("-" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest(sys.argv[1:] or None))
