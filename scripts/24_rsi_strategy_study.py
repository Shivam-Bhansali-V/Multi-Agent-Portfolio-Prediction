"""
24_rsi_strategy_study.py -- Phase 3.8 (add-on): RSI used properly, in all the ways it
is actually used in practice -- each one MEASURED, not assumed.

WHY THIS EXISTS: Phase 3's momentum family tested exactly ONE RSI usage -- classic
mean-reversion (enter below 30, exit above 50) -- which scored Sharpe 0.14, the worst
of all 11 indicator rules. The user correctly pointed out that RSI is used far more
widely than that single framing, and specifically asked for the 60/40 range strategy.
That is a real, documented approach (Andrew Cardwell / Constance Brown "RSI range
rules"): in a sustained uptrend RSI oscillates roughly between 40 and 80, so RSI
holding ABOVE 40 means the bull range is intact and crossing ABOVE 60 confirms bull
momentum -- the opposite framing from "RSI 70 = overbought = sell." Phase 3 never
tested this trend-following framing at all. This script does.

PROJECT RULE RESPECTED: CLAUDE.md says never copy code or indicator settings from the
old `Multi_Agent` folder as-is (archive only). The RSI-derived concepts that folder
used (RSI velocity/diff, rolling RSI z-scores, RSI higher-low / lower-high structure,
RSI divergence, distance-from-EMA20/50) are RE-DERIVED here from scratch against
TA-Lib's RSI and this project's own clean adjusted data, with this project's own
causality checks and cost model applied. Nothing is lifted from those files, and none
of that folder's claimed win rates are used -- they were hardcoded literals, as
established 9 Oct 2026.

TWO WINDOWS ARE REPORTED, deliberately, and must not be mixed up:
  - FULL DEV WINDOW (2015-01-01 .. 2025-03-31): comparable to checkpoint 2.4's
    baselines, where NIFTY100 buy-and-hold scored Sharpe 1.02. Rule backtests need no
    training data, so they can use the whole window.
  - OOS WINDOW (2018-01-01 .. 2025-03-31): the period the Phase 4 MODELS were tested
    on (folds 1-8). Only numbers from this window are comparable to the model results
    (e.g. the volatility specialist's Sharpe 0.53).
Quoting a full-window rule Sharpe against an OOS-window model Sharpe would be an
unfair comparison, so both are printed for every rule.

ACCURACY, not just P&L: every rule also gets its triple-barrier label scores
(precision on the 'Up' class, and lift over the Up base rate) via 06_baselines'
label_scores -- a long/flat rule is a two-class (Up vs not-Up) predictor, so this is
precision/lift, NOT 3-class accuracy, and that distinction is kept explicit.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import talib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase3"
OUT_DIR = ROOT / "data" / "features_rsi"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("04_backtest")
m24 = _load("06_baselines")
mom = _load("09_indicators_momentum")

PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
COST_PCT = bt.COST_PCT
DEV_START = "2015-01-01"
DEV_END = "2025-03-31"
OOS_START = "2018-01-01"
RSI_WINDOW = 14


# ======================================================================================
# RSI and friends -- all strictly causal (value at t uses only bars <= t)
# ======================================================================================

def rsi_frame(df: pd.DataFrame) -> pd.DataFrame:
    """RSI(14) via TA-Lib (same source as Phase 3.1, which cross-checked it against an
    independent pandas-EWM implementation) plus the derived RSI quantities."""
    c = df["AdjClose"].to_numpy(dtype=float)
    out = pd.DataFrame(index=df.index)
    out["rsi14"] = talib.RSI(c, timeperiod=RSI_WINDOW)
    out["ema20"] = talib.EMA(c, timeperiod=20)
    out["ema50"] = talib.EMA(c, timeperiod=50)

    r = out["rsi14"]
    out["rsi_diff1"] = r.diff(1)
    out["rsi_diff5"] = r.diff(5)
    for w in (30, 60):
        mu = r.rolling(w, min_periods=w).mean()
        sd = r.rolling(w, min_periods=w).std(ddof=1)
        out[f"rsi_zscore_{w}"] = (r - mu) / sd.replace(0, np.nan)

    # 60/40 RANGE REGIME (the user's requested concept, as a feature rather than only a
    # rule): over the trailing 20 sessions, did RSI hold entirely above 40 (bull range
    # intact), entirely below 60 (bear range), or neither (transition)? Uses a 20-bar
    # window ending at t, so causal.
    roll_min = r.rolling(20, min_periods=20).min()
    roll_max = r.rolling(20, min_periods=20).max()
    regime = pd.Series(0.0, index=df.index)
    regime[roll_min >= 40] = 1.0
    regime[roll_max <= 60] = -1.0
    regime[roll_min.isna()] = np.nan
    out["rsi_range_regime"] = regime
    out["rsi_above_60"] = (r > 60).astype(float).where(r.notna())
    out["rsi_below_40"] = (r < 40).astype(float).where(r.notna())

    # Where RSI sits inside its own trailing 10-session range (0 = bottom, 1 = top).
    r_min10 = r.rolling(10, min_periods=10).min()
    r_max10 = r.rolling(10, min_periods=10).max()
    out["rsi_rel_pos_10"] = (r - r_min10) / (r_max10 - r_min10).replace(0, np.nan)

    # DIVERGENCE, re-derived: bullish = price makes a new 10-bar low while RSI does NOT
    # (RSI stays above its own prior 10-bar low). `.shift(1).rolling(10)` so the
    # comparison window is strictly PRIOR bars -- no same-bar self-reference.
    close = df["AdjClose"]
    prior_px_low = close.shift(1).rolling(10, min_periods=10).min()
    prior_px_high = close.shift(1).rolling(10, min_periods=10).max()
    prior_rsi_low = r.shift(1).rolling(10, min_periods=10).min()
    prior_rsi_high = r.shift(1).rolling(10, min_periods=10).max()
    out["rsi_bull_div"] = ((close < prior_px_low) & (r > prior_rsi_low)).astype(float)
    out["rsi_bear_div"] = ((close > prior_px_high) & (r < prior_rsi_high)).astype(float)

    # Distance from EMA20/EMA50 -- the feature the Multi_Agent docs claimed was its
    # single biggest driver (32.5% weight). Re-derived here; that claimed weight is
    # NOT assumed, it gets measured below like everything else.
    out["dist_ema20_pct"] = (close - out["ema20"]) / out["ema20"]
    out["dist_ema50_pct"] = (close - out["ema50"]) / out["ema50"]
    return out


# ======================================================================================
# The RSI rules -- every documented framing, as a long/cash signal
# ======================================================================================

def sig_rsi_30_70_meanrev(df, ind) -> pd.Series:
    """Classic oversold/overbought mean reversion: buy below 30, sell above 70."""
    return pd.Series(mom._state_machine(ind["rsi14"].to_numpy(), enter_below=30, exit_above=70), index=df.index)


def sig_rsi_30_50_meanrev(df, ind) -> pd.Series:
    """Phase 3's original framing, re-run here for direct comparison (scored 0.14)."""
    return pd.Series(mom._state_machine(ind["rsi14"].to_numpy(), enter_below=30, exit_above=50), index=df.index)


