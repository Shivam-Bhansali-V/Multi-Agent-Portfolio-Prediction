"""
19_model_backtest.py -- Phase 4.5: backtest the model after costs, vs. the Phase 2.4
baselines. Pass check per docs/Stock_MultiAgent_Phase_Plan.pdf: "Compared with 2.4
baselines" -- a reporting requirement, not an automatic pass/fail on beating them. This
script reports the comparison honestly either way; it does not force a pass.

HOW THE MODEL'S OUTPUT BECOMES A TRADING DECISION (this is new design work done here,
not specified by the plan PDF -- stated as my own choice, not a user-confirmed spec
item, because it isn't one of CLAUDE.md's listed approval points, but flagged clearly
since the user should be able to override it):

  - Direction comes from the RAW (uncalibrated) 4.2 XGBoost model's own class choice
    (argmax of its raw probabilities) -- not the 4.3-calibrated model's argmax. 4.3
    showed calibrating pushed the model's argmax hard toward the majority "Down" class
    (macro-F1 0.3733 -> 0.2540), so using the calibrated model to pick direction would
    throw away most of the "Up" calls that give this strategy anything to trade on.
  - Confidence comes from the 4.3-CALIBRATED probabilities (specifically P(Up)) --
    calibration exists so this number means what it says, even though it shouldn't
    replace the classifier's own class choice.
  - Explicit "no pattern" abstention, per the user's request: a day is only traded
    (signal=1, go long) when BOTH (a) the raw model's call is "Up" AND (b) the
    calibrated P(Up) clears CONF_THRESHOLD. Every other day is held in cash, and -- the
    actual new piece -- the REASON is recorded rather than silently defaulted: predicted
    "Down" (avoid), predicted "Sideways" (no directional read), or predicted "Up" but
    not confident enough (no clear pattern). This makes "no pattern detected" a visible,
    reported outcome rather than indistinguishable from a bearish call.
  - CONF_THRESHOLD = 0.40, chosen only because it is just above the 1/3 random-guess
    level for a 3-class problem -- round number, not tuned against this backtest's own
    results (that would be a second kind of leakage: fitting the threshold to the test
    set). Stated as an assumption; the user may want it set differently.

Backtest window: the pooled out-of-sample test period actually covered by the 8 walk-
forward folds, 2018-01-01 through 2025-03-31 -- NOT the full 2015-2025 dev window
checkpoint 2.4 used, because the model has no genuine out-of-sample prediction before
2018 (that period was training data for fold 1). The NIFTY100 buy-and-hold and per-
symbol buy-and-hold comparisons below are RECOMPUTED over this same shorter window for
an apples-to-apples comparison -- quoting checkpoint 2.4's full-window Sharpe 1.02
against this shorter window would not be a fair comparison and is not done here.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import accuracy_score, f1_score, log_loss

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase4"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m41 = _load("15_model_logreg_floor")
m42 = _load("16_model_gbt")
m43 = _load("17_model_calibration")
bt = _load("04_backtest")
m24 = _load("06_baselines")

CLASSES = m41.CLASSES
FOLD_TEST_RANGES = m41.FOLD_TEST_RANGES
GBT_PARAMS = m43.GBT_PARAMS
PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
COST_PCT = bt.COST_PCT
CONF_THRESHOLD = 0.40  # see module docstring -- stated assumption, not tuned on this backtest

OOS_START = pd.Timestamp(FOLD_TEST_RANGES[0][0])   # 2018-01-01
OOS_END = pd.Timestamp(FOLD_TEST_RANGES[-1][1])     # 2025-03-31


def build_pooled_predictions(data: pd.DataFrame, feat_cols) -> pd.DataFrame:
    """Re-runs the 4.2/4.3 fold machinery once more, but this time keeps `symbol` and
    `date` attached to every pooled OOS row (4.1/4.2/4.3's own saved CSVs dropped
    those columns -- they only needed the pooled arrays for a metric, this script
    needs to turn each prediction into a per-symbol signal on a specific date)."""
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    rows = []

    for k, (ts, te) in enumerate(FOLD_TEST_RANGES, start=1):
        test_start, test_end = pd.Timestamp(ts), pd.Timestamp(te)
        train_mask = data["window_end"] < test_start
        for ts_prev, te_prev in FOLD_TEST_RANGES[: k - 1]:
            prev_end = pd.Timestamp(te_prev)
            train_mask &= ~((data["date"] > prev_end) & (data["window_end"] <= test_start))
        test_mask = (data["date"] >= test_start) & (data["date"] <= test_end) & (data["window_end"] <= test_end)

        train = data.loc[train_mask]
        test = data.loc[test_mask]
        if len(train) < 200 or len(test) == 0:
            continue

        calib_cutoff = train["date"].quantile(0.8)
        fit_mask = train["window_end"] < calib_cutoff
        calib_mask = (train["date"] >= calib_cutoff) & (~fit_mask)
        train_fit = train.loc[fit_mask]
        train_calib = train.loc[calib_mask]
        if len(train_fit) < 100 or len(train_calib) < 100:
            continue

        Xtr = train_fit[feat_cols].to_numpy(dtype=float)
        ytr_idx = train_fit["label"].map(class_to_idx).to_numpy()
        Xcal = train_calib[feat_cols].to_numpy(dtype=float)
        ycal_idx = train_calib["label"].map(class_to_idx).to_numpy()
        Xte = test[feat_cols].to_numpy(dtype=float)

        counts = pd.Series(ytr_idx).value_counts()
        n_classes = len(CLASSES)
        class_weight = {i: len(ytr_idx) / (n_classes * counts.get(i, 1)) for i in range(n_classes)}
        sw = pd.Series(ytr_idx).map(class_weight).to_numpy()

        base_clf = xgb.XGBClassifier(
            objective="multi:softprob", num_class=3, eval_metric="mlogloss",
            tree_method="hist", random_state=0, **GBT_PARAMS,
        )
        base_clf.fit(Xtr, ytr_idx, sample_weight=sw)
        proba_raw = base_clf.predict_proba(Xte)

        cal = CalibratedClassifierCV(FrozenEstimator(base_clf), method="isotonic")
        cal.fit(Xcal, ycal_idx)
        proba_cal = cal.predict_proba(Xte)

        raw_pred = np.array(CLASSES)[proba_raw.argmax(axis=1)]

        chunk = pd.DataFrame({
            "symbol": test["symbol"].to_numpy(),
            "date": test["date"].to_numpy(),
            "fold": k,
            "y_true": test["label"].to_numpy(),
            "raw_pred": raw_pred,
            "raw_proba_up": proba_raw[:, class_to_idx["Up"]],
            "cal_proba_up": proba_cal[:, class_to_idx["Up"]],
            "cal_proba_down": proba_cal[:, class_to_idx["Down"]],
            "cal_proba_sideways": proba_cal[:, class_to_idx["Sideways"]],
        })
        rows.append(chunk)

    return pd.concat(rows, ignore_index=True)


def make_decision(row) -> str:
    if row["raw_pred"] == "Down":
        return "AVOID_DOWN"
    if row["raw_pred"] == "Sideways":
        return "NO_PATTERN_SIDEWAYS"
    # raw_pred == "Up"
    if row["cal_proba_up"] >= CONF_THRESHOLD:
        return "BUY"
    return "NO_PATTERN_LOW_CONF"


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

    print("=" * 78)
    print("19_model_backtest.py -- Phase 4.5: backtest after costs vs. 2.4 baselines")
    print("=" * 78)

    labels, calendar = m41.build_pooled_labels()
    data, n_lost, n_warmup_dropped = m41.attach_features(labels)
    check("every kept label has a matching frozen feature row", n_lost == 0, f"{n_lost} unmatched")
    feat_cols = m41.feature_columns(data)

    preds = build_pooled_predictions(data, feat_cols)
    check("pooled per-symbol/date predictions exist", len(preds) > 0, "none")
    preds["decision"] = preds.apply(make_decision, axis=1)
    preds["signal"] = (preds["decision"] == "BUY").astype(int)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    preds.to_csv(REPORTS_DIR / "checkpoint_4_5_decisions.csv", index=False)

    counts = preds["decision"].value_counts()
    pct = (counts / len(preds) * 100).round(1)
    print(f"\n--- Decision breakdown across {len(preds)} pooled out-of-sample days (CONF_THRESHOLD={CONF_THRESHOLD}) ---")
    for dec in ["BUY", "AVOID_DOWN", "NO_PATTERN_SIDEWAYS", "NO_PATTERN_LOW_CONF"]:
        c = int(counts.get(dec, 0))
        print(f"  {dec:<22} {c:>6}  ({pct.get(dec, 0.0):>5.1f}%)")
    check("every pooled day got a decision (no row fell through the rule)",
          counts.sum() == len(preds), f"{counts.sum()} vs {len(preds)}")

    # ---- Per-symbol backtest, OOS window only ----
    bench_df = bt.dev_window(bt.load_clean(BENCHMARK), start=str(OOS_START.date()), end=str(OOS_END.date()))
    bench_bh = bt.buy_and_hold(bench_df)
    bench_daily = bench_bh["daily_net"]

    per_sym_rows: List[dict] = []
    model_daily_list: List[pd.Series] = []
    bh_daily_list: List[pd.Series] = []
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=str(OOS_START.date()), end=str(OOS_END.date()))
        sym_preds = preds.loc[preds["symbol"] == sym].set_index("date")
        sig = sym_preds["signal"].reindex(df.index).fillna(0).astype(int)

        res_model = bt.backtest_signal(df, sig, cost_pct=COST_PCT)
        res_bh = bt.buy_and_hold(df, cost_pct=COST_PCT)

        m_model = res_model["metrics"]
        m_bh = res_bh["metrics"]
        ab = m24.alpha_beta(res_model["daily_net"], bench_daily)

        per_sym_rows.append({
            "symbol": sym,
            "model_cagr": m_model.get("cagr"), "model_sharpe": m_model.get("sharpe"),
            "model_max_dd": m_model.get("max_drawdown"), "model_exposure": res_model["exposure"],
            "model_n_trades": res_model["n_round_trips"],
            "bh_cagr": m_bh.get("cagr"), "bh_sharpe": m_bh.get("sharpe"), "bh_max_dd": m_bh.get("max_drawdown"),
            "model_beats_bh_sharpe": (m_model.get("sharpe") or float("-inf")) > (m_bh.get("sharpe") or float("-inf")),
            **{f"model_{k}": v for k, v in ab.items()},
        })
        model_daily_list.append(res_model["daily_net"].rename(sym))
        bh_daily_list.append(res_bh["daily_net"].rename(sym))

    per_sym = pd.DataFrame(per_sym_rows)
    per_sym.to_csv(REPORTS_DIR / "checkpoint_4_5_backtest_per_symbol.csv", index=False)

    pd.set_option("display.width", 220)
    print(f"\n--- Per-symbol, OOS window {OOS_START.date()} to {OOS_END.date()} (model vs. buy-and-hold, after costs) ---")
    show = per_sym.copy()
    for c in ["model_cagr", "model_sharpe", "model_max_dd", "bh_cagr", "bh_sharpe", "bh_max_dd"]:
        show[c] = show[c].astype(float).round(4)
    print(show[["symbol", "model_cagr", "model_sharpe", "model_max_dd", "model_exposure", "model_n_trades",
                "bh_cagr", "bh_sharpe", "bh_max_dd", "model_beats_bh_sharpe"]].to_string(index=False))

    # ---- Equal-weight portfolio: model strategy vs. buy-and-hold vs. NIFTY100 ----
    model_panel = pd.concat(model_daily_list, axis=1)
    bh_panel = pd.concat(bh_daily_list, axis=1)
    model_port_daily = model_panel.mean(axis=1)
    bh_port_daily = bh_panel.mean(axis=1)
    model_port_eq = (1.0 + model_port_daily).cumprod()
    bh_port_eq = (1.0 + bh_port_daily).cumprod()

    m_model_port = bt.performance_metrics(model_port_eq)
    m_bh_port = bt.performance_metrics(bh_port_eq)
    m_nifty = bench_bh["metrics"]
    ab_model_port = m24.alpha_beta(model_port_daily, bench_daily)
    ab_bh_port = m24.alpha_beta(bh_port_daily, bench_daily)

    port_summary = pd.DataFrame([
        {"strategy": "model (4.2 XGBoost + 4.3 calibrated confidence filter)",
         "cagr": m_model_port.get("cagr"), "sharpe": m_model_port.get("sharpe"),
         "max_drawdown": m_model_port.get("max_drawdown"), **ab_model_port},
        {"strategy": "equal-weight 8-symbol buy-and-hold",
         "cagr": m_bh_port.get("cagr"), "sharpe": m_bh_port.get("sharpe"),
         "max_drawdown": m_bh_port.get("max_drawdown"), **ab_bh_port},
        {"strategy": "NIFTY100 buy-and-hold",
         "cagr": m_nifty.get("cagr"), "sharpe": m_nifty.get("sharpe"),
         "max_drawdown": m_nifty.get("max_drawdown"), "beta": 1.0, "alpha_annual": 0.0},
    ])
    port_summary.to_csv(REPORTS_DIR / "checkpoint_4_5_backtest_portfolio.csv", index=False)

    print(f"\n--- Equal-weight 8-symbol portfolio, OOS window only (after 0.35%/round-trip costs) ---")
    show2 = port_summary.copy()
    for c in ["cagr", "sharpe", "max_drawdown", "alpha_annual"]:
        if c in show2.columns:
            show2[c] = show2[c].astype(float).round(4)
    print(show2.to_string(index=False))

    model_sharpe = m_model_port.get("sharpe")
    bh_sharpe = m_bh_port.get("sharpe")
    nifty_sharpe = m_nifty.get("sharpe")
    check("checkpoint 4.5 reporting requirement: model backtest run and compared against the "
          "2.4-style baselines (buy-and-hold, NIFTY100), same OOS window", True)
    print(f"\n--- Honest verdict (reported, not a pass/fail gate -- this is the real question) ---")
    beats_bh = model_sharpe is not None and bh_sharpe is not None and model_sharpe > bh_sharpe
    beats_nifty = model_sharpe is not None and nifty_sharpe is not None and model_sharpe > nifty_sharpe
    print(f"Model portfolio Sharpe {model_sharpe:.4f} vs. equal-weight buy-and-hold {bh_sharpe:.4f}: "
          f"{'model wins' if beats_bh else 'model does NOT beat this baseline'}.")
    print(f"Model portfolio Sharpe {model_sharpe:.4f} vs. NIFTY100 buy-and-hold {nifty_sharpe:.4f}: "
          f"{'model wins' if beats_nifty else 'model does NOT beat this baseline'}.")
    print("(Note: 'beats the base paper' in CLAUDE.md refers to Kotekar et al. -- a different task, "
          "next-day Nifty 50 index direction, not this 10-day multi-stock setup. That comparison "
          "needs rebuilding their model inside this engine, which has not been started. The "
          "comparison above is against this project's OWN baselines (checkpoint 2.4 / NIFTY100), "
          "which is what checkpoint 4.5 itself asks for.)")

    print(f"\nwrote reports/phase4/checkpoint_4_5_decisions.csv")
    print(f"wrote reports/phase4/checkpoint_4_5_backtest_per_symbol.csv")
    print(f"wrote reports/phase4/checkpoint_4_5_backtest_portfolio.csv")
    print("\n" + "-" * 78)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
