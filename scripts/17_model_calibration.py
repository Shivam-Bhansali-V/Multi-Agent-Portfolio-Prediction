"""
17_model_calibration.py -- Phase 4.3: probability calibration.

Pass check per docs/Stock_MultiAgent_Phase_Plan.pdf: "Predicted probability matches
observed frequency." Both 4.1 (logistic regression) and 4.2 (XGBoost, weighted) passed
their own gates on hard predictions (macro-F1) but both were FLAGGED, not fixed, for
poor probability calibration: log-loss worse than a naive class-prior baseline in both
cases. This checkpoint addresses that directly.

ASSUMPTION, stated plainly (no explicit user confirmation yet -- not one of the listed
approval points in CLAUDE.md [base paper / families-setups / news sources / risk
limits / spec change], so treated as a modeling-implementation detail rather than
something to stop and ask about, but flagged here in case the user disagrees):
  - Which model to calibrate: the 4.2 XGBoost model (sample_weight + 100/depth-2/
    reg_lambda=5), since it is the one that actually passed its gate and is the
    current best-macro-F1 candidate carried forward. Logistic regression (4.1) is not
    separately recalibrated here.
  - Calibration method: isotonic regression (sklearn CalibratedClassifierCV +
    FrozenEstimator -- 'cv=prefit' was removed in sklearn >=1.6, FrozenEstimator is its
    replacement). Isotonic over Platt/sigmoid because it makes no parametric shape
    assumption and we have thousands of calibration rows per fold -- enough to avoid
    isotonic's usual small-sample overfitting risk.
  - Calibration-fit split: within each fold's TRAIN window only (never touching the
    fold's test rows), the last `calib_frac` (20%) of train by date is held out as a
    calibration set; the classifier is fit on the earlier 80% only, then the isotonic
    calibrator is fit on that held-out calibration set's predictions. This mirrors the
    outer walk-forward purge logic (calibration rows always chronologically after the
    rows the classifier trained on, within the same train window) rather than a random
    split, to avoid leaking label-window information the same way the outer CV avoids
    it.
  - Pass metric, operationalized: "predicted probability matches observed frequency" is
    implemented as Expected Calibration Error (ECE, 10 equal-width confidence bins,
    weighted by bin size) on the pooled out-of-sample predictions -- this IS the
    standard metric for that exact statement. Gate: calibrated ECE < raw (uncalibrated)
    ECE, AND calibrated log-loss <= raw log-loss. Both must hold -- picking a looser
    single-metric gate would risk calling it a pass on a technicality (e.g. ECE improves
    while log-loss gets worse from a few badly placed probabilities). No specific
    numeric ECE threshold (e.g. "ECE < 0.05") is imposed, since the PDF's pass check
    is comparative ("matches observed frequency" / improves), not absolute, and 4.1/4.2
    didn't set an absolute bar either.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path

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
CLASSES = m41.CLASSES
FOLD_TEST_RANGES = m41.FOLD_TEST_RANGES

# the 4.2 winning config, kept in sync by hand with 16_model_gbt.py's _selftest() --
# flagged so a future change to one must be mirrored in the other.
GBT_PARAMS = dict(n_estimators=100, max_depth=2, learning_rate=0.05,
                   subsample=0.8, colsample_bytree=0.8, reg_lambda=5)


def expected_calibration_error(y_true, proba, classes, n_bins: int = 10) -> float:
    """Weighted mean |confidence - accuracy| across n_bins equal-width confidence bins,
    using each sample's top predicted-class probability as its 'confidence'. Standard
    ECE definition -- directly operationalizes 'predicted probability matches observed
    frequency'."""
    conf = proba.max(axis=1)
    pred = np.array(classes)[proba.argmax(axis=1)]
    correct = (pred == y_true).astype(float)
    n = len(y_true)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        bin_conf = conf[mask].mean()
        bin_acc = correct[mask].mean()
        ece += (mask.sum() / n) * abs(bin_conf - bin_acc)
    return ece


