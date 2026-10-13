# backtest_v3.py
"""Simple back‑test harness for the v3 prediction signal.
It loads a CSV of historical OHLCV data (must contain a 'Date' column),
computes the signal for each row (starting after enough look‑back) and
evaluates a naive strategy:

* If the score > 0.1 → go long for the next candle.
* If the score < -0.1 → go short.
* Otherwise stay flat.

The script records cumulative returns, Sharpe ratio and hit‑rate, then
prints a short report.  This is sufficient for a quick demo and can be
extended for proper walk‑forward / holdout testing later.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Import the v3 scoring function.
sys.path.append(str(Path(__file__).parent))
from prediction_method_v3 import next_candle_score_v3

# Frozen spec (CLAUDE.md, approved 7 Oct 2026): development window ends
# 2025-03-31; 2025-04-01 onward is the final holdout, opened once in Phase 9
# and not to be touched by exploratory runs like this one.
DEV_END = pd.Timestamp("2025-03-31")
HOLDOUT_START = pd.Timestamp("2025-04-01")


def run_backtest(csv_path: str, allow_short: bool = False, allow_holdout: bool = False):
    """
    allow_short: the project is cash-equity, long-or-cash only (no shorting
        available). Default False means a score < -0.1 is treated the same
        as a flat score (no position) rather than opening a short that
        couldn't actually be traded. Pass True only for a deliberate,
        clearly-labelled long/short comparison run.
    allow_holdout: default False truncates the input to dates <= DEV_END so
        this can't silently burn the frozen Apr-2025+ holdout on an ordinary
        exploratory run. Pass True only when you mean to open the holdout.
    """
    df = pd.read_csv(csv_path)

    # Auto-detect and parse date column
    date_col = None
    for col in df.columns:
        if col.lower() in ("date", "datetime", "timestamp"):
            date_col = col
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.rename(columns={date_col: "Date"})
    else:
        # No date column found — create a synthetic one
        df["Date"] = pd.date_range(start="2020-01-01", periods=len(df), freq="B")

    df = df.sort_values("Date").reset_index(drop=True)

    if not allow_holdout:
        holdout_rows = (df["Date"] >= HOLDOUT_START).sum()
        df = df.loc[df["Date"] <= DEV_END].reset_index(drop=True)
        if holdout_rows:
            print(f"NOTE: {holdout_rows} row(s) on/after {HOLDOUT_START.date()} "
                  f"dropped -- that's the frozen holdout (CLAUDE.md), not "
                  f"touched by this run. Pass allow_holdout=True to include it "
                  f"deliberately.")
        if len(df) == 0:
            print("No rows left before the holdout boundary -- nothing to backtest.")
            return

    print(f"File: {csv_path}")
    print(f"Date range: {df['Date'].iloc[0].date()} → {df['Date'].iloc[-1].date()}")
    if not allow_short:
        print("Mode: long-or-cash only (allow_short=False)")
    print()

    # Prepare columns for results
    df["Signal"] = 0.0
    df["Return"] = df["Close"].pct_change().shift(-1)  # next‑candle return

    # Compute signal for each row where we have enough history
    for i in range(30, len(df) - 1):  # need at least 30 rows for indicators
        window_df = df.iloc[: i + 1]
        try:
            score = next_candle_score_v3(window_df)
        except Exception:
            score = None
        if score is None:
            df.at[i, "Signal"] = 0.0
        elif score > 0.1:
            df.at[i, "Signal"] = 1.0
        elif allow_short and score < -0.1:
            df.at[i, "Signal"] = -1.0
        else:
            df.at[i, "Signal"] = 0.0

    # Strategy return = signal * next-candle return
    df["StrategyRet"] = df["Signal"] * df["Return"]

    # Only evaluate rows where we actually took a position AND have a known next-day return
    active = df.loc[(df["Signal"] != 0) & df["Return"].notna()].copy()

    # Simple performance metrics
    if len(active) == 0:
        print("=== Back-test report ===")
        print("No trades were generated.")
        return

    total_ret = (1 + df["StrategyRet"].fillna(0)).prod() - 1
    strat_rets = active["StrategyRet"]
    sharpe = (strat_rets.mean() / strat_rets.std()) * np.sqrt(252) if strat_rets.std() != 0 else np.nan
    hits = (active["StrategyRet"] > 0).sum()
    hit_rate = hits / len(active)

    print("=== Back-test report ===")
    print(f"Rows processed:          {len(df)}")
    print(f"Trades taken:            {len(active)}")
    print(f"Final cumulative return: {total_ret:.2%}")
    print(f"Sharpe (annualised):     {sharpe:.2f}")
    print(f"Hit-rate:                {hit_rate:.2%}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backtest_v3.py <historical_csv> [--allow-short] [--allow-holdout]")
        sys.exit(1)
    flags = sys.argv[2:]
    run_backtest(
        sys.argv[1],
        allow_short="--allow-short" in flags,
        allow_holdout="--allow-holdout" in flags,
    )