def sig_rsi_50_momentum(df, ind) -> pd.Series:
    """Momentum framing: long while RSI above 50, flat below. The 50 line as trend proxy."""
    r = ind["rsi14"]
    return (r > 50).astype(int).where(r.notna(), 0).astype(int)


def sig_rsi_60_40_range(df, ind) -> pd.Series:
    """THE 60/40 RANGE RULE the user asked for (Cardwell/Brown range framing):
    ENTER long when RSI crosses ABOVE 60 (bull momentum confirmed), and HOLD until RSI
    drops BELOW 40 (bull range broken). Note the hysteresis -- this is NOT the same as
    'long whenever RSI > 60'; it deliberately keeps the position through the 40-60
    middle zone instead of churning in and out of it."""
    return pd.Series(mom._state_machine(ind["rsi14"].to_numpy(), enter_below=None, exit_above=None,
                                         enter_above=60, exit_below=40), index=df.index)


def sig_rsi_above_40(df, ind) -> pd.Series:
    """Pure 'bull range intact' rule: long whenever RSI >= 40, flat below."""
    r = ind["rsi14"]
    return (r >= 40).astype(int).where(r.notna(), 0).astype(int)


def sig_rsi_60_40_plus_ema20(df, ind) -> pd.Series:
    """The 60/40 range rule AND price above EMA20 -- the EMA20 confirmation the user
    asked about, layered on the range rule as a second, independent condition."""
    base = sig_rsi_60_40_range(df, ind)
    above = (df["AdjClose"] > ind["ema20"]).astype(int).where(ind["ema20"].notna(), 0).astype(int)
    return (base & above).astype(int)


