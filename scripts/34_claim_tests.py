"""
Checkpoint 5.4 - test published claims on this data instead of assuming them.

Each candidate signal gets a score for every (date, stock). Untrained signals are the
ranked features themselves. Trained models (ridge, LightGBM) are scored out-of-sample by
purged block CV crossed with 3 random stock folds, so every prediction is for a stock and
a period the model did not train on.

To limit data-snooping, the 10 time blocks are split at random (fixed seed) into 5 DESIGN
blocks and 5 CONFIRM blocks. The winner is chosen on DESIGN blocks only (highest IC
t-stat) and then read off on CONFIRM blocks.
"""
from pathlib import Path
import numpy as np, pandas as pd, sys, warnings
from sklearn.linear_model import Ridge
import lightgbm as lgb
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xs_lib as L
warnings.filterwarnings("ignore")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
REP = ROOT / "reports" / "phase5"; SEED = 20261012; N_BLOCKS, PURGE = 10, 6

D, TR = L.load(ROOT)
FEATS = pd.read_csv(REP / "checkpoint_5_2_feature_list.csv")["feature"].tolist()
DATES = np.array(sorted(D.date.unique())); didx = np.searchsorted(DATES, D.date.values)
blocks = np.array_split(np.arange(len(DATES)), N_BLOCKS)
rng = np.random.default_rng(SEED)
design_blocks = sorted(rng.choice(N_BLOCKS, 5, replace=False).tolist())
block_of = np.concatenate([[b] * len(ix) for b, ix in enumerate(blocks)])
D["block"] = block_of[didx]; D["is_design"] = D.block.isin(design_blocks)
# hypothesised sign of each signal, written down before looking at any IC
SIGN = dict(mom_12_1=1, mom_6_1=1, mom_3_1=1, rev_1m=-1, rev_1w=-1, vol_20=-1, vol_60=-1, vol_252=-1,
            mom_12_1_riskadj=1, dist_52w_high=1, px_vs_sma200=1, sma50_vs_sma200=1, ema20_vs_ema50=1,
            rsi_14=1, rsi_20=1, macd_hist=1, bollinger_pctb=1, max_ret_21=-1, skew_60=-1, turnover_trend=1,
            amihud_60=1, beta_252=-1, idio_vol_60=-1, mom_6_1_vs_sector=1)

# --- extra signals built from prices -------------------------------------------------
lr = np.log(TR).diff(); sig = lr.rolling(252).std() * np.sqrt(252)
mr12 = (TR / TR.shift(252) - 1) / sig; mr6 = (TR / TR.shift(126) - 1) / sig
def at(panel): return panel.stack().reindex(pd.MultiIndex.from_frame(D[["date", "symbol"]])).values
D["_mr12"], D["_mr6"] = at(mr12), at(mr6)
z = lambda c: D.groupby("date")[c].transform(lambda s: (s - s.mean()) / s.std())
D["nse_momentum_index_score"] = (z("_mr12") + z("_mr6")) / 2          # NSE Nifty200 Momentum 30 recipe
D["nse_momentum_index_score"] = D.groupby("date")["nse_momentum_index_score"].transform(lambda s: s.fillna(s.median()))
D["composite_mom_lowvol"] = (D.mom_12_1 + D.mom_6_1 + D.dist_52w_high - D.vol_252) / 4
D["composite_all_signed"] = sum(SIGN[f] * D[f] for f in FEATS) / len(FEATS)
for h in (5, 63):
    D[f"fwd_{h}"] = at(TR.shift(-(1 + h)) / TR.shift(-1) - 1)

# --- trained models: unseen stock x unseen block -------------------------------------
syms = np.array(sorted(D.symbol.unique())); rng2 = np.random.default_rng(SEED + 1)
fold_of = dict(zip(rng2.permutation(syms), np.arange(len(syms)) % 3)); D["sfold"] = D.symbol.map(fold_of)
for m in ("ridge", "lgbm"): D[m] = np.nan
for b in range(N_BLOCKS):
    ix = blocks[b]; banned = (didx >= ix[0] - PURGE) & (didx <= ix[-1] + PURGE)
    for f in range(3):
        tr = D[~banned & (D.sfold != f)]; te = (D.block == b) & (D.sfold == f)
        assert not set(tr.symbol) & set(D[te].symbol)
        D.loc[te, "ridge"] = Ridge(alpha=100.0).fit(tr[FEATS], tr.y_rank).predict(D.loc[te, FEATS])
        g = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=8, min_child_samples=200, subsample=0.7,
                              subsample_freq=1, colsample_bytree=0.7, reg_lambda=10.0, random_state=0, n_jobs=2, verbose=-1)
        D.loc[te, "lgbm"] = g.fit(tr[FEATS], tr.y_rank).predict(D.loc[te, FEATS])
