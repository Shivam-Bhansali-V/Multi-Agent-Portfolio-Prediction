"""
04_backtest.py -- Phase 2.2: backtest engine with costs and next-day execution.

Frozen spec (CLAUDE.md, approved 7 Oct 2026):
    Direction:  long-only ("Long or cash only")
    Execution:  "Entry at next day's open; no fill on price-band-locked days"
    Costs:      0.35% per round trip (0.25% verified charges + 0.10% assumed slippage)
    Holdout:    April 2025 onward is SEALED. Development data is Jan 2015 - Mar 2025.
                This module refuses to read past HOLDOUT_START unless explicitly
                unsealed with allow_holdout=True (Phase 9 only, once).
    Settlement: T+1 (T+2 before Jan 2023) is a cash/share-availability constraint on
                the investor, NOT a price-path mechanic. It is deliberately not modeled
                here. The no-lookahead rule actually enforced is next-day-open
                execution, below.

EXECUTION MODEL (this is the part the previous draft of this file got wrong)
---------------------------------------------------------------------------
signal[t] in {0,1} is decided using information through Close[t]. It cannot be acted
on until Open[t+1]. Therefore the Close[t] -> Open[t+1] overnight gap belongs to the
market, not to the strategy. Concretely, for a position that runs from entry day e to
exit day x (both in calendar order, e <= x):

    day e  (entry, buy at Open[e]):      r = Close[e] / Open[e]   - 1
    day i  (hold, e < i < x):            r = Close[i] / Close[i-1] - 1
    day x  (exit, sell at Open[x]):      r = Open[x]  / Close[x-1] - 1
    cost charged once, at exit:          equity *= (1 - cost_pct)

A naive implementation marks every held day close-to-close, including the entry day.
That silently hands the strategy the Close[t] -> Open[t+1] gap for free -- i.e. it
executes at Close[t], simultaneous with the signal decision, which is lookahead. In
Indian equities overnight gaps are a large and news-driven share of total return, so
that leak flatters any news- or event-driven signal badly. `_check_no_gap_leak` below
is a direct regression test against it: a signal with PERFECT foresight of tomorrow's
overnight gap must earn nothing in this engine.

NO FILL ON NON-TRADEABLE DAYS
-----------------------------
A day is tradeable only if it has positive volume and is not flagged NoData. Flat
zero-volume bars exist in data/clean (7 such dates in 2025-2026 for the pilot symbols)
and are a mix of real exchange holidays wrongly admitted to the trading calendar and
one verified real session with missing Yahoo data (2025-03-18). On a non-tradeable day
the position cannot change: the desired position is deferred to the next tradeable
day. This is also where a true price-band (circuit) lock would be handled once a
band-lock flag exists in the clean data -- it does not yet, so band locks are
currently approximated by the volume/NoData test only. That limitation is reported,
not papered over.

CHECKS (checkpoint 2.2: "buy-and-hold matches the index, random signals lose roughly
the costs"). Run with `python 04_backtest.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "clean"
REPORTS_DIR = ROOT / "reports" / "phase2"

COST_PCT = 0.0035                                 # frozen spec: 0.35% per round trip
HOLDOUT_START = pd.Timestamp("2025-04-01")        # frozen spec: sealed until Phase 9
TRADING_DAYS_PER_YEAR = 252

PILOT_SYMBOLS = ["TCS", "RELIANCE", "HDFCBANK", "ITC",
                 "SIEMENS", "TATASTEEL", "BHARTIARTL", "ULTRACEMCO"]
# Swapped 8 Oct 2026 per user decision: BAJAJFINSV, VEDL, IDEA, ADANIENT were flagged in
# reports/phase1/checkpoint_1_3_universe.csv with unresolved corporate-action adjustment
# problems (BAJAJFINSV: 1 unexplained move; VEDL: APPROX_RATIO on 96% of rows; IDEA: 33
# unexplained moves; ADANIENT: 17 unexplained moves). Replaced with HDFCBANK, TATASTEEL,
# BHARTIARTL, ULTRACEMCO -- all confirmed clean (no exclude_reason, AdjQuality=OK) in the
# same universe check. All Phase 2/3 checkpoints computed before this swap (with the old
# 8) are stale and have been re-run.
BENCHMARK_SYMBOL = "NIFTY100"


# ======================================================================================
# Data loading
# ======================================================================================

def load_clean(
    symbol: str,
    clean_dir: Path = CLEAN_DIR,
    allow_holdout: bool = False,
    holdout_start: pd.Timestamp = HOLDOUT_START,
) -> pd.DataFrame:
    """Load data/clean/<symbol>.csv, add a `Tradeable` column, and (by default) cut
    the frame at the sealed holdout boundary.

    allow_holdout=True is Phase 9 only. It is an explicit argument rather than a
    default so that no development-phase code path can touch the holdout by accident.
    """
    path = Path(clean_dir) / f"{symbol}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"no clean file at {path}")
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.set_index("Date").sort_index()

    required = ["AdjOpen", "AdjHigh", "AdjLow", "AdjClose"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{symbol}: clean file missing required columns {missing}")

    vol = df["AdjVolume"] if "AdjVolume" in df.columns else pd.Series(1.0, index=df.index)
    nodata = df["NoData"].astype(bool) if "NoData" in df.columns else pd.Series(False, index=df.index)
    prelist = df["PreListing"].astype(bool) if "PreListing" in df.columns else pd.Series(False, index=df.index)
    postdelist = df["PostDelisting"].astype(bool) if "PostDelisting" in df.columns else pd.Series(False, index=df.index)

    priced = df[required].notna().all(axis=1)
    # Zero volume ALONE is not a non-tradeable signal: the NIFTY100 index series
    # legitimately reports zero volume on 256 dev-window sessions while still having a
    # real high/low range. The forward-filled phantom sessions are identified by the
    # conjunction of zero volume AND a completely flat bar (O==H==L==C), which is what
    # an ffill of the previous close produces.
    flat_bar = (
        (df["AdjOpen"] == df["AdjHigh"])
        & (df["AdjHigh"] == df["AdjLow"])
        & (df["AdjLow"] == df["AdjClose"])
    )
    phantom = flat_bar & (vol.fillna(0) <= 0)
    df["Tradeable"] = priced & ~phantom & ~nodata & ~prelist & ~postdelist

    if not allow_holdout:
        df = df.loc[df.index < holdout_start]
    return df


def dev_window(df: pd.DataFrame, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    out = df
    if start is not None:
        out = out.loc[out.index >= pd.Timestamp(start)]
    if end is not None:
        out = out.loc[out.index <= pd.Timestamp(end)]
    return out


# ======================================================================================
# The engine
# ======================================================================================

def backtest_signal(
    df: pd.DataFrame,
    signal: pd.Series,
    cost_pct: float = COST_PCT,
    force_close_at_end: bool = True,
) -> dict:
    """Long-only, next-day-open-execution, cost-per-round-trip backtest.

    df      : indexed by date, with AdjOpen/AdjClose (and optionally `Tradeable`).
    signal  : 0/1 series aligned to df.index. signal[t] uses info through Close[t]
              and is executed at Open[t+1].

    Returns a dict with:
        equity          net equity curve, starts at 1.0
        gross_equity    the same path with no costs charged
        daily_net       per-day net simple returns
        daily_gross     per-day gross simple returns
        position        the position actually held each day (after fill deferral)
        trades          list of per-trade dicts with real prices and returns
        n_round_trips, gross_return, net_return, exposure, metrics
    """
    idx = df.index
    if len(idx) == 0:
        raise ValueError("empty frame")

    op = df["AdjOpen"].to_numpy(dtype=float)
    cl = df["AdjClose"].to_numpy(dtype=float)
    tradeable = (df["Tradeable"].to_numpy(dtype=bool) if "Tradeable" in df.columns
                 else np.ones(len(idx), dtype=bool))

    sig = signal.reindex(idx).fillna(0).astype(int).to_numpy()
    # Next-day execution: the position intended for day i comes from signal[i-1].
    desired = np.empty(len(idx), dtype=int)
    desired[0] = 0
    desired[1:] = sig[:-1]

    n = len(idx)
    position = np.zeros(n, dtype=int)
    daily_gross = np.zeros(n, dtype=float)
    cost_factor = np.ones(n, dtype=float)

    held = 0                 # position carried into day i
    entry_i: Optional[int] = None
    entry_px = np.nan
    trades: List[Dict] = []
    # Mark-to-market reference price. This must be the last price the position was
    # actually marked at, NOT cl[i-1]: a NaN or phantom bar in between would otherwise
    # break the return chain and silently drop a real price move. (NIFTY100 has 15
    # NoData sessions in the dev window; using cl[i-1] lost 23 percentage points of
    # index return across them.)
    mark_px = np.nan

    for i in range(n):
        want = desired[i]
        can_trade = bool(tradeable[i]) and np.isfinite(op[i]) and np.isfinite(cl[i])
        # No fill on a non-tradeable day: the position simply cannot change.
        now = want if can_trade else held

        if held == 0 and now == 1:
            # Entry at today's open. The Close[t] -> Open[t+1] gap is NOT earned.
            daily_gross[i] = cl[i] / op[i] - 1.0
            entry_i, entry_px = i, op[i]
            mark_px = cl[i]
        elif held == 1 and now == 1:
            if np.isfinite(cl[i]) and np.isfinite(mark_px) and mark_px > 0:
                daily_gross[i] = cl[i] / mark_px - 1.0
                mark_px = cl[i]
            # else: unpriced session, carry the mark forward at a zero return.
        elif held == 1 and now == 0:
            # Exit at today's open. The last return earned is mark -> Open[i].
            ref = mark_px if np.isfinite(mark_px) and mark_px > 0 else op[i]
            daily_gross[i] = op[i] / ref - 1.0
            cost_factor[i] = 1.0 - cost_pct
            trades.append({
                "entry_date": idx[entry_i], "entry_price": float(entry_px),
                "exit_date": idx[i], "exit_price": float(op[i]),
                "bars_held": int(i - entry_i),
                "gross_return": float(op[i] / entry_px - 1.0),
                "net_return": float((op[i] / entry_px) * (1.0 - cost_pct) - 1.0),
                "force_closed": False,
            })
            entry_i, entry_px, mark_px = None, np.nan, np.nan
        # else: flat yesterday, flat today -> zero return, nothing to do.

        if not np.isfinite(daily_gross[i]):
            daily_gross[i] = 0.0
        position[i] = now
        held = now

    if held == 1 and entry_i is not None and force_close_at_end:
        # Cannot exit at an open that does not exist; close at the last close and still
        # charge the round trip. An open, uncosted position must never be reported free.
        last_px = cl[n - 1] if np.isfinite(cl[n - 1]) else mark_px
        cost_factor[n - 1] *= (1.0 - cost_pct)
        trades.append({
            "entry_date": idx[entry_i], "entry_price": float(entry_px),
            "exit_date": idx[n - 1], "exit_price": float(last_px),
            "bars_held": int(n - 1 - entry_i),
            "gross_return": float(last_px / entry_px - 1.0),
            "net_return": float((last_px / entry_px) * (1.0 - cost_pct) - 1.0),
            "force_closed": True,
        })

    gross_equity = np.cumprod(1.0 + daily_gross)
    net_equity = np.cumprod((1.0 + daily_gross) * cost_factor)
    daily_net = np.empty(n, dtype=float)
    daily_net[0] = net_equity[0] - 1.0
    daily_net[1:] = net_equity[1:] / net_equity[:-1] - 1.0

    eq = pd.Series(net_equity, index=idx)
    geq = pd.Series(gross_equity, index=idx)
    pos = pd.Series(position, index=idx)

    return {
        "equity": eq,
        "gross_equity": geq,
        "daily_net": pd.Series(daily_net, index=idx),
        "daily_gross": pd.Series(daily_gross, index=idx),
        "position": pos,
        "trades": trades,
        "n_round_trips": len(trades),
        "gross_return": float(geq.iloc[-1] - 1.0),
        "net_return": float(eq.iloc[-1] - 1.0),
        "exposure": float(pos.mean()),
        "metrics": performance_metrics(eq, pos),
    }


def performance_metrics(equity: pd.Series, position: Optional[pd.Series] = None) -> dict:
    """CAGR / vol / Sharpe / max drawdown / exposure from a net equity curve."""
    if len(equity) < 2:
        return {}
    r = equity.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if equity.iloc[-1] > 0 else float("nan")
    vol = float(r.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)) if r.std(ddof=1) > 0 else float("nan")
    dd = float((equity / equity.cummax() - 1.0).min())
    out = {"total_return": total, "cagr": cagr, "ann_vol": vol,
           "sharpe": sharpe, "max_drawdown": dd, "years": float(years)}
    if position is not None:
        out["exposure"] = float(position.mean())
    return out


def buy_and_hold(df: pd.DataFrame, cost_pct: float = COST_PCT) -> dict:
    """Always-long benchmark run through the same engine, so it pays the same one
    round trip and obeys the same next-day-open rule."""
    return backtest_signal(df, pd.Series(1, index=df.index), cost_pct=cost_pct)


# ======================================================================================
# Checks
# ======================================================================================

def _check_buy_and_hold_identity(check, symbols: Sequence[str]) -> None:
    """Checkpoint 2.2, part 1a: an always-long signal must reproduce the instrument's
    own open-to-close price return exactly, minus exactly one round-trip cost."""
    print("\n--- Check 1a: buy-and-hold reproduces the raw price return exactly ---")
    for sym in symbols:
        df = dev_window(load_clean(sym))
        res = buy_and_hold(df)
        pos = res["position"]
        held = pos[pos == 1]
        entry_date, exit_date = held.index[0], held.index[-1]
        entry_px = float(df.loc[entry_date, "AdjOpen"])
        exit_px = float(df.loc[exit_date, "AdjClose"])
        expected_gross = exit_px / entry_px - 1.0
        expected_net = (1.0 + expected_gross) * (1.0 - COST_PCT) - 1.0
        check(
            f"{sym}: B&H gross == Open[{entry_date.date()}] -> Close[{exit_date.date()}]",
            abs(res["gross_return"] - expected_gross) < 1e-9,
            f"got {res['gross_return']:.10f}, expected {expected_gross:.10f}",
        )
        check(
            f"{sym}: B&H net == gross minus exactly one round trip, {res['n_round_trips']} trip(s)",
            abs(res["net_return"] - expected_net) < 1e-9 and res["n_round_trips"] == 1,
            f"got {res['net_return']:.10f}, expected {expected_net:.10f}, trips={res['n_round_trips']}",
        )


def _check_buy_and_hold_matches_index(check) -> None:
    """Checkpoint 2.2, part 1b, as the user worded it: "buy-and-hold matches the
    index". Run B&H on the NIFTY100 series through the engine and confirm it equals
    the index's own return over the same window."""
    print("\n--- Check 1b: buy-and-hold on NIFTY100 matches the index's own return ---")
    df = dev_window(load_clean(BENCHMARK_SYMBOL))
    res = buy_and_hold(df)
    tr = df.loc[df["Tradeable"]]
    index_return = float(tr["AdjClose"].iloc[-1] / tr["AdjOpen"].iloc[0] - 1.0)
    # The engine enters on the first tradeable day after the first bar, so compare
    # against the engine's own realised entry/exit rather than assuming day 0.
    pos = res["position"]
    held = pos[pos == 1]
    eng_entry = float(df.loc[held.index[0], "AdjOpen"])
    eng_exit = float(df.loc[held.index[-1], "AdjClose"])
    eng_index_return = eng_exit / eng_entry - 1.0
    check(
        "NIFTY100 B&H gross return equals the index price return over the held window",
        abs(res["gross_return"] - eng_index_return) < 1e-9,
        f"engine {res['gross_return']:.10f} vs index {eng_index_return:.10f}",
    )
    check(
        "NIFTY100 B&H is within 1% of the naive first-tradeable-open to last-close return",
        abs(res["gross_return"] - index_return) < 0.01,
        f"engine {res['gross_return']:.6f} vs naive {index_return:.6f}",
    )
    print(f"      NIFTY100 dev-window B&H: gross {res['gross_return']*100:.2f}%, "
          f"net {res['net_return']*100:.2f}%, CAGR {res['metrics']['cagr']*100:.2f}%, "
          f"maxDD {res['metrics']['max_drawdown']*100:.2f}%")