def sig_rsi_60_40_plus_ema20_50(df, ind) -> pd.Series:
    """60/40 range rule gated by BOTH moving averages (price > EMA20 and EMA20 > EMA50)
    -- a stricter trend filter."""
    base = sig_rsi_60_40_range(df, ind)
    trend = ((df["AdjClose"] > ind["ema20"]) & (ind["ema20"] > ind["ema50"]))
    trend = trend.astype(int).where(ind["ema50"].notna(), 0).astype(int)
    return (base & trend).astype(int)


def sig_ema20_only(df, ind) -> pd.Series:
    """Control: price above EMA20, no RSI at all. If an RSI rule cannot beat this, the
    RSI part is not adding anything -- this is the comparison that matters most for
    'does RSI actually help', and it is the reason this control is included."""
    e = ind["ema20"]
    return (df["AdjClose"] > e).astype(int).where(e.notna(), 0).astype(int)


def sig_rsi_velocity(df, ind) -> pd.Series:
    """RSI velocity framing (re-derived Multi_Agent concept): long while RSI is rising
    over 5 sessions AND above 50."""
    cond = (ind["rsi_diff5"] > 0) & (ind["rsi14"] > 50)
    return cond.astype(int).where(ind["rsi_diff5"].notna(), 0).astype(int)


def sig_rsi_zscore60(df, ind) -> pd.Series:
    """RSI 60-day z-score framing (re-derived Multi_Agent concept): long while RSI is
    above its own 60-session average (z > 0)."""
    z = ind["rsi_zscore_60"]
    return (z > 0).astype(int).where(z.notna(), 0).astype(int)


def sig_rsi_bull_div(df, ind) -> pd.Series:
    """Bullish-divergence entry (re-derived), exit when RSI recovers above 60."""
    div = ind["rsi_bull_div"].to_numpy()
    r = ind["rsi14"].to_numpy()
    out = np.zeros(len(r), dtype=int)
    state = 0
    for i in range(len(r)):
        if not np.isfinite(r[i]):
            out[i], state = 0, 0
            continue
        if state == 0 and div[i] == 1.0:
            state = 1
        elif state == 1 and r[i] > 60:
            state = 0
        out[i] = state
    return pd.Series(out, index=df.index)


RSI_RULES: Dict[str, Callable] = {
    "rsi_30_70_meanrev": sig_rsi_30_70_meanrev,
    "rsi_30_50_meanrev (Phase 3's original)": sig_rsi_30_50_meanrev,
    "rsi_50_momentum": sig_rsi_50_momentum,
    "rsi_60_40_range  <-- requested": sig_rsi_60_40_range,
    "rsi_above_40_bullrange": sig_rsi_above_40,
    "rsi_60_40 + EMA20": sig_rsi_60_40_plus_ema20,
    "rsi_60_40 + EMA20 + EMA50": sig_rsi_60_40_plus_ema20_50,
    "EMA20_only (CONTROL, no RSI)": sig_ema20_only,
    "rsi_velocity_5d": sig_rsi_velocity,
    "rsi_zscore_60": sig_rsi_zscore60,
    "rsi_bull_divergence": sig_rsi_bull_div,
}


