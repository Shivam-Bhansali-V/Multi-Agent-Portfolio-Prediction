"""
27_rsi_ema_grid.py -- Phase 3.10: the RSI-period / EMA-period grid, scored on the
user's own success metric, with the overfitting gap measured and shown.

THE USER'S METRIC (new, and better than what I was using before): "at least my model
should give better profit MOST OF THE TIMES than the whole-year return of that
specific stock." Implemented literally:
    for every (stock, calendar year) pair in the dev window:
        strategy return for that stock that year   vs   that stock's own return that year
    win_rate = share of those stock-years the strategy won
8 stocks x ~10 years = ~80 stock-years, so this is a far bigger sample of "did it
help" than one portfolio Sharpe number, and it is the thing the user actually asked
for. Portfolio Sharpe/CAGR are still reported alongside, because win_rate alone can
mislead (see the caveat below).

CAVEAT ON THIS METRIC, STATED UP FRONT so no one reads the headline number wrongly:
in a year when a stock FALLS, simply sitting in cash beats it. So a strategy that is
mostly in cash wins most down-years automatically while losing most up-years. A high
win_rate is therefore NOT the same as making money. That is why this script also
reports, for every combination:
    - mean and median ANNUAL EXCESS return (strategy minus buy-and-hold, per stock-year)
    - the share of stock-years where the stock itself was UP (the context: if 70% of
      stock-years were positive, a cash-heavy rule's win_rate is capped near 30%)
    - portfolio CAGR and Sharpe
A combination is only genuinely good if win_rate > 50% AND mean annual excess >= 0.

GRID (108 combinations): RSI period {7, 14, 20} x EMA period {14, 20} x entry level
{55, 60, 65} x exit floor {20, 30, 40} x EMA-confirmation-on-entry {off, on}.

OVERFITTING, MEASURED RATHER THAN WARNED ABOUT -- the user explicitly asked to see
how much an overfitted model gives. Two numbers are reported for the same grid:
  1. OVERFITTED: the best combination chosen using the WHOLE dev window, and its score
     on that same whole window. This is the number that would be reported by anyone
     who tunes on all their data -- it is inflated by construction and labelled as
     such. It is the headline "look how good it is" figure, and it is not trustworthy.
  2. HONEST (walk-forward): pick the best combination using 2015-2020 ONLY, then score
     that same combination on 2021-2025, which was never used to choose it.
The difference between those two IS the overfitting, quantified in the units the user
cares about (win_rate and annual excess return), not in abstract terms.

COSTS: 0% leads (as asked), frozen-spec 0.35% beside it in the same row. 0.25pp of
that 0.35 is non-optional verified brokerage/STT/exchange charges, so 0% is a
diagnostic, not an achievable account result. Both shown; neither hidden.
"""

from __future__ import annotations

import importlib.util as _ilu
import itertools
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

PILOT_SYMBOLS = bt.PILOT_SYMBOLS
SPEC_COST = bt.COST_PCT
ZERO_COST = 0.0
DEV_START, DEV_END = "2015-01-01", "2025-03-31"
SELECT_END = "2020-12-31"
TEST_START = "2021-01-01"

RSI_PERIODS = [7, 14, 20]
EMA_PERIODS = [14, 20]
ENTRY_LEVELS = [55.0, 60.0, 65.0]
EXIT_FLOORS = [20.0, 30.0, 40.0]
EMA_CONFIRM = [False, True]


# ======================================================================================
# Cached data + indicators (the grid touches 8 symbols x 108 combos; reloading CSVs or
# recomputing TA-Lib per combination would dominate the runtime for no reason)
# ======================================================================================

_PRICE_CACHE: Dict[str, pd.DataFrame] = {}
_IND_CACHE: Dict[Tuple[str, int, int], pd.DataFrame] = {}


def price_frame(symbol: str) -> pd.DataFrame:
    if symbol not in _PRICE_CACHE:
        _PRICE_CACHE[symbol] = bt.dev_window(bt.load_clean(symbol), start=DEV_START, end=DEV_END)
    return _PRICE_CACHE[symbol]


