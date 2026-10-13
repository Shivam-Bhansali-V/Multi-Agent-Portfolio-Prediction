"""Checkpoint 5.4b - is the 'illiquidity' edge real or a survivor-list artifact?
(a) which stocks does the top-20% Amihud portfolio hold, and when did they list;
(b) do the trained models keep their edge when the liquidity/size proxies are removed."""
from pathlib import Path
import numpy as np, pandas as pd, sys, warnings
from sklearn.linear_model import Ridge
import lightgbm as lgb
sys.path.insert(0, str(Path(__file__).resolve().parent)); import xs_lib as L
warnings.filterwarnings("ignore")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
REP = ROOT / "reports" / "phase5"; SEED, N_BLOCKS, PURGE = 20261012, 10, 6
D, TR = L.load(ROOT); FEATS = pd.read_csv(REP / "checkpoint_5_2_feature_list.csv")["feature"].tolist()
TO = pd.read_parquet(ROOT / "data" / "panel_v2" / "turnover_inr.parquet").loc[:L.DEV_END]
top = D[D.groupby("date").amihud_60.rank(pct=True) > 0.8]
share = (top.symbol.value_counts() / D.date.nunique()).round(2)
med_to = TO.rolling(252, min_periods=120).median()
rank_to = med_to.rank(axis=1, pct=True)
r0 = {s: rank_to[s].dropna().iloc[0] for s in share.index[:15]}; r1 = {s: rank_to[s].dropna().iloc[-1] for s in share.index[:15]}
A = pd.DataFrame({"share_of_dates_in_top20pct_illiquid": share.head(15), "turnover_pct_rank_at_start": pd.Series(r0).round(2),
                  "turnover_pct_rank_at_end_of_dev": pd.Series(r1).round(2)})
A["total_return_multiple_2016_to_2025"] = [round(float(TR[s].dropna().iloc[-1] / TR[s].loc["2016-02-12":].dropna().iloc[0]), 1) for s in A.index]
print(A.to_string()); print("median multiple, all stocks:", round(float((TR.ffill().iloc[-1] / TR.loc["2016-02-12":].bfill().iloc[0]).median()), 1))
A.to_csv(REP / "checkpoint_5_4b_illiquid_names.csv")
DATES = np.array(sorted(D.date.unique())); didx = np.searchsorted(DATES, D.date.values); blocks = np.array_split(np.arange(len(DATES)), N_BLOCKS)
D["block"] = np.concatenate([[b] * len(ix) for b, ix in enumerate(blocks)])[didx]
syms = np.array(sorted(D.symbol.unique())); rng2 = np.random.default_rng(SEED + 1)
D["sfold"] = D.symbol.map(dict(zip(rng2.permutation(syms), np.arange(len(syms)) % 3)))
SETS = {"all_24_features": FEATS, "without_liquidity_proxies": [f for f in FEATS if f not in ("amihud_60", "turnover_trend")],
        "price_only_no_liquidity_no_risk": [f for f in FEATS if f not in ("amihud_60", "turnover_trend", "beta_252", "vol_20", "vol_60", "vol_252", "idio_vol_60", "max_ret_21", "skew_60")]}
out = []
for name, fs in SETS.items():
    for scheme in ("block_cv_unseen_stock", "walk_forward"):
        for m in ("ridge", "lgbm"):
            D["_p"] = np.nan
            def fit(tr, te):
                if m == "ridge": return Ridge(alpha=100.0).fit(tr[fs], tr.y_rank).predict(D.loc[te, fs])
                return lgb.LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=8, min_child_samples=200, subsample=0.7, subsample_freq=1,
                                         colsample_bytree=0.7, reg_lambda=10.0, random_state=0, n_jobs=2, verbose=-1).fit(tr[fs], tr.y_rank).predict(D.loc[te, fs])
            if scheme == "walk_forward":
                for y in range(2018, 2026):
                    te = D.date.dt.year == y
                    if te.sum() == 0: continue
                    first = didx[te.values].min(); D.loc[te, "_p"] = fit(D[didx < first - PURGE], te)
            else:
                for b in range(N_BLOCKS):
                    ix = blocks[b]; banned = (didx >= ix[0] - PURGE) & (didx <= ix[-1] + PURGE)
                    for f in range(3):
                        te = (D.block == b) & (D.sfold == f); D.loc[te, "_p"] = fit(D[~banned & (D.sfold != f)], te)
            P = D[D._p.notna()]; ic, t, _ = L.ic_table(P, "_p")
            runs = [L.daily_backtest(P[["date", "symbol"]].assign(score=P._p), TR, 0.20, o) for o in range(4)]
            es = [L.excess_stats(x.strat, x.bench, seed=i) for i, x in enumerate(runs)]
            out.append(dict(features=name, n_features=len(fs), scheme=scheme, model=m, ic=ic, ic_t=t, accuracy=L.accuracy(P, "_p")[0],
                            excess_ann=np.mean([e["excess_ann"] for e in es]), ci05=np.mean([e["ci05"] for e in es]), ci95=np.mean([e["ci95"] for e in es]),
                            sharpe=np.mean([L.perf(x.strat)["sharpe"] for x in runs]), bench_sharpe=np.mean([L.perf(x.bench)["sharpe"] for x in runs]),
                            max_dd=np.mean([L.perf(x.strat)["max_dd"] for x in runs])))
O = pd.DataFrame(out).round(4); O.to_csv(REP / "checkpoint_5_4b_feature_set_ablation.csv", index=False)
pd.set_option("display.width", 250); print(O.to_string(index=False))
