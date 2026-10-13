"""
28_sharpe_levers.py -- Phase 4.9: the levers that actually move SHARPE.

THE USER'S TARGET: Sharpe > 1 minimum, ideally 2-3, and real profit.

WHERE WE ALREADY ARE (measured, not asserted): checkpoint 3.10 found RSI20 + EMA20,
enter >55, exit <20 already scores portfolio Sharpe 1.0175 at frozen-spec cost on the
8 pilot symbols. So "Sharpe > 1" is ALREADY MET. The problem was never the Sharpe
threshold -- it is that equal-weight buy-and-hold on the same 8 stocks scores 1.0173
over the same window, i.e. the strategy's Sharpe is the MARKET's Sharpe, and the
strategy adds nothing. Raising Sharpe further therefore is not an indicator problem.

WHY MORE INDICATOR TUNING CANNOT GET TO SHARPE 2-3, stated plainly rather than
discovered again: Sharpe is return divided by volatility. Phase 3.8/3.9/3.10 tested
11 RSI framings, 19 exit variants, 60 Monte Carlo parameter sets and 108 RSI/EMA
combinations -- and every single improvement came from REDUCING TRADING, which
converges on buy-and-hold rather than beating it. The remaining levers are structural,
in portfolio construction, not in the signal. That is what this script tests.

THE FOUR STRUCTURAL LEVERS TESTED HERE (each one standard practice in quant equity):
  L1. VOLATILITY TARGETING -- scale position size so the portfolio runs at a constant
      target volatility instead of whatever the market happens to deliver. Cuts
      exposure when realised vol spikes. This is the single most reliable Sharpe
      improver in practice because it directly attacks the denominator. Capped at
      100% exposure: the frozen spec says "long or cash only", so LEVERAGE (>100%) is
      NOT used -- that would be a spec change requiring the user's approval, and is
      flagged below as the one lever left untested for that reason.
  L2. INVERSE-VOLATILITY WEIGHTING across symbols -- instead of equal weight, give
      calmer stocks more capital. Standard risk-parity-lite.
  L3. WIDER UNIVERSE -- 30 clean symbols instead of 8. Sharpe scales roughly with the
      square root of the number of INDEPENDENT bets; 8 correlated large caps are far
      fewer than 8 independent bets. All 30 pass the same Phase 1.3 corporate-action
      cleanliness check that the 8 pilots pass, so no data-quality compromise is made
      to get the extra names.
  L4. INDEX-LEVEL REGIME FILTER -- go to cash across the whole book when NIFTY100
      itself is below its own 200-day average, rather than deciding per stock.

HONEST EXPECTATION BEFORE RUNNING (recorded so it cannot be retrofitted): L1 and L3
should raise Sharpe meaningfully; L2 modestly; L4 is a coin flip (it helps in bear
markets and costs money in bull markets, and 2015-2025 was mostly bull). I do NOT
expect to reach Sharpe 2-3 long-only on daily Indian large caps -- that range
generally requires leverage, short books, intraday horizons, or hundreds of
instruments. If the numbers below contradict this expectation, the numbers win.

NEW BACKTESTER, VALIDATED BEFORE USE: position sizing needs fractional weights, and
04_backtest.backtest_signal takes a 0/1 integer signal only. So a fractional-weight
portfolio backtester is written here -- and `_check_engine_agreement` verifies it
reproduces the verified engine's net return when handed 0/1 weights, before any
result from it is reported. Cost convention: cost is charged on TURNOVER at
cost_pct/2 per unit, so a full round trip (0 -> 1 -> 0, turnover 2.0) costs exactly
cost_pct, matching the frozen spec's "per round trip" definition.

COSTS: 0% leads (as the user asked), frozen-spec 0.35% beside it in every row.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import talib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase4"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("04_backtest")

PILOT_8 = bt.PILOT_SYMBOLS
# All 30 tradeable symbols with no exclude_reason in reports/phase1/checkpoint_1_3_universe.csv
# (NIFTY100/NIFTY50 are indices, excluded from the tradeable universe).
CLEAN_30 = ["ABB", "ASIANPAINT", "BAJAJ-AUTO", "BHARTIARTL", "BOSCHLTD", "BRITANNIA", "CIPLA",
            "COALINDIA", "CUMMINSIND", "DMART", "DRREDDY", "EICHERMOT", "HCLTECH", "HDFCBANK",
            "HINDUNILVR", "ITC", "JIOFIN", "KOTAKBANK", "NESTLEIND", "POWERGRID", "RELIANCE",
            "SBILIFE", "SIEMENS", "SOLARINDS", "TATACONSUM", "TATASTEEL", "TCS", "TVSMOTOR",
            "ULTRACEMCO", "VBL"]
BENCHMARK = "NIFTY100"
SPEC_COST, ZERO_COST = bt.COST_PCT, 0.0
DEV_START, DEV_END = "2015-01-01", "2025-03-31"
TRADING_DAYS = 252

# The best signal found in checkpoint 3.10.
RSI_PERIOD, EMA_PERIOD, ENTRY_LEVEL, EXIT_FLOOR = 20, 20, 55.0, 20.0
TARGET_VOL = 0.15          # 15% annualised, a conventional target for an equity book
VOL_LOOKBACK = 20          # sessions of realised vol used for sizing
MAX_EXPOSURE = 1.0         # long-or-cash: never leveraged (spec); see docstring

_PRICE: Dict[str, pd.DataFrame] = {}


def price(symbol: str) -> pd.DataFrame:
    if symbol not in _PRICE:
        _PRICE[symbol] = bt.dev_window(bt.load_clean(symbol), start=DEV_START, end=DEV_END)
    return _PRICE[symbol]


# ======================================================================================
# Signal
# ======================================================================================

def rsi_signal(symbol: str) -> pd.Series:
    df = price(symbol)
    c = df["AdjClose"].to_numpy(dtype=float)
    rsi = talib.RSI(c, timeperiod=RSI_PERIOD)
    out = np.zeros(len(c), dtype=float)
    state = 0
    for i, r in enumerate(rsi):
        if not np.isfinite(r):
            out[i], state = 0.0, 0
            continue
        if state == 0 and r > ENTRY_LEVEL:
            state = 1
        elif state == 1 and r < EXIT_FLOOR:
            state = 0
        out[i] = float(state)
    return pd.Series(out, index=df.index)


# ======================================================================================
# Fractional-weight portfolio backtester (validated against the verified engine below)
# ======================================================================================

def portfolio_backtest(weights: pd.DataFrame, cost_pct: float) -> dict:
    """weights: index = dates, columns = symbols, values in [0, 1] = target fraction of
    total capital in that symbol, decided using information through Close[t].

    Execution: the weight decided at t is applied from t+1, so the Close[t]->Open[t+1]
    gap is never earned -- the same no-lookahead rule 04_backtest enforces. Each
    symbol's day return is Close/Close.shift(1) once held. Cost = cost_pct/2 per unit
    of turnover, so a full round trip costs cost_pct (the spec's definition).
    """
    syms = list(weights.columns)
    rets = pd.DataFrame({s: price(s)["AdjClose"].pct_change() for s in syms})
    rets = rets.reindex(weights.index).fillna(0.0)

    w_applied = weights.shift(1).fillna(0.0)            # decided at t, held from t+1
    gross = (w_applied * rets).sum(axis=1)
    turnover = (w_applied - w_applied.shift(1).fillna(0.0)).abs().sum(axis=1)
    cost = turnover * (cost_pct / 2.0)
    net = gross - cost

    eq = (1.0 + net).cumprod()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    sd = net.std(ddof=1)
    return {
        "daily_net": net,
        "equity": eq,
        "cagr": float(eq.iloc[-1] ** (1.0 / years) - 1.0) if eq.iloc[-1] > 0 else float("nan"),
        "sharpe": float(net.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else float("nan"),
        "ann_vol": float(sd * np.sqrt(TRADING_DAYS)),
        "max_dd": float((eq / eq.cummax() - 1.0).min()),
        "avg_exposure": float(w_applied.sum(axis=1).mean()),
        "total_turnover": float(turnover.sum()),
    }


def _check_engine_agreement(check) -> None:
    """The new fractional engine must reproduce the VERIFIED 04_backtest engine's net
    return on a 0/1 single-symbol signal before any of its numbers are trusted. Small
    differences are expected and bounded: the verified engine executes entries/exits at
    the OPEN and this one marks close-to-close, so the two differ by the overnight gap
    on trade days only. The tolerance below reflects that, and is checked rather than
    waved through."""
    for sym in ["ITC", "TCS"]:
        sig = rsi_signal(sym)
        ref = bt.backtest_signal(price(sym), sig.astype(int), cost_pct=SPEC_COST)
        mine = portfolio_backtest(pd.DataFrame({sym: sig}), cost_pct=SPEC_COST)
        a, b = ref["net_return"], float(mine["equity"].iloc[-1] - 1.0)
        rel = abs(a - b) / max(abs(a), 1e-9)
        check(f"{sym}: new fractional engine agrees with the verified 04_backtest engine "
              f"on a 0/1 signal (within 25% relative, the open-vs-close execution gap)",
              rel < 0.25, f"verified {a:.4f} vs new {b:.4f} (rel diff {rel:.3f})")


# ======================================================================================
# The levers
# ======================================================================================

def weights_equal(symbols: List[str], use_signal: bool = True) -> pd.DataFrame:
    idx = price(BENCHMARK).index
    cols = {}
    for s in symbols:
        sig = rsi_signal(s).reindex(idx).fillna(0.0) if use_signal else \
            pd.Series(1.0, index=price(s).index).reindex(idx).fillna(0.0)
        cols[s] = sig / len(symbols)
    return pd.DataFrame(cols, index=idx).fillna(0.0)


def weights_inverse_vol(symbols: List[str], use_signal: bool = True) -> pd.DataFrame:
    """Weight each held symbol by 1/realised-vol, renormalised so the total never
    exceeds 1.0 (no leverage). Vol uses a trailing window ending at t -- causal."""
    idx = price(BENCHMARK).index
    sigs, invvol = {}, {}
    for s in symbols:
        sig = (rsi_signal(s) if use_signal else pd.Series(1.0, index=price(s).index))
        v = price(s)["AdjClose"].pct_change().rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).std()
        sigs[s] = sig.reindex(idx).fillna(0.0)
        invvol[s] = (1.0 / v.replace(0, np.nan)).reindex(idx)
    S = pd.DataFrame(sigs, index=idx).fillna(0.0)
    IV = pd.DataFrame(invvol, index=idx).replace([np.inf, -np.inf], np.nan)
    IV = IV.fillna(IV.mean(axis=1).to_frame().values if False else 0.0)
    raw = S * IV
    tot = raw.sum(axis=1).replace(0, np.nan)
    return raw.div(tot, axis=0).fillna(0.0)


def apply_vol_target(weights: pd.DataFrame, target_vol: float = TARGET_VOL) -> pd.DataFrame:
    """Scale the whole book each day so its trailing realised vol equals target_vol,
    capped at MAX_EXPOSURE (no leverage). The scalar at t uses the portfolio's realised
    vol through t only -- causal -- and is applied to t's weights, which themselves are
    only executed at t+1 by the backtester."""
    syms = list(weights.columns)
    rets = pd.DataFrame({s: price(s)["AdjClose"].pct_change() for s in syms}).reindex(weights.index).fillna(0.0)
    port_ret = (weights.shift(1).fillna(0.0) * rets).sum(axis=1)
    realised = port_ret.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).std() * np.sqrt(TRADING_DAYS)
    scalar = (target_vol / realised.replace(0, np.nan)).clip(upper=MAX_EXPOSURE / max(weights.sum(axis=1).max(), 1e-9))
    scalar = scalar.fillna(1.0).clip(lower=0.0)
    out = weights.mul(scalar, axis=0)
    # hard cap: total exposure never above MAX_EXPOSURE
    tot = out.sum(axis=1)
    over = tot > MAX_EXPOSURE
    out.loc[over] = out.loc[over].div(tot[over], axis=0) * MAX_EXPOSURE
    return out


def apply_index_regime(weights: pd.DataFrame) -> pd.DataFrame:
    """Zero the whole book on days when NIFTY100 closed below its own 200-day SMA."""
    bench = price(BENCHMARK)["AdjClose"]
    sma200 = bench.rolling(200, min_periods=200).mean()
    ok = (bench > sma200).reindex(weights.index).fillna(False).astype(float)
    return weights.mul(ok, axis=0)


# ======================================================================================
# Report
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

    print("=" * 118)
    print("28_sharpe_levers.py -- Phase 4.9: the structural levers that move SHARPE")
    print("=" * 118)
    print(f"Signal held fixed at checkpoint 3.10's best: RSI{RSI_PERIOD} enter>{int(ENTRY_LEVEL)} "
          f"exit<{int(EXIT_FLOOR)}. Only PORTFOLIO CONSTRUCTION changes below.")
    print(f"Universes: 8 pilot symbols vs {len(CLEAN_30)} clean symbols (all pass the same "
          f"Phase 1.3 corp-action check).")
    print("0% costs lead (as asked); frozen-spec 0.35% beside. No leverage anywhere "
          "(spec: long or cash only).")

    _check_engine_agreement(check)

    rows = []

    def add(name: str, w: pd.DataFrame, universe: str) -> None:
        r0 = portfolio_backtest(w, ZERO_COST)
        rS = portfolio_backtest(w, SPEC_COST)
        rows.append({"strategy": name, "universe": universe,
                      "sharpe_0pct": r0["sharpe"], "sharpe_spec": rS["sharpe"],
                      "cagr_0pct": r0["cagr"], "cagr_spec": rS["cagr"],
                      "ann_vol_spec": rS["ann_vol"], "max_dd_spec": rS["max_dd"],
                      "avg_exposure": rS["avg_exposure"], "turnover": rS["total_turnover"]})

    # --- 8-symbol universe ---
    w8_eq = weights_equal(PILOT_8)
    add("baseline: RSI signal, equal weight", w8_eq, "8 pilot")
    add("L1 + volatility targeting (15%)", apply_vol_target(w8_eq), "8 pilot")
    add("L2 + inverse-vol weighting", weights_inverse_vol(PILOT_8), "8 pilot")
    add("L1+L2 + inverse-vol AND vol targeting",
        apply_vol_target(weights_inverse_vol(PILOT_8)), "8 pilot")
    add("L4 + NIFTY100 200-day regime filter", apply_index_regime(w8_eq), "8 pilot")
    add("REFERENCE: buy-and-hold, equal weight", weights_equal(PILOT_8, use_signal=False), "8 pilot")
    add("REFERENCE: buy-and-hold + vol targeting",
        apply_vol_target(weights_equal(PILOT_8, use_signal=False)), "8 pilot")

    # --- 30-symbol universe (L3) ---
    w30_eq = weights_equal(CLEAN_30)
    add("L3 baseline: RSI signal, equal weight", w30_eq, "30 clean")
    add("L3+L1 + volatility targeting (15%)", apply_vol_target(w30_eq), "30 clean")
    add("L3+L2 + inverse-vol weighting", weights_inverse_vol(CLEAN_30), "30 clean")
    add("L3+L1+L2 ALL LEVERS", apply_vol_target(weights_inverse_vol(CLEAN_30)), "30 clean")
    add("L3+L1+L2+L4 ALL + regime filter",
        apply_index_regime(apply_vol_target(weights_inverse_vol(CLEAN_30))), "30 clean")
    add("REFERENCE: buy-and-hold, equal weight", weights_equal(CLEAN_30, use_signal=False), "30 clean")
    add("REFERENCE: buy-and-hold + vol targeting",
        apply_vol_target(weights_equal(CLEAN_30, use_signal=False)), "30 clean")

    table = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(REPORTS_DIR / "checkpoint_4_9_sharpe_levers.csv", index=False)

    pd.set_option("display.width", 320)
    show = table.copy()
    for c in ["sharpe_0pct", "sharpe_spec", "cagr_0pct", "cagr_spec", "ann_vol_spec",
              "max_dd_spec", "avg_exposure", "turnover"]:
        show[c] = show[c].astype(float).round(4)
    for uni in ["8 pilot", "30 clean"]:
        print(f"\n--- {uni} universe ---")
        print(show.loc[show["universe"] == uni].drop(columns=["universe"]).to_string(index=False))

    strat = table.loc[~table["strategy"].str.startswith("REFERENCE")]
    best = strat.loc[strat["sharpe_spec"].astype(float).idxmax()]
    bh30 = table.loc[(table["universe"] == "30 clean") &
                      (table["strategy"] == "REFERENCE: buy-and-hold, equal weight")].iloc[0]
    bh30vt = table.loc[(table["universe"] == "30 clean") &
                        (table["strategy"] == "REFERENCE: buy-and-hold + vol targeting")].iloc[0]

    print("\n" + "=" * 118)
    print("VERDICTS vs THE USER'S TARGET (Sharpe > 1 minimum, ideally 2-3)")
    print("=" * 118)
    print(f"Best strategy: {best['strategy']}  [{best['universe']}]")
    print(f"  Sharpe {float(best['sharpe_spec']):.4f} @0.35%  /  {float(best['sharpe_0pct']):.4f} @0%")
    print(f"  CAGR   {float(best['cagr_spec']):.4f} @0.35%,  vol {float(best['ann_vol_spec']):.4f},  "
          f"max DD {float(best['max_dd_spec']):.4f}")
    print(f"\nBest buy-and-hold reference (30 clean, vol-targeted): Sharpe "
          f"{float(bh30vt['sharpe_spec']):.4f}, CAGR {float(bh30vt['cagr_spec']):.4f}")
    print(f"Plain buy-and-hold (30 clean, equal weight):          Sharpe "
          f"{float(bh30['sharpe_spec']):.4f}, CAGR {float(bh30['cagr_spec']):.4f}")

    check("the user's minimum bar is met: at least one strategy has Sharpe > 1 after real costs",
          bool((strat["sharpe_spec"].astype(float) > 1.0).any()),
          f"best {float(strat['sharpe_spec'].astype(float).max()):.4f}")
    reached_2 = bool((strat["sharpe_spec"].astype(float) > 2.0).any())
    print(f"\nDid anything reach Sharpe 2+? {'YES' if reached_2 else 'NO'}  "
          f"(best was {float(strat['sharpe_spec'].astype(float).max()):.4f})")
    beats_bh = float(best["sharpe_spec"]) > float(bh30vt["sharpe_spec"])
    print(f"Does the best strategy beat the best buy-and-hold reference? "
          f"{'YES' if beats_bh else 'NO'}")

    print(f"\n--- What each lever contributed (8-symbol universe, at real cost) ---")
    base8 = table.loc[(table['universe'] == '8 pilot') &
                       (table['strategy'] == 'baseline: RSI signal, equal weight')].iloc[0]
    for nm in ["L1 + volatility targeting (15%)", "L2 + inverse-vol weighting",
               "L1+L2 + inverse-vol AND vol targeting", "L4 + NIFTY100 200-day regime filter"]:
        r = table.loc[(table['universe'] == '8 pilot') & (table['strategy'] == nm)].iloc[0]
        print(f"  {nm:<45} {float(r['sharpe_spec']):+.4f}  "
              f"(delta {float(r['sharpe_spec']) - float(base8['sharpe_spec']):+.4f})")
    b8 = float(base8["sharpe_spec"])
    b30 = float(table.loc[(table['universe'] == '30 clean') &
                           (table['strategy'] == 'L3 baseline: RSI signal, equal weight')].iloc[0]["sharpe_spec"])
    print(f"  {'L3 universe 8 -> 30 symbols':<45} {b30:+.4f}  (delta {b30 - b8:+.4f})")

    print(f"\nNOT TESTED, and why: LEVERAGE. Volatility targeting is capped at 100% exposure "
          f"here because the\nfrozen spec says 'long or cash only'. Allowing, say, 2x gross "
          f"exposure would roughly double both\nreturn and vol, leaving Sharpe about UNCHANGED "
          f"-- leverage raises RETURN, not Sharpe -- so it is not\na route to Sharpe 2-3 either. "
          f"It is a spec change and needs explicit approval regardless.")

    print(f"\nwrote reports/phase4/checkpoint_4_9_sharpe_levers.csv")
    print("\n" + "-" * 118)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 118)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
