"""
14_feature_freeze.py -- Phase 3, checkpoint 3.5: add-on test + freeze.

Combines every indicator family's continuous values (09-12) with their vote columns
into one wide feature table per symbol, then runs an ADD-ON test that is NOT redundant
with the per-family leak tests already passed in checkpoints 3.2: those proved each
family's own compute function is causal in isolation. The risk this test targets is
different -- a bug in the MERGE itself (misaligned index after an outer/inner join, a
silently reordered date column, a duplicate 'close' column overwriting another family's
column of the same name) that none of the per-family tests could catch because they
never built the combined table.

After the add-on test passes, this script freezes the Phase 3 feature set: writes the
combined feature table for the 8 pilot symbols (dev window only -- the April-2025
holdout stays sealed, same as every other Phase 2/3 script) to data/features/<symbol>.csv,
and writes a feature manifest (name, family, source script, kind) to
reports/phase3/checkpoint_3_5_feature_manifest.csv.

Per the user's own confirmed checkpoint-3.4 decision, NOTHING is dropped here on
correlation grounds -- all 13 vote columns and all 22 continuous indicator values carry
forward. The correlation clusters from checkpoint 3.4 are carried into the manifest as
an annotation column only (not applied), for Phase 4's own feature-selection step to use
or ignore.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORTS_DIR = ROOT / "reports" / "phase3"
FEATURES_DIR = ROOT / "data" / "features"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("04_backtest")
bl = _load("06_baselines")
fam_mom = _load("09_indicators_momentum")
fam_trend = _load("10_indicators_trend")
fam_vol = _load("11_indicators_volatility")
fam_volu = _load("12_indicators_volume")

PILOT_SYMBOLS = bt.PILOT_SYMBOLS
DEV_END = bl.DEV_END

# Continuous indicator columns kept per family -- 'close' is dropped from the
# volatility/volume family outputs since it is already in the clean OHLC data and
# duplicating it under two different family prefixes invites exactly the kind of
# merge ambiguity this checkpoint's add-on test exists to catch.
CONTINUOUS_COLS = {
    "mom": ["rsi14", "stoch_k", "stoch_d", "cci20", "willr14"],
    "trend": ["ema20", "ema50", "adx14", "macd_line", "macd_signal"],
    "vol": ["atr14", "atr_pct", "bb_upper", "bb_mid", "bb_lower", "kc_upper", "kc_mid", "kc_lower"],
    "volu": ["obv", "obv_ema20", "ad", "vwpm20"],
}

WARMUP_SESSIONS = 60  # longest indicator warm-up (EMA50/ADX14/Bollinger20) is well under this


def build_combined_features(df: pd.DataFrame) -> pd.DataFrame:
    mom = fam_mom.compute_momentum_indicators(df)[CONTINUOUS_COLS["mom"]].add_prefix("mom_")
    trend = fam_trend.compute_trend_indicators(df)[CONTINUOUS_COLS["trend"]].add_prefix("trend_")
    vol = fam_vol.compute_vol_indicators(df)[CONTINUOUS_COLS["vol"]].add_prefix("vol_")
    volu = fam_volu.compute_volume_indicators(df)[CONTINUOUS_COLS["volu"]].add_prefix("volu_")

    v_mom = fam_mom.votes(fam_mom.compute_momentum_indicators(df))
    v_trend = fam_trend.votes(fam_trend.compute_trend_indicators(df))
    v_vol = fam_vol.votes(fam_vol.compute_vol_indicators(df))
    v_volu = fam_volu.votes(fam_volu.compute_volume_indicators(df))

    parts = [mom, trend, vol, volu, v_mom, v_trend, v_vol, v_volu]
    # All parts share df's exact index by construction (each compute_* returns a frame
    # indexed by df.index) -- concatenated on axis=1 rather than merged on a date column,
    # which is the alignment-safe operation; still verified explicitly below rather than
    # assumed.
    for p in parts:
        if not p.index.equals(df.index):
            raise AssertionError("a family's output index does not match the input "
                                  "DataFrame's index -- merge would silently misalign")
    combined = pd.concat(parts, axis=1)
    combined.insert(0, "date", df.index)
    return combined


def _check_addon_leak(check, symbols: Sequence[str]) -> None:
    print("\n--- Checkpoint 3.5 add-on test: the COMBINED feature table, built on data "
          "truncated at an arbitrary point, must equal the full-series combined table up "
          "to that point -- this is new risk (the merge), not a repeat of checkpoints "
          "3.2's per-family tests ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        full = build_combined_features(df)
        cut = len(df) // 2
        head = df.iloc[:cut]
        trunc = build_combined_features(head)

        check(f"{sym}: combined table row count after truncation matches input length",
              len(trunc) == cut, f"{len(trunc)} rows vs cut={cut}")
        check(f"{sym}: combined table column set is identical truncated vs full",
              set(trunc.columns) == set(full.columns),
              f"symmetric diff: {set(trunc.columns) ^ set(full.columns)}")
        check(f"{sym}: combined table dates truncated vs full are identical up to the cut",
              bool((trunc['date'].to_numpy() == full['date'].iloc[:cut].to_numpy()).all()),
              "date columns diverge")

        value_cols = [c for c in full.columns if c != "date"]
        a = full[value_cols].iloc[:cut].to_numpy(dtype=float)
        b = trunc[value_cols].to_numpy(dtype=float)
        both_finite = np.isfinite(a) & np.isfinite(b)
        same = bool(np.allclose(a[both_finite], b[both_finite])) if both_finite.any() else True
        n_bad = int((~np.isclose(a[both_finite], b[both_finite])).sum()) if both_finite.any() else 0
        check(f"{sym}: every combined feature value at the truncation point is unaffected "
              f"by later data (merge introduced no leak)",
              same, f"{n_bad} of {int(both_finite.sum())} overlapping values differ")


def _check_warmup_and_nan(check, symbols: Sequence[str]) -> None:
    print(f"\n--- NaN/warm-up sanity: after the first {WARMUP_SESSIONS} sessions, the "
          f"combined table should have no NaN in any feature column ---")
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        combined = build_combined_features(df)
        value_cols = [c for c in combined.columns if c != "date"]
        tail = combined[value_cols].iloc[WARMUP_SESSIONS:]
        n_nan = int(tail.isna().sum().sum())
        check(f"{sym}: no NaN in any feature column after the {WARMUP_SESSIONS}-session warm-up",
              n_nan == 0,
              f"{n_nan} NaN cells; worst columns: "
              f"{tail.isna().sum()[tail.isna().sum() > 0].sort_values(ascending=False).head(3).to_dict()}")


def freeze(symbols: Optional[Sequence[str]] = None) -> dict:
    symbols = list(symbols or PILOT_SYMBOLS)
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    written = []
    date_ranges = []
    for sym in symbols:
        df = bt.dev_window(bt.load_clean(sym), end=DEV_END)
        combined = build_combined_features(df)
        combined.insert(0, "symbol", sym)
        out_path = FEATURES_DIR / f"{sym}.csv"
        combined.to_csv(out_path, index=False)
        written.append(str(out_path.relative_to(ROOT)))
        date_ranges.append((sym, str(combined["date"].iloc[0].date()), str(combined["date"].iloc[-1].date())))

    # Correlation clusters from checkpoint 3.4, carried as annotation only.
    clusters_path = REPORTS_DIR / "checkpoint_3_4_clusters.csv"
    cluster_lookup: Dict[str, dict] = {}
    if clusters_path.is_file():
        cl = pd.read_csv(clusters_path)
        for _, row in cl.iterrows():
            cluster_lookup[row["feature"]] = {
                "cluster_id": int(row["cluster_id"]),
                "cluster_size": int(row["cluster_size"]),
                "max_intra_cluster_abs_corr": row["max_intra_cluster_abs_corr"],
            }

    manifest_rows = []
    family_map = {"mom": ("momentum", "09_indicators_momentum.py"),
                  "trend": ("trend", "10_indicators_trend.py"),
                  "vol": ("volatility", "11_indicators_volatility.py"),
                  "volu": ("volume", "12_indicators_volume.py")}
    for prefix, cols in CONTINUOUS_COLS.items():
        fam, src = family_map[prefix]
        for c in cols:
            colname = f"{prefix}_{c}"
            manifest_rows.append({
                "feature": colname, "kind": "continuous", "family": fam, "source_script": src,
                "cluster_id": np.nan, "cluster_size": np.nan, "max_intra_cluster_abs_corr": np.nan,
            })
    for colname, info in cluster_lookup.items():
        fam = {"vote_rsi14": "momentum", "vote_stoch": "momentum", "vote_cci20": "momentum",
               "vote_willr14": "momentum", "vote_ema_cross": "trend", "vote_adx_trending": "trend",
               "vote_macd": "trend", "vote_bb": "volatility", "vote_kc_breakout": "volatility",
               "vote_high_vol_regime": "volatility", "vote_obv_trend": "volume",
               "vote_ad_trend": "volume", "vote_vwpm": "volume"}.get(colname, "unknown")
        src = {"momentum": "09_indicators_momentum.py", "trend": "10_indicators_trend.py",
               "volatility": "11_indicators_volatility.py", "volume": "12_indicators_volume.py"}.get(fam, "")
        manifest_rows.append({
            "feature": colname, "kind": "vote", "family": fam, "source_script": src,
            **info,
        })

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(REPORTS_DIR / "checkpoint_3_5_feature_manifest.csv", index=False)

    ranges_df = pd.DataFrame(date_ranges, columns=["symbol", "start", "end"])
    ranges_df.to_csv(REPORTS_DIR / "checkpoint_3_5_feature_table_ranges.csv", index=False)

    return {"written": written, "manifest": manifest, "ranges": ranges_df}


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
    print("14_feature_freeze.py -- Phase 3, checkpoint 3.5: add-on test + freeze")
    print("=" * 78)

    _check_addon_leak(check, symbols)
    _check_warmup_and_nan(check, symbols)

    if n_fail > 0:
        print("\n" + "-" * 78)
        print(f"{n_pass} passed, {n_fail} failed")
        print("GATE: add-on test failed -- NOT freezing. Fix the failures above before "
              "writing any frozen feature file.")
        for f in failures:
            print(f"  - {f}")
        print("-" * 78)
        return 1

    out = freeze(symbols)
    manifest, ranges = out["manifest"], out["ranges"]

    check("every pilot symbol's feature table was written", len(out["written"]) == len(symbols),
          f"{len(out['written'])} of {len(symbols)} written")
    check("no feature table extends past the sealed holdout boundary",
          (ranges["end"] <= "2025-03-31").all(), f"max end {ranges['end'].max()}")
    n_continuous_expected = sum(len(v) for v in CONTINUOUS_COLS.values())  # 5+5+8+4 = 22
    n_vote_expected = 13  # 4 momentum + 3 trend + 3 volatility + 3 volume
    check(f"feature manifest covers exactly {n_continuous_expected} continuous + "
          f"{n_vote_expected} vote = {n_continuous_expected + n_vote_expected} features",
          len(manifest) == n_continuous_expected + n_vote_expected,
          f"{len(manifest)} features in manifest")
    check("feature manifest has no duplicate feature names",
          manifest["feature"].is_unique, "duplicate feature name found")

    pd.set_option("display.width", 200)
    print(f"\n--- Frozen Phase 3 feature set: {len(manifest)} features "
          f"({(manifest['kind']=='continuous').sum()} continuous, "
          f"{(manifest['kind']=='vote').sum()} vote) ---")
    print(manifest.to_string(index=False))

    print(f"\n--- Feature table date ranges (8 pilot symbols, dev window) ---")
    print(ranges.to_string(index=False))

    for w in out["written"]:
        print(f"wrote {w}")
    print(f"wrote reports/phase3/checkpoint_3_5_feature_manifest.csv")
    print(f"wrote reports/phase3/checkpoint_3_5_feature_table_ranges.csv")

    print("\n" + "-" * 78)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 78)
    if n_fail == 0:
        print(f"\nPhase 3 FROZEN: {len(manifest)} features ({n_continuous_expected} "
              f"continuous + {n_vote_expected} vote columns) across 4 families, for the "
              f"8 pilot symbols, dev window only. Checkpoint 3.4's correlation clusters "
              f"are carried as an annotation, not applied -- nothing dropped, per the "
              f"user's confirmed choice.")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest(sys.argv[1:] or None))
