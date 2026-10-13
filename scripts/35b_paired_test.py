"""Checkpoint 5.5b - paired tests on the same 20 stocks and the same days (protocol B walk-forward).
(1) as designed: our monthly momentum (after costs, one-day lag) minus each rebuilt baseline model
    traded its own way (daily, rank-weighted, after costs, one-day lag);
(2) both at zero cost;
(3) matched frequency: the baseline's smoothed forecast pushed through OUR engine (top third,
    20-day rebalance, costs), so only the signal differs. (3) is the fair test of signal quality."""
from pathlib import Path
import numpy as np, pandas as pd, sys, importlib.util
sys.path.insert(0, str(Path(__file__).resolve().parent)); import xs_lib as L
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("b", Path(__file__).resolve().parent / "35_baseline_replication.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
P = pd.read_parquet(ROOT / "data" / "panel_v2" / "baseline_predictions.parquet"); P = P[P.protocol.str.startswith("B")]
TRp = pd.read_parquet(ROOT / "data" / "panel_v2" / "close_total_return.parquet").loc[:L.DEV_END].ffill(); R = TRp[b.PAPER20].pct_change(fill_method=None)
TR20 = TRp[b.PAPER20]; mom = TR20.shift(21) / TR20.shift(252) - 1; cal = TR20.index
sd = cal[(cal >= P.date.min()) & (cal <= P.date.max())][::5]
def long(frame): return frame.loc[frame.index.intersection(sd)].stack().rename("score").rename_axis(["date", "symbol"]).reset_index()
def engine(scores, cost): return pd.concat([L.daily_backtest(scores, TR20, 1 / 3, o, cost_side=cost).strat for o in range(4)], axis=1).mean(axis=1)
ours_c, ours_0 = engine(long(mom), b.COST_SIDE), engine(long(mom), 0.0)
def paired(x, y, tag):
    j = pd.concat([x, y], axis=1, join="inner").dropna(); j.columns = ["a", "b"]; e = L.excess_stats(j.a, j.b, seed=1)
    return {f"{tag}__diff_per_year": e["excess_ann"], f"{tag}__ci05": e["ci05"], f"{tag}__ci95": e["ci95"], f"{tag}__prob_ours_better": e["p_gt0"],
            f"{tag}__corr_of_daily_returns": float(j.a.corr(j.b))}
rows = []
for m in [c for c in P.columns if c in ("ridge", "lasso", "random_forest", "gradient_boosting", "mlp", "lstm")]:
    S = b.smooth_signal(P, m, R)
    r = dict(baseline_model=m)
    r.update(paired(ours_c, b.portfolio(S, R, 1, b.COST_SIDE)[0], "as_designed_with_cost"))
    r.update(paired(ours_0, b.portfolio(S, R, 1, 0.0)[0], "as_designed_zero_cost"))
    r.update(paired(ours_c, engine(long(S), b.COST_SIDE), "matched_frequency_with_cost"))
    rows.append(r)
T = pd.DataFrame(rows).round(4); T.to_csv(ROOT / "reports" / "phase5" / "checkpoint_5_5b_paired_test.csv", index=False)
pd.set_option("display.width", 250); print(T.set_index("baseline_model").T.to_string())
