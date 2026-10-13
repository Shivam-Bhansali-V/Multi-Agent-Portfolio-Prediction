"""
03_labels.py -- Phase 1->2 bridge: triple-barrier labeling on the remediated clean data.

Frozen spec (do not change without asking):
    Labels: triple-barrier, +2*ATR up / -1*ATR down / 10-day timeout = Sideways
    Label horizon: 10 trading days
    Direction: long-only
    Costs: 0.35% per round trip (NOT applied here -- that's a backtest/P&L concern,
           not a labeling concern; labels are pure price-barrier outcomes)

This is the first module past Phase 1 (data cleaning). It consumes, rather than
re-derives, everything already built:
    - data/clean/<symbol>.csv          (02_clean_adjust.py output: AdjOpen/AdjHigh/
                                         AdjLow/AdjClose, calendar-aligned)
    - reports/phase1/checkpoint_1_3_universe.csv  (truncate_at per symbol)
    - 02d_universe.purge_windows()     (label-poisoned windows around structural
                                         corporate actions -- F15 fix)

Per-bar pipeline:
    1. ATR(14) on the adjusted OHLC, min_periods=14 (no ffill-damage degenerate ATR --
       see 02c_calendar.assert_no_ffill_damage's warning this guards against).
    2. For each date t with a full ATR and a full 10-day forward window available:
       upper = AdjClose[t] + 2*ATR[t], lower = AdjClose[t] - 1*ATR[t].
       Scan t+1 .. t+10 using AdjHigh (upper touch) / AdjLow (lower touch).
       First touch wins (by session order); if both touch the same session, Down
       wins (conservative -- long-only, we don't assume the favorable fill).
       No touch in 10 sessions -> Sideways (timeout).
    3. Drop any label date inside a purge window (F15) or on/after that symbol's
       truncate_at (structural truncation -- VEDL/SIEMENS-style demergers), or
       whose forward window would cross truncate_at.

This module does NOT touch, re-verify, or "fix" any of the uncaught-move /
exclude_reason numbers from checkpoint 1.3 -- those stand as reported.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import importlib.util as _ilu  # noqa: E402


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


a02a = _load("02a_build_corp_actions")
a02d = _load("02d_universe")

CLEAN_DIR = ROOT / "data" / "clean"
REPORTS_DIR = ROOT / "reports" / "phase1"
UNIVERSE_CSV = REPORTS_DIR / "checkpoint_1_3_universe.csv"
OUT_DIR = ROOT / "data" / "labels"

ATR_WINDOW = 14
HORIZON = 10         # frozen spec
UP_MULT = 2.0        # frozen spec: +2*ATR
DOWN_MULT = 1.0       # frozen spec: -1*ATR


def compute_atr(df: pd.DataFrame, window: int = ATR_WINDOW) -> pd.Series:
    """Wilder-style True Range / simple rolling ATR on the adjusted OHLC.

    min_periods=window -- never a partial-window ATR. A partial window
    understates true range (the exact degenerate-ATR failure mode 02c_calendar's
    assert_no_ffill_damage exists to catch one layer up).
    """
    high = df["AdjHigh"]
    low = df["AdjLow"]
    close = df["AdjClose"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=window, min_periods=window).mean()


def _in_any_window(date: pd.Timestamp, windows) -> bool:
    return any(start <= date <= end for start, end in windows)


def triple_barrier_labels(
    df: pd.DataFrame,
    symbol: str,
    purge_wins=None,
    truncate_at: pd.Timestamp = None,
    atr_window: int = ATR_WINDOW,
    horizon: int = HORIZON,
    up_mult: float = UP_MULT,
    down_mult: float = DOWN_MULT,
) -> pd.DataFrame:
    """Return one row per candidate label date with columns:
    date, label (Up/Down/Sideways), touch_date, atr, upper_barrier, lower_barrier,
    dropped_reason (None if kept; else 'purge_window' / 'post_truncate' /
    'crosses_truncate' / 'insufficient_atr_warmup' / 'insufficient_forward_window').
    """
    purge_wins = purge_wins or []
    idx = df.index
    atr = compute_atr(df, atr_window)
    close = df["AdjClose"]
    high = df["AdjHigh"]
    low = df["AdjLow"]

    rows = []
    n = len(idx)
    for i in range(n):
        t = idx[i]
        rec = {"date": t, "symbol": symbol, "label": None, "touch_date": None,
               "atr": float(atr.iloc[i]) if np.isfinite(atr.iloc[i]) else np.nan,
               "upper_barrier": np.nan, "lower_barrier": np.nan,
               "dropped_reason": None}

        if truncate_at is not None and t >= truncate_at:
            rec["dropped_reason"] = "post_truncate"
            rows.append(rec); continue
        if _in_any_window(t, purge_wins):
            rec["dropped_reason"] = "purge_window"
            rows.append(rec); continue
        if not np.isfinite(atr.iloc[i]) or pd.isna(close.iloc[i]):
            rec["dropped_reason"] = "insufficient_atr_warmup"
            rows.append(rec); continue
        if i + horizon >= n:
            rec["dropped_reason"] = "insufficient_forward_window"
            rows.append(rec); continue

        fwd_end_date = idx[i + horizon]
        if truncate_at is not None and fwd_end_date >= truncate_at:
            rec["dropped_reason"] = "crosses_truncate"
            rows.append(rec); continue

        c0 = float(close.iloc[i])
        a0 = float(atr.iloc[i])
        upper = c0 + up_mult * a0
        lower = c0 - down_mult * a0
        rec["upper_barrier"] = upper
        rec["lower_barrier"] = lower

        label = "Sideways"
        touch_date = None
        for j in range(i + 1, i + horizon + 1):
            h, l = high.iloc[j], low.iloc[j]
            if pd.isna(h) or pd.isna(l):
                continue
            up_hit = h >= upper
            down_hit = l <= lower
            if up_hit and down_hit:
                label = "Down"  # conservative: don't assume the favorable fill
                touch_date = idx[j]
                break
            elif down_hit:
                label = "Down"
                touch_date = idx[j]
                break
            elif up_hit:
                label = "Up"
                touch_date = idx[j]
                break
        rec["label"] = label
        rec["touch_date"] = touch_date
        rows.append(rec)

    return pd.DataFrame(rows)


def run(symbols) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    actions_df = a02a.load_corp_actions(ROOT)
    universe_df = pd.read_csv(UNIVERSE_CSV) if UNIVERSE_CSV.is_file() else pd.DataFrame()

    summary = []
    for sym in symbols:
        path = CLEAN_DIR / f"{sym}.csv"
        if not path.is_file():
            summary.append({"symbol": sym, "error": f"no clean file at {path}"})
            continue
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        df = df.set_index("Date").sort_index()

        truncate_at = None
        if not universe_df.empty:
            row = universe_df.loc[universe_df["symbol"] == sym]
            if not row.empty and isinstance(row.iloc[0].get("truncate_at"), str) and row.iloc[0]["truncate_at"]:
                truncate_at = pd.Timestamp(row.iloc[0]["truncate_at"])

        pw = a02d.purge_windows(actions_df, sym, horizon=HORIZON)

        labels = triple_barrier_labels(df, sym, purge_wins=pw, truncate_at=truncate_at)
        out_path = OUT_DIR / f"{sym}.csv"
        labels.to_csv(out_path, index=False)

        kept = labels[labels["dropped_reason"].isna()]
        dist = kept["label"].value_counts().to_dict()
        dropped = labels["dropped_reason"].value_counts().to_dict()
        summary.append({
            "symbol": sym,
            "total_candidate_dates": len(labels),
            "kept": len(kept),
            "up": dist.get("Up", 0),
            "down": dist.get("Down", 0),
            "sideways": dist.get("Sideways", 0),
            "dropped_purge_window": dropped.get("purge_window", 0),
            "dropped_post_truncate": dropped.get("post_truncate", 0),
            "dropped_crosses_truncate": dropped.get("crosses_truncate", 0),
            "dropped_insufficient_atr_warmup": dropped.get("insufficient_atr_warmup", 0),
            "dropped_insufficient_forward_window": dropped.get("insufficient_forward_window", 0),
            "truncate_at": str(truncate_at.date()) if truncate_at is not None else "",
            "purge_windows_in_range": sum(
                1 for s, e in pw if e >= df.index[0] and s <= df.index[-1]
            ),
        })

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(REPORTS_DIR / "checkpoint_2_1_labels_summary.csv", index=False)
    return {"summary": summary_df}


if __name__ == "__main__":
    syms = sys.argv[1:] or ["TCS", "RELIANCE", "BAJAJFINSV", "ITC", "SIEMENS", "VEDL", "IDEA", "ADANIENT"]
    result = run(syms)
    pd.set_option("display.width", 160)
    print(result["summary"].to_string(index=False))
