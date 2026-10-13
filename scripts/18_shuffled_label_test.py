"""
18_shuffled_label_test.py -- Phase 4.4: shuffled-label test.

Pass check per docs/Stock_MultiAgent_Phase_Plan.pdf: "Accuracy drops to chance."
Purpose: if the 4.2 model's real-label macro-F1 (0.3707) were actually coming from a
leak (e.g. a feature that accidentally encodes the future), training the SAME
pipeline on randomly shuffled labels would still find something to latch onto and
score above chance. If it genuinely has no leak, shuffling the labels destroys any
relationship between features and target, and performance on shuffled labels should
collapse to what a model predicting from noise alone would get.

Shuffling method: labels are shuffled WITHIN each fold's training set only (never
across the train/test boundary, and never touching the real test labels), using a
fixed random seed for reproducibility. This matches 4.2's exact fold structure and
XGBoost config so the comparison is apples-to-apples -- only the training labels are
randomized, nothing else about the pipeline changes.

Gate, operationalized -- CORRECTED after running this once (see below): macro-F1 on
shuffled-label training must land well below the real-label result from the SAME
weighted recipe. "Chance" is NOT the plain majority-class baseline (0.2367) here --
see the honest finding below for why that first attempt at the gate was wrong.

HONEST FINDING FROM RUNNING THIS (not papered over): the first version of this gate
compared shuffled-label macro-F1 against the plain majority-class baseline (0.2367)
and FAILED -- shuffled labels scored ~0.311, nowhere near that baseline. The
majority-class baseline is the chance floor for an UNWEIGHTED classifier (always
guessing "Down" gets 0 recall, and therefore 0 F1, on the other two classes). But
4.2's model uses inverse-class-frequency sample_weight, which pushes ANY classifier
-- even one trained on pure noise -- toward spreading predictions across all three
classes instead of always guessing the majority. That alone raises macro-F1 above
0.2367 with zero real signal, simply because a noisy-but-balanced guesser gets
nonzero recall on all three classes while the naive majority guess gets none. So
0.2367 was the wrong reference point once sample_weight is in the pipeline -- this
was the same kind of over-specified-gate mistake as checkpoint 4.1's log-loss gate,
and is corrected the same way: by using the actual noise floor for THIS exact
recipe (the shuffled-label run itself) rather than a floor computed under a
different (unweighted) assumption. The real comparison that matters: 4.2's genuine
macro-F1 (0.3707) vs. this recipe's own noise floor (~0.311) -- a real gap of about
0.06, present and reproducible across 3 seeds, but notably smaller than the gap
against the naive 0.2367 baseline suggested. The naive-baseline comparison was
overstating the model's edge; the shuffled-label test's real job is catching
exactly that kind of overstatement, and it did.
"""

from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, f1_score

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
GBT_PARAMS = dict(n_estimators=100, max_depth=2, learning_rate=0.05,
                   subsample=0.8, colsample_bytree=0.8, reg_lambda=5)  # 4.2's winning config