# ======================================================================================
# Backtest harness
# ======================================================================================

def backtest_rule(fn: Callable, start: str, end: str = DEV_END,
                   cost_pct: float = COST_PCT) -> dict:
    """cost_pct defaults to the frozen-spec 0.35%/round trip. A 0.0 run is ALSO reported
    below as a diagnostic, at the user's request (9 Oct 2026) -- but it does NOT replace
    the costed number, and the frozen spec is unchanged. Reason, stated plainly: the
    0% figure is not a result you could ever achieve in a real account (0.25% of the
    0.35% is verified Zerodha brokerage/STT/exchange charges, which are not optional),
    so reporting it as the headline would be reporting a number that cannot happen.
    Its diagnostic VALUE is real though: comparing the two columns isolates how much of
    each rule's shortfall is cost drag versus simply not having enough signal. Note the
    benchmark pays costs on the same basis in each column, so the comparison stays fair
    -- zeroing costs helps buy-and-hold too (it pays one round trip)."""
    daily_list, label_rows, n_trips = [], [], 0
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=start, end=end)
        ind = rsi_frame(df)
        sig = fn(df, ind)
        res = bt.backtest_signal(df, sig, cost_pct=cost_pct)
        daily_list.append(res["daily_net"].rename(sym))
        n_trips += res["n_round_trips"]
        ls = m24.label_scores(sym, sig)
        if ls:
            label_rows.append(ls)
    port_daily = pd.concat(daily_list, axis=1).mean(axis=1)
    m = bt.performance_metrics((1.0 + port_daily).cumprod())
    lab = pd.DataFrame(label_rows)
    return {
        "cagr": m.get("cagr"), "sharpe": m.get("sharpe"), "max_dd": m.get("max_drawdown"),
        "n_round_trips": n_trips,
        "up_precision": float(lab["up_precision"].mean()) if len(lab) else float("nan"),
        "up_lift": float(lab["up_lift"].mean()) if len(lab) else float("nan"),
        "up_base_rate": float(lab["up_base_rate"].mean()) if len(lab) else float("nan"),
        "n_long_calls": int(lab["n_long_calls"].sum()) if len(lab) else 0,
        "n_labels": int(lab["n_labels"].sum()) if len(lab) else 0,
    }


def _check_causality(check) -> None:
    """Truncating history must not change any already-computed RSI feature value."""
    for sym in ["ITC", "TATASTEEL"]:
        df = bt.dev_window(bt.load_clean(sym), start=DEV_START, end=DEV_END)
        full = rsi_frame(df)
        cut_i = 400
        cut_date = df.index[cut_i]
        trunc = rsi_frame(df.iloc[: cut_i + 1])
        row_f, row_t = full.loc[cut_date], trunc.loc[cut_date]
        same = all(
            (pd.isna(row_f[c]) and pd.isna(row_t[c])) or np.isclose(row_f[c], row_t[c], equal_nan=True)
            for c in full.columns
        )
        check(f"{sym}: every RSI-derived feature is causal (truncated recompute matches)",
              same, f"mismatch at {cut_date.date()}")