def run_folds_calibrated(data: pd.DataFrame, feat_cols, xgb_params: dict,
                          calib_frac: float = 0.2) -> dict:
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    fold_rows = []
    pooled_true, pooled_fold = [], []
    pooled_proba_raw, pooled_proba_cal = [], []

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
            fold_rows.append({"fold": k, "n_train": len(train), "n_test": len(test),
                               "n_calib": 0, "skipped": True, "skip_reason": "too few train/test rows"})
            continue

        calib_cutoff = train["date"].quantile(1 - calib_frac)
        fit_mask = train["window_end"] < calib_cutoff
        calib_mask = (train["date"] >= calib_cutoff) & (~fit_mask)
        train_fit = train.loc[fit_mask]
        train_calib = train.loc[calib_mask]
        if len(train_fit) < 100 or len(train_calib) < 100:
            fold_rows.append({"fold": k, "n_train": len(train), "n_test": len(test),
                               "n_calib": len(train_calib), "skipped": True,
                               "skip_reason": "too few rows to split off a calibration set"})
            continue

        Xtr = train_fit[feat_cols].to_numpy(dtype=float)
        ytr_idx = train_fit["label"].map(class_to_idx).to_numpy()
        Xcal = train_calib[feat_cols].to_numpy(dtype=float)
        ycal_idx = train_calib["label"].map(class_to_idx).to_numpy()
        Xte = test[feat_cols].to_numpy(dtype=float)
        yte = test["label"].to_numpy()

        counts = pd.Series(ytr_idx).value_counts()
        n_classes = len(CLASSES)
        class_weight = {i: len(ytr_idx) / (n_classes * counts.get(i, 1)) for i in range(n_classes)}
        sw = pd.Series(ytr_idx).map(class_weight).to_numpy()

        base_clf = xgb.XGBClassifier(
            objective="multi:softprob", num_class=3, eval_metric="mlogloss",
            tree_method="hist", random_state=0, **xgb_params,
        )
        base_clf.fit(Xtr, ytr_idx, sample_weight=sw)
        proba_raw = base_clf.predict_proba(Xte)

        cal = CalibratedClassifierCV(FrozenEstimator(base_clf), method="isotonic")
        cal.fit(Xcal, ycal_idx)
        proba_cal = cal.predict_proba(Xte)

        eps = 1e-9
        ll_raw = log_loss(yte, np.clip(proba_raw, eps, 1 - eps), labels=CLASSES)
        ll_cal = log_loss(yte, np.clip(proba_cal, eps, 1 - eps), labels=CLASSES)

        fold_rows.append({
            "fold": k, "test_start": str(test_start.date()), "test_end": str(test_end.date()),
            "n_train_fit": len(train_fit), "n_calib": len(train_calib), "n_test": len(test),
            "skipped": False, "skip_reason": "",
            "logloss_raw": ll_raw, "logloss_calibrated": ll_cal,
        })
        pooled_true.extend(yte.tolist())
        pooled_fold.extend([k] * len(yte))
        pooled_proba_raw.append(proba_raw)
        pooled_proba_cal.append(proba_cal)

    return {
        "fold_rows": pd.DataFrame(fold_rows),
        "pooled_true": np.array(pooled_true),
        "pooled_fold": np.array(pooled_fold),
        "pooled_proba_raw": np.concatenate(pooled_proba_raw, axis=0) if pooled_proba_raw else np.zeros((0, 3)),
        "pooled_proba_cal": np.concatenate(pooled_proba_cal, axis=0) if pooled_proba_cal else np.zeros((0, 3)),
    }


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
    print("17_model_calibration.py -- Phase 4.3: probability calibration")
    print("=" * 78)

    labels, calendar = m41.build_pooled_labels()
    data, n_lost, n_warmup_dropped = m41.attach_features(labels)
    check("every kept label has a matching frozen feature row", n_lost == 0, f"{n_lost} unmatched")
    feat_cols = m41.feature_columns(data)

    out = run_folds_calibrated(data, feat_cols, GBT_PARAMS, calib_frac=0.2)
    folds = out["fold_rows"]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    folds.to_csv(REPORTS_DIR / "checkpoint_4_3_calibration_folds.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n--- Per-fold log-loss, raw vs isotonic-calibrated (4.2's XGBoost config) ---")
    show = folds[folds["skipped"] == False].copy()
    for c in ["logloss_raw", "logloss_calibrated"]:
        show[c] = show[c].round(4)
    print(show.to_string(index=False))
    n_skipped = int((folds["skipped"] == True).sum())
    if n_skipped:
        print(f"\n({n_skipped} of {len(folds)} folds skipped -- too little train data early on to "
              f"carve out a calibration set without starving the classifier; see skip_reason column.)")

    yte = out["pooled_true"]
    proba_raw = out["pooled_proba_raw"]
    proba_cal = out["pooled_proba_cal"]
    n_pooled = len(yte)
    check("pooled out-of-sample predictions exist across the usable folds", n_pooled > 0, "none")

    eps = 1e-9
    ll_raw = log_loss(yte, np.clip(proba_raw, eps, 1 - eps), labels=CLASSES)
    ll_cal = log_loss(yte, np.clip(proba_cal, eps, 1 - eps), labels=CLASSES)
    ece_raw = expected_calibration_error(yte, proba_raw, CLASSES)
    ece_cal = expected_calibration_error(yte, proba_cal, CLASSES)

    # class-prior null, recomputed on this same pooled set for an up-to-date reference
    # point (same idea as 4.1/4.2's prior-null baseline).
    priors = pd.Series(yte).value_counts(normalize=True).reindex(CLASSES).to_numpy()
    prior_proba = np.tile(priors, (n_pooled, 1))
    ll_prior = log_loss(yte, np.clip(prior_proba, eps, 1 - eps), labels=CLASSES)

    acc_raw = accuracy_score(yte, np.array(CLASSES)[proba_raw.argmax(axis=1)])
    acc_cal = accuracy_score(yte, np.array(CLASSES)[proba_cal.argmax(axis=1)])
    f1_raw = f1_score(yte, np.array(CLASSES)[proba_raw.argmax(axis=1)], average="macro", labels=CLASSES, zero_division=0)
    f1_cal = f1_score(yte, np.array(CLASSES)[proba_cal.argmax(axis=1)], average="macro", labels=CLASSES, zero_division=0)

    print(f"\n--- Pooled out-of-sample comparison ({n_pooled} predictions) ---")
    print(f"{'metric':<16}{'raw (4.2)':>14}{'calibrated':>14}{'class-prior null':>18}")
    print(f"{'accuracy':<16}{acc_raw:>14.4f}{acc_cal:>14.4f}{'--':>18}")
    print(f"{'macro_f1':<16}{f1_raw:>14.4f}{f1_cal:>14.4f}{'--':>18}")
    print(f"{'logloss':<16}{ll_raw:>14.4f}{ll_cal:>14.4f}{ll_prior:>18.4f}")
    print(f"{'ECE (10-bin)':<16}{ece_raw:>14.4f}{ece_cal:>14.4f}{'--':>18}")

    check("checkpoint 4.3 pass check: isotonic calibration lowers ECE vs raw XGBoost probabilities",
          ece_cal < ece_raw, f"calibrated ECE {ece_cal:.4f} vs raw ECE {ece_raw:.4f}")
    check("calibration does not make log-loss worse (calibrated logloss <= raw logloss)",
          ll_cal <= ll_raw, f"calibrated {ll_cal:.4f} vs raw {ll_raw:.4f}")
    print(f"\n(Reported, not separately gated: calibrated log-loss {ll_cal:.4f} vs class-prior-null "
          f"{ll_prior:.4f} -- {'now beats the naive prior baseline' if ll_cal < ll_prior else 'still worse than the naive prior baseline'}.)")
    print(f"(Reported: calibration changes hard predictions' macro-F1 from {f1_raw:.4f} (raw) to "
          f"{f1_cal:.4f} (calibrated) -- isotonic calibration can shift which class has the top "
          f"probability, so this is not expected to be identical, and a drop here would be a real "
          f"cost of calibrating, not a bug.)")

    pd.DataFrame({
        "fold": out["pooled_fold"], "y_true": yte,
        "proba_raw_down": proba_raw[:, 0], "proba_raw_sideways": proba_raw[:, 1], "proba_raw_up": proba_raw[:, 2],
        "proba_cal_down": proba_cal[:, 0], "proba_cal_sideways": proba_cal[:, 1], "proba_cal_up": proba_cal[:, 2],
    }).to_csv(REPORTS_DIR / "checkpoint_4_3_pooled_predictions.csv", index=False)

    print(f"\nwrote reports/phase4/checkpoint_4_3_calibration_folds.csv")
    print(f"wrote reports/phase4/checkpoint_4_3_pooled_predictions.csv")
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
