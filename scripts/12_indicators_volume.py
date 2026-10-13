"""
12_indicators_volume.py -- Phase 3, volume family (OBV, volume-weighted price moves,
Accumulation/Distribution line). Entirely new -- no existing baseline uses volume at
all, so there is nothing from 06_baselines to cross-check against here.

Same structure/checkpoints as 09/10/11 -- see 09's docstring for the full rationale.

Checkpoint 3.1: OBV and AD are taken directly from TA-Lib (stated assumption, no second
implementation). "Volume-weighted price move" (vwpm) is NOT a TA-Lib function -- it is
defined here explicitly: a rolling, volume-weighted average of daily returns, so its
formula is given in full rather than referenced, since there is no reference to check
it against.

Checkpoint 3.2: leak test via truncation -- the one that matters most for OBV, since
it's a cumulative running sum and a bug could silently use the wrong starting point
after truncation.

Checkpoint 3.3: OBV-trend, A/D-trend and a volume-confirmation filter through the
engine, dev window, 8 pilot symbols.

Open data-quality note, stated rather than hidden: AdjVolume has 0 NaNs across the 8
pilot symbols (checked directly), but 7 genuine phantom/ffill sessions exist per the
Phase 2.2 Tradeable flag (flat O=H=L=C AND zero volume) -- those sessions report
AdjVolume=0 by construction and OBV/AD correctly treat that as "no net flow," not an
error, which is the intended behavior.
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

OBV_TREND_WINDOW = 20   # OBV vs its own N-day EMA, for the trend vote/rule
VWPM_WINDOW = 20


def vol_weighted_price_move(close: pd.Series, volume: pd.Series, window: int = VWPM_WINDOW) -> pd.Series:
    """Rolling volume-weighted average of daily returns over `window` sessions:
    sum(ret_i * vol_i) / sum(vol_i) for i in the trailing window, using only data
    through t (a plain rolling window is causal by construction -- no shift needed).
    Positive means recent up-moves carried more volume than down-moves; this is a
    custom feature (not a textbook-named indicator), defined fully here since there is
    no external formula to point to."""
    ret = close.pct_change()
    weighted = (ret * volume)
    num = weighted.rolling(window, min_periods=window).sum()
    den = volume.rolling(window, min_periods=window).sum()
    return num / den.replace(0.0, np.nan)


def compute_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    h, l, c, v = (df["AdjHigh"].to_numpy(dtype=float), df["AdjLow"].to_numpy(dtype=float),
                  df["AdjClose"].to_numpy(dtype=float), df["AdjVolume"].to_numpy(dtype=float))
    obv = talib.OBV(c, v)
    ad = talib.AD(h, l, c, v)
    obv_s = pd.Series(obv, index=df.index)
    obv_ema = obv_s.ewm(span=OBV_TREND_WINDOW, adjust=False, min_periods=OBV_TREND_WINDOW).mean()
    vwpm = vol_weighted_price_move(df["AdjClose"], df["AdjVolume"])
    out = pd.DataFrame({
        "obv": obv, "obv_ema20": obv_ema.to_numpy(),
        "ad": ad, "vwpm20": vwpm.to_numpy(),
    }, index=df.index)
    out["close"] = c
    return out


def votes(ind: pd.DataFrame) -> pd.DataFrame:
    v = pd.DataFrame(index=ind.index)
    v["vote_obv_trend"] = np.select(
        [ind["obv"] > ind["obv_ema20"], ind["obv"] < ind["obv_ema20"]], [1, -1], default=0)
    v.loc[ind["obv_ema20"].isna(), "vote_obv_trend"] = 0
    # AD trend: rising vs falling over a short lookback (AD has no natural zero line).
    ad_diff = ind["ad"].diff(OBV_TREND_WINDOW)
    v["vote_ad_trend"] = np.select([ad_diff > 0, ad_diff < 0], [1, -1], default=0)
    v.loc[ad_diff.isna(), "vote_ad_trend"] = 0
    v["vote_vwpm"] = np.select(
        [ind["vwpm20"] > 0, ind["vwpm20"] < 0], [1, -1], default=0)
    v.loc[ind["vwpm20"].isna(), "vote_vwpm"] = 0
    return v


def sig_obv_trend(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """Long while OBV is above its own 20-session EMA (net volume flow trending up)."""
    cond = (ind["obv"] > ind["obv_ema20"]) & ind["obv_ema20"].notna()
    return cond.astype(int)


def sig_ad_trend(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """Long while the A/D line has risen over the trailing 20 sessions."""
    ad_diff = ind["ad"].diff(OBV_TREND_WINDOW)
    cond = (ad_diff > 0) & ad_diff.notna()
    return cond.astype(int)


def sig_vwpm_positive(df: pd.DataFrame, ind: pd.DataFrame) -> pd.Series:
    """Long while the rolling volume-weighted price move is positive."""
    cond = (ind["vwpm20"] > 0) & ind["vwpm20"].notna()
    return cond.astype(int)


FAMILY_SIGNALS = {
    "vol_obv_trend": sig_obv_trend,
    "vol_ad_trend": sig_ad_trend,
    "vol_vwpm20": sig_vwpm_positive,
}


def _check_sanity(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.1: sanity (OBV/AD taken directly from TA-Lib -- stated "
          "assumption; vwpm is a custom feature, checked against a brute-force "
          "re-computation of its own definition) ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        ind = compute_volume_indicators(df)
        # Brute-force cross-check of vwpm at one arbitrary interior point.
        i = len(df) - 500
        ret = df["AdjClose"].pct_change()
        window = ret.iloc[i - VWPM_WINDOW + 1:i + 1]
        vol_window = df["AdjVolume"].iloc[i - VWPM_WINDOW + 1:i + 1]
        brute = float((window * vol_window).sum() / vol_window.sum())
        vectorised = float(ind["vwpm20"].iloc[i])
        ok = bool(np.isclose(brute, vectorised, rtol=1e-9))
        check(f"{sym}: vwpm20 brute-force recomputation at one interior point matches the vectorised result",
              ok, f"brute {brute:.8f} vs vectorised {vectorised:.8f}")
        finite_obv = np.isfinite(ind["obv"].to_numpy())
        check(f"{sym}: OBV is finite for all defined sessions",
              bool(finite_obv.all()), f"{int((~finite_obv).sum())} non-finite")


def _check_leak(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.2: leak test (OBV is a cumulative sum -- the riskiest case "
          "for a silent truncation bug) ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        full = compute_volume_indicators(df)
        cut = len(df) // 2
        head = df.iloc[:cut]
        trunc = compute_volume_indicators(head)
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
        ind = compute_volume_indicators(df)
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
    per_sym.to_csv(REPORTS_DIR / "checkpoint_3_1_3_volume_per_symbol.csv", index=False)
    port.to_csv(REPORTS_DIR / "checkpoint_3_3_volume_portfolio.csv", index=False)
    all_votes.to_csv(REPORTS_DIR / "volume_votes.csv", index=False)
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
    print("12_indicators_volume.py -- Phase 3: volume family")
    print("=" * 78)

    _check_sanity(check, symbols)
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

    print(f"\nwrote reports/phase3/checkpoint_3_1_3_volume_per_symbol.csv")
    print(f"wrote reports/phase3/checkpoint_3_3_volume_portfolio.csv")
    print(f"wrote reports/phase3/volume_votes.csv")
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