def indicators(symbol: str, rsi_period: int, ema_period: int) -> pd.DataFrame:
    key = (symbol, rsi_period, ema_period)
    if key not in _IND_CACHE:
        df = price_frame(symbol)
        c = df["AdjClose"].to_numpy(dtype=float)
        out = pd.DataFrame(index=df.index)
        out["rsi"] = talib.RSI(c, timeperiod=rsi_period)
        out["ema"] = talib.EMA(c, timeperiod=ema_period)
        _IND_CACHE[key] = out
    return _IND_CACHE[key]


def build_signal(df: pd.DataFrame, ind: pd.DataFrame, entry_level: float,
                  exit_floor: float, ema_confirm: bool) -> pd.Series:
    """Entry: RSI > entry_level (and, if ema_confirm, Close > EMA). Exit: RSI < exit_floor.
    Hysteresis state machine -- the position is HELD through the middle band rather than
    flipping on every threshold touch, which is the whole point of the range framing."""
    rsi = ind["rsi"].to_numpy(dtype=float)
    ema = ind["ema"].to_numpy(dtype=float)
    close = df["AdjClose"].to_numpy(dtype=float)
    n = len(rsi)
    out = np.zeros(n, dtype=int)
    state = 0
    for i in range(n):
        r = rsi[i]
        if not np.isfinite(r):
            out[i], state = 0, 0
            continue
        if state == 0:
            enter = r > entry_level
            if enter and ema_confirm:
                enter = bool(np.isfinite(ema[i]) and close[i] > ema[i])
            if enter:
                state = 1
        else:
            if r < exit_floor:
                state = 0
        out[i] = state
    return pd.Series(out, index=df.index)


# ======================================================================================
# Scoring on the user's metric
# ======================================================================================

_BH_CACHE: Dict[Tuple[str, float, str, str], pd.Series] = {}


def _buyhold_daily(sym: str, df: pd.DataFrame, cost_pct: float, start: str, end: str) -> pd.Series:
    """Buy-and-hold for a symbol/window/cost is identical across every grid combination,
    so it is computed once and reused -- the grid calls this 108 times per symbol."""
    key = (sym, cost_pct, start, end)
    if key not in _BH_CACHE:
        _BH_CACHE[key] = bt.buy_and_hold(df, cost_pct=cost_pct)["daily_net"]
    return _BH_CACHE[key]


def score(params: dict, cost_pct: float, start: str, end: str) -> dict:
    """Runs each symbol's backtest ONCE and derives both the per-stock-year table and
    the portfolio metrics from the same daily series (an earlier version ran every
    backtest twice, which doubled the grid's runtime for no benefit)."""
    rows, daily = [], []
    for sym in PILOT_SYMBOLS:
        full_df = price_frame(sym)
        df = full_df.loc[(full_df.index >= pd.Timestamp(start)) & (full_df.index <= pd.Timestamp(end))]
        if len(df) < 60:
            continue
        ind = indicators(sym, params["rsi_period"], params["ema_period"]).reindex(df.index)
        sig = build_signal(df, ind, params["entry_level"], params["exit_floor"], params["ema_confirm"])
        strat = bt.backtest_signal(df, sig, cost_pct=cost_pct)["daily_net"]
        bh = _buyhold_daily(sym, df, cost_pct, start, end)
        daily.append(strat.rename(sym))
        for year, idx in strat.groupby(strat.index.year).groups.items():
            s_ret = float((1.0 + strat.loc[idx]).prod() - 1.0)
            b_ret = float((1.0 + bh.loc[idx]).prod() - 1.0)
            rows.append({"symbol": sym, "year": int(year), "strategy_return": s_ret,
                          "buyhold_return": b_ret, "excess": s_ret - b_ret,
                          "won": s_ret > b_ret, "stock_was_up": b_ret > 0})
    ann = pd.DataFrame(rows)
    if ann.empty:
        return {}
    port = pd.concat(daily, axis=1).mean(axis=1)
    m = bt.performance_metrics((1.0 + port).cumprod())
    return {
        "win_rate": float(ann["won"].mean()),
        "n_stock_years": int(len(ann)),
        "mean_excess": float(ann["excess"].mean()),
        "median_excess": float(ann["excess"].median()),
        "pct_stock_years_up": float(ann["stock_was_up"].mean()),
        "win_rate_up_years": float(ann.loc[ann["stock_was_up"], "won"].mean()) if ann["stock_was_up"].any() else float("nan"),
        "win_rate_down_years": float(ann.loc[~ann["stock_was_up"], "won"].mean()) if (~ann["stock_was_up"]).any() else float("nan"),
        "portfolio_cagr": m.get("cagr"), "portfolio_sharpe": m.get("sharpe"),
        "portfolio_max_dd": m.get("max_drawdown"),
    }