def _check_cost_identity(check, symbols: Sequence[str]) -> None:
    """Checkpoint 2.2, part 2a: costs charged must be EXACTLY n round trips and
    nothing else. net_final == gross_final * (1 - c)^n, to floating point.

    This is the precise form of "random signals lose roughly the costs". The looser
    version -- comparing the net-vs-gross gap against the linear sum n*c -- cannot
    hold, because n round trips compound as (1-c)^n, not 1 - n*c. With ~125 round
    trips at 0.35% the linear sum is 43.8% while the true compounded drag is 35.5%;
    a test written against the linear sum fails or passes depending on the gross
    return, which is noise, not correctness.
    """
    print("\n--- Check 2a: cost drag is exactly (1-c)^n, no more and no less ---")
    rng = np.random.default_rng(7)
    for sym in symbols:
        df = dev_window(load_clean(sym))
        sig = pd.Series(rng.integers(0, 2, size=len(df)), index=df.index)
        res = backtest_signal(df, sig)
        n = res["n_round_trips"]
        expected_net = (1.0 + res["gross_return"]) * (1.0 - COST_PCT) ** n - 1.0
        check(
            f"{sym}: net == gross * (1-c)^{n}",
            abs(res["net_return"] - expected_net) < 1e-8,
            f"got {res['net_return']:.10f}, expected {expected_net:.10f}",
        )
        check(
            f"{sym}: random signal ends below its own gross (it pays the costs)",
            res["net_return"] < res["gross_return"],
            f"net {res['net_return']:.4f} vs gross {res['gross_return']:.4f}",
        )