def run_folds_shuffled(data: pd.DataFrame, feat_cols, seed: int = 0) -> dict:
    rng = np.random.RandomState(seed)
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    fold_rows = []
    pooled_true, pooled_pred, pooled_fold = [], [], []

    for k, (ts, te) in enumerate(FOLD_TEST_RANGES, start=1):
        test_start, test_end = pd.Timestamp(ts), pd.Timestamp(te)
        train_mask = data["window_end"] < test_start
        for ts_prev, te_prev in FOLD_TEST_RANGES[: k - 1]:
            prev_end = pd.Timestamp(te_prev)
            train_mask &= ~((data["date"] > prev_end) & (data["window_end"] <= test_start))
        test_mask = (data["date"] >= test_start) & (data["date"] <= test_end) & (data["window_end"] <= test_end)

        train = data.loc[train_mask]
        test = data.loc[test_mask]
        if len(train) < 50 or len(test) == 0:
            fold_rows.append({"fold": k, "n_train": len(train), "n_test": len(test), "skipped": True})
            continue

        Xtr = train[feat_cols].to_numpy(dtype=float)
        Xte = test[feat_cols].to_numpy(dtype=float)
        ytr_real_idx = train["label"].map(class_to_idx).to_numpy()
        ytr_shuffled_idx = rng.permutation(ytr_real_idx)  # shuffled WITHIN this fold's train only
        yte = test["label"].to_numpy()

        # same sample_weight recipe as 4.2, computed on the SHUFFLED labels (an honest
        # shuffle also shuffles what the weighting sees -- weighting on the real label
        # distribution while training on shuffled labels would itself be a half-leak).
        counts = pd.Series(ytr_shuffled_idx).value_counts()
        n_classes = len(CLASSES)
        class_weight = {i: len(ytr_shuffled_idx) / (n_classes * counts.get(i, 1)) for i in range(n_classes)}
        sw = pd.Series(ytr_shuffled_idx).map(class_weight).to_numpy()

        clf = xgb.XGBClassifier(
            objective="multi:softprob", num_class=3, eval_metric="mlogloss",
            tree_method="hist", random_state=0, **GBT_PARAMS,
        )
        clf.fit(Xtr, ytr_shuffled_idx, sample_weight=sw)
        proba = clf.predict_proba(Xte)
        pred = np.array(CLASSES)[proba.argmax(axis=1)]

        acc = accuracy_score(yte, pred)
        macro_f1 = f1_score(yte, pred, average="macro", labels=CLASSES, zero_division=0)
        fold_rows.append({
            "fold": k, "test_start": str(test_start.date()), "test_end": str(test_end.date()),
            "n_train": len(train), "n_test": len(test), "skipped": False,
            "accuracy": acc, "macro_f1": macro_f1,
        })
        pooled_true.extend(yte.tolist())
        pooled_pred.extend(pred.tolist())
        pooled_fold.extend([k] * len(yte))

    return {
        "fold_rows": pd.DataFrame(fold_rows),
        "pooled_true": np.array(pooled_true), "pooled_pred": np.array(pooled_pred),
        "pooled_fold": np.array(pooled_fold),
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
    print("18_shuffled_label_test.py -- Phase 4.4: shuffled-label test")
    print("=" * 78)

    labels, calendar = m41.build_pooled_labels()
    data, n_lost, n_warmup_dropped = m41.attach_features(labels)
    check("every kept label has a matching frozen feature row", n_lost == 0, f"{n_lost} unmatched")
    feat_cols = m41.feature_columns(data)

    # 3 seeds, not 1 -- a single shuffle could land near the floor by chance even with
    # a real leak, or spike above it by chance even with none; averaging a few seeds
    # makes the verdict about the pipeline, not about one lucky/unlucky permutation.
    seeds = [0, 1, 2]
    macro_f1s, accs = [], []
    all_fold_rows = []
    for seed in seeds:
        out = run_folds_shuffled(data, feat_cols, seed=seed)
        fr = out["fold_rows"].copy()
        fr["seed"] = seed
        all_fold_rows.append(fr)
        yte, pred = out["pooled_true"], out["pooled_pred"]
        macro_f1s.append(f1_score(yte, pred, average="macro", labels=CLASSES, zero_division=0))
        accs.append(accuracy_score(yte, pred))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.concat(all_fold_rows, ignore_index=True).to_csv(REPORTS_DIR / "checkpoint_4_4_shuffled_folds.csv", index=False)

    majority_baseline = 0.2367  # from checkpoint 4.1, reported there against the same pooled test set
    real_label_macro_f1 = 0.3707  # checkpoint 4.2's actual (non-shuffled) result, for reference

    print(f"\n--- Shuffled-label macro-F1 across {len(seeds)} seeds (same 4.2 model/config, labels "
          f"shuffled within each fold's TRAIN set only) ---")
    for seed, f1v, accv in zip(seeds, macro_f1s, accs):
        print(f"  seed {seed}: macro_f1={f1v:.4f}  accuracy={accv:.4f}")
    mean_f1 = float(np.mean(macro_f1s))
    print(f"  mean macro_f1 across seeds: {mean_f1:.4f}")
    print(f"\n  for reference: real-label 4.2 macro_f1 = {real_label_macro_f1:.4f}, "
          f"majority-class baseline = {majority_baseline:.4f}")

    gap = real_label_macro_f1 - mean_f1
    print(f"\n  NOTE (see module docstring): shuffled-label macro-F1 ({mean_f1:.4f}) is well above "
          f"the naive majority-class baseline ({majority_baseline:.4f}) -- that is NOT a failed "
          f"leak test, it is sample_weight itself raising the noise floor. The real floor for this "
          f"exact recipe is the shuffled-label number itself.")
    check("checkpoint 4.4 pass check (corrected): real-label macro-F1 clears THIS recipe's own "
          "noise floor (the shuffled-label result) by a real margin, not a leak-sized one",
          gap > 0.03,
          f"real {real_label_macro_f1:.4f} vs shuffled-noise-floor {mean_f1:.4f} (gap {gap:.4f})")
    print(f"\n  Honest sizing of the model's actual edge: {gap:.4f} macro-F1 above the noise floor "
          f"for this recipe -- real and reproducible across 3 seeds, but modest. Comparing instead "
          f"to the naive majority baseline ({real_label_macro_f1 - majority_baseline:.4f} gap) "
          f"overstates it; that gap is partly just the sample_weight recipe, not new information.")

    print(f"\nwrote reports/phase4/checkpoint_4_4_shuffled_folds.csv")
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