assert D[["ridge", "lgbm"]].notna().all().all()

CANDS = FEATS + ["nse_momentum_index_score", "composite_mom_lowvol", "composite_all_signed", "ridge", "lgbm"]
day_block = pd.Series(D.groupby("date").block.first())
def day_is_design(formed):                 # a day belongs to the block of the date that formed its position
    return day_block.reindex(pd.DatetimeIndex(formed)).isin(design_blocks).values
rows = []
for c in CANDS:
    s = SIGN.get(c, 1); D["_s"] = s * D[c]
    r = dict(signal=c, hypothesised_sign=s, kind="feature" if c in FEATS else "composite/model")
    for name, part in (("design", D[D.is_design]), ("confirm", D[~D.is_design]), ("all", D)):
        ic, t, _ = L.ic_table(part, "_s"); r[f"ic_{name}"] = ic; r[f"ic_t_{name}"] = t
        r[f"acc_{name}"] = L.accuracy(part, "_s")[0]; r[f"acc_top_bottom20_{name}"] = L.accuracy(part, "_s", tail=0.2)[0]
    runs = [L.daily_backtest(D[["date", "symbol"]].assign(score=D["_s"]), TR, 0.20, o) for o in range(4)]
    for name, sel in (("design", True), ("confirm", False), ("all", None)):
        ex, sh, bsh, dd = [], [], [], []
        for x in runs:
            y = x if sel is None else x[day_is_design(x.formed) == sel]
            ex.append((y.strat - y.bench).mean() * 247); sh.append(y.strat.mean() / y.strat.std() * np.sqrt(247))
            bsh.append(y.bench.mean() / y.bench.std() * np.sqrt(247))
        r[f"excess_ann_{name}"] = np.mean(ex); r[f"sharpe_{name}"] = np.mean(sh); r[f"bench_sharpe_{name}"] = np.mean(bsh)
    r["max_dd_all"] = np.mean([L.perf(x.strat)["max_dd"] for x in runs]); r["bench_max_dd_all"] = np.mean([L.perf(x.bench)["max_dd"] for x in runs])
    r["turnover"] = np.mean([x.attrs["turnover"] for x in runs])
    es = [L.excess_stats(x.strat, x.bench, seed=i) for i, x in enumerate(runs)]
    r["excess_ci05_all"] = np.mean([e["ci05"] for e in es]); r["excess_ci95_all"] = np.mean([e["ci95"] for e in es])
    rows.append(r)
T = pd.DataFrame(rows).round(4); T.to_csv(REP / "checkpoint_5_4_claim_tests.csv", index=False)
show = ["signal", "ic_design", "ic_t_design", "ic_confirm", "ic_t_confirm", "acc_all", "acc_top_bottom20_all",
        "excess_ann_design", "excess_ann_confirm", "excess_ann_all", "sharpe_all", "bench_sharpe_all", "turnover"]
pd.set_option("display.width", 250)
print("design blocks:", design_blocks); print(T.sort_values("ic_t_design", ascending=False)[show].to_string(index=False))
win = T.sort_values("ic_t_design", ascending=False).iloc[0]
print("\nSELECTED ON DESIGN:", win.signal); print(win.to_string())
# horizons
H = []
for c in ("mom_12_1", "nse_momentum_index_score", "vol_252", "rev_1m", "rsi_14", "lgbm"):
    D["_s"] = SIGN.get(c, 1) * D[c]
    for h, col, step in ((5, "fwd_5", 1), (21, "fwd_ret", 4), (63, "fwd_63", 13)):
        p = D[D[col].notna()]; ic, t, _ = L.ic_table(p, "_s", col, step); H.append(dict(signal=c, horizon_days=h, ic=ic, ic_t=t, accuracy=L.accuracy(p, "_s", col)[0]))
H = pd.DataFrame(H).round(4); H.to_csv(REP / "checkpoint_5_4_horizons.csv", index=False); print(H.to_string(index=False))
D[["date", "symbol", "fwd_ret", "block", "is_design", "ridge", "lgbm", "nse_momentum_index_score", "composite_mom_lowvol", "composite_all_signed"]].to_parquet(ROOT / "data" / "panel_v2" / "oos_scores.parquet")