def _check_no_gap_leak(check) -> None:
    """Deterministic regression test for the execution bug this file was rewritten to
    fix: the entry day must NOT be marked close-to-close.

    A statistical version of this test (does perfect foresight of tomorrow's gap earn
    anything?) cannot work, because gap continuation is a real and sizeable effect in
    Indian equities -- a stock that gaps up often keeps rising intraday. Such a test
    conflates a genuine signal with a leak. So this is a hand-built frame where the
    correct answer is known exactly.

    Frame: a 10% overnight gap up between Close[0] and Open[1], then a flat session.
        Signal turns on at t=0, so execution is at Open[1] = 110.
        Correct engine: day-1 return = Close[1]/Open[1] - 1 = 0%.
        Leaky engine:   day-1 return = Close[1]/Close[0] - 1 = +10%.
    """
    print("\n--- Check 3: entry forfeits the overnight gap, exit earns it ---")
    idx = pd.date_range("2020-01-01", periods=4, freq="D")

    # Entry side: a 10% gap up must NOT be captured.
    df_in = pd.DataFrame({
        "AdjOpen":  [100.0, 110.0, 110.0, 110.0],
        "AdjHigh":  [100.0, 110.0, 110.0, 110.0],
        "AdjLow":   [100.0, 110.0, 110.0, 110.0],
        "AdjClose": [100.0, 110.0, 110.0, 110.0],
        "Tradeable": [True, True, True, True],
    }, index=idx)
    res = backtest_signal(df_in, pd.Series([1, 1, 1, 1], index=idx), cost_pct=0.0)
    check("a 10% overnight gap before entry earns exactly 0% (no close-to-close leak)",
          abs(res["gross_return"]) < 1e-12,
          f"got {res['gross_return']*100:.4f}%, a leaky engine returns +10%")

    # Exit side: the gap between the last held close and the exit open IS earned.
    df_out = pd.DataFrame({
        "AdjOpen":  [100.0, 100.0, 110.0, 110.0],
        "AdjHigh":  [100.0, 100.0, 110.0, 110.0],
        "AdjLow":   [100.0, 100.0, 110.0, 110.0],
        "AdjClose": [100.0, 100.0, 110.0, 110.0],
        "Tradeable": [True, True, True, True],
    }, index=idx)
    # on at t=0 -> entry Open[1]=100; off at t=1 -> exit Open[2]=110.
    res2 = backtest_signal(df_out, pd.Series([1, 0, 0, 0], index=idx), cost_pct=0.0)
    check("the gap between the last held close and the exit open is earned (+10%)",
          abs(res2["gross_return"] - 0.10) < 1e-12,
          f"got {res2['gross_return']*100:.4f}%")
    check("that round trip is recorded entry Open -> exit Open",
          res2["n_round_trips"] == 1
          and abs(res2["trades"][0]["entry_price"] - 100.0) < 1e-12
          and abs(res2["trades"][0]["exit_price"] - 110.0) < 1e-12,
          f"trades {res2['trades']}")

    # Return chain must survive an unpriced session mid-position.
    idx5 = pd.date_range("2020-01-01", periods=5, freq="D")
    df_gap = pd.DataFrame({
        "AdjOpen":  [100.0, 100.0, np.nan, 120.0, 120.0],
        "AdjHigh":  [100.0, 100.0, np.nan, 120.0, 120.0],
        "AdjLow":   [100.0, 100.0, np.nan, 120.0, 120.0],
        "AdjClose": [100.0, 100.0, np.nan, 120.0, 120.0],
        "Tradeable": [True, True, False, True, True],
    }, index=idx5)
    res3 = backtest_signal(df_gap, pd.Series([1, 1, 1, 1, 1], index=idx5), cost_pct=0.0)
    check("a mid-position unpriced session does not break the return chain (+20%)",
          abs(res3["gross_return"] - 0.20) < 1e-12,
          f"got {res3['gross_return']*100:.4f}% (a cl[i-1] mark drops this move entirely)")


