"""
23_family_specialist_comparison.py -- per-family specialist models, compared side by
side, per the user's explicit request: rather than always fusing every indicator into
one model (risk of "wrong correlation" / spurious interactions when everything is
mixed together), train a SEPARATE small model per indicator "class" -- momentum,
trend, volatility, volume, sector/cross-sectional, long-term-trend -- each using only
its own few features, each evaluated on its own pooled walk-forward macro-F1 AND its
own backtest (after costs). All classes' numbers are reported side by side; nothing
is picked as "the winner" here -- the user sees every class's accuracy and backtest
result and decides which to trust, which is exactly what was asked for.

Method: identical fold structure, sample_weight recipe, and XGBoost hyperparameters
as checkpoint 4.2 (scripts/16_model_gbt.py / scripts/22_model_expanded.py) for every
specialist -- the ONLY thing that changes between rows of the comparison table is
which columns of X the model is allowed to see. This keeps the comparison apples to
apples: a class scoring lower is not scoring lower because of a different training
recipe.

A "fused" row (every class's features in one model) is included for reference -- this
is checkpoint 4.6's already-computed expanded-feature result, re-stated here, not
recomputed, since it is unchanged.
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
m43 = _load("17_model_calibration")
m46 = _load("22_model_expanded")
bt = _load("04_backtest")

CLASSES = m41.CLASSES
FOLD_TEST_RANGES = m41.FOLD_TEST_RANGES
GBT_PARAMS = m43.GBT_PARAMS
PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
COST_PCT = bt.COST_PCT
CONF_THRESHOLD = 0.40
OOS_START = pd.Timestamp(FOLD_TEST_RANGES[0][0])
OOS_END = pd.Timestamp(FOLD_TEST_RANGES[-1][1])
MAJORITY_BASELINE_F1 = 0.2367  # from checkpoint 4.1, same pooled test set every time

FAMILY_GROUPS: Dict[str, List[str]] = {
    "momentum": ["mom_rsi14", "mom_stoch_k", "mom_stoch_d", "mom_cci20", "mom_willr14",
                 "vote_rsi14", "vote_stoch", "vote_cci20", "vote_willr14"],
    "trend": ["trend_ema20", "trend_ema50", "trend_adx14", "trend_macd_line", "trend_macd_signal",
              "vote_ema_cross", "vote_adx_trending", "vote_macd"],
    "volatility": ["vol_atr14", "vol_atr_pct", "vol_bb_upper", "vol_bb_mid", "vol_bb_lower",
                   "vol_kc_upper", "vol_kc_mid", "vol_kc_lower",
                   "vote_bb", "vote_kc_breakout", "vote_high_vol_regime"],
    "volume": ["volu_obv", "volu_obv_ema20", "volu_ad", "volu_vwpm20",
               "vote_obv_trend", "vote_ad_trend", "vote_vwpm"],
    "sector_crosssectional": m46.SECTOR_COLS,
    "longterm_trend": m46.LONGTERM_COLS,
}


def run_folds(data: pd.DataFrame, feat_cols: List[str]) -> dict:
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    pooled_true, pooled_pred, pooled_proba = [], [], []
    for k, (ts, te) in enumerate(FOLD_TEST_RANGES, start=1):
        test_start, test_end = pd.Timestamp(ts), pd.Timestamp(te)
        train_mask = data["window_end"] < test_start
        for ts_prev, te_prev in FOLD_TEST_RANGES[: k - 1]:
            prev_end = pd.Timestamp(te_prev)
            train_mask &= ~((data["date"] > prev_end) & (data["window_end"] <= test_start))
        test_mask = (data["date"] >= test_start) & (data["date"] <= test_end) & (data["window_end"] <= test_end)
        train, test = data.loc[train_mask], data.loc[test_mask]
        if len(train) < 50 or len(test) == 0:
            continue
        Xtr, Xte = train[feat_cols].to_numpy(dtype=float), test[feat_cols].to_numpy(dtype=float)
        ytr_idx = train["label"].map(class_to_idx).to_numpy()
        yte = test["label"].to_numpy()
        counts = pd.Series(ytr_idx).value_counts()
        cw = {i: len(ytr_idx) / (3 * counts.get(i, 1)) for i in range(3)}
        sw = pd.Series(ytr_idx).map(cw).to_numpy()
        clf = xgb.XGBClassifier(objective="multi:softprob", num_class=3, eval_metric="mlogloss",
                                 tree_method="hist", random_state=0, **GBT_PARAMS)
        clf.fit(Xtr, ytr_idx, sample_weight=sw)
        proba = clf.predict_proba(Xte)
        pred = np.array(CLASSES)[proba.argmax(axis=1)]
        pooled_true.extend(yte.tolist())
        pooled_pred.extend(pred.tolist())
        pooled_proba.append(proba)
    return {"pooled_true": np.array(pooled_true), "pooled_pred": np.array(pooled_pred),
            "pooled_proba": np.concatenate(pooled_proba, axis=0) if pooled_proba else np.zeros((0, 3))}


def build_predictions_with_symbol_date(data: pd.DataFrame, feat_cols: List[str]) -> pd.DataFrame:
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    rows = []
    for k, (ts, te) in enumerate(FOLD_TEST_RANGES, start=1):
        test_start, test_end = pd.Timestamp(ts), pd.Timestamp(te)
        train_mask = data["window_end"] < test_start
        for ts_prev, te_prev in FOLD_TEST_RANGES[: k - 1]:
            prev_end = pd.Timestamp(te_prev)
            train_mask &= ~((data["date"] > prev_end) & (data["window_end"] <= test_start))
        test_mask = (data["date"] >= test_start) & (data["date"] <= test_end) & (data["window_end"] <= test_end)
        train, test = data.loc[train_mask], data.loc[test_mask]
        if len(train) < 200 or len(test) == 0:
            continue
        calib_cutoff = train["date"].quantile(0.8)
        fit_mask = train["window_end"] < calib_cutoff
        calib_mask = (train["date"] >= calib_cutoff) & (~fit_mask)
        train_fit, train_calib = train.loc[fit_mask], train.loc[calib_mask]
        if len(train_fit) < 100 or len(train_calib) < 100:
            continue
        Xtr = train_fit[feat_cols].to_numpy(dtype=float)
        ytr_idx = train_fit["label"].map(class_to_idx).to_numpy()
        Xcal = train_calib[feat_cols].to_numpy(dtype=float)
        ycal_idx = train_calib["label"].map(class_to_idx).to_numpy()
        Xte = test[feat_cols].to_numpy(dtype=float)
        counts = pd.Series(ytr_idx).value_counts()
        cw = {i: len(ytr_idx) / (3 * counts.get(i, 1)) for i in range(3)}
        sw = pd.Series(ytr_idx).map(cw).to_numpy()
        base_clf = xgb.XGBClassifier(objective="multi:softprob", num_class=3, eval_metric="mlogloss",
                                      tree_method="hist", random_state=0, **GBT_PARAMS)
        base_clf.fit(Xtr, ytr_idx, sample_weight=sw)
        proba_raw = base_clf.predict_proba(Xte)
        cal = CalibratedClassifierCV(FrozenEstimator(base_clf), method="isotonic")
        cal.fit(Xcal, ycal_idx)
        proba_cal = cal.predict_proba(Xte)
        raw_pred = np.array(CLASSES)[proba_raw.argmax(axis=1)]
        rows.append(pd.DataFrame({
            "symbol": test["symbol"].to_numpy(), "date": test["date"].to_numpy(),
            "raw_pred": raw_pred, "cal_proba_up": proba_cal[:, class_to_idx["Up"]],
        }))
    return pd.concat(rows, ignore_index=True)


def make_decision(row) -> str:
    if row["raw_pred"] == "Down":
        return "AVOID_DOWN"
    if row["raw_pred"] == "Sideways":
        return "NO_PATTERN_SIDEWAYS"
    return "BUY" if row["cal_proba_up"] >= CONF_THRESHOLD else "NO_PATTERN_LOW_CONF"


def backtest_from_predictions(preds: pd.DataFrame) -> dict:
    preds = preds.copy()
    preds["decision"] = preds.apply(make_decision, axis=1)
    preds["signal"] = (preds["decision"] == "BUY").astype(int)
    daily_list = []
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=str(OOS_START.date()), end=str(OOS_END.date()))
        sym_preds = preds.loc[preds["symbol"] == sym].set_index("date")
        sig = sym_preds["signal"].reindex(df.index).fillna(0).astype(int)
        res = bt.backtest_signal(df, sig, cost_pct=COST_PCT)
        daily_list.append(res["daily_net"].rename(sym))
    port_daily = pd.concat(daily_list, axis=1).mean(axis=1)
    m = bt.performance_metrics((1.0 + port_daily).cumprod())
    n_buy = int((preds["decision"] == "BUY").sum())
    return {**m, "n_buy_days": n_buy, "buy_pct": n_buy / len(preds) * 100}


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
    print("23_family_specialist_comparison.py -- per-class model comparison")
    print("=" * 78)

    labels, calendar = m41.build_pooled_labels()
    data, expanded_cols, n_lost, n_warmup_dropped = m46.attach_expanded_features(labels)
    check("every kept label has a matching frozen feature row", n_lost == 0, f"{n_lost} unmatched")

    rows = []
    bench_df = bt.dev_window(bt.load_clean(BENCHMARK), start=str(OOS_START.date()), end=str(OOS_END.date()))
    m_nifty = bt.buy_and_hold(bench_df).get("metrics", {})
    bh_daily_list = [bt.buy_and_hold(bt.dev_window(bt.load_clean(s), start=str(OOS_START.date()),
                     end=str(OOS_END.date())), cost_pct=COST_PCT)["daily_net"].rename(s) for s in PILOT_SYMBOLS]
    m_bh = bt.performance_metrics((1.0 + pd.concat(bh_daily_list, axis=1).mean(axis=1)).cumprod())

    print(f"\n--- Training one specialist model per class, {len(FAMILY_GROUPS)} classes ---")
    for cls_name, cols in FAMILY_GROUPS.items():
        present_cols = [c for c in cols if c in data.columns]
        out = run_folds(data, present_cols)
        f1 = f1_score(out["pooled_true"], out["pooled_pred"], average="macro", labels=CLASSES, zero_division=0)
        acc = accuracy_score(out["pooled_true"], out["pooled_pred"])

        preds = build_predictions_with_symbol_date(data, present_cols)
        bt_metrics = backtest_from_predictions(preds)

        rows.append({
            "class": cls_name, "n_features": len(present_cols),
            "macro_f1": f1, "beats_majority_baseline": f1 > MAJORITY_BASELINE_F1,
            "accuracy": acc,
            "backtest_cagr": bt_metrics.get("cagr"), "backtest_sharpe": bt_metrics.get("sharpe"),
            "backtest_max_dd": bt_metrics.get("max_drawdown"),
            "n_buy_days": bt_metrics.get("n_buy_days"), "buy_pct": bt_metrics.get("buy_pct"),
        })
        print(f"  {cls_name:<24} macro_f1={f1:.4f}  sharpe={bt_metrics.get('sharpe', float('nan')):.4f}  "
              f"buy_days={bt_metrics.get('n_buy_days')} ({bt_metrics.get('buy_pct', 0):.1f}%)")

    # Fused reference row -- recomputed fresh here (not re-reading 4.6's old CSV) so
    # the whole comparison table comes from one consistent run.
    out_fused = run_folds(data, expanded_cols)
    f1_fused = f1_score(out_fused["pooled_true"], out_fused["pooled_pred"], average="macro",
                         labels=CLASSES, zero_division=0)
    preds_fused = build_predictions_with_symbol_date(data, expanded_cols)
    bt_fused = backtest_from_predictions(preds_fused)
    rows.append({
        "class": "ALL_FUSED (every class combined)", "n_features": len(expanded_cols),
        "macro_f1": f1_fused, "beats_majority_baseline": f1_fused > MAJORITY_BASELINE_F1,
        "accuracy": accuracy_score(out_fused["pooled_true"], out_fused["pooled_pred"]),
        "backtest_cagr": bt_fused.get("cagr"), "backtest_sharpe": bt_fused.get("sharpe"),
        "backtest_max_dd": bt_fused.get("max_drawdown"),
        "n_buy_days": bt_fused.get("n_buy_days"), "buy_pct": bt_fused.get("buy_pct"),
    })
    rows.append({
        "class": "REFERENCE: buy_and_hold_8symbol", "n_features": np.nan, "macro_f1": np.nan,
        "beats_majority_baseline": np.nan, "accuracy": np.nan,
        "backtest_cagr": m_bh.get("cagr"), "backtest_sharpe": m_bh.get("sharpe"),
        "backtest_max_dd": m_bh.get("max_drawdown"), "n_buy_days": np.nan, "buy_pct": np.nan,
    })
    rows.append({
        "class": "REFERENCE: NIFTY100_buy_and_hold", "n_features": np.nan, "macro_f1": np.nan,
        "beats_majority_baseline": np.nan, "accuracy": np.nan,
        "backtest_cagr": m_nifty.get("cagr"), "backtest_sharpe": m_nifty.get("sharpe"),
        "backtest_max_dd": m_nifty.get("max_drawdown"), "n_buy_days": np.nan, "buy_pct": np.nan,
    })

    table = pd.DataFrame(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(REPORTS_DIR / "checkpoint_4_7_family_comparison.csv", index=False)

    pd.set_option("display.width", 220)
    show = table.copy()
    for c in ["macro_f1", "accuracy", "backtest_cagr", "backtest_sharpe", "backtest_max_dd", "buy_pct"]:
        show[c] = show[c].astype(float).round(4)
    print(f"\n--- Full comparison table: every class, plus the fused model, plus both baselines ---")
    print(show.to_string(index=False))

    n_classes_beat_majority = int(table["beats_majority_baseline"].sum())
    check(f"at least one individual class clears the majority-class macro-F1 baseline on its own",
          n_classes_beat_majority > 0, f"{n_classes_beat_majority} of {len(FAMILY_GROUPS)} classes")

    best_sharpe_row = table.loc[table["backtest_sharpe"].astype(float).idxmax()]
    print(f"\nBest single class/model by backtest Sharpe: {best_sharpe_row['class']} "
          f"(Sharpe {float(best_sharpe_row['backtest_sharpe']):.4f}) -- still shown against both "
          f"baselines above for the user to judge, not declared a winner here.")

    print(f"\nwrote reports/phase4/checkpoint_4_7_family_comparison.csv")
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
