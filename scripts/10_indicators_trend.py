"""
10_indicators_trend.py -- Phase 3, trend/moving-average family (EMA crossover, ADX,
MACD -- MACD already exists as a baseline in 06_baselines.py and is re-exposed here
only as a vote column, not recomputed as a second implementation).

Same structure and checkpoints as 09_indicators_momentum.py -- see that module's
docstring for the full rationale; this one states only what differs.

Checkpoint 3.1: ADX and EMA are taken directly from TA-Lib (no second implementation --
stated assumption, same as Stochastic/CCI/Williams %R in the momentum module). MACD is
cross-checked against 06_baselines.macd_lines, which is itself pandas EWM (span-based,
not Wilder) -- the two MACD forms use a different EMA convention (span vs TA-Lib's
default EMA), so they are expected to be close but not identical; the check uses a
correlation threshold, not exact equality, and that choice is stated rather than hidden.

Checkpoint 3.2: leak test via truncation, same method.

Checkpoint 3.3: EMA-crossover and ADX-filtered-trend rules through the engine on the 8
pilot symbols, dev window. MACD's own rule (macd_12_26_9) was already gated in
06_baselines.py (Sharpe 0.84) -- not re-run here, just referenced.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import talib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase3"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("04_backtest")
bl = _load("06_baselines")

PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
COST_PCT = bt.COST_PCT
DEV_END = bl.DEV_END

EMA_FAST, EMA_SLOW = 20, 50
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25.0


def compute_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
    h, l, c = (df["AdjHigh"].to_numpy(dtype=float), df["AdjLow"].to_numpy(dtype=float),
               df["AdjClose"].to_numpy(dtype=float))
    ema_fast = talib.EMA(c, timeperiod=EMA_FAST)
    ema_slow = talib.EMA(c, timeperiod=EMA_SLOW)
    adx = talib.ADX(h, l, c, timeperiod=ADX_PERIOD)
    macd_line, macd_signal = bl.macd_lines(df["AdjClose"])
    return pd.DataFrame({
        "ema20": ema_fast, "ema50": ema_slow, "adx14": adx,
        "macd_line": macd_line.to_numpy(), "macd_signal": macd_signal.to_numpy(),
    }, index=df.index)


def votes(ind: pd.DataFrame) -> pd.DataFrame:
    v = pd.DataFrame(index=ind.index)
    v["vote_ema_cross"] = np.select(
        [ind["ema20"] > ind["ema50"], ind["ema20"] < ind["ema50"]], [1, -1], default=0)
    v.loc[ind["ema20"].isna() | ind["ema50"].isna(), "vote_ema_cross"] = 0
    v["vote_adx_trending"] = (ind["adx14"] > ADX_TREND_THRESHOLD).astype(int)
    v.loc[ind["adx14"].isna(), "vote_adx_trending"] = 0
    v["vote_macd"] = np.select(
        [ind["macd_line"] > ind["macd_signal"], ind["macd_line"] < ind["macd_signal"]], [1, -1], default=0)
    v.loc[ind["macd_line"].isna() | ind["macd_signal"].isna(), "vote_macd"] = 0
    return v


def sig_ema_cross(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """Long while the fast EMA is above the slow EMA -- classic trend-following, no
    path-dependent state needed (the crossover itself is the state)."""
    cond = (ind["ema20"] > ind["ema50"]) & ind["ema20"].notna() & ind["ema50"].notna()
    return cond.astype(int)


def sig_ema_cross_adx_filtered(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """EMA crossover, but only acted on while ADX says the market is actually trending
    (ADX > 25) -- the textbook fix for whipsaw in chop."""
    cond = ((ind["ema20"] > ind["ema50"]) & (ind["adx14"] > ADX_TREND_THRESHOLD)
            & ind["ema20"].notna() & ind["ema50"].notna() & ind["adx14"].notna())
    return cond.astype(int)


FAMILY_SIGNALS = {
    "trend_ema_20_50": sig_ema_cross,
    "trend_ema_20_50_adx_filtered": sig_ema_cross_adx_filtered,
}


def _check_crosscheck_macd(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.1: MACD cross-check (talib MACD vs 06_baselines.macd_lines "
          "-- different EMA convention, so checked by correlation not equality) ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        c = df["AdjClose"].to_numpy(dtype=float)
        talib_line, talib_signal, _ = talib.MACD(c, fastperiod=12, slowperiod=26, signalperiod=9)
        base_line, base_signal = bl.macd_lines(df["AdjClose"])
        both = np.isfinite(talib_line) & np.isfinite(base_line.to_numpy())
        corr = float(np.corrcoef(talib_line[both], base_line.to_numpy()[both])[0, 1]) if both.sum() > 30 else float("nan")
        check(f"{sym}: TA-Lib MACD line and pandas-EWM MACD line correlate >0.98 (both causal, different EMA seed)",
              np.isfinite(corr) and corr > 0.98, f"corr {corr:.4f}")
    print("EMA20/EMA50/ADX14 are used directly from TA-Lib -- stated assumption, not "
          "independently re-derived here.")


def _check_leak(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.2: leak test ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        full = compute_trend_indicators(df)
        cut = len(df) // 2
        head = df.iloc[:cut]
        trunc = compute_trend_indicators(head)
        for col in full.columns:
            a = full[col].iloc[:cut].to_numpy()
            b = trunc[col].to_numpy()
            both_finite = np.isfinite(a) & np.isfinite(b)
            same = bool(np.allclose(a[both_finite], b[both_finite])) if both_finite.any() else True
            n_bad = int((~np.isclose(a[both_finite], b[both_finite])).sum()) if both_finite.any() else 0
            check(f"{sym}/{col}: value at truncation point unaffected by later data",
                  same, f"{n_bad} of {int(both_finite.sum())} overlapping values differ")


def run_family_gate(symbols: Optional[Sequence[str]] = None) -> dict:
    symbols = list(symbols or PILOT_SYMBOLS)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    bench_df = bt.dev_window(bt.load_clean(BENCHMARK), end=DEV_END)
    bench_daily = bt.buy_and_hold(bench_df)["daily_net"]

    rows: List[dict] = []
    vote_frames: List[pd.DataFrame] = []
    per_strategy_daily: Dict[str, List[pd.Series]] = {k: [] for k in FAMILY_SIGNALS}

    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        ind = compute_trend_indicators(df)
        v = votes(ind)
        v.insert(0, "symbol", sym)
        v.insert(0, "date", df.index)
        vote_frames.append(v.reset_index(drop=True))

        for name, fn in FAMILY_SIGNALS.items():
            sig = fn(df, ind)
            res = bt.backtest_signal(df, sig, cost_pct=COST_PCT)
            m = res["metrics"]
            ab = bl.alpha_beta(res["daily_net"], bench_daily)
            ls = bl.label_scores(sym, sig)
            rows.append({
                "symbol": sym, "strategy": name,
                "gross_return": res["gross_return"], "net_return": res["net_return"],
                "cagr": m.get("cagr"), "ann_vol": m.get("ann_vol"), "sharpe": m.get("sharpe"),
                "max_drawdown": m.get("max_drawdown"), "exposure": res["exposure"],
                "n_round_trips": res["n_round_trips"],
                "cost_drag": res["gross_return"] - res["net_return"],
                **{k: v2 for k, v2 in ab.items()}, **ls,
            })
            per_strategy_daily[name].append(res["daily_net"].rename(sym))

    port_rows = []
    for name, series_list in per_strategy_daily.items():
        panel = pd.concat(series_list, axis=1)
        pr = panel.mean(axis=1)
        eq = (1.0 + pr).cumprod()
        m = bt.performance_metrics(eq)
        ab = bl.alpha_beta(pr, bench_daily)
        port_rows.append({"strategy": name, "net_return": float(eq.iloc[-1] - 1.0),
                           "cagr": m.get("cagr"), "ann_vol": m.get("ann_vol"),
                           "sharpe": m.get("sharpe"), "max_drawdown": m.get("max_drawdown"),
                           **ab})

    per_sym = pd.DataFrame(rows)
    port = pd.DataFrame(port_rows)
    all_votes = pd.concat(vote_frames, ignore_index=True)
    per_sym.to_csv(REPORTS_DIR / "checkpoint_3_1_3_trend_per_symbol.csv", index=False)
    port.to_csv(REPORTS_DIR / "checkpoint_3_3_trend_portfolio.csv", index=False)
    all_votes.to_csv(REPORTS_DIR / "trend_votes.csv", index=False)
    return {"per_symbol": per_sym, "portfolio": port, "votes": all_votes}


def _selftest(symbols: Optional[Sequence[str]] = None) -> int:
    symbols = list(symbols or PILOT_SYMBOLS)
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
    print("10_indicators_trend.py -- Phase 3: trend/moving-average family")
    print("=" * 78)

    _check_crosscheck_macd(check, symbols)
    _check_leak(check, symbols)

    out = run_family_gate(symbols)
    port, per_sym = out["portfolio"], out["per_symbol"]

    pd.set_option("display.width", 200)
    print("\n--- Standalone family gate: equal-weight portfolio of the 8 pilot stocks, "
          "after costs (checkpoint 3.3) ---")
    show = port[["strategy", "net_return", "cagr", "ann_vol", "sharpe", "max_drawdown",
                 "beta", "alpha_annual", "alpha_t_stat"]].copy()
    for c in ["net_return", "cagr", "ann_vol", "max_drawdown", "alpha_annual"]:
        show[c] = (show[c] * 100).round(2)
    show["sharpe"] = show["sharpe"].round(2)
    show["beta"] = show["beta"].round(2)
    show["alpha_t_stat"] = show["alpha_t_stat"].round(2)
    print(show.to_string(index=False))
    print("\n(Compare against 06_baselines on the swapped 8-symbol pilot (8 Oct 2026): "
          "buy_and_hold Sharpe 1.02, momentum_252d 0.84, macd_12_26_9 0.47 -- macd_12_26_9 "
          "is this family's third member, already gated.)")

    for name in FAMILY_SIGNALS:
        r = port.loc[port["strategy"] == name].iloc[0]
        check(f"{name}: produced a finite, costed result",
              np.isfinite(r["cagr"]) and np.isfinite(r["sharpe"]),
              f"cagr {r['cagr']}, sharpe {r['sharpe']}")
    tot_trips = per_sym.loc[:, "n_round_trips"].sum()
    check("the family's rules actually traded (so their costs are real)",
          tot_trips > 100, f"{tot_trips} round trips")

    print(f"\nwrote reports/phase3/checkpoint_3_1_3_trend_per_symbol.csv")
    print(f"wrote reports/phase3/checkpoint_3_3_trend_portfolio.csv")
    print(f"wrote reports/phase3/trend_votes.csv")
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