def _check_random_loses_the_costs(check, symbols: Sequence[str], n_seeds: int = 200) -> None:
    """Checkpoint 2.2, part 2, economic half: "random signals lose roughly the costs".

    The honest way to state this: a random long/flat signal should earn, gross, about
    what its market exposure entitles it to -- no more -- and should then fall short of
    that by the compounded cost drag, and by nothing else.

    Benchmark choice matters. The naive comparison against close-to-close buy-and-hold
    is wrong under open execution: an entry day earns only Close/Open (it forfeits the
    overnight gap) while an exit day earns only Open/Close_prev. Each trade therefore
    earns open-to-open, not close-to-close, and in Indian equities overnight drift is a
    large share of total drift -- so close-to-close is a biased yardstick that would
    make a correct engine look like it had a negative edge. The benchmark used here is
    the market's own OPEN-TO-OPEN log return, exposure-scaled.
    """
    print(f"\n--- Check 2b: random signal earns its exposure, loses the costs "
          f"({n_seeds} seeds/symbol) ---")
    for sym in symbols:
        df = dev_window(load_clean(sym))
        tr = df.loc[df["Tradeable"]]
        # Market open-to-open log return over the tradeable sessions.
        oo = np.log(tr["AdjOpen"] / tr["AdjOpen"].shift(1)).dropna()
        mkt_oo_total = float(oo.sum())

        edges, drags = [], []
        rng = np.random.default_rng(abs(hash(sym)) % (2**32))
        for _ in range(n_seeds):
            sig = pd.Series(rng.integers(0, 2, size=len(df)), index=df.index)
            res = backtest_signal(df, sig)
            if res["n_round_trips"] < 10:
                continue
            lr_gross = np.log1p(res["gross_return"])
            edges.append(lr_gross - res["exposure"] * mkt_oo_total)
            # Realised cost drag in log space vs what n round trips should cost.
            realised = np.log1p(res["gross_return"]) - np.log1p(res["net_return"])
            expected = -res["n_round_trips"] * np.log(1.0 - COST_PCT)
            drags.append(realised - expected)

        e = np.array(edges)
        t_edge = e.mean() / (e.std(ddof=1) / np.sqrt(len(e)))
        check(
            f"{sym}: gross return is not distinguishable from exposure-scaled market (|t|<3)",
            abs(t_edge) < 3.0,
            f"mean log edge {e.mean():+.4f} over {len(e)} seeds, t={t_edge:.2f}, "
            f"market open-to-open log return {mkt_oo_total:.4f}",
        )
        d = np.array(drags)
        check(
            f"{sym}: realised cost drag equals n x 0.35% exactly, every seed",
            np.abs(d).max() < 1e-8,
            f"max deviation {np.abs(d).max():.3e}",
        )


