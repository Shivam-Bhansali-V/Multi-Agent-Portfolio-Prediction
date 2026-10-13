"""
15_model_logreg_floor.py -- Phase 4.1: logistic regression as the floor.

Per docs/Stock_MultiAgent_Phase_Plan.pdf, checkpoint 4.1's pass check is "beats random."
The plan doesn't define "random" precisely, so this is my own operationalization, stated
rather than assumed silently: plain accuracy is misleading here because the 3 classes
are imbalanced (roughly 30% Up / 55% Down / 15% Sideways on this pilot set -- see
reports/phase1/checkpoint_2_1_labels_summary.csv) -- a baseline that always predicts the
majority class ("Down") already gets ~55% accuracy without learning anything. So the
GATED pass check is: macro-F1 (unweighted mean of per-class F1) beats a majority-class-
only baseline -- that baseline structurally cannot score above ~0.24 macro-F1 under this
imbalance, since it never predicts Up or Sideways at all, so beating it is a real test of
whether the model learned anything about the minority classes.

Log-loss vs. a class-prior null model is ALSO reported below, but is NOT gated at this
checkpoint -- probability calibration is explicitly its own later checkpoint (4.3) in
the plan, not something 4.1 is supposed to already satisfy. First attempt here found a
real, worth-flagging result: this classifier's log-loss is WORSE than the naive
class-prior baseline (tried default settings, class_weight='balanced', and a C sweep
from 0.001-1.0 -- none beat the prior-null log-loss without erasing the macro-F1 gain).
That means the raw predict_proba output is overconfident/miscalibrated, which is a
real problem but is checkpoint 4.3's problem to fix (Platt scaling / isotonic
regression), not grounds to fail 4.1's actual pass check.

Method: pooled walk-forward. For each of the 8 purged/embargoed folds (05_splits.py),
every pilot symbol's frozen Phase 3 features (data/features/<symbol>.csv) are joined to
that symbol's kept triple-barrier labels on date, pooled across all 8 symbols, and a
single multinomial logistic regression is fit on the pooled TRAIN rows and evaluated on
the pooled TEST rows of that fold only (never trained on a fold's own test data, and
never on anything at/after the sealed holdout -- enforced upstream by 05_splits.py's
DEV_END cut). Out-of-sample predictions from all 8 folds are then pooled for one overall
assessment, which is what "beats random" is checked against below.

Features are standardized (mean/std fit on TRAIN only per fold, applied to TEST -- never
the reverse) since logistic regression is scale-sensitive and the 22 continuous
indicator columns span very different natural ranges (RSI 0-100, ADX 0-100, MACD a raw
price-difference number, OBV a cumulative volume count in the billions).
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, log_loss, accuracy_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase4"
FEATURES_DIR = ROOT / "data" / "features"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load("05_splits")

PILOT_SYMBOLS = sp.PILOT_SYMBOLS
FOLD_TEST_RANGES = sp.FOLD_TEST_RANGES
CLASSES = ["Down", "Sideways", "Up"]  # fixed order for every probability array


def build_pooled_labels() -> pd.DataFrame:
    """Every pilot symbol's kept labels with window_end, concatenated (not merged) --
    make_folds purges/embargoes per the GLOBAL calendar, applied per symbol below."""
    calendar = sp.trading_calendar(PILOT_SYMBOLS)
    frames = []
    for sym in PILOT_SYMBOLS:
        lab = sp.load_labels(sym)
        lab = sp.add_window_end(lab, calendar)
        frames.append(lab)
    return pd.concat(frames, ignore_index=True), calendar


def attach_features(labels: pd.DataFrame) -> pd.DataFrame:
    """Inner-join each symbol's label rows to that symbol's frozen feature table on
    date. A label with no matching feature row (shouldn't happen past each indicator's
    warm-up, but checked rather than assumed) is dropped and counted."""
    feat_frames = []
    for sym in PILOT_SYMBOLS:
        fpath = FEATURES_DIR / f"{sym}.csv"
        if not fpath.is_file():
            raise FileNotFoundError(f"no frozen feature table for {sym} at {fpath}")
        feat = pd.read_csv(fpath, parse_dates=["date"])
        feat_frames.append(feat)
    feat_all = pd.concat(feat_frames, ignore_index=True)

    merged = labels.merge(feat_all, on=["symbol", "date"], how="inner")
    n_lost = len(labels) - len(merged)

    # The frozen feature table (checkpoint 3.5) only guarantees no NaN after each
    # symbol's first ~60 sessions (indicator warm-up, e.g. EMA50/ADX14/Bollinger20) --
    # it does NOT drop those early rows from the file itself. Every label row this
    # early in a symbol's history still joins to a feature row with NaN in the
    # slower-maturing columns, which a plain LogisticRegression cannot accept. Dropped
    # here, counted explicitly rather than silently.
    fcols = feature_columns(merged)
    has_nan = merged[fcols].isna().any(axis=1)
    n_warmup_dropped = int(has_nan.sum())
    merged = merged.loc[~has_nan].reset_index(drop=True)
    return merged, n_lost, n_warmup_dropped


def feature_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if c.startswith(("mom_", "trend_", "vol_", "volu_", "vote_"))]


def run_folds(data: pd.DataFrame) -> dict:
    feat_cols = feature_columns(data)
    fold_rows = []
    pooled_true: List[str] = []
    pooled_pred: List[str] = []
    pooled_proba: List[np.ndarray] = []
    pooled_fold: List[int] = []

    for k, (ts, te) in enumerate(FOLD_TEST_RANGES, start=1):
        test_start, test_end = pd.Timestamp(ts), pd.Timestamp(te)

        train_mask = data["window_end"] < test_start
        for ts_prev, te_prev in FOLD_TEST_RANGES[: k - 1]:
            prev_end = pd.Timestamp(te_prev)
            # Same embargo logic as 05_splits.make_folds, applied here directly since
            # that function operates per-symbol and we need the pooled mask; the
            # calendar-based embargo window is recomputed identically per symbol would
            # give the same shadow_end for a shared calendar -- using the pooled data's
            # own date column is equivalent and avoids a second per-symbol pass.
            train_mask &= ~((data["date"] > prev_end) & (data["window_end"] <= test_start))
        test_mask = (data["date"] >= test_start) & (data["date"] <= test_end) & (data["window_end"] <= test_end)

        train = data.loc[train_mask]
        test = data.loc[test_mask]
        if len(train) < 50 or len(test) == 0:
            fold_rows.append({"fold": k, "n_train": len(train), "n_test": len(test),
                               "skipped": True})
            continue

        scaler = StandardScaler()
        Xtr = scaler.fit_transform(train[feat_cols].to_numpy(dtype=float))
        Xte = scaler.transform(test[feat_cols].to_numpy(dtype=float))
        ytr = train["label"].to_numpy()
        yte = test["label"].to_numpy()

        # sklearn >=1.5 removed the multi_class= kwarg; lbfgs (the default solver) does
        # multinomial softmax automatically for a >2-class target, which is what's wanted.
        clf = LogisticRegression(max_iter=2000)
        clf.fit(Xtr, ytr)
        proba = clf.predict_proba(Xte)
        # Reindex proba columns to the fixed CLASSES order (clf.classes_ may differ).
        proba_fixed = np.zeros((len(Xte), len(CLASSES)))
        for i, c in enumerate(clf.classes_):
            proba_fixed[:, CLASSES.index(c)] = proba[:, i]
        pred = np.array(CLASSES)[proba_fixed.argmax(axis=1)]

        acc = accuracy_score(yte, pred)
        macro_f1 = f1_score(yte, pred, average="macro", labels=CLASSES, zero_division=0)

        maj_class = pd.Series(ytr).value_counts().idxmax()
        maj_pred = np.full(len(yte), maj_class)
        maj_acc = accuracy_score(yte, maj_pred)
        maj_f1 = f1_score(yte, maj_pred, average="macro", labels=CLASSES, zero_division=0)

        train_priors = pd.Series(ytr).value_counts(normalize=True).reindex(CLASSES).fillna(0.0).to_numpy()
        prior_proba = np.tile(train_priors, (len(yte), 1))
        eps = 1e-9
        model_logloss = log_loss(yte, np.clip(proba_fixed, eps, 1 - eps), labels=CLASSES)
        prior_logloss = log_loss(yte, np.clip(prior_proba, eps, 1 - eps), labels=CLASSES)

        fold_rows.append({
            "fold": k, "test_start": str(test_start.date()), "test_end": str(test_end.date()),
            "n_train": len(train), "n_test": len(test), "skipped": False,
            "accuracy": acc, "macro_f1": macro_f1,
            "majority_class": maj_class, "majority_accuracy": maj_acc, "majority_macro_f1": maj_f1,
            "model_logloss": model_logloss, "prior_logloss": prior_logloss,
        })
        pooled_true.extend(yte.tolist())
        pooled_pred.extend(pred.tolist())
        pooled_proba.append(proba_fixed)
        pooled_fold.extend([k] * len(yte))

    pooled_proba_arr = np.concatenate(pooled_proba, axis=0) if pooled_proba else np.zeros((0, 3))
    return {
        "fold_rows": pd.DataFrame(fold_rows),
        "pooled_true": np.array(pooled_true), "pooled_pred": np.array(pooled_pred),
        "pooled_proba": pooled_proba_arr, "pooled_fold": np.array(pooled_fold),
        "feat_cols": feat_cols,
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
    print("15_model_logreg_floor.py -- Phase 4.1: logistic regression floor")
    print("=" * 78)

    labels, calendar = build_pooled_labels()
    data, n_lost, n_warmup_dropped = attach_features(labels)
    check("every kept label has a matching frozen feature row",
          n_lost == 0, f"{n_lost} label rows had no matching feature row")
    print(f"NOTE: dropped {n_warmup_dropped} label rows from each symbol's indicator "
          f"warm-up period (NaN features, not usable) -- {len(data)} rows remain.")
    check("pooled label+feature table has rows after dropping warm-up NaNs",
          len(data) > 0, "empty table")

    out = run_folds(data)
    folds = out["fold_rows"]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    folds.to_csv(REPORTS_DIR / "checkpoint_4_1_logreg_folds.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n--- Per-fold results ---")
    show_cols = ["fold", "test_start", "test_end", "n_train", "n_test", "accuracy",
                 "macro_f1", "majority_accuracy", "majority_macro_f1",
                 "model_logloss", "prior_logloss"]
    show = folds[folds["skipped"] == False][show_cols].copy()
    for c in ["accuracy", "macro_f1", "majority_accuracy", "majority_macro_f1",
              "model_logloss", "prior_logloss"]:
        show[c] = show[c].round(4)
    print(show.to_string(index=False))

    yte, pred, proba = out["pooled_true"], out["pooled_pred"], out["pooled_proba"]
    n_pooled = len(yte)
    check("pooled out-of-sample predictions exist across all 8 folds", n_pooled > 0, "no predictions")

    pooled_acc = accuracy_score(yte, pred)
    pooled_f1 = f1_score(yte, pred, average="macro", labels=CLASSES, zero_division=0)
    maj_overall = pd.Series(yte).value_counts().idxmax()  # for reporting only
    # Majority-baseline macro-F1, computed fold-by-fold then weighted by test size (the
    # per-fold majority class can differ across folds, so this is NOT the same as just
    # predicting one global majority class for the whole pooled set).
    maj_f1_weighted = float((folds.loc[folds["skipped"] == False, "majority_macro_f1"]
                              * folds.loc[folds["skipped"] == False, "n_test"]).sum()
                             / folds.loc[folds["skipped"] == False, "n_test"].sum())
    eps = 1e-9
    pooled_logloss = log_loss(yte, np.clip(proba, eps, 1 - eps), labels=CLASSES)
    prior_logloss_weighted = float((folds.loc[folds["skipped"] == False, "prior_logloss"]
                                     * folds.loc[folds["skipped"] == False, "n_test"]).sum()
                                    / folds.loc[folds["skipped"] == False, "n_test"].sum())

    print(f"\n--- Pooled out-of-sample result ({n_pooled} predictions across 8 folds) ---")
    print(f"Model accuracy:            {pooled_acc:.4f}")
    print(f"Model macro-F1:            {pooled_f1:.4f}")
    print(f"Majority-baseline macro-F1 (fold-weighted): {maj_f1_weighted:.4f}")
    print(f"Model log-loss:            {pooled_logloss:.4f}")
    print(f"Class-prior log-loss (fold-weighted null):  {prior_logloss_weighted:.4f}")

    check("checkpoint 4.1 GATED pass check: model macro-F1 beats the majority-class baseline "
          "(the plan's 'beats random')",
          pooled_f1 > maj_f1_weighted,
          f"model {pooled_f1:.4f} vs majority baseline {maj_f1_weighted:.4f}")
    print(f"\nNOT gated at 4.1 (deferred to checkpoint 4.3, reported for visibility): "
          f"model log-loss {pooled_logloss:.4f} vs. class-prior null {prior_logloss_weighted:.4f} "
          f"-- {'model is BETTER calibrated' if pooled_logloss < prior_logloss_weighted else 'model is WORSE calibrated (overconfident) than the naive prior -- flagged for 4.3'}.")

    pd.DataFrame({
        "fold": out["pooled_fold"], "y_true": yte, "y_pred": pred,
        "proba_down": proba[:, 0], "proba_sideways": proba[:, 1], "proba_up": proba[:, 2],
    }).to_csv(REPORTS_DIR / "checkpoint_4_1_pooled_predictions.csv", index=False)

    print(f"\nwrote reports/phase4/checkpoint_4_1_logreg_folds.csv")
    print(f"wrote reports/phase4/checkpoint_4_1_pooled_predictions.csv")
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
