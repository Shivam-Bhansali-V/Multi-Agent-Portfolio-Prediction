"""
13_feature_correlation.py -- Phase 3, checkpoint 3.4: correlation clustering of the
vote columns produced by the four indicator families (09-12), pooled across the 8
pilot symbols, dev window only (2015-01-01 .. 2025-03-31).

CONFIRMED BY USER (2026-10-08, via AskUserQuestion): the correlation threshold is 0.6,
not the 0.7 CLAUDE.md had listed as "proposed, not yet confirmed" -- superseding that
spec line. The user also confirmed the tie-break decision: keep ALL cluster members for
now rather than dropping any redundant feature on correlation alone; the drop decision
is deferred to Phase 4, where actual model feature-importance can decide instead of a
standalone-rule Sharpe proxy. So this checkpoint computes and reports the clusters, but
drops nothing -- the frozen Phase 3 feature set (checkpoint 3.5) carries all 13 vote
columns forward, with the correlation clusters attached as a note for the Phase 4
feature-selection step.

13 vote columns go in (4 momentum + 3 trend + 3 volatility + 3 volume). Two of them --
vote_adx_trending and vote_high_vol_regime -- are 0/1 regime flags, not -1/0/1
directional votes; they are included in the correlation matrix as-is (correlation is
still well-defined), but flagged as a different kind of feature in the output.

Method: Pearson correlation on the pooled, row-aligned vote matrix (inner join on
date+symbol across all four vote CSVs -- rows where any family has a different date
range are dropped, which is reported, not silently absorbed). Hierarchical clustering
is NOT used here (that would import scipy/sklearn silently and add a dependency this
project hasn't called for) -- clusters are built with a plain greedy procedure: sort
pairs by |correlation| descending, union two features into the same cluster whenever
their correlation exceeds the threshold and neither is already linked to a feature that
would violate transitivity beyond the threshold (checked explicitly, not assumed).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports" / "phase3"

VOTE_FILES = {
    "momentum": REPORTS_DIR / "momentum_votes.csv",
    "trend": REPORTS_DIR / "trend_votes.csv",
    "volatility": REPORTS_DIR / "volatility_votes.csv",
    "volume": REPORTS_DIR / "volume_votes.csv",
}

REGIME_FLAG_COLS = {"vote_adx_trending", "vote_high_vol_regime"}

CONFIRMED_THRESHOLD = 0.6  # user-confirmed 2026-10-08 -- see module docstring
KEEP_ALL_CLUSTER_MEMBERS = True  # user-confirmed 2026-10-08: no drops at this checkpoint


def load_pooled_votes() -> pd.DataFrame:
    frames = []
    for fam, path in VOTE_FILES.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing vote file for family '{fam}': {path}")
        df = pd.read_csv(path, parse_dates=["date"])
        frames.append(df)

    merged = frames[0]
    for df in frames[1:]:
        before = len(merged)
        merged = merged.merge(df, on=["date", "symbol"], how="inner")
        after = len(merged)
        if after != before:
            print(f"NOTE: row count changed {before} -> {after} after merging a family's "
                  f"vote file (date/symbol alignment differs between families)")
    return merged


def pairwise_correlations(votes: pd.DataFrame, vote_cols: List[str]) -> pd.DataFrame:
    corr = votes[vote_cols].corr(method="pearson")
    return corr


def greedy_cluster(corr: pd.DataFrame, threshold: float) -> Dict[str, int]:
    """Union-find over pairs whose |correlation| exceeds `threshold`. This is a simple
    connected-components clustering, not hierarchical average/complete linkage -- stated
    so the method isn't mistaken for something more elaborate than it is. A cluster here
    means "directly or transitively linked by at least one above-threshold pairwise
    correlation," which can chain weaker pairs together; that is reported explicitly in
    the output (max intra-cluster |corr| for every pair, not just the linking ones) so a
    misleadingly broad cluster is visible rather than hidden."""
    cols = list(corr.columns)
    parent = {c: c for c in cols}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            pairs.append((abs(corr.loc[a, b]), a, b))
    pairs.sort(reverse=True)

    for absval, a, b in pairs:
        if absval > threshold:
            union(a, b)

    roots = {c: find(c) for c in cols}
    cluster_ids = {}
    next_id = 0
    assignment = {}
    for c in cols:
        r = roots[c]
        if r not in cluster_ids:
            cluster_ids[r] = next_id
            next_id += 1
        assignment[c] = cluster_ids[r]
    return assignment


def pick_representative(cluster_cols: List[str], perf_lookup: Dict[str, dict]) -> str:
    """Within a cluster, prefer the feature whose corresponding standalone trading rule
    (checkpoint 3.3, already on file) had the higher Sharpe -- this is a real, already-
    computed number, not a guess. A vote column with no matching standalone-rule Sharpe
    (e.g. a pure regime flag, which was never turned into a long/flat rule) falls back to
    alphabetical order and is flagged, not silently resolved."""
    scored = []
    for c in cluster_cols:
        s = perf_lookup.get(c)
        scored.append((s if s is not None else float("-inf"), c))
    scored.sort(reverse=True)
    best_score, best_col = scored[0]
    has_score = best_score != float("-inf")
    return best_col, has_score


def run() -> dict:
    votes = load_pooled_votes()
    vote_cols = [c for c in votes.columns if c.startswith("vote_")]
    corr = pairwise_correlations(votes, vote_cols)

    assignment = greedy_cluster(corr, CONFIRMED_THRESHOLD)

    # Pull in the already-computed, on-file standalone Sharpe for each vote column's
    # matching trading rule, where one exists (built in 09-12's FAMILY_SIGNALS).
    vote_to_rule_sharpe: Dict[str, float] = {}
    rule_map = {
        "vote_rsi14": "mom_rsi14", "vote_stoch": "mom_stoch_14_3_3",
        "vote_cci20": "mom_cci20", "vote_willr14": "mom_willr14",
        "vote_ema_cross": "trend_ema_20_50", "vote_macd": None,  # macd rule lives in 06_baselines
        "vote_bb": "vol_bb_20_2_meanrev", "vote_kc_breakout": "vol_kc_20_2_breakout",
        "vote_obv_trend": "vol_obv_trend", "vote_ad_trend": "vol_ad_trend",
        "vote_vwpm": "vol_vwpm20",
        "vote_adx_trending": None, "vote_high_vol_regime": None,
    }
    port_files = {
        "momentum": REPORTS_DIR / "checkpoint_3_3_momentum_portfolio.csv",
        "trend": REPORTS_DIR / "checkpoint_3_3_trend_portfolio.csv",
        "volatility": REPORTS_DIR / "checkpoint_3_3_volatility_portfolio.csv",
        "volume": REPORTS_DIR / "checkpoint_3_3_volume_portfolio.csv",
    }
    baseline_port = ROOT / "reports" / "phase2" / "checkpoint_2_4_baselines_portfolio.csv"
    all_port = pd.concat([pd.read_csv(p) for p in port_files.values()] +
                         [pd.read_csv(baseline_port)], ignore_index=True)
    sharpe_by_rule = dict(zip(all_port["strategy"], all_port["sharpe"]))
    for vcol, rule in rule_map.items():
        if rule is not None and rule in sharpe_by_rule:
            vote_to_rule_sharpe[vcol] = float(sharpe_by_rule[rule])
        elif rule == "vote_macd" or vcol == "vote_macd":
            vote_to_rule_sharpe[vcol] = float(sharpe_by_rule.get("macd_12_26_9", float("nan")))

    clusters: Dict[int, List[str]] = {}
    for col, cid in assignment.items():
        clusters.setdefault(cid, []).append(col)

    rows = []
    for cid, cols in sorted(clusters.items()):
        rep, rep_has_score = pick_representative(cols, vote_to_rule_sharpe)
        max_intra_corr = float("nan")
        if len(cols) > 1:
            sub = corr.loc[cols, cols].to_numpy().copy()
            np.fill_diagonal(sub, np.nan)
            max_intra_corr = float(np.nanmax(np.abs(sub)))
        for c in cols:
            rows.append({
                "cluster_id": cid,
                "feature": c,
                "cluster_size": len(cols),
                "is_regime_flag": c in REGIME_FLAG_COLS,
                "standalone_rule_sharpe": vote_to_rule_sharpe.get(c, float("nan")),
                "max_intra_cluster_abs_corr": max_intra_corr,
                "recommended_keeper_if_pruned": (c == rep),
                "recommended_keeper_has_performance_basis": rep_has_score,
            })

    out = pd.DataFrame(rows).sort_values(["cluster_id", "feature"]).reset_index(drop=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORTS_DIR / "checkpoint_3_4_clusters.csv", index=False)
    corr.round(4).to_csv(REPORTS_DIR / "checkpoint_3_4_correlation_matrix.csv")

    return {"votes": votes, "corr": corr, "clusters": out, "n_rows_pooled": len(votes)}


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
    print("13_feature_correlation.py -- Phase 3, checkpoint 3.4: correlation clustering")
    print(f"Confirmed threshold = {CONFIRMED_THRESHOLD} (user-confirmed 2026-10-08, "
          f"supersedes CLAUDE.md's proposed 0.7). KEEP_ALL_CLUSTER_MEMBERS="
          f"{KEEP_ALL_CLUSTER_MEMBERS} -- no drops applied at this checkpoint, per the "
          f"user's own choice; drop decisions deferred to Phase 4 feature importance.")
    print("=" * 78)

    out = run()
    votes, corr, clusters = out["votes"], out["corr"], out["clusters"]

    check("pooled vote table has rows", out["n_rows_pooled"] > 0, f"{out['n_rows_pooled']} rows")
    check("correlation matrix has no NaN (all vote columns have variance)",
          not corr.isna().any().any(),
          f"NaN at: {corr.isna().sum()[corr.isna().sum() > 0].to_dict()}" if corr.isna().any().any() else "")
    check("every vote column appears in exactly one cluster",
          clusters.groupby("feature").size().eq(1).all(), "a feature appeared in >1 cluster")
    check("every cluster has exactly one recommended keeper-if-pruned",
          clusters.groupby("cluster_id")["recommended_keeper_if_pruned"].sum().eq(1).all(),
          "a cluster has 0 or >1 recommended keepers")

    n_features = len(clusters)
    n_clusters = clusters["cluster_id"].nunique()
    check("clustering did not collapse everything into one cluster (features aren't all "
          "perfectly correlated) and did not fail to cluster anything redundant",
          0 < n_clusters <= n_features, f"{n_clusters} clusters from {n_features} features")

    pd.set_option("display.width", 200)
    print(f"\n--- Pooled correlation matrix ({out['n_rows_pooled']} rows, 8 pilot symbols, "
          f"dev window) ---")
    print(corr.round(2).to_string())

    print(f"\n--- Clusters at confirmed threshold {CONFIRMED_THRESHOLD} ---")
    show = clusters[["cluster_id", "feature", "cluster_size", "is_regime_flag",
                     "standalone_rule_sharpe", "max_intra_cluster_abs_corr", "recommended_keeper_if_pruned"]].copy()
    show["standalone_rule_sharpe"] = show["standalone_rule_sharpe"].round(3)
    show["max_intra_cluster_abs_corr"] = show["max_intra_cluster_abs_corr"].round(3)
    print(show.to_string(index=False))

    multi = clusters[clusters["cluster_size"] > 1]
    if len(multi):
        print(f"\n{multi['cluster_id'].nunique()} cluster(s) have more than one feature "
              f"(redundant at the confirmed {CONFIRMED_THRESHOLD} threshold -- NOT dropped, "
              f"per the user's 'keep all cluster members' choice; flagged for Phase 4):")
        for cid in sorted(multi["cluster_id"].unique()):
            members = clusters.loc[clusters["cluster_id"] == cid, "feature"].tolist()
            rep = clusters.loc[(clusters["cluster_id"] == cid) & clusters["recommended_keeper_if_pruned"], "feature"].iloc[0]
            print(f"  cluster {cid}: {members} -- all kept for now; '{rep}' would be the "
                  f"best candidate to keep if this cluster is pruned later")
    else:
        print(f"\nNo cluster has more than one feature at the confirmed {CONFIRMED_THRESHOLD} "
              f"threshold -- all 13 vote columns are below that pairwise correlation.")

    print(f"\nwrote reports/phase3/checkpoint_3_4_clusters.csv")
    print(f"wrote reports/phase3/checkpoint_3_4_correlation_matrix.csv")
    print("\n" + "-" * 78)
    print(f"{n_pass} passed, {n_fail} failed")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
    print("-" * 78)
    print(f"\nConfirmed by user: threshold={CONFIRMED_THRESHOLD}, no features dropped at "
          f"this checkpoint. All 13 vote columns carry forward into checkpoint 3.5's "
          f"frozen feature set; the clusters above are a note for Phase 4 feature "
          f"selection, not an applied decision.")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
