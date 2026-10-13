"""
Checkpoint 5.6 - point-in-time universe by traded value.

On each date the investable set is the N most-traded stocks of the pool, ranked on the
trailing 126-day median rupee turnover known that day. A stock that has since shrunk is
still in the set on the dates when it was big, as long as it is somewhere in the pool, so a
wide pool (NIFTY 500) with a narrow N (100) removes most, not all, survivorship bias.
With the present 97-stock pool only N=50 is meaningful.
Trained models use past data only (yearly refit) and exclude the liquidity features.
"""
from pathlib import Path
import numpy as np, pandas as pd, sys, warnings
from sklearn.linear_model import Ridge
import lightgbm as lgb
sys.path.insert(0, str(Path(__file__).resolve().parent)); import xs_lib as L
warnings.filterwarnings("ignore")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
REP = ROOT / "reports" / "phase5"; PURGE = 6
D, TR = L.load(ROOT)
FEATS = [f for f in pd.read_csv(REP / "checkpoint_5_2_feature_list.csv")["feature"] if f not in ("amihud_60", "turnover_trend")]
DATES = np.array(sorted(D.date.unique())); didx = np.searchsorted(DATES, D.date.values)
pool = D.symbol.nunique(); NS = [n for n in (50, 100, 200) if n <= pool * 0.6] or [int(pool * 0.5)]
for m in ("ridge", "lgbm"): D[m] = np.nan
for y in range(2018, 2026):
    te = (D.date.dt.year == y).values
    if te.sum() == 0: continue
    tr = D[didx < didx[te].min() - PURGE]
    D.loc[te, "ridge"] = Ridge(alpha=100.0).fit(tr[FEATS], tr.y_rank).predict(D.loc[te, FEATS])
    D.loc[te, "lgbm"] = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=8, min_child_samples=200, subsample=0.7, subsample_freq=1,
                                          colsample_bytree=0.7, reg_lambda=10.0, random_state=0, n_jobs=2, verbose=-1).fit(tr[FEATS], tr.y_rank).predict(D.loc[te, FEATS])
W = D[D.date >= "2018-01-01"]; rows = []
for N in NS + [pool]:
    U = W[W.turnover_rank <= N]
    ever = U.symbol.nunique(); stay = U.groupby("symbol").date.count().eq(U.date.nunique()).sum()
    for sig in ("mom_12_1", "mom_6_1", "ridge", "lgbm"):
        P = U[U[sig].notna()]; ic, t, _ = L.ic_table(P, sig)
        runs = [L.daily_backtest(P[["date", "symbol"]].assign(score=P[sig]), TR, 0.20, o) for o in range(4)]
        s4 = pd.concat([x.strat for x in runs], axis=1).mean(axis=1).dropna(); b4 = pd.concat([x.bench for x in runs], axis=1).mean(axis=1).dropna()
        e = L.excess_stats(s4, b4); ps, pb = L.perf(s4), L.perf(b4)
        rows.append(dict(universe=f"top {N} by turnover" if N < pool else f"whole pool ({pool})", stocks_ever_in=ever, stocks_always_in=int(stay), signal=sig,
                         ic=ic, ic_t=t, accuracy=L.accuracy(P, sig)[0], cagr=ps["cagr"], bench_cagr=pb["cagr"], sharpe=ps["sharpe"], bench_sharpe=pb["sharpe"],
                         max_dd=ps["max_dd"], bench_max_dd=pb["max_dd"], excess_ann=e["excess_ann"], ci05=e["ci05"], ci95=e["ci95"], prob_gt0=e["p_gt0"]))
T = pd.DataFrame(rows).round(4); T.to_csv(REP / "checkpoint_5_6_pit_universe.csv", index=False)
pd.set_option("display.width", 250); print(T.to_string(index=False))
