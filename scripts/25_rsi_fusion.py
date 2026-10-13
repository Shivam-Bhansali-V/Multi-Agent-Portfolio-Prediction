"""
25_rsi_fusion.py -- Phase 4.8: integrate the two things that actually worked.

Where this comes from, in order:
  - checkpoint 4.7 (23_family_specialist_comparison.py): of six indicator classes
    modelled separately, only VOLATILITY (ATR/Bollinger/Keltner) produced a
    meaningfully positive backtest (Sharpe 0.53 OOS). Momentum/trend/volume/sector
    were all negative standalone, and fusing all 45 features DILUTED volatility
    (fused Sharpe 0.18 < volatility-alone 0.53).
  - checkpoint 3.8 (24_rsi_strategy_study.py): RSI used in the 60/40 RANGE framing
    (the user's suggestion) scores Sharpe 0.72 full-dev / 0.74 OOS, and the simpler
    "RSI >= 40 = bull range intact" rule scores 0.83 full-dev -- versus 0.14 for
    Phase 3's original 30/50 mean-reversion framing, and 0.25 for a plain EMA20
    control. So RSI, used as a TREND/REGIME tool rather than an overbought-oversold
    oscillator, is the single best-performing signal in this project so far.

So this script tests the obvious combination, and tests it honestly -- three ways of
putting them together, not one, because "which way" is an empirical question:
  A) RSI-FEATURES specialist model (13 re-derived RSI features, one model).
  B) VOLATILITY + RSI features fused into one model (small, deliberate fusion --
     NOT all 45 features, which 4.7 showed dilutes).
  C) RULE-GATED model: take the volatility specialist's BUY decisions and keep only
     those where the RSI 60/40 range rule ALSO says the bull range is intact. This is
     the "how to make the decision using both of them" integration -- a model and a
     rule as two independent conditions, rather than mixing their inputs.
  D) The RSI rule alone, and the volatility model alone, as the references any
     combination must beat to justify its extra complexity.

COSTS -- three levels, after the user asked to see 0%:
  0.35% = frozen spec (0.25% verified Zerodha charges + 0.10% assumed slippage)
  0.25% = verified charges only, zero slippage. This is the genuinely OPTIMISTIC
          but still REAL floor -- brokerage, STT and exchange fees are not optional.
  0.00% = diagnostic only. Not achievable in any real account. Included because it
          isolates how much of a shortfall is cost drag vs. missing signal, and
          because 3.8 showed that answer differs sharply by rule (a 1786-round-trip
          rule bled 1.17 Sharpe to costs; a 69-round-trip rule bled 0.03).
The benchmark pays the same cost level in every column, so no column is rigged.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase4"
RSI_DIR = ROOT / "data" / "features_rsi"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m41 = _load("15_model_logreg_floor")
m46 = _load("22_model_expanded")
m47 = _load("23_family_specialist_comparison")
m38 = _load("24_rsi_strategy_study")
bt = _load("04_backtest")

CLASSES = m41.CLASSES
FOLD_TEST_RANGES = m41.FOLD_TEST_RANGES
PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
OOS_START = pd.Timestamp(FOLD_TEST_RANGES[0][0])
OOS_END = pd.Timestamp(FOLD_TEST_RANGES[-1][1])
COST_LEVELS = {"0.35% (frozen spec)": 0.0035, "0.25% (verified charges only)": 0.0025,
                "0.00% (diagnostic only)": 0.0}

RSI_FEATURE_COLS = ["rsi14", "rsi_diff1", "rsi_diff5", "rsi_zscore_30", "rsi_zscore_60",
                     "rsi_range_regime", "rsi_above_60", "rsi_below_40", "rsi_rel_pos_10",
                     "rsi_bull_div", "rsi_bear_div", "dist_ema20_pct", "dist_ema50_pct"]
VOLATILITY_COLS = m47.FAMILY_GROUPS["volatility"]


def attach_all(labels: pd.DataFrame):
    data, expanded_cols, n_lost, n_warm = m46.attach_expanded_features(labels)
    rsi_frames = [pd.read_csv(RSI_DIR / f"{s}.csv", parse_dates=["date"]) for s in PILOT_SYMBOLS]
    rsi_all = pd.concat(rsi_frames, ignore_index=True)[["symbol", "date"] + RSI_FEATURE_COLS]
    data = data.merge(rsi_all, on=["symbol", "date"], how="left")
    return data, expanded_cols, n_lost


def rsi_rule_signals() -> pd.DataFrame:
    """The RSI 60/40 range rule's long/flat state per symbol/date, as a lookup table so
    it can gate a model's decisions. Computed by the same function 3.8 backtested, so
    the gate is exactly the rule that scored 0.72/0.74 -- not a re-implementation."""
    rows = []
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=str(OOS_START.date()), end=str(OOS_END.date()))
        ind = m38.rsi_frame(df)
        sig = m38.sig_rsi_60_40_range(df, ind)
        rows.append(pd.DataFrame({"symbol": sym, "date": df.index, "rsi_gate": sig.to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def backtest_signal_table(sig_table: pd.DataFrame, cost_pct: float) -> dict:
    """sig_table: columns symbol, date, signal (0/1). Equal-weight 8-symbol portfolio."""
    daily, n_trips = [], 0
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=str(OOS_START.date()), end=str(OOS_END.date()))
        s = sig_table.loc[sig_table["symbol"] == sym].set_index("date")["signal"]
        sig = s.reindex(df.index).fillna(0).astype(int)
        res = bt.backtest_signal(df, sig, cost_pct=cost_pct)
        daily.append(res["daily_net"].rename(sym))
        n_trips += res["n_round_trips"]
    port = pd.concat(daily, axis=1).mean(axis=1)
    m = bt.performance_metrics((1.0 + port).cumprod())
    return {"sharpe": m.get("sharpe"), "cagr": m.get("cagr"), "max_dd": m.get("max_drawdown"),
            "n_round_trips": n_trips, "daily": port}


def model_signal_table(data: pd.DataFrame, feat_cols: List[str]) -> pd.DataFrame:
    preds = m47.build_predictions_with_symbol_date(data, [c for c in feat_cols if c in data.columns])
    preds["decision"] = preds.apply(m47.make_decision, axis=1)
    preds["signal"] = (preds["decision"] == "BUY").astype(int)
    return preds[["symbol", "date", "signal", "decision", "raw_pred", "cal_proba_up"]]


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

    print("=" * 110)
    print("25_rsi_fusion.py -- Phase 4.8: volatility class + RSI, three ways of combining")
    print("=" * 110)

    labels, calendar = m41.build_pooled_labels()
    data, expanded_cols, n_lost = attach_all(labels)
    check("every kept label has a matching feature row", n_lost == 0, f"{n_lost} unmatched")
    check("RSI features merged onto the pooled table",
          data["rsi_range_regime"].notna().any(), "all NaN")

    gate = rsi_rule_signals()
    candidates: Dict[str, pd.DataFrame] = {}
    macro_f1s: Dict[str, float] = {}

    # --- A) RSI-features specialist model ---
    out = m47.run_folds(data, RSI_FEATURE_COLS)
    macro_f1s["A) RSI-features model"] = f1_score(out["pooled_true"], out["pooled_pred"],
                                                   average="macro", labels=CLASSES, zero_division=0)
    candidates["A) RSI-features model"] = model_signal_table(data, RSI_FEATURE_COLS)

    # --- B) volatility + RSI features, one small fused model ---
    vol_rsi_cols = VOLATILITY_COLS + RSI_FEATURE_COLS
    out = m47.run_folds(data, [c for c in vol_rsi_cols if c in data.columns])
    macro_f1s["B) volatility+RSI fused model"] = f1_score(out["pooled_true"], out["pooled_pred"],
                                                            average="macro", labels=CLASSES, zero_division=0)
    candidates["B) volatility+RSI fused model"] = model_signal_table(data, vol_rsi_cols)

    # --- D-ref) volatility-only model (4.7's best) ---
    out = m47.run_folds(data, VOLATILITY_COLS)
    macro_f1s["D1) volatility-only model (4.7 best)"] = f1_score(out["pooled_true"], out["pooled_pred"],
                                                                   average="macro", labels=CLASSES, zero_division=0)
    vol_only = model_signal_table(data, VOLATILITY_COLS)
    candidates["D1) volatility-only model (4.7 best)"] = vol_only

    # --- C) RULE-GATED: volatility model BUY *and* RSI 60/40 range rule says bull intact ---
    gated = vol_only.merge(gate, on=["symbol", "date"], how="left")
    gated["rsi_gate"] = gated["rsi_gate"].fillna(0).astype(int)
    gated["signal"] = (gated["signal"].astype(int) & gated["rsi_gate"]).astype(int)
    candidates["C) volatility model GATED by RSI 60/40 rule"] = gated[["symbol", "date", "signal"]]
    macro_f1s["C) volatility model GATED by RSI 60/40 rule"] = float("nan")  # not a pure classifier

    # --- D2) the RSI 60/40 rule alone, on the same OOS window ---
    rule_only = gate.rename(columns={"rsi_gate": "signal"})
    candidates["D2) RSI 60/40 rule alone (no model)"] = rule_only
    macro_f1s["D2) RSI 60/40 rule alone (no model)"] = float("nan")

    # ---- Score every candidate at every cost level ----
    rows = []
    for name, sig_table in candidates.items():
        row = {"strategy": name, "macro_f1": macro_f1s.get(name, float("nan"))}
        for cost_label, cpct in COST_LEVELS.items():
            r = backtest_signal_table(sig_table[["symbol", "date", "signal"]], cpct)
            row[f"sharpe @ {cost_label}"] = r["sharpe"]
            row[f"cagr @ {cost_label}"] = r["cagr"]
            if cpct == 0.0035:
                row["max_dd"] = r["max_dd"]
                row["n_round_trips"] = r["n_round_trips"]
                row["exposure_buy_days"] = int(sig_table["signal"].sum())
        rows.append(row)

    # ---- Baselines at every cost level ----
    for bench_name, syms in (("REFERENCE: buy_and_hold_8symbol", PILOT_SYMBOLS),
                              ("REFERENCE: NIFTY100_buy_and_hold", [BENCHMARK])):
        row = {"strategy": bench_name, "macro_f1": float("nan")}
        for cost_label, cpct in COST_LEVELS.items():
            daily = [bt.buy_and_hold(bt.dev_window(bt.load_clean(s), start=str(OOS_START.date()),
                      end=str(OOS_END.date())), cost_pct=cpct)["daily_net"].rename(s) for s in syms]
            m = bt.performance_metrics((1.0 + pd.concat(daily, axis=1).mean(axis=1)).cumprod())
            row[f"sharpe @ {cost_label}"] = m.get("sharpe")
            row[f"cagr @ {cost_label}"] = m.get("cagr")
            if cpct == 0.0035:
                row["max_dd"] = m.get("max_drawdown")
        rows.append(row)

    table = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(REPORTS_DIR / "checkpoint_4_8_rsi_fusion.csv", index=False)

    pd.set_option("display.width", 300)
    show = table.copy()
    for c in show.columns:
        if c != "strategy":
            show[c] = show[c].astype(float).round(4)
    print(f"\n--- Every combination, at all three cost levels, OOS window "
          f"{OOS_START.date()} to {OOS_END.date()} ---")
    print(show[["strategy", "macro_f1", "sharpe @ 0.35% (frozen spec)",
                "sharpe @ 0.25% (verified charges only)", "sharpe @ 0.00% (diagnostic only)",
                "cagr @ 0.35% (frozen spec)", "max_dd", "n_round_trips",
                "exposure_buy_days"]].to_string(index=False))

    # ---- The verdicts, each answerable either way ----
    strat = table.set_index("strategy")
    bh = strat.loc["REFERENCE: buy_and_hold_8symbol", "sharpe @ 0.35% (frozen spec)"]
    vol = strat.loc["D1) volatility-only model (4.7 best)", "sharpe @ 0.35% (frozen spec)"]
    cands = table.loc[~table["strategy"].str.startswith("REFERENCE")]
    best = cands.loc[cands["sharpe @ 0.35% (frozen spec)"].astype(float).idxmax()]

    print(f"\n--- Verdicts at the real (frozen-spec) cost level ---")
    print(f"Best combination: {best['strategy']}  Sharpe {float(best['sharpe @ 0.35% (frozen spec)']):.4f}")
    print(f"  vs volatility-only (previous best model): {float(vol):.4f}")
    print(f"  vs equal-weight buy-and-hold:             {float(bh):.4f}")
    check("the best RSI combination improves on the volatility-only model from 4.7 "
          "(i.e. adding RSI was worth it)",
          float(best["sharpe @ 0.35% (frozen spec)"]) > float(vol),
          f"best {float(best['sharpe @ 0.35% (frozen spec)']):.4f} vs volatility-only {float(vol):.4f}")
    beats_bh = float(best["sharpe @ 0.35% (frozen spec)"]) > float(bh)
    print(f"\nDoes anything now beat buy-and-hold after real costs? "
          f"{'YES' if beats_bh else 'NO -- still short, reported as-is'}")

    bh0 = strat.loc["REFERENCE: buy_and_hold_8symbol", "sharpe @ 0.00% (diagnostic only)"]
    best0 = cands["sharpe @ 0.00% (diagnostic only)"].astype(float).max()
    print(f"At ZERO cost (not tradeable, diagnostic): best candidate {best0:.4f} vs "
          f"buy-and-hold {float(bh0):.4f} -> "
          f"{'candidate ahead' if best0 > float(bh0) else 'still behind'}")

    print(f"\nwrote reports/phase4/checkpoint_4_8_rsi_fusion.csv")
    print("\n" + "-" * 110)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 110)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
