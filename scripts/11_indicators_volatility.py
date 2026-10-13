"""
11_indicators_volatility.py -- Phase 3, volatility family (ATR-normalized range,
Bollinger Bands, Keltner Channels).

Same structure/checkpoints as 09/10 -- see 09's docstring for the full rationale.

Note on ATR: ATR(14) already exists and is frozen as the *label-generating* indicator
(triple-barrier target/stop, Phase 2.1 -- do not touch that use). Here ATR is reused
only as an input feature (ATR-normalized range = ATR / Close, a volatility-regime
measure), a different and separate use from the label barriers. Keeping the same
TA-Lib ATR(14) for both is intentional consistency, not an accidental coupling -- stated
plainly since the project rule is to label every assumption.

Checkpoint 3.1: all three (ATR, Bollinger, Keltner) are taken directly from TA-Lib / a
direct TA-Lib-ATR-based formula -- stated assumption, no second implementation. Keltner
is not a native TA-Lib function (TA-Lib has no KELTNER call); it is built here from
TA-Lib's own EMA and ATR, so it is not an independent re-derivation of those two, only a
combination of them.

Checkpoint 3.2: leak test via truncation.

Checkpoint 3.3: Bollinger mean-reversion rule and Keltner breakout rule through the
engine, dev window, 8 pilot symbols. ATR itself is not turned into a standalone trading
rule here (it is a regime filter/feature, not a directional signal) -- its vote column
instead flags "high volatility regime" (expanding range), which is informational only.
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

ATR_PERIOD = 14
BB_PERIOD, BB_NSTD = 20, 2.0
KC_EMA_PERIOD, KC_ATR_MULT = 20, 2.0
ATR_PCT_LOOKBACK = 252  # for the "high-vol regime" vote, relative to trailing 1y range


def compute_vol_indicators(df: pd.DataFrame) -> pd.DataFrame:
    h, l, c = (df["AdjHigh"].to_numpy(dtype=float), df["AdjLow"].to_numpy(dtype=float),
               df["AdjClose"].to_numpy(dtype=float))
    atr14 = talib.ATR(h, l, c, timeperiod=ATR_PERIOD)
    atr_pct = atr14 / c  # ATR normalized by price -- the actual feature, not raw ATR

    upper, mid, lower = talib.BBANDS(c, timeperiod=BB_PERIOD, nbdevup=BB_NSTD,
                                     nbdevdn=BB_NSTD, matype=0)

    ema20 = talib.EMA(c, timeperiod=KC_EMA_PERIOD)
    kc_upper = ema20 + KC_ATR_MULT * atr14
    kc_lower = ema20 - KC_ATR_MULT * atr14

    out = pd.DataFrame({
        "atr14": atr14, "atr_pct": atr_pct,
        "bb_upper": upper, "bb_mid": mid, "bb_lower": lower,
        "kc_upper": kc_upper, "kc_mid": ema20, "kc_lower": kc_lower,
    }, index=df.index)
    out["close"] = c
    return out


def votes(ind: pd.DataFrame) -> pd.DataFrame:
    v = pd.DataFrame(index=ind.index)
    # Bollinger: price below lower band -> oversold Up vote; above upper -> Down vote.
    v["vote_bb"] = np.select(
        [ind["close"] < ind["bb_lower"], ind["close"] > ind["bb_upper"]], [1, -1], default=0)
    v.loc[ind["bb_lower"].isna() | ind["bb_upper"].isna(), "vote_bb"] = 0
    # Keltner: breakout framing (opposite sense to Bollinger's mean-reversion) -- price
    # above upper channel -> Up vote (breakout continuation), below lower -> Down vote.
    v["vote_kc_breakout"] = np.select(
        [ind["close"] > ind["kc_upper"], ind["close"] < ind["kc_lower"]], [1, -1], default=0)
    v.loc[ind["kc_upper"].isna() | ind["kc_lower"].isna(), "vote_kc_breakout"] = 0
    # ATR regime: not directional -- 1 means "currently in the top quartile of its own
    # trailing-1y ATR% range" (high-volatility regime), 0 otherwise. Informational only.
    atr_pctile = ind["atr_pct"].rolling(ATR_PCT_LOOKBACK, min_periods=60).rank(pct=True)
    v["vote_high_vol_regime"] = (atr_pctile > 0.75).astype(int)
    v.loc[ind["atr_pct"].isna(), "vote_high_vol_regime"] = 0
    return v


def sig_bb_meanreversion(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """Long when price closes below the lower Bollinger band, exit back to flat once
    price recovers to the middle band -- textbook mean-reversion state machine."""
    close = ind["close"].to_numpy()
    lower = ind["bb_lower"].to_numpy()
    mid = ind["bb_mid"].to_numpy()
    out = np.zeros(len(close), dtype=int)
    state = 0
    for i in range(len(close)):
        if not (np.isfinite(lower[i]) and np.isfinite(mid[i])):
            out[i] = 0
            state = 0
            continue
        if state == 0 and close[i] < lower[i]:
            state = 1
        elif state == 1 and close[i] > mid[i]:
            state = 0
        out[i] = state
    return pd.Series(out, index=df.index)


def sig_kc_breakout(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """Long while price is above the Keltner upper channel, exit back to flat once it
    falls back below the midline -- breakout/continuation framing (opposite logic to
    Bollinger mean-reversion, deliberately, since the two represent different theories
    of what a band touch means)."""
    close = ind["close"].to_numpy()
    upper = ind["kc_upper"].to_numpy()
    mid = ind["kc_mid"].to_numpy()
    out = np.zeros(len(close), dtype=int)
    state = 0
    for i in range(len(close)):
        if not (np.isfinite(upper[i]) and np.isfinite(mid[i])):
            out[i] = 0
            state = 0
            continue
        if state == 0 and close[i] > upper[i]:
            state = 1
        elif state == 1 and close[i] < mid[i]:
            state = 0
        out[i] = state
    return pd.Series(out, index=df.index)


FAMILY_SIGNALS = {
    "vol_bb_20_2_meanrev": sig_bb_meanreversion,
    "vol_kc_20_2_breakout": sig_kc_breakout,
}


def _check_atr_sanity(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.1: ATR sanity ---")
    print("NOTE: could not cross-check against 03_labels.py's own ATR in this sandbox -- "
          "that module imports scripts/02a_build_corp_actions.py, which is not present "
          "here (only on the user's PC). This is an environment gap, not a result; "
          "flagged rather than skipped silently. Falling back to a sanity check: ATR14 "
          "must be finite and strictly positive wherever defined, and TA-Lib's ATR (Wilder "
          "RMA of True Range) is the same well-known formula the label pipeline's docstring "
          "describes ('Wilder-style True Range / simple rolling ATR'), so this is a real but "
          "weaker check than exact-value equality.")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        ours = compute_vol_indicators(df)["atr14"].to_numpy()
        finite = ours[np.isfinite(ours)]
        check(f"{sym}: ATR14 is finite and strictly positive wherever defined",
              bool(len(finite) > 0 and np.all(finite > 0)), "non-positive or empty ATR found")
    print("Bollinger/Keltner bands are TA-Lib EMA/stdev combinations -- stated "
          "assumption, not independently re-derived here.")


def _check_leak(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.2: leak test ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        full = compute_vol_indicators(df)
        cut = len(df) // 2
        head = df.iloc[:cut]
        trunc = compute_vol_indicators(head)
        for col in [c for c in full.columns if c != "close"]:
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
        ind = compute_vol_indicators(df)
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
    per_sym.to_csv(REPORTS_DIR / "checkpoint_3_1_3_volatility_per_symbol.csv", index=False)
    port.to_csv(REPORTS_DIR / "checkpoint_3_3_volatility_portfolio.csv", index=False)
    all_votes.to_csv(REPORTS_DIR / "volatility_votes.csv", index=False)
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
    print("11_indicators_volatility.py -- Phase 3: volatility family")
    print("=" * 78)

    _check_atr_sanity(check, symbols)
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
          "buy_and_hold Sharpe 1.02, momentum_252d 0.84, macd_12_26_9 0.47, "
          "rsi_14_30_50 0.14.)")

    for name in FAMILY_SIGNALS:
        r = port.loc[port["strategy"] == name].iloc[0]
        check(f"{name}: produced a finite, costed result",
              np.isfinite(r["cagr"]) and np.isfinite(r["sharpe"]),
              f"cagr {r['cagr']}, sharpe {r['sharpe']}")
    tot_trips = per_sym.loc[:, "n_round_trips"].sum()
    check("the family's rules actually traded (so their costs are real)",
          tot_trips > 100, f"{tot_trips} round trips")

    print(f"\nwrote reports/phase3/checkpoint_3_1_3_volatility_per_symbol.csv")
    print(f"wrote reports/phase3/checkpoint_3_3_volatility_portfolio.csv")
    print(f"wrote reports/phase3/volatility_votes.csv")
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
