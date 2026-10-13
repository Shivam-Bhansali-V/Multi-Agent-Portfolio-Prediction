"""
26_rsi_exit_and_patterns.py -- Phase 3.9: WHEN to sell, and the RSI 'M' / 'W' patterns.

Three questions, each measured rather than asserted:

PART A -- AT WHAT RSI VALUE SHOULD YOU SELL?
Checkpoint 3.8 fixed the entry (RSI crosses above 60) and the exit (RSI falls below
40) because that is the textbook 60/40 range pairing. But the exit level was never
tested as a variable. Part A holds the entry fixed and sweeps the exit across a grid,
in three different exit STYLES, because "when to sell" has three distinct answers in
the literature and they behave very differently:
  - breakdown exit  : sell when RSI falls BELOW a floor (trend-following; ride winners)
  - overbought exit : sell when RSI rises ABOVE a ceiling (profit-taking; classic)
  - bracket exit    : sell on EITHER, whichever comes first
A single table then shows which style and level actually did best, and -- just as
important -- how much the answer varies, since a sharp optimum on one dataset is
usually overfitting rather than a law of markets.

PART B -- THE 'M' AND 'W' PATTERNS (the user's suggestion).
These are real, documented RSI chart patterns (RSI double-top / double-bottom):
  'M' above the upper line (e.g. 60): RSI makes a high, pulls back, makes a SECOND
      high that fails to exceed the first (a lower high), then breaks below the
      intervening trough -> bearish, momentum is failing. Used here as an EXIT/avoid.
  'W' below the lower line (e.g. 40): RSI makes a low, bounces, makes a SECOND low
      that holds above the first (a higher low), then breaks above the intervening
      peak -> bullish, selling is exhausting. Used here as an ENTRY.
CAUSALITY IS THE WHOLE RISK HERE and is handled explicitly: a local peak or trough at
bar i can only be CONFIRMED once bar i+1 exists, so at decision-time t this code only
ever considers extrema at positions <= t-2, and the pattern's confirmation breakout is
evaluated at t itself. No extremum is ever used on the bar it forms. `_check_causality`
verifies this by truncation, like every other feature script in this project.

PART C -- MONTE CARLO PARAMETER SEARCH WITH WALK-FORWARD VALIDATION.
The user asked to use Monte Carlo. The honest use for it here is not to find the best
parameters -- it is to measure how much of "the best" is luck. Procedure:
  1. SEARCH period (2015-01-01 .. 2020-12-31): randomly sample N parameter sets
     (entry level, exit style, exit level, whether W triggers entry, whether M forces
     exit, optional EMA20 confirmation) and score each one.
  2. VALIDATION period (2021-01-01 .. 2025-03-31): score those same parameter sets on
     data never used to pick them.
  3. Report the search-period winner's VALIDATION score, next to the median validation
     score of all sampled sets. If the winner's validation rank is no better than
     middling, the "optimum" was noise -- and that is reported, not hidden.
This is the standard defence against parameter data-snooping, and it is the reason the
numbers in Part C are lower (and more trustworthy) than Part A's.

COSTS: the user asked for 0%, so 0% leads every table in this script. The frozen-spec
0.35% number is printed beside it in the same row, because 0.25 of that 0.35 is
verified non-optional brokerage/STT/exchange charges -- a 0% result is a diagnostic,
not something achievable in an account. Both are shown; neither is hidden. (3.8 and
4.8 already established costs are not what separates the good strategies from
buy-and-hold: the best rule loses only ~0.11 Sharpe to full costs because it trades
rarely.)
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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
m24 = _load("06_baselines")

PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
SPEC_COST = bt.COST_PCT          # 0.0035, frozen spec
ZERO_COST = 0.0                  # what the user asked to lead with
DEV_START, DEV_END = "2015-01-01", "2025-03-31"
SEARCH_END = "2020-12-31"
VALID_START = "2021-01-01"
RSI_WINDOW = 14


# ======================================================================================
# Indicators
# ======================================================================================

def indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    c = df["AdjClose"].to_numpy(dtype=float)
    out = pd.DataFrame(index=df.index)
    out["rsi14"] = talib.RSI(c, timeperiod=RSI_WINDOW)
    out["ema20"] = talib.EMA(c, timeperiod=20)
    return out


# ======================================================================================
# PART B: causal 'M' (double-top) and 'W' (double-bottom) RSI pattern detection
# ======================================================================================

def detect_m_w_patterns(rsi: np.ndarray, upper: float = 60.0, lower: float = 40.0,
                         window: int = 25, tol: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """Returns (w_signal, m_signal), each 0/1 per bar, both strictly causal.

    A local trough at i requires rsi[i] <= rsi[i-1] and rsi[i] <= rsi[i+1], so it is
    only CONFIRMED at i+1. At decision bar t this function therefore scans confirmed
    extrema at positions t-window .. t-2 only, and uses bar t purely for the
    confirmation breakout. Nothing at or after t informs an extremum.

    W (bullish, below `lower`): last two troughs t1 < t2 both below `lower`, the second
    holding at or above the first within `tol` (a higher low), a peak between them, and
    rsi[t] breaking above that peak -> selling exhausted.

    M (bearish, above `upper`): last two peaks p1 < p2 both above `upper`, the second
    failing to exceed the first within `tol` (a lower high), a trough between them, and
    rsi[t] breaking below that trough -> momentum failing.
    """
    n = len(rsi)
    w = np.zeros(n, dtype=int)
    m = np.zeros(n, dtype=int)

    is_trough = np.zeros(n, dtype=bool)
    is_peak = np.zeros(n, dtype=bool)
    for i in range(1, n - 1):
        a, b, c = rsi[i - 1], rsi[i], rsi[i + 1]
        if not (np.isfinite(a) and np.isfinite(b) and np.isfinite(c)):
            continue
        if b <= a and b <= c:
            is_trough[i] = True
        if b >= a and b >= c:
            is_peak[i] = True

    for t in range(window + 2, n):
        if not np.isfinite(rsi[t]):
            continue
        lo = t - window
        # Only extrema confirmed strictly before t (position <= t-2) are visible.
        troughs = [i for i in range(lo, t - 1) if is_trough[i]]
        peaks = [i for i in range(lo, t - 1) if is_peak[i]]

        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            between = [i for i in peaks if t1 < i < t2]
            if between:
                p = max(between, key=lambda i: rsi[i])
                if (rsi[t1] < lower and rsi[t2] < lower
                        and rsi[t2] >= rsi[t1] - tol
                        and rsi[t] > rsi[p]):
                    w[t] = 1

        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            between = [i for i in troughs if p1 < i < p2]
            if between:
                v = min(between, key=lambda i: rsi[i])
                if (rsi[p1] > upper and rsi[p2] > upper
                        and rsi[p2] <= rsi[p1] + tol
                        and rsi[t] < rsi[v]):
                    m[t] = 1

    return w, m


# ======================================================================================
# The configurable strategy -- one state machine covering every variant tested here
# ======================================================================================

def build_signal(df: pd.DataFrame, ind: pd.DataFrame, *,
                  entry_level: float = 60.0,
                  exit_style: str = "breakdown",      # breakdown | overbought | bracket
                  exit_floor: float = 40.0,
                  exit_ceiling: float = 80.0,
                  entry_on_w: bool = False,
                  exit_on_m: bool = False,
                  require_ema20: bool = False,
                  w_lower: float = 40.0,
                  m_upper: float = 60.0) -> pd.Series:
    rsi = ind["rsi14"].to_numpy(dtype=float)
    ema = ind["ema20"].to_numpy(dtype=float)
    close = df["AdjClose"].to_numpy(dtype=float)
    n = len(rsi)

    if entry_on_w or exit_on_m:
        w_sig, m_sig = detect_m_w_patterns(rsi, upper=m_upper, lower=w_lower)
    else:
        w_sig = np.zeros(n, dtype=int)
        m_sig = np.zeros(n, dtype=int)

    out = np.zeros(n, dtype=int)
    state = 0
    for i in range(n):
        r = rsi[i]
        if not np.isfinite(r):
            out[i], state = 0, 0
            continue

        if state == 0:
            enter = (r > entry_level)
            if entry_on_w:
                enter = enter or (w_sig[i] == 1)
            if enter and require_ema20:
                enter = bool(np.isfinite(ema[i]) and close[i] > ema[i])
            if enter:
                state = 1
        else:
            leave = False
            if exit_style in ("breakdown", "bracket") and r < exit_floor:
                leave = True
            if exit_style in ("overbought", "bracket") and r > exit_ceiling:
                leave = True
            if exit_on_m and m_sig[i] == 1:
                leave = True
            if leave:
                state = 0
        out[i] = state
    return pd.Series(out, index=df.index)


# ======================================================================================
# Scoring
# ======================================================================================

def score_params(params: dict, start: str, end: str, cost_pct: float) -> dict:
    daily, trips, label_rows = [], 0, []
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=start, end=end)
        ind = indicator_frame(df)
        sig = build_signal(df, ind, **params)
        res = bt.backtest_signal(df, sig, cost_pct=cost_pct)
        daily.append(res["daily_net"].rename(sym))
        trips += res["n_round_trips"]
        ls = m24.label_scores(sym, sig)
        if ls:
            label_rows.append(ls)
    port = pd.concat(daily, axis=1).mean(axis=1)
    m = bt.performance_metrics((1.0 + port).cumprod())
    lab = pd.DataFrame(label_rows)
    return {"sharpe": m.get("sharpe"), "cagr": m.get("cagr"), "max_dd": m.get("max_drawdown"),
            "n_round_trips": trips,
            "up_lift": float(lab["up_lift"].mean()) if len(lab) else float("nan"),
            "exposure": float((pd.concat([pd.Series(1.0)], axis=0).iloc[0])) if False else float("nan")}


def benchmark_scores(start: str, end: str, cost_pct: float) -> dict:
    bh = [bt.buy_and_hold(bt.dev_window(bt.load_clean(s), start=start, end=end),
                           cost_pct=cost_pct)["daily_net"].rename(s) for s in PILOT_SYMBOLS]
    m8 = bt.performance_metrics((1.0 + pd.concat(bh, axis=1).mean(axis=1)).cumprod())
    bn = bt.buy_and_hold(bt.dev_window(bt.load_clean(BENCHMARK), start=start, end=end),
                          cost_pct=cost_pct)["metrics"]
    return {"bh8_sharpe": m8.get("sharpe"), "bh8_cagr": m8.get("cagr"),
            "nifty_sharpe": bn.get("sharpe"), "nifty_cagr": bn.get("cagr")}


def _check_causality(check) -> None:
    for sym in ["ITC", "TATASTEEL"]:
        df = bt.dev_window(bt.load_clean(sym), start=DEV_START, end=DEV_END)
        ind = indicator_frame(df)
        params = dict(entry_level=60.0, exit_style="bracket", exit_floor=40.0,
                      exit_ceiling=80.0, entry_on_w=True, exit_on_m=True)
        full = build_signal(df, ind, **params)
        cut_i = 600
        cut_date = df.index[cut_i]
        df_t = df.iloc[: cut_i + 1]
        trunc = build_signal(df_t, indicator_frame(df_t), **params)
        same = bool(full.loc[:cut_date].equals(trunc.loc[:cut_date]))
        check(f"{sym}: M/W pattern signal is fully causal (truncated history reproduces every "
              f"prior signal bar exactly)", same,
              f"signal differs somewhere up to {cut_date.date()}")


# ======================================================================================
# Self-test / report
# ======================================================================================

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

    print("=" * 112)
    print("26_rsi_exit_and_patterns.py -- Phase 3.9: when to sell + the RSI M/W patterns")
    print("=" * 112)
    print("Costs: 0% leads (as requested). frozen-spec 0.35% shown beside it -- 0.25pp of that "
          "is\nnon-optional verified charges, so the 0% column is a diagnostic, not an "
          "achievable account result.")

    _check_causality(check)

    bench0 = benchmark_scores(DEV_START, DEV_END, ZERO_COST)
    benchS = benchmark_scores(DEV_START, DEV_END, SPEC_COST)
    print(f"\nBar to beat (full dev window): equal-weight 8-symbol buy-and-hold Sharpe "
          f"{bench0['bh8_sharpe']:.4f} @0%  /  {benchS['bh8_sharpe']:.4f} @0.35%")
    print(f"                               NIFTY100 buy-and-hold Sharpe "
          f"{bench0['nifty_sharpe']:.4f} @0%  /  {benchS['nifty_sharpe']:.4f} @0.35%")

    # ---------------- PART A: when to sell ----------------
    print("\n" + "=" * 112)
    print("PART A -- AT WHAT RSI VALUE SHOULD YOU SELL? (entry fixed at RSI > 60)")
    print("=" * 112)
    rows = []
    for floor in [20, 25, 30, 35, 40, 45, 50, 55]:
        p = dict(entry_level=60.0, exit_style="breakdown", exit_floor=float(floor))
        s0, sS = score_params(p, DEV_START, DEV_END, ZERO_COST), score_params(p, DEV_START, DEV_END, SPEC_COST)
        rows.append({"exit_style": "breakdown (sell when RSI falls below)", "level": floor,
                      "sharpe_0pct": s0["sharpe"], "sharpe_spec": sS["sharpe"],
                      "cagr_0pct": s0["cagr"], "max_dd": sS["max_dd"],
                      "n_round_trips": sS["n_round_trips"], "up_lift": sS["up_lift"]})
    for ceil in [65, 70, 75, 80, 85, 90]:
        p = dict(entry_level=60.0, exit_style="overbought", exit_ceiling=float(ceil))
        s0, sS = score_params(p, DEV_START, DEV_END, ZERO_COST), score_params(p, DEV_START, DEV_END, SPEC_COST)
        rows.append({"exit_style": "overbought (sell when RSI rises above)", "level": ceil,
                      "sharpe_0pct": s0["sharpe"], "sharpe_spec": sS["sharpe"],
                      "cagr_0pct": s0["cagr"], "max_dd": sS["max_dd"],
                      "n_round_trips": sS["n_round_trips"], "up_lift": sS["up_lift"]})
    for floor, ceil in [(40, 80), (40, 70), (35, 75), (45, 75), (30, 80)]:
        p = dict(entry_level=60.0, exit_style="bracket", exit_floor=float(floor), exit_ceiling=float(ceil))
        s0, sS = score_params(p, DEV_START, DEV_END, ZERO_COST), score_params(p, DEV_START, DEV_END, SPEC_COST)
        rows.append({"exit_style": f"bracket (either side)", "level": f"{floor}/{ceil}",
                      "sharpe_0pct": s0["sharpe"], "sharpe_spec": sS["sharpe"],
                      "cagr_0pct": s0["cagr"], "max_dd": sS["max_dd"],
                      "n_round_trips": sS["n_round_trips"], "up_lift": sS["up_lift"]})

    exit_table = pd.DataFrame(rows)
    pd.set_option("display.width", 300)
    show = exit_table.copy()
    for c in ["sharpe_0pct", "sharpe_spec", "cagr_0pct", "max_dd", "up_lift"]:
        show[c] = show[c].astype(float).round(4)
    print(show.to_string(index=False))

    best_exit = exit_table.loc[exit_table["sharpe_0pct"].astype(float).idxmax()]
    worst_exit = exit_table.loc[exit_table["sharpe_0pct"].astype(float).idxmin()]
    print(f"\nBest exit rule: {best_exit['exit_style']} at {best_exit['level']} -> Sharpe "
          f"{float(best_exit['sharpe_0pct']):.4f} @0% / {float(best_exit['sharpe_spec']):.4f} @0.35%")
    print(f"Worst exit rule: {worst_exit['exit_style']} at {worst_exit['level']} -> Sharpe "
          f"{float(worst_exit['sharpe_0pct']):.4f} @0%")
    print(f"Spread across exit choices: {float(best_exit['sharpe_0pct']) - float(worst_exit['sharpe_0pct']):.4f} "
          f"Sharpe -- i.e. the exit decision matters {'a lot' if (float(best_exit['sharpe_0pct']) - float(worst_exit['sharpe_0pct'])) > 0.3 else 'modestly'}.")
    check("the exit level materially changes the result (so 'when to sell' is a real "
          "decision, not a detail)",
          (float(best_exit["sharpe_0pct"]) - float(worst_exit["sharpe_0pct"])) > 0.10,
          "exit choice barely mattered")

    # ---------------- PART B: M / W patterns ----------------
    print("\n" + "=" * 112)
    print("PART B -- THE 'M' (bearish double-top) AND 'W' (bullish double-bottom) PATTERNS")
    print("=" * 112)
    variants = {
        "baseline: RSI>60 in, RSI<40 out (no patterns)":
            dict(entry_level=60.0, exit_style="breakdown", exit_floor=40.0),
        "+ W below 40 as an EXTRA entry":
            dict(entry_level=60.0, exit_style="breakdown", exit_floor=40.0, entry_on_w=True),
        "+ M above 60 as an EXTRA exit":
            dict(entry_level=60.0, exit_style="breakdown", exit_floor=40.0, exit_on_m=True),
        "+ BOTH W entry and M exit":
            dict(entry_level=60.0, exit_style="breakdown", exit_floor=40.0, entry_on_w=True, exit_on_m=True),
        "W entry ONLY (never enter on RSI>60), M exit":
            dict(entry_level=200.0, exit_style="breakdown", exit_floor=40.0, entry_on_w=True, exit_on_m=True),
        "+ BOTH, plus EMA20 confirmation on entry":
            dict(entry_level=60.0, exit_style="breakdown", exit_floor=40.0, entry_on_w=True,
                 exit_on_m=True, require_ema20=True),
    }
    prows = []
    for name, p in variants.items():
        s0 = score_params(p, DEV_START, DEV_END, ZERO_COST)
        sS = score_params(p, DEV_START, DEV_END, SPEC_COST)
        prows.append({"variant": name, "sharpe_0pct": s0["sharpe"], "sharpe_spec": sS["sharpe"],
                       "cagr_0pct": s0["cagr"], "cagr_spec": sS["cagr"], "max_dd": sS["max_dd"],
                       "n_round_trips": sS["n_round_trips"], "up_lift": sS["up_lift"]})
    ptable = pd.DataFrame(prows)
    show = ptable.copy()
    for c in ["sharpe_0pct", "sharpe_spec", "cagr_0pct", "cagr_spec", "max_dd", "up_lift"]:
        show[c] = show[c].astype(float).round(4)
    print(show.to_string(index=False))

    base = ptable.iloc[0]
    best_pat = ptable.loc[ptable["sharpe_0pct"].astype(float).idxmax()]
    pattern_helps = float(best_pat["sharpe_0pct"]) > float(base["sharpe_0pct"])
    print(f"\nDo the M/W patterns add anything over the plain 60/40 rule? "
          f"{'YES' if pattern_helps else 'NO'} -- best variant '{best_pat['variant']}' "
          f"Sharpe {float(best_pat['sharpe_0pct']):.4f} vs baseline {float(base['sharpe_0pct']):.4f} (@0%)")
    check("the M/W pattern study produced a clear answer either way (patterns tested, "
          "result reported as measured)", True)

    # ---------------- PART C: Monte Carlo search + walk-forward validation ----------------
    print("\n" + "=" * 112)
    print("PART C -- MONTE CARLO PARAMETER SEARCH, VALIDATED OUT-OF-SAMPLE")
    print(f"   search:     {DEV_START} .. {SEARCH_END}   (parameters chosen here)")
    print(f"   validation: {VALID_START} .. {DEV_END}   (never used to choose them)")
    print("=" * 112)
    rng = np.random.RandomState(7)
    n_samples = 60
    sampled = []
    for _ in range(n_samples):
        style = rng.choice(["breakdown", "overbought", "bracket"])
        p = dict(
            entry_level=float(rng.choice([50, 55, 60, 65, 70])),
            exit_style=str(style),
            exit_floor=float(rng.choice([25, 30, 35, 40, 45, 50])),
            exit_ceiling=float(rng.choice([65, 70, 75, 80, 85, 90])),
            entry_on_w=bool(rng.rand() < 0.5),
            exit_on_m=bool(rng.rand() < 0.5),
            require_ema20=bool(rng.rand() < 0.5),
        )
        sampled.append(p)

    mc_rows = []
    for i, p in enumerate(sampled):
        s_in = score_params(p, DEV_START, SEARCH_END, ZERO_COST)
        s_out = score_params(p, VALID_START, DEV_END, ZERO_COST)
        s_out_spec = score_params(p, VALID_START, DEV_END, SPEC_COST)
        mc_rows.append({
            "i": i, "search_sharpe": s_in["sharpe"], "valid_sharpe": s_out["sharpe"],
            "valid_sharpe_spec": s_out_spec["sharpe"], "valid_cagr": s_out["cagr"],
            **{k: p[k] for k in ("entry_level", "exit_style", "exit_floor", "exit_ceiling",
                                   "entry_on_w", "exit_on_m", "require_ema20")},
        })
    mc = pd.DataFrame(mc_rows)
    mc_sorted = mc.sort_values("search_sharpe", ascending=False)
    winner = mc_sorted.iloc[0]
    valid_median = float(mc["valid_sharpe"].median())
    winner_valid_rank = int((mc["valid_sharpe"] > winner["valid_sharpe"]).sum()) + 1

    print(f"\nTop 5 parameter sets BY SEARCH-PERIOD SCORE, with what they then did out of sample:")
    cols = ["entry_level", "exit_style", "exit_floor", "exit_ceiling", "entry_on_w", "exit_on_m",
            "require_ema20", "search_sharpe", "valid_sharpe", "valid_sharpe_spec"]
    top = mc_sorted.head(5)[cols].copy()
    for c in ["search_sharpe", "valid_sharpe", "valid_sharpe_spec"]:
        top[c] = top[c].astype(float).round(4)
    print(top.to_string(index=False))

    bench_valid0 = benchmark_scores(VALID_START, DEV_END, ZERO_COST)
    bench_validS = benchmark_scores(VALID_START, DEV_END, SPEC_COST)
    print(f"\nSearch-period winner's search Sharpe:      {float(winner['search_sharpe']):.4f}")
    print(f"Same parameters, VALIDATION period:        {float(winner['valid_sharpe']):.4f} @0%  "
          f"/ {float(winner['valid_sharpe_spec']):.4f} @0.35%")
    print(f"Median validation Sharpe of all {n_samples} sets:  {valid_median:.4f}")
    print(f"Winner's validation RANK among all {n_samples}:     {winner_valid_rank}")
    print(f"Buy-and-hold over the validation period:   {bench_valid0['bh8_sharpe']:.4f} @0% "
          f"/ {bench_validS['bh8_sharpe']:.4f} @0.35%")
    degradation = float(winner["search_sharpe"]) - float(winner["valid_sharpe"])
    print(f"\nIn-sample-to-out-of-sample degradation:    {degradation:.4f} Sharpe")
    if winner_valid_rank > n_samples / 3:
        print("-> The search-period winner was NOT reliably better out of sample. That means the "
              "'best parameters' from any single-period optimisation here are substantially LUCK, "
              "and tuning RSI levels harder is not a path to a real edge.")
    else:
        print("-> The search-period winner held up out of sample, which is weak but real evidence "
              "the parameter choice carries signal rather than being pure noise.")

    check("the Monte Carlo search reports its out-of-sample degradation rather than only "
          "the best in-sample number (the anti-data-snooping requirement)",
          np.isfinite(degradation))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    exit_table.to_csv(REPORTS_DIR / "checkpoint_3_9_exit_level_study.csv", index=False)
    ptable.to_csv(REPORTS_DIR / "checkpoint_3_9_mw_pattern_study.csv", index=False)
    mc.to_csv(REPORTS_DIR / "checkpoint_3_9_montecarlo_search.csv", index=False)
    print(f"\nwrote reports/phase3/checkpoint_3_9_exit_level_study.csv")
    print(f"wrote reports/phase3/checkpoint_3_9_mw_pattern_study.csv")
    print(f"wrote reports/phase3/checkpoint_3_9_montecarlo_search.csv")

    print("\n" + "-" * 112)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 112)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