def _check_no_fill_on_nontradeable(check) -> None:
    """The frozen spec's "no fill on price-band-locked days". A desired position
    change landing on a non-tradeable day must be deferred, not filled."""
    print("\n--- Check 4: no fill on non-tradeable days ---")
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    df = pd.DataFrame({
        "AdjOpen":  [100.0, 101.0, 102.0, 102.0, 103.0, 104.0],
        "AdjHigh":  [100.0, 101.0, 102.0, 102.0, 103.0, 104.0],
        "AdjLow":   [100.0, 101.0, 102.0, 102.0, 103.0, 104.0],
        "AdjClose": [100.0, 101.0, 102.0, 102.0, 103.0, 104.0],
        "Tradeable": [True, True, True, False, True, True],
    }, index=idx)
    # Signal turns on at t=2, so the desired fill lands on t=3, which is not tradeable.
    sig = pd.Series([0, 0, 1, 1, 1, 0], index=idx)
    res = backtest_signal(df, sig)
    pos = res["position"].to_list()
    check("position stays flat on the non-tradeable day (fill deferred)",
          pos[3] == 0, f"position path {pos}")
    check("position fills on the next tradeable day instead",
          pos[4] == 1, f"position path {pos}")
    check("exactly one round trip results", res["n_round_trips"] == 1,
          f"trips {res['n_round_trips']}")


