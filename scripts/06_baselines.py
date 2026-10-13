"""
06_baselines.py -- Phase 2.4: the baselines. "These are the numbers to beat."

Runs buy-and-hold, time-series momentum, a plain RSI rule and a MACD rule through the
Phase 2.2 engine (04_backtest.backtest_signal), on the 8 pilot symbols, on the
development window only (2015-01-01 .. 2025-03-31). The April-2025 holdout stays
sealed.

Every rule is computed from information through Close[t] and executed at Open[t+1] by
the engine. `_check_causality` proves that directly: each indicator recomputed on data
truncated at an arbitrary date must equal the value it had in the full series. That is
checkpoint 3.2's leak test, applied early here because a baseline with lookahead would
set a target that no honest model could ever beat.

Indicator note: RSI and MACD are implemented here with pandas EWM (Wilder-style
alpha=1/n for RSI). They have NOT yet been validated against TA-Lib -- that is
checkpoint 3.1 and has not run. Treat the exact baseline numbers as provisional to
within indicator-implementation differences; the engine, costs and execution are what
51/51 verified in 2.2.

TWO KINDS OF NUMBER ARE REPORTED, because the project's success criterion is "beat the
base paper on accuracy OR alpha":
  1. Trading performance after costs: CAGR, Sharpe, max drawdown, alpha vs NIFTY100.
  2. Classification performance against the Phase 2.1 triple-barrier labels: how often
     a rule's long call coincides with an actual 'Up' label, against the Up base rate.
     A long/flat rule is a two-class (Up vs not-Up) predictor, so this is precision and
     lift, not 3-class accuracy. The eventual model is 3-class; these are the floor for
     the Up class only, and that difference must not be glossed over when the paper
     compares them.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase2"
LABELS_DIR = ROOT / "data" / "labels"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("04_backtest")

PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
COST_PCT = bt.COST_PCT
DEV_END = "2025-03-31"
TRADING_DAYS = 252


# ======================================================================================
# Indicators -- all strictly causal (value at t uses only data up to and including t)
# ======================================================================================

def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # avg_loss == 0 with positive gains is RSI 100 by definition, not NaN.
    out = out.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    return out


def macd_lines(close: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    ema_f = close.ewm(span=fast, adjust=False, min_periods=slow).mean()
    ema_s = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    line = ema_f - ema_s
    signal = line.ewm(span=sig, adjust=False, min_periods=slow + sig).mean()
    return line, signal


# ======================================================================================
# Baseline signals. Each returns a 0/1 series decided using info through Close[t].
# ======================================================================================

def sig_buy_and_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1, index=df.index)


def sig_momentum(df: pd.DataFrame, lookback: int = 252) -> pd.Series:
    """Classic time-series momentum: long while the trailing 12-month return is
    positive, otherwise cash."""
    c = df["AdjClose"]
    mom = c / c.shift(lookback) - 1.0
    return (mom > 0).astype(int).where(mom.notna(), 0).astype(int)


def sig_rsi_rule(df: pd.DataFrame, window: int = 14,
                 entry: float = 30.0, exit_: float = 50.0) -> pd.Series:
    """Plain textbook RSI rule: go long when RSI(14) drops below 30, hold until it
    recovers above 50. Implemented as an explicit state machine because the rule is
    path-dependent -- a vectorised `RSI < 30` would be a different (and much
    worse-behaved) strategy."""
    r = rsi(df["AdjClose"], window)
    out = np.zeros(len(df), dtype=int)
    state = 0
    vals = r.to_numpy()
    for i, v in enumerate(vals):
        if not np.isfinite(v):
            out[i] = 0
            state = 0
            continue
        if state == 0 and v < entry:
            state = 1
        elif state == 1 and v > exit_:
            state = 0
        out[i] = state
    return pd.Series(out, index=df.index)


def sig_macd_rule(df: pd.DataFrame) -> pd.Series:
    """Plain MACD rule: long while the MACD line is above its signal line."""
    line, signal = macd_lines(df["AdjClose"])
    ok = line.notna() & signal.notna()
    return ((line > signal) & ok).astype(int)


BASELINES: Dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "buy_and_hold": sig_buy_and_hold,
    "momentum_252d": sig_momentum,
    "rsi_14_30_50": sig_rsi_rule,
    "macd_12_26_9": sig_macd_rule,
}


# ======================================================================================
# Causality / leak test (checkpoint 3.2's rule, applied to the baselines)
# ======================================================================================

def _check_causality(check, symbols: Sequence[str]) -> None:
    print("\n--- Leak test: indicators computed on truncated data equal the full-series "
          "values ---")
    for sym in symbols[:4]:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        cut = len(df) // 2
        head = df.iloc[:cut]
        for name, fn in BASELINES.items():
            full = fn(df).iloc[:cut]
            trunc = fn(head)
            same = bool((full.to_numpy() == trunc.to_numpy()).all())
            check(f"{sym}/{name}: signal on data truncated at {head.index[-1].date()} "
                  f"equals the full-series signal",
                  same,
                  f"{int((full.to_numpy() != trunc.to_numpy()).sum())} of {cut} values differ")


# ======================================================================================
# Classification scoring against the Phase 2.1 labels
# ======================================================================================

def label_scores(symbol: str, signal: pd.Series) -> dict:
    """How often does a long call coincide with an actual 'Up' triple-barrier label?

    The signal at t is a call about the next 10 sessions, and the label at t is the
    outcome of those same 10 sessions, so they are aligned on t with no shift.
    """
    p = LABELS_DIR / f"{symbol}.csv"
    if not p.is_file():
        return {}
    lab = pd.read_csv(p)
    lab["date"] = pd.to_datetime(lab["date"]).dt.normalize()
    lab = lab.loc[lab["dropped_reason"].isna() & lab["label"].notna()]
    lab = lab.loc[lab["date"] <= pd.Timestamp(DEV_END)].set_index("date")

    s = signal.reindex(lab.index).dropna()
    y = lab.loc[s.index, "label"]
    if len(s) == 0:
        return {}
    is_up = (y == "Up")
    long_calls = (s == 1)
    n_long = int(long_calls.sum())
    base_rate = float(is_up.mean())
    precision = float(is_up[long_calls].mean()) if n_long else float("nan")
    recall = float(long_calls[is_up].mean()) if int(is_up.sum()) else float("nan")
    # Down-avoidance: a long-only system also wants to be flat before Down labels.
    down_rate_when_long = float((y[long_calls] == "Down").mean()) if n_long else float("nan")
    return {
        "n_labels": int(len(s)),
        "n_long_calls": n_long,
        "up_base_rate": base_rate,
        "up_precision": precision,
        "up_lift": (precision / base_rate) if (base_rate > 0 and np.isfinite(precision)) else float("nan"),
        "up_recall": recall,
        "down_rate_when_long": down_rate_when_long,
    }


# ======================================================================================
# Alpha vs the benchmark
# ======================================================================================

def alpha_beta(strategy_daily: pd.Series, bench_daily: pd.Series) -> dict:
    """Daily OLS of strategy excess return on benchmark return. Risk-free is taken as
    zero -- an assumption, stated: an Indian risk-free rate series has not been loaded,
    and a non-zero rf would lower both alphas roughly equally."""
    a = pd.concat([strategy_daily, bench_daily], axis=1).dropna()
    a.columns = ["s", "b"]
    if len(a) < 100:
        return {}
    x = a["b"].to_numpy()
    y = a["s"].to_numpy()
    beta, intercept = np.polyfit(x, y, 1)
    resid = y - (intercept + beta * x)
    se = float(np.std(resid, ddof=2) / (np.sqrt(len(x)) * np.std(x, ddof=1))) if np.std(x, ddof=1) > 0 else float("nan")
    return {
        "beta": float(beta),
        "alpha_daily": float(intercept),
        "alpha_annual": float(intercept * TRADING_DAYS),
        "alpha_t_stat": float(intercept / (np.std(resid, ddof=2) / np.sqrt(len(x)))) if len(x) > 2 else float("nan"),
        "beta_se": se,
    }


# ======================================================================================
# Run
# ======================================================================================

def run(symbols: Optional[Sequence[str]] = None) -> dict:
    symbols = list(symbols or PILOT_SYMBOLS)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    bench_df = bt.dev_window(bt.load_clean(BENCHMARK), end=DEV_END)
    bench_bh = bt.buy_and_hold(bench_df)
    bench_daily = bench_bh["daily_net"]

    rows: List[dict] = []
    curves: Dict[str, pd.Series] = {}
    per_strategy_daily: Dict[str, List[pd.Series]] = {k: [] for k in BASELINES}

    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        for name, fn in BASELINES.items():
            sig = fn(df)
            res = bt.backtest_signal(df, sig, cost_pct=COST_PCT)
            m = res["metrics"]
            ab = alpha_beta(res["daily_net"], bench_daily)
            ls = label_scores(sym, sig)
            rows.append({
                "symbol": sym, "strategy": name,
                "start": str(df.index[0].date()), "end": str(df.index[-1].date()),
                "gross_return": res["gross_return"], "net_return": res["net_return"],
                "cagr": m.get("cagr"), "ann_vol": m.get("ann_vol"),
                "sharpe": m.get("sharpe"), "max_drawdown": m.get("max_drawdown"),
                "exposure": res["exposure"], "n_round_trips": res["n_round_trips"],
                "cost_drag": res["gross_return"] - res["net_return"],
                **{f"{k}": v for k, v in ab.items()},
                **ls,
            })
            per_strategy_daily[name].append(res["daily_net"].rename(sym))
            curves[f"{sym}|{name}"] = res["equity"]

    # Equal-weight, daily-rebalanced portfolio per strategy across the 8 symbols.
    port_rows = []
    port_curves: Dict[str, pd.Series] = {}
    for name, series_list in per_strategy_daily.items():
        panel = pd.concat(series_list, axis=1)
        pr = panel.mean(axis=1)
        eq = (1.0 + pr).cumprod()
        m = bt.performance_metrics(eq)
        ab = alpha_beta(pr, bench_daily)
        port_rows.append({
            "strategy": name, "net_return": float(eq.iloc[-1] - 1.0),
            "cagr": m.get("cagr"), "ann_vol": m.get("ann_vol"),
            "sharpe": m.get("sharpe"), "max_drawdown": m.get("max_drawdown"),
            **ab,
        })
        port_curves[name] = eq

    bm = bench_bh["metrics"]
    port_rows.append({
        "strategy": "NIFTY100_buy_and_hold", "net_return": bench_bh["net_return"],
        "cagr": bm.get("cagr"), "ann_vol": bm.get("ann_vol"),
        "sharpe": bm.get("sharpe"), "max_drawdown": bm.get("max_drawdown"),
        "beta": 1.0, "alpha_daily": 0.0, "alpha_annual": 0.0,
    })
    port_curves["NIFTY100_buy_and_hold"] = bench_bh["equity"]

    per_sym = pd.DataFrame(rows)
    port = pd.DataFrame(port_rows)
    per_sym.to_csv(REPORTS_DIR / "checkpoint_2_4_baselines_per_symbol.csv", index=False)
    port.to_csv(REPORTS_DIR / "checkpoint_2_4_baselines_portfolio.csv", index=False)

    # Equity curves, monthly-sampled, for the dashboard.
    cdf = pd.DataFrame(port_curves)
    cdf.index.name = "date"
    cdf.resample("ME").last().to_csv(REPORTS_DIR / "checkpoint_2_4_equity_curves_monthly.csv")

    return {"per_symbol": per_sym, "portfolio": port, "curves": cdf}


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
    print("06_baselines.py -- Phase 2.4: the numbers to beat (dev window only)")
    print("=" * 78)

    _check_causality(check, symbols)

    out = run(symbols)
    port, per_sym = out["portfolio"], out["per_symbol"]

    pd.set_option("display.width", 200)
    print("\n--- Equal-weight portfolio of the 8 pilot stocks, after 0.35%/round-trip costs ---")
    show = port[["strategy", "net_return", "cagr", "ann_vol", "sharpe",
                 "max_drawdown", "beta", "alpha_annual", "alpha_t_stat"]].copy()
    for c in ["net_return", "cagr", "ann_vol", "max_drawdown", "alpha_annual"]:
        show[c] = (show[c] * 100).round(2)
    show["sharpe"] = show["sharpe"].round(2)
    show["beta"] = show["beta"].round(2)
    show["alpha_t_stat"] = show["alpha_t_stat"].round(2)
    print(show.to_string(index=False))

    print("\n--- Classification floor: Up-class precision vs base rate (pooled) ---")
    cls = per_sym.groupby("strategy").apply(
        lambda g: pd.Series({
            "up_base_rate": (g["up_base_rate"] * g["n_labels"]).sum() / g["n_labels"].sum(),
            "up_precision": (g["up_precision"] * g["n_long_calls"]).sum() / g["n_long_calls"].sum(),
            "up_recall": (g["up_recall"] * g["n_labels"]).sum() / g["n_labels"].sum(),
            "down_rate_when_long": (g["down_rate_when_long"] * g["n_long_calls"]).sum() / g["n_long_calls"].sum(),
            "n_long_calls": g["n_long_calls"].sum(),
        }), include_groups=False
    ).reset_index()
    cls["up_lift"] = (cls["up_precision"] / cls["up_base_rate"]).round(3)
    for c in ["up_base_rate", "up_precision", "up_recall", "down_rate_when_long"]:
        cls[c] = (cls[c] * 100).round(2)
    print(cls.to_string(index=False))

    # Sanity assertions on the baselines themselves.
    bh = port.loc[port["strategy"] == "buy_and_hold"].iloc[0]
    check("portfolio buy-and-hold has ~full exposure and a positive CAGR over 2015-2025",
          bh["cagr"] > 0, f"CAGR {bh['cagr']:.4f}")
    for name in ["momentum_252d", "rsi_14_30_50", "macd_12_26_9"]:
        r = port.loc[port["strategy"] == name].iloc[0]
        check(f"{name}: produced a finite, costed result",
              np.isfinite(r["cagr"]) and np.isfinite(r["sharpe"]),
              f"cagr {r['cagr']}, sharpe {r['sharpe']}")
    tot_trips = per_sym.loc[per_sym["strategy"] != "buy_and_hold", "n_round_trips"].sum()
    check("the rule baselines actually traded (so their costs are real)",
          tot_trips > 100, f"{tot_trips} round trips")
    check("no baseline result extends past the sealed holdout boundary",
          (per_sym["end"] <= "2025-03-31").all(), f"max end {per_sym['end'].max()}")

    print(f"\nwrote reports/phase2/checkpoint_2_4_baselines_per_symbol.csv")
    print(f"wrote reports/phase2/checkpoint_2_4_baselines_portfolio.csv")
    print(f"wrote reports/phase2/checkpoint_2_4_equity_curves_monthly.csv")
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
