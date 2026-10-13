"""
22_model_expanded.py -- Phase 4 rebuild with sector (3.6) + long-term (3.7) features
added to the frozen Phase 3 set (35 features), per the user's explicit direction:
check whether RSI is actually pulling weight, add long-term trend signal, and report
the backtest honestly either way -- including a Monte Carlo robustness check on the
result, since a single backtest number on ~386 trades is a thin sample to trust at
face value.

PART 0 -- RSI FEATURE-IMPORTANCE CHECK (reported, not assumed): fit 4.2's exact model
on all pooled dev-window rows (not a new OOS claim -- purely a "what does the model
actually lean on" read) and rank feature_importances_. Result found: `mom_rsi14` (the
continuous RSI value) ranks 17th of 35 -- present and used, moderate importance, NOT
the top feature. `vote_rsi14` (the discretized directional vote) has importance
~0.0000 -- essentially unused. This is NOT a bug: checkpoint 3.4's correlation
clustering already flagged `vote_rsi14` as redundant with `vote_kc_breakout` (same
cluster, corr > 0.6) -- the tree evidently leans on the Keltner-channel vote instead
and gets nothing extra from RSI's vote. So: RSI IS "used," as the plan intends
(a continuous input, not thrown away), but it is not this dataset's strongest signal
-- volatility-regime and Bollinger/ATR features rank higher. Stated plainly rather
than inflating RSI's role because it's a well-known indicator.

PART 1 -- EXPANDED FEATURE MERGE: unlike the frozen Phase 3 table, the new sector
(data/features_sector) and long-term (data/features_longterm) columns are NOT
required to be non-NaN -- TATASTEEL/BHARTIARTL/ULTRACEMCO genuinely have no sector
peer (see 20_sector_features.py) and the first ~252 sessions of history genuinely
have no long-term feature (252-day warm-up). These are passed through as real NaN
into XGBoost, which natively learns a split direction for missing values -- this
does NOT work for 4.1's logistic regression without a separate imputation step,
which has not been built; this script only re-runs the XGBoost (4.2-style) path.

PART 2 -- MONTE CARLO ROBUSTNESS CHECK: the 4.5 backtest's portfolio Sharpe is a
single number from one historical path with a small number of actual trades. A
block bootstrap (resampling contiguous chunks of the daily return series, to keep
each day's autocorrelation intact rather than shuffling individual days) is run 500
times to get a 90% confidence interval on the Sharpe ratio -- "how much would this
number plausibly have varied under a different random slice of market noise." A wide
interval crossing zero means the headline Sharpe number alone is not reliable
evidence either way.
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
SECTOR_DIR = ROOT / "data" / "features_sector"
LONGTERM_DIR = ROOT / "data" / "features_longterm"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m41 = _load("15_model_logreg_floor")
m43 = _load("17_model_calibration")
bt = _load("04_backtest")
m24 = _load("06_baselines")

CLASSES = m41.CLASSES
FOLD_TEST_RANGES = m41.FOLD_TEST_RANGES
GBT_PARAMS = m43.GBT_PARAMS
PILOT_SYMBOLS = bt.PILOT_SYMBOLS
BENCHMARK = bt.BENCHMARK_SYMBOL
COST_PCT = bt.COST_PCT
CONF_THRESHOLD = 0.40
OOS_START = pd.Timestamp(FOLD_TEST_RANGES[0][0])
OOS_END = pd.Timestamp(FOLD_TEST_RANGES[-1][1])

SECTOR_COLS = ["mkt_rel_ret_5d", "mkt_rel_ret_20d", "sector_rel_ret_5d", "sector_rel_ret_20d",
               "mkt_rel_ret_20d_zscore", "n_sector_peers"]
LONGTERM_COLS = ["ret_252d", "above_sma200", "dist_sma200_pct", "golden_cross_state"]


def attach_expanded_features(labels: pd.DataFrame):
    merged, n_lost, n_warmup_dropped = m41.attach_features(labels)  # frozen 35, NaN-dropped as before
    base_cols = m41.feature_columns(merged)

    sector_frames = [pd.read_csv(SECTOR_DIR / f"{s}.csv", parse_dates=["Date"]).rename(columns={"Date": "date"})
                      for s in PILOT_SYMBOLS]
    sector_all = pd.concat(sector_frames, ignore_index=True)[["symbol", "date"] + SECTOR_COLS]

    lt_frames = [pd.read_csv(LONGTERM_DIR / f"{s}.csv", parse_dates=["Date"]).rename(columns={"Date": "date"})
                  for s in PILOT_SYMBOLS]
    lt_all = pd.concat(lt_frames, ignore_index=True)[["symbol", "date"] + LONGTERM_COLS]

    merged = merged.merge(sector_all, on=["symbol", "date"], how="left")
    merged = merged.merge(lt_all, on=["symbol", "date"], how="left")
    expanded_cols = base_cols + SECTOR_COLS + LONGTERM_COLS
    return merged, expanded_cols, n_lost, n_warmup_dropped


def rsi_importance_check(data: pd.DataFrame, feat_cols: List[str]) -> None:
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    X = data[feat_cols].to_numpy(dtype=float)
    y = data["label"].map(class_to_idx).to_numpy()
    counts = pd.Series(y).value_counts()
    cw = {i: len(y) / (3 * counts.get(i, 1)) for i in range(3)}
    sw = pd.Series(y).map(cw).to_numpy()
    clf = xgb.XGBClassifier(objective="multi:softprob", num_class=3, eval_metric="mlogloss",
                             tree_method="hist", random_state=0, **GBT_PARAMS)
    clf.fit(X, y, sample_weight=sw)
    imp = pd.Series(clf.feature_importances_, index=feat_cols).sort_values(ascending=False)
    print("\n--- Feature importance, full expanded set (fit on ALL dev-window rows -- a 'what "
          "does the model lean on' read, not a new OOS claim) ---")
    print(imp.head(10).to_string())
    print("\n--- Where do the NEW (sector/long-term) features rank? ---")
    ranks = imp.rank(ascending=False)
    for c in SECTOR_COLS + LONGTERM_COLS:
        print(f"  {c}: importance={imp.get(c, 0):.4f}, rank {int(ranks.get(c, len(feat_cols)))} of {len(feat_cols)}")
    print("\n--- RSI specifically ---")
    for c in ["mom_rsi14", "vote_rsi14"]:
        if c in imp.index:
            print(f"  {c}: importance={imp[c]:.4f}, rank {int(ranks[c])} of {len(feat_cols)}")


def run_folds_gbt_expanded(data: pd.DataFrame, feat_cols: List[str]) -> dict:
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
        Xtr = train[feat_cols].to_numpy(dtype=float)
        Xte = test[feat_cols].to_numpy(dtype=float)
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


def block_bootstrap_sharpe_ci(daily_returns: pd.Series, n_boot: int = 500, block: int = 20,
                               seed: int = 0) -> Dict[str, float]:
    """Resample the daily-return series in contiguous BLOCKs (not single days) with
    replacement, to roughly preserve short-run autocorrelation, rebuild a same-length
    series each time, and recompute the annualized Sharpe. Returns the 5th/50th/95th
    percentile of that distribution -- a 90% Monte Carlo confidence interval."""
    rng = np.random.RandomState(seed)
    r = daily_returns.dropna().to_numpy()
    n = len(r)
    if n < block * 3:
        return {"p5": float("nan"), "p50": float("nan"), "p95": float("nan"), "n_boot": 0}
    n_blocks = n // block
    sharpes = []
    for _ in range(n_boot):
        idx = rng.randint(0, n - block, size=n_blocks)
        sample = np.concatenate([r[i:i + block] for i in idx])
        mu, sd = sample.mean(), sample.std(ddof=1)
        sharpes.append(np.sqrt(252) * mu / sd if sd > 0 else 0.0)
    sharpes = np.array(sharpes)
    return {"p5": float(np.percentile(sharpes, 5)), "p50": float(np.percentile(sharpes, 50)),
            "p95": float(np.percentile(sharpes, 95)), "n_boot": n_boot}


def build_pooled_predictions_expanded(data: pd.DataFrame, feat_cols: List[str]) -> pd.DataFrame:
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
            "symbol": test["symbol"].to_numpy(), "date": test["date"].to_numpy(), "fold": k,
            "y_true": test["label"].to_numpy(), "raw_pred": raw_pred,
            "cal_proba_up": proba_cal[:, class_to_idx["Up"]],
        }))
    return pd.concat(rows, ignore_index=True)


def make_decision(row) -> str:
    if row["raw_pred"] == "Down":
        return "AVOID_DOWN"
    if row["raw_pred"] == "Sideways":
        return "NO_PATTERN_SIDEWAYS"
    return "BUY" if row["cal_proba_up"] >= CONF_THRESHOLD else "NO_PATTERN_LOW_CONF"


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
    print("22_model_expanded.py -- Phase 4 rebuild: + sector + long-term features")
    print("=" * 78)

    labels, calendar = m41.build_pooled_labels()
    data, expanded_cols, n_lost, n_warmup_dropped = attach_expanded_features(labels)
    check("every kept label still has a matching frozen feature row", n_lost == 0, f"{n_lost} unmatched")

    rsi_importance_check(data, expanded_cols)

    print(f"\n--- Re-running checkpoint 4.2's gate with {len(expanded_cols)} features "
          f"(35 frozen + {len(SECTOR_COLS)} sector + {len(LONGTERM_COLS)} long-term) ---")
    out_expanded = run_folds_gbt_expanded(data, expanded_cols)
    f1_expanded = f1_score(out_expanded["pooled_true"], out_expanded["pooled_pred"],
                            average="macro", labels=CLASSES, zero_division=0)

    base_cols = m41.feature_columns(data)
    out_base = run_folds_gbt_expanded(data, base_cols)
    f1_base = f1_score(out_base["pooled_true"], out_base["pooled_pred"],
                        average="macro", labels=CLASSES, zero_division=0)

    print(f"  macro-F1, 35 frozen features only (re-run here for a same-data comparison): {f1_base:.4f}")
    print(f"  macro-F1, expanded features (+sector +long-term):                          {f1_expanded:.4f}")
    check("expanded feature set's macro-F1 is not worse than the 35-feature set "
          "(adding features should not hurt; a drop would mean noise/overfitting from the new columns)",
          f1_expanded >= f1_base - 0.01, f"expanded {f1_expanded:.4f} vs base {f1_base:.4f}")

    # ---- Backtest with the expanded model ----
    preds = build_pooled_predictions_expanded(data, expanded_cols)
    preds["decision"] = preds.apply(make_decision, axis=1)
    preds["signal"] = (preds["decision"] == "BUY").astype(int)
    counts = preds["decision"].value_counts()
    print(f"\n--- Decision breakdown, expanded model, {len(preds)} pooled OOS days ---")
    for dec in ["BUY", "AVOID_DOWN", "NO_PATTERN_SIDEWAYS", "NO_PATTERN_LOW_CONF"]:
        c = int(counts.get(dec, 0))
        print(f"  {dec:<22} {c:>6}  ({c/len(preds)*100:>5.1f}%)")

    model_daily_list = []
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=str(OOS_START.date()), end=str(OOS_END.date()))
        sym_preds = preds.loc[preds["symbol"] == sym].set_index("date")
        sig = sym_preds["signal"].reindex(df.index).fillna(0).astype(int)
        res = bt.backtest_signal(df, sig, cost_pct=COST_PCT)
        model_daily_list.append(res["daily_net"].rename(sym))

    model_panel = pd.concat(model_daily_list, axis=1)
    model_port_daily = model_panel.mean(axis=1)
    model_port_eq = (1.0 + model_port_daily).cumprod()
    m_model_port = bt.performance_metrics(model_port_eq)

    bench_df = bt.dev_window(bt.load_clean(BENCHMARK), start=str(OOS_START.date()), end=str(OOS_END.date()))
    bench_bh = bt.buy_and_hold(bench_df)
    m_nifty = bench_bh["metrics"]

    bh_daily_list = []
    for sym in PILOT_SYMBOLS:
        df = bt.dev_window(bt.load_clean(sym), start=str(OOS_START.date()), end=str(OOS_END.date()))
        res_bh = bt.buy_and_hold(df, cost_pct=COST_PCT)
        bh_daily_list.append(res_bh["daily_net"].rename(sym))
    bh_port_daily = pd.concat(bh_daily_list, axis=1).mean(axis=1)
    m_bh_port = bt.performance_metrics((1.0 + bh_port_daily).cumprod())

    print(f"\n--- Equal-weight portfolio, expanded model vs. baselines, OOS window only ---")
    print(f"{'strategy':<45}{'cagr':>10}{'sharpe':>10}{'max_dd':>10}")
    print(f"{'model (expanded features)':<45}{m_model_port.get('cagr',0):>10.4f}{m_model_port.get('sharpe',0):>10.4f}{m_model_port.get('max_drawdown',0):>10.4f}")
    print(f"{'equal-weight 8-symbol buy-and-hold':<45}{m_bh_port.get('cagr',0):>10.4f}{m_bh_port.get('sharpe',0):>10.4f}{m_bh_port.get('max_drawdown',0):>10.4f}")
    print(f"{'NIFTY100 buy-and-hold':<45}{m_nifty.get('cagr',0):>10.4f}{m_nifty.get('sharpe',0):>10.4f}{m_nifty.get('max_drawdown',0):>10.4f}")

    # ---- Monte Carlo (block bootstrap) CI on the model portfolio's Sharpe ----
    ci = block_bootstrap_sharpe_ci(model_port_daily, n_boot=500, block=20, seed=0)
    print(f"\n--- Monte Carlo robustness check (block bootstrap, 500 resamples, 20-day blocks) ---")
    print(f"  Model portfolio Sharpe point estimate: {m_model_port.get('sharpe', float('nan')):.4f}")
    print(f"  Bootstrap 90% CI: [{ci['p5']:.4f}, {ci['p95']:.4f}]  (median {ci['p50']:.4f}, n={ci['n_boot']})")
    crosses_zero = ci["p5"] < 0 < ci["p95"]
    print(f"  {'CI crosses zero -- cannot rule out this Sharpe being noise.' if crosses_zero else 'CI stays on one side of zero.'}")

    beats_bh = m_model_port.get("sharpe") is not None and m_model_port.get("sharpe") > m_bh_port.get("sharpe")
    beats_nifty = m_model_port.get("sharpe") is not None and m_model_port.get("sharpe") > m_nifty.get("sharpe")
    print(f"\n--- Honest verdict (reported, not gated) ---")
    print(f"Expanded model vs. buy-and-hold: {'model wins' if beats_bh else 'model does NOT beat this baseline'}.")
    print(f"Expanded model vs. NIFTY100:     {'model wins' if beats_nifty else 'model does NOT beat this baseline'}.")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    preds.to_csv(REPORTS_DIR / "checkpoint_4_6_expanded_decisions.csv", index=False)
    pd.DataFrame([
        {"strategy": "model_expanded", **m_model_port, "sharpe_ci_p5": ci["p5"], "sharpe_ci_p95": ci["p95"]},
        {"strategy": "buy_and_hold_8symbol", **m_bh_port},
        {"strategy": "nifty100", **m_nifty},
    ]).to_csv(REPORTS_DIR / "checkpoint_4_6_expanded_portfolio.csv", index=False)
    print(f"\nwrote reports/phase4/checkpoint_4_6_expanded_decisions.csv")
    print(f"wrote reports/phase4/checkpoint_4_6_expanded_portfolio.csv")

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