def _check_holdout_sealed(check) -> None:
    print("\n--- Check 5: the April-2025 holdout is sealed by default ---")
    df = load_clean(PILOT_SYMBOLS[0])
    check("load_clean() returns no rows on/after 2025-04-01 by default",
          df.index.max() < HOLDOUT_START,
          f"max date {df.index.max()}")
    df_open = load_clean(PILOT_SYMBOLS[0], allow_holdout=True)
    check("allow_holdout=True does expose later rows (Phase 9 path exists)",
          df_open.index.max() >= HOLDOUT_START,
          f"max date {df_open.index.max()}")


def _selftest(symbols: Optional[Sequence[str]] = None) -> int:
    symbols = list(symbols or PILOT_SYMBOLS)
    n_pass, n_fail = 0, 0
    failures: List[str] = []

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
    print("04_backtest.py -- Phase 2.2 checkpoint self-test (REAL data, dev window only)")
    print("=" * 78)

    _check_buy_and_hold_identity(check, symbols)
    _check_buy_and_hold_matches_index(check)
    _check_cost_identity(check, symbols)
    _check_random_loses_the_costs(check, symbols[:4])
    _check_no_gap_leak(check)
    _check_no_fill_on_nontradeable(check)
    _check_holdout_sealed(check)

    print("\n" + "-" * 78)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest(sys.argv[1:] or None))