def freeze_rsi_features(symbols: Optional[Sequence[str]] = None) -> None:
    """Write the RSI feature class out so the model scripts can train a specialist on
    it, same pattern as data/features_sector and data/features_longterm."""
    symbols = list(symbols or PILOT_SYMBOLS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["rsi14", "rsi_diff1", "rsi_diff5", "rsi_zscore_30", "rsi_zscore_60",
            "rsi_range_regime", "rsi_above_60", "rsi_below_40", "rsi_rel_pos_10",
            "rsi_bull_div", "rsi_bear_div", "dist_ema20_pct", "dist_ema50_pct"]
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), start=DEV_START, end=DEV_END)
        ind = rsi_frame(df)[cols].copy()
        ind.insert(0, "date", df.index)
        ind["symbol"] = sym
        ind.to_csv(OUT_DIR / f"{sym}.csv", index=False)


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

    print("=" * 100)
    print("24_rsi_strategy_study.py -- Phase 3.8: every documented RSI usage, measured")
    print("=" * 100)

    _check_causality(check)

    # Benchmarks for BOTH windows, so each rule is judged against the right bar.
    bars = {}
    for label, start, cpct in (("FULL DEV (2015+), 0.35% costs", DEV_START, COST_PCT),
                                ("FULL DEV (2015+), ZERO costs", DEV_START, 0.0),
                                ("OOS (2018+), 0.35% costs", OOS_START, COST_PCT)):
        bench = bt.buy_and_hold(bt.dev_window(bt.load_clean(BENCHMARK), start=start, end=DEV_END),
                                 cost_pct=cpct)
        bh_daily = [bt.buy_and_hold(bt.dev_window(bt.load_clean(s), start=start, end=DEV_END),
                                     cost_pct=cpct)["daily_net"].rename(s) for s in PILOT_SYMBOLS]
        bh_port = bt.performance_metrics((1.0 + pd.concat(bh_daily, axis=1).mean(axis=1)).cumprod())
        bars[label] = {"nifty_sharpe": bench["metrics"].get("sharpe"),
                        "bh8_sharpe": bh_port.get("sharpe"),
                        "nifty_cagr": bench["metrics"].get("cagr"),
                        "bh8_cagr": bh_port.get("cagr")}
        print(f"\nBar to beat, {label}: NIFTY100 b&h Sharpe {bars[label]['nifty_sharpe']:.4f} "
              f"(CAGR {bars[label]['nifty_cagr']:.4f}) | equal-weight 8-symbol b&h Sharpe "
              f"{bars[label]['bh8_sharpe']:.4f} (CAGR {bars[label]['bh8_cagr']:.4f})")

    rows = []
    for name, fn in RSI_RULES.items():
        full = backtest_rule(fn, start=DEV_START)
        full0 = backtest_rule(fn, start=DEV_START, cost_pct=0.0)
        oos = backtest_rule(fn, start=OOS_START)
        rows.append({
            "rule": name,
            "full_sharpe": full["sharpe"], "full_cagr": full["cagr"], "full_max_dd": full["max_dd"],
            "zerocost_sharpe": full0["sharpe"], "zerocost_cagr": full0["cagr"],
            "cost_drag_sharpe": (full0["sharpe"] - full["sharpe"]),
            "n_round_trips": full["n_round_trips"],
            "oos_sharpe": oos["sharpe"], "oos_cagr": oos["cagr"],
            "up_precision": full["up_precision"], "up_base_rate": full["up_base_rate"],
            "up_lift": full["up_lift"], "n_long_calls": full["n_long_calls"],
        })

    table = pd.DataFrame(rows).sort_values("full_sharpe", ascending=False)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(REPORTS_DIR / "checkpoint_3_8_rsi_rule_study.csv", index=False)

    pd.set_option("display.width", 250)
    show = table.copy()
    for c in ["full_sharpe", "full_cagr", "full_max_dd", "zerocost_sharpe", "zerocost_cagr",
              "cost_drag_sharpe", "oos_sharpe", "oos_cagr", "up_precision", "up_base_rate", "up_lift"]:
        show[c] = show[c].astype(float).round(4)
    print(f"\n--- Every RSI framing as a standalone long/cash rule ---")
    print("(up_precision = how often a long call coincided with a real 'Up' label; "
          "up_lift = that precision / the Up base rate, so 1.00 = no edge.")
    print(" full_* = frozen-spec 0.35%/round-trip costs. zerocost_* = the same rule with "
          "costs set to 0, as a diagnostic only -- NOT achievable in a real account.)")
    print(show[["rule", "full_sharpe", "zerocost_sharpe", "cost_drag_sharpe", "n_round_trips",
                "full_cagr", "zerocost_cagr", "full_max_dd", "oos_sharpe", "up_precision",
                "up_lift"]].to_string(index=False))

    # The honest question the zero-cost run exists to answer.
    bh0 = bars["FULL DEV (2015+), ZERO costs"]["bh8_sharpe"]
    best0_row = table.loc[table["zerocost_sharpe"].astype(float).idxmax()]
    print(f"\n--- Does removing costs fix it? (the user's hypothesis) ---")
    print(f"Best rule at ZERO cost: {best0_row['rule']} Sharpe {float(best0_row['zerocost_sharpe']):.4f}")
    print(f"Buy-and-hold at ZERO cost: Sharpe {bh0:.4f}")
    if float(best0_row["zerocost_sharpe"]) > bh0:
        print("-> At zero cost the best rule DOES beat buy-and-hold, so cost drag is a real "
              "part of the gap. It is still not a result you can trade: 0.25% of the 0.35% "
              "is verified, non-optional brokerage/STT/exchange charges.")
    else:
        print("-> Even at ZERO cost the best rule still does NOT beat buy-and-hold. So costs "
              "were NOT what was holding these rules back -- removing them changes the "
              "numbers but not the conclusion. The shortfall is signal, not fees.")
    print(f"Mean cost drag across all {len(table)} rules: "
          f"{table['cost_drag_sharpe'].astype(float).mean():.4f} Sharpe "
          f"(median {table['cost_drag_sharpe'].astype(float).median():.4f}).")

    # Gated checks -- real questions, answerable either way.
    best = table.iloc[0]
    ema_control = table.loc[table["rule"] == "EMA20_only (CONTROL, no RSI)"].iloc[0]
    range_rule = table.loc[table["rule"] == "rsi_60_40_range  <-- requested"].iloc[0]
    orig = table.loc[table["rule"] == "rsi_30_50_meanrev (Phase 3's original)"].iloc[0]

    print(f"\n--- The questions that actually matter ---")
    print(f"1. Does the 60/40 range rule beat Phase 3's original mean-reversion framing? "
          f"{range_rule['full_sharpe']:.4f} vs {orig['full_sharpe']:.4f} -> "
          f"{'YES' if range_rule['full_sharpe'] > orig['full_sharpe'] else 'NO'}")
    print(f"2. Does the best RSI rule beat the plain EMA20 control (i.e. does RSI add anything "
          f"over a simple moving average)? best={best['rule']} {best['full_sharpe']:.4f} vs "
          f"EMA20-only {ema_control['full_sharpe']:.4f} -> "
          f"{'YES' if best['full_sharpe'] > ema_control['full_sharpe'] else 'NO'}")
    print(f"3. Does any RSI rule beat buy-and-hold (full dev window, Sharpe "
          f"{bars["FULL DEV (2015+), 0.35% costs"]["bh8_sharpe"]:.4f})? -> "
          f"{'YES' if best['full_sharpe'] > bars["FULL DEV (2015+), 0.35% costs"]["bh8_sharpe"] else 'NO'}")

    check("the 60/40 range rule beats Phase 3's original 30/50 mean-reversion framing "
          "(the user's hypothesis that RSI was being used too narrowly)",
          range_rule["full_sharpe"] > orig["full_sharpe"],
          f"60/40 {range_rule['full_sharpe']:.4f} vs 30/50 {orig['full_sharpe']:.4f}")
    check("at least one RSI framing shows real 'Up'-label lift (> 1.05) rather than none at all",
          table["up_lift"].max() > 1.05, f"best lift {table['up_lift'].max():.4f}")

    freeze_rsi_features()
    print(f"\nwrote data/features_rsi/<symbol>.csv (13 RSI-derived features, for the "
          f"specialist-model comparison in 25_rsi_fusion.py)")
    print(f"wrote reports/phase3/checkpoint_3_8_rsi_rule_study.csv")
    print("\n" + "-" * 100)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 100)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