def grid_params() -> List[dict]:
    out = []
    for rp, ep, en, ex, ec in itertools.product(RSI_PERIODS, EMA_PERIODS, ENTRY_LEVELS,
                                                  EXIT_FLOORS, EMA_CONFIRM):
        out.append({"rsi_period": rp, "ema_period": ep, "entry_level": en,
                     "exit_floor": ex, "ema_confirm": ec})
    return out


def label(p: dict) -> str:
    return (f"RSI{p['rsi_period']} EMA{p['ema_period']} in>{int(p['entry_level'])} "
            f"out<{int(p['exit_floor'])} {'EMAconf' if p['ema_confirm'] else 'noEMAconf'}")


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

    print("=" * 120)
    print("27_rsi_ema_grid.py -- Phase 3.10: RSI period x EMA period grid, scored on "
          "'beats the stock's own yearly return'")
    print("=" * 120)
    print("Metric: per (stock, calendar year), did the strategy beat THAT stock's own return "
          "that year?\nwin_rate = share of ~80 stock-years won. 0% costs lead; frozen-spec "
          "0.35% shown beside.\nIMPORTANT: in a DOWN year, sitting in cash wins automatically "
          "-- so win_rate alone is not profit.\nA combination is only good if win_rate > 50% "
          "AND mean annual excess >= 0. Both are shown.")

    params_list = grid_params()
    print(f"\nGrid size: {len(params_list)} combinations "
          f"({len(RSI_PERIODS)} RSI x {len(EMA_PERIODS)} EMA x {len(ENTRY_LEVELS)} entry x "
          f"{len(EXIT_FLOORS)} exit x {len(EMA_CONFIRM)} EMA-confirm)")

    # ---------- full-window scores (this is the OVERFITTED view) ----------
    rows = []
    for p in params_list:
        s0 = score(p, ZERO_COST, DEV_START, DEV_END)
        sS = score(p, SPEC_COST, DEV_START, DEV_END)
        rows.append({"combo": label(p), **{f"{k}": v for k, v in p.items()},
                      "win_rate_0pct": s0["win_rate"], "win_rate_spec": sS["win_rate"],
                      "mean_excess_0pct": s0["mean_excess"], "mean_excess_spec": sS["mean_excess"],
                      "median_excess_spec": sS["median_excess"],
                      "win_up_years_spec": sS["win_rate_up_years"],
                      "win_down_years_spec": sS["win_rate_down_years"],
                      "cagr_0pct": s0["portfolio_cagr"], "cagr_spec": sS["portfolio_cagr"],
                      "sharpe_0pct": s0["portfolio_sharpe"], "sharpe_spec": sS["portfolio_sharpe"],
                      "max_dd_spec": sS["portfolio_max_dd"],
                      "n_stock_years": sS["n_stock_years"],
                      "pct_stock_years_up": sS["pct_stock_years_up"]})
    full = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    full.to_csv(REPORTS_DIR / "checkpoint_3_10_rsi_ema_grid_full.csv", index=False)

    ctx_up = float(full["pct_stock_years_up"].iloc[0])
    print(f"\nCONTEXT: {ctx_up*100:.1f}% of the {int(full['n_stock_years'].iloc[0])} stock-years "
          f"in this window were POSITIVE for the stock itself.")
    print(f"So a strategy permanently in cash would win about {(1-ctx_up)*100:.1f}% of stock-years "
          f"while making nothing. Beat that AND make money, or it is not real.")

    pd.set_option("display.width", 320)
    cols = ["combo", "win_rate_spec", "mean_excess_spec", "win_up_years_spec",
            "win_down_years_spec", "cagr_spec", "sharpe_spec", "max_dd_spec",
            "win_rate_0pct", "cagr_0pct", "sharpe_0pct"]

    print(f"\n--- TOP 12 of {len(full)} combinations by win_rate (at frozen-spec 0.35% cost) ---")
    top_wr = full.sort_values("win_rate_spec", ascending=False).head(12)[cols].copy()
    for c in cols[1:]:
        top_wr[c] = top_wr[c].astype(float).round(4)
    print(top_wr.to_string(index=False))

    print(f"\n--- TOP 12 by MEAN ANNUAL EXCESS RETURN (strategy minus that stock's own year) ---")
    top_ex = full.sort_values("mean_excess_spec", ascending=False).head(12)[cols].copy()
    for c in cols[1:]:
        top_ex[c] = top_ex[c].astype(float).round(4)
    print(top_ex.to_string(index=False))

    print(f"\n--- Does the RSI PERIOD matter? (mean across all combos sharing that period) ---")
    by_rsi = full.groupby("rsi_period")[["win_rate_spec", "mean_excess_spec", "sharpe_spec",
                                           "cagr_spec"]].mean().round(4)
    print(by_rsi.to_string())
    print(f"\n--- Does the EMA PERIOD matter? ---")
    by_ema = full.groupby("ema_period")[["win_rate_spec", "mean_excess_spec", "sharpe_spec",
                                           "cagr_spec"]].mean().round(4)
    print(by_ema.to_string())
    print(f"\n--- Does EMA confirmation on entry help? ---")
    by_conf = full.groupby("ema_confirm")[["win_rate_spec", "mean_excess_spec", "sharpe_spec",
                                             "cagr_spec"]].mean().round(4)
    print(by_conf.to_string())
    print(f"\n--- Exit floor: the single biggest lever found in 3.9, re-confirmed here ---")
    by_exit = full.groupby("exit_floor")[["win_rate_spec", "mean_excess_spec", "sharpe_spec",
                                            "cagr_spec"]].mean().round(4)
    print(by_exit.to_string())

    # ---------- the overfitting measurement the user asked for ----------
    print("\n" + "=" * 120)
    print("HOW MUCH DOES THE OVERFITTED NUMBER FLATTER ITSELF? (the user's question, measured)")
    print("=" * 120)

    overfit_best = full.sort_values("win_rate_spec", ascending=False).iloc[0]
    print(f"\n[1] OVERFITTED -- best combo chosen on the WHOLE window, scored on that same window:")
    print(f"    {overfit_best['combo']}")
    print(f"    win_rate {float(overfit_best['win_rate_spec']):.4f} @0.35%  "
          f"({float(overfit_best['win_rate_0pct']):.4f} @0%),  mean annual excess "
          f"{float(overfit_best['mean_excess_spec']):+.4f},  CAGR "
          f"{float(overfit_best['cagr_spec']):.4f},  Sharpe {float(overfit_best['sharpe_spec']):.4f}")
    print(f"    ^ THIS NUMBER IS NOT TRUSTWORTHY. It is the best of {len(full)} tries measured on "
          f"the same data used to pick it.")

    sel_rows = []
    for p in params_list:
        s = score(p, SPEC_COST, DEV_START, SELECT_END)
        sel_rows.append({"combo": label(p), **p, "sel_win_rate": s["win_rate"],
                          "sel_mean_excess": s["mean_excess"]})
    sel = pd.DataFrame(sel_rows)
    wf_choice = sel.sort_values("sel_win_rate", ascending=False).iloc[0]
    wf_params = {k: wf_choice[k] for k in ("rsi_period", "ema_period", "entry_level",
                                             "exit_floor", "ema_confirm")}
    wf_params = {"rsi_period": int(wf_params["rsi_period"]), "ema_period": int(wf_params["ema_period"]),
                  "entry_level": float(wf_params["entry_level"]), "exit_floor": float(wf_params["exit_floor"]),
                  "ema_confirm": bool(wf_params["ema_confirm"])}
    wf_test = score(wf_params, SPEC_COST, TEST_START, DEV_END)
    wf_test0 = score(wf_params, ZERO_COST, TEST_START, DEV_END)

    print(f"\n[2] HONEST (walk-forward) -- combo chosen on {DEV_START}..{SELECT_END} only, then "
          f"scored on {TEST_START}..{DEV_END} which was never used to choose it:")
    print(f"    {label(wf_params)}")
    print(f"    selection-period win_rate: {float(wf_choice['sel_win_rate']):.4f}")
    print(f"    TEST-period win_rate:      {wf_test['win_rate']:.4f} @0.35%  "
          f"({wf_test0['win_rate']:.4f} @0%)")
    print(f"    TEST-period mean annual excess: {wf_test['mean_excess']:+.4f}  "
          f"(median {wf_test['median_excess']:+.4f})")
    print(f"    TEST-period CAGR {wf_test['portfolio_cagr']:.4f}, Sharpe "
          f"{wf_test['portfolio_sharpe']:.4f}, max DD {wf_test['portfolio_max_dd']:.4f}")

    gap_wr = float(overfit_best["win_rate_spec"]) - wf_test["win_rate"]
    gap_ex = float(overfit_best["mean_excess_spec"]) - wf_test["mean_excess"]
    print(f"\n[3] THE OVERFITTING GAP, in the units you care about:")
    print(f"    win_rate:            overfitted {float(overfit_best['win_rate_spec']):.4f}  ->  "
          f"honest {wf_test['win_rate']:.4f}   (inflated by {gap_wr:+.4f})")
    print(f"    mean annual excess:  overfitted {float(overfit_best['mean_excess_spec']):+.4f}  ->  "
          f"honest {wf_test['mean_excess']:+.4f}   (inflated by {gap_ex:+.4f})")
    print(f"    Median win_rate across ALL {len(full)} combos (no selection at all): "
          f"{float(full['win_rate_spec'].median()):.4f} -- compare to the 'best' above to see how "
          f"much of the best is just picking the luckiest of {len(full)}.")

    # ---------- verdicts ----------
    print("\n" + "=" * 120)
    print("VERDICTS")
    print("=" * 120)
    good = full.loc[(full["win_rate_spec"] > 0.5) & (full["mean_excess_spec"] >= 0)]
    print(f"Combinations clearing BOTH bars (win_rate > 50% AND mean annual excess >= 0) at real "
          f"cost: {len(good)} of {len(full)}")
    if len(good):
        g = good.sort_values("mean_excess_spec", ascending=False).head(5)[cols].copy()
        for c in cols[1:]:
            g[c] = g[c].astype(float).round(4)
        print(g.to_string(index=False))
    best_mean_ex = float(full["mean_excess_spec"].max())
    print(f"\nBest mean annual excess return of any combination, at real cost: {best_mean_ex:+.4f} "
          f"({best_mean_ex*100:+.2f} percentage points per stock-year)")

    check("the grid ran and produced a scored result for every combination",
          len(full) == len(params_list), f"{len(full)} of {len(params_list)}")
    check("the overfitting gap was measured by walk-forward selection rather than asserted",
          np.isfinite(gap_wr) and np.isfinite(gap_ex))
    check("at least one combination beats the stock's own yearly return MORE than half the time "
          "at real cost (the user's stated bar) -- reported either way",
          bool((full["win_rate_spec"] > 0.5).any()),
          f"best win_rate {float(full['win_rate_spec'].max()):.4f}")

    sel.to_csv(REPORTS_DIR / "checkpoint_3_10_selection_period_scores.csv", index=False)
    pd.DataFrame([{
        "view": "OVERFITTED (chosen and scored on whole window)", "combo": overfit_best["combo"],
        "win_rate": overfit_best["win_rate_spec"], "mean_excess": overfit_best["mean_excess_spec"],
        "cagr": overfit_best["cagr_spec"], "sharpe": overfit_best["sharpe_spec"],
    }, {
        "view": f"HONEST walk-forward (chosen {DEV_START}..{SELECT_END}, scored {TEST_START}..{DEV_END})",
        "combo": label(wf_params), "win_rate": wf_test["win_rate"],
        "mean_excess": wf_test["mean_excess"], "cagr": wf_test["portfolio_cagr"],
        "sharpe": wf_test["portfolio_sharpe"],
    }]).to_csv(REPORTS_DIR / "checkpoint_3_10_overfit_vs_honest.csv", index=False)

    print(f"\nwrote reports/phase3/checkpoint_3_10_rsi_ema_grid_full.csv ({len(full)} rows)")
    print(f"wrote reports/phase3/checkpoint_3_10_selection_period_scores.csv")
    print(f"wrote reports/phase3/checkpoint_3_10_overfit_vs_honest.csv")
    print("\n" + "-" * 120)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 120)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
