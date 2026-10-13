"""
Checkpoint 5.3 - cross-sectional ranking model, validated two ways.

A) Combinatorial purged CV x random stock hold-out (Monte Carlo).  Time is cut into
   N_BLOCKS contiguous blocks; every pair of blocks is a test set (45 splits), so test
   periods come from everywhere in history, not just the end. In each split a random
   30% of stocks is ALSO held out, so a test prediction is for a stock the model never
   trained on, in a period it never trained on. Training rows within PURGE sample-steps
   of a test block are deleted (label overlap + embargo). Plain random row splits are
   not used: neighbouring rows share 21-day label windows and would leak.
B) Purged expanding walk-forward on all stocks (the conservative single path).

Hyper-parameters below were fixed before any result was seen and were not tuned.
Costs: 0.175% of traded value per side (0.35% per round trip), charged to the strategy
AND to the equal-weight benchmark. Signal at close t, trade at close t+1.
"""
from pathlib import Path
from itertools import combinations
import numpy as np, pandas as pd, sys, warnings, json
from sklearn.linear_model import Ridge
import lightgbm as lgb
warnings.filterwarnings("ignore")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
P = ROOT / "data" / "panel_v2"; REP = ROOT / "reports" / "phase5"
DEV_END = "2025-03-31"
N_BLOCKS, K_TEST, PURGE, REPEATS, HOLD_FRAC = 10, 2, 6, 4, 0.30
REBAL_EVERY, COST_SIDE, PER_YEAR = 4, 0.00175, 252 / 20
SEED = 20261012

D = pd.read_parquet(P / "xs_panel.parquet")
FEATS = pd.read_csv(REP / "checkpoint_5_2_feature_list.csv")["feature"].tolist()
TR = pd.read_parquet(P / "close_total_return.parquet").loc[:DEV_END].ffill()
CAL = TR.index; DATES = np.array(sorted(D.date.unique()))
POS = {d: i for i, d in enumerate(CAL)}

def fit_predict(model, tr, te, shuffle_rng=None):
    y = tr.y_rank.values
    if shuffle_rng is not None:                       # permute labels within each date
        y = tr.groupby("date").y_rank.transform(lambda s: shuffle_rng.permutation(s.values)).values
    if model == "momentum_12_1": return te["mom_12_1"].values
    if model == "ridge": return Ridge(alpha=100.0).fit(tr[FEATS].values, y).predict(te[FEATS].values)
    if model == "lgbm":
        m = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=8, min_child_samples=200,
                              subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=10.0,
                              random_state=0, n_jobs=2, verbose=-1)
        return m.fit(tr[FEATS].values, y).predict(te[FEATS].values)
    raise ValueError(model)

def segments(test_dates):
    idx = np.searchsorted(DATES, np.array(sorted(test_dates))); out, cur = [], [idx[0]]
    for i in idx[1:]:
        if i == cur[-1] + 1: cur.append(i)
        else: out.append(cur); cur = [i]
    out.append(cur); return [[DATES[i] for i in s] for s in out]

def backtest(te, frac):
    """te: rows (date, symbol, score) for the test group. Returns per-period net returns."""
    rec = []
    by = {d: g for d, g in te.groupby("date")}
    for seg in segments(te.date.unique()):
        rb = seg[::REBAL_EVERY]
        w_s, w_b = pd.Series(dtype=float), pd.Series(dtype=float)
        for j, d in enumerate(rb):
            e0 = POS[d] + 1; e1 = min((POS[rb[j + 1]] + 1) if j + 1 < len(rb) else e0 + 20, len(CAL) - 1)
            if e1 <= e0: continue
            g = by[d]; n = max(int(round(len(g) * frac)), 3)
            top = g.nlargest(n, "score").symbol
            t_s = pd.Series(1 / n, index=top.values); t_b = pd.Series(1 / len(g), index=g.symbol.values)
            ret = TR.iloc[e1] / TR.iloc[e0] - 1
            out = {}
            for name, tgt, prev in (("strat", t_s, w_s), ("bench", t_b, w_b)):
                traded = tgt.sub(prev, fill_value=0).abs().sum()      # buys + sells as share of capital
                gross = float((tgt * ret.reindex(tgt.index)).sum())
                last = j + 1 == len(rb)
                net = (1 - traded * COST_SIDE) * (1 + gross) * (1 - (COST_SIDE if last else 0)) - 1
                drift = tgt * (1 + ret.reindex(tgt.index)); drift = drift / drift.sum()
                out[name] = net; out[name + "_traded"] = traded
                if name == "strat": w_s = drift
                else: w_b = drift
            rec.append(dict(date=d, **out))
    return pd.DataFrame(rec)

def score_fold(te, frac):
    te = te.copy()
    g = te.groupby("date")
    te["up"] = (te.fwd_ret > g.fwd_ret.transform("median")).astype(int)
    te["pred_up"] = (te.score > g.score.transform("median")).astype(int)
    ic = g.apply(lambda x: x.score.rank().corr(x.fwd_ret.rank())).mean()
    bt = backtest(te, frac)
    ex = bt.strat - bt.bench
    return dict(accuracy=float((te.up == te.pred_up).mean()), rank_ic=float(ic),
                strat_ann=float(bt.strat.mean() * PER_YEAR), bench_ann=float(bt.bench.mean() * PER_YEAR),
                excess_ann=float(ex.mean() * PER_YEAR), n_test_rows=len(te), n_periods=len(bt),
                turnover_per_rebalance=float(bt.strat_traded.mean() / 2)), te, bt

def stats(x, per_year=PER_YEAR):
    x = np.asarray(x, float); eq = np.cumprod(1 + x)
    return dict(cagr=float(eq[-1] ** (per_year / len(x)) - 1), ann_vol=float(x.std(ddof=1) * np.sqrt(per_year)),
                sharpe=float(x.mean() / x.std(ddof=1) * np.sqrt(per_year)),
                max_dd=float((eq / np.maximum.accumulate(eq) - 1).min()))

def main():
    rng = np.random.default_rng(SEED)
    blocks = np.array_split(DATES, N_BLOCKS); syms = np.array(sorted(D.symbol.unique()))
    didx = pd.Series(np.searchsorted(DATES, D.date.values), index=D.index)
    MODELS = ["momentum_12_1", "ridge", "lgbm"]
    rows, plan = [], []
    for combo in combinations(range(N_BLOCKS), K_TEST):
        for r in range(REPEATS):
            plan.append((combo, r, rng.choice(syms, int(round(len(syms) * HOLD_FRAC)), replace=False)))
    for combo, r, held in plan:
        test_i = np.concatenate([np.searchsorted(DATES, blocks[b]) for b in combo])
        banned = set()
        for b in combo:
            bi = np.searchsorted(DATES, blocks[b]); banned |= set(range(bi[0] - PURGE, bi[-1] + PURGE + 1))
        is_te_date = didx.isin(test_i); is_held = D.symbol.isin(held)
        tr = D[~didx.isin(banned) & ~is_held]; te0 = D[is_te_date & is_held]
        assert not set(tr.symbol) & set(te0.symbol) and not set(tr.date) & set(te0.date)
        for m in MODELS + ["lgbm_shuffled_labels"]:
            if m == "lgbm_shuffled_labels" and r > 0: continue
            te = te0[["date", "symbol", "fwd_ret"]].copy()
            te["score"] = fit_predict("lgbm" if "shuffled" in m else m, tr, te0,
                                      np.random.default_rng(SEED + len(rows)) if "shuffled" in m else None)
            s, _, _ = score_fold(te, 1 / 3)
            rows.append(dict(model=m, test_blocks=str(combo), repeat=r, n_train_rows=len(tr), **s))
    R = pd.DataFrame(rows); R.to_csv(REP / "checkpoint_5_3_cpcv_runs.csv", index=False)
    def agg(g):
        o = {}
        for c in ["accuracy", "rank_ic", "excess_ann"]:
            o[c + "_mean"] = g[c].mean(); o[c + "_p05"] = g[c].quantile(.05); o[c + "_p95"] = g[c].quantile(.95)
        o["share_runs_accuracy_above_50pct"] = (g.accuracy > .5).mean()
        o["share_runs_excess_positive"] = (g.excess_ann > 0).mean()
        o["strat_ann_mean"] = g.strat_ann.mean(); o["bench_ann_mean"] = g.bench_ann.mean()
        o["turnover_per_rebalance"] = g.turnover_per_rebalance.mean(); o["runs"] = len(g)
        return pd.Series(o)
    A = R.groupby("model").apply(agg).round(4); A.to_csv(REP / "checkpoint_5_3_cpcv_summary.csv")
    print("=== A) CPCV x random stock hold-out ==="); print(A.T.to_string())

    # ---- B) purged expanding walk-forward, all stocks ----
    years = sorted({pd.Timestamp(d).year for d in DATES if pd.Timestamp(d).year >= 2018})
    wf = {m: [] for m in MODELS}
    for y in years:
        te0 = D[D.date.dt.year == y]; first = np.searchsorted(DATES, te0.date.min())
        tr = D[didx < first - PURGE]
        for m in MODELS:
            te = te0[["date", "symbol", "fwd_ret"]].copy(); te["score"] = fit_predict(m, tr, te0); wf[m].append(te)
    out, series = [], {}
    for m in MODELS:
        te = pd.concat(wf[m]); s, te2, bt = score_fold(te, 0.20)
        ex = (bt.strat - bt.bench).values
        bs = np.random.default_rng(SEED); n = len(ex); B = 5000; L = 6
        means = []
        for _ in range(B):
            st = bs.integers(0, n, int(np.ceil(n / L))); ii = np.concatenate([(np.arange(L) + a) % n for a in st])[:n]
            means.append(ex[ii].mean() * PER_YEAR)
        series[m] = bt.assign(model=m)
        out.append(dict(model=m, accuracy=s["accuracy"], rank_ic=s["rank_ic"], periods=n,
                        **{"strat_" + k: v for k, v in stats(bt.strat).items()},
                        excess_ann=float(ex.mean() * PER_YEAR), excess_ci05=float(np.quantile(means, .05)),
                        excess_ci95=float(np.quantile(means, .95)), prob_excess_gt0=float((np.array(means) > 0).mean()),
                        share_periods_beating_benchmark=float((ex > 0).mean()), turnover_per_rebalance=s["turnover_per_rebalance"]))
    bt = series[MODELS[0]]
    e0 = [POS[d] + 1 for d in bt.date]; e1 = e0[1:] + [min(e0[-1] + 20, len(CAL) - 1)]
    nifty = pd.read_parquet(P / "index.parquet").loc[:DEV_END, "NIFTY100"].ffill().reindex(CAL).ffill()
    nret = nifty.iloc[e1].values / nifty.iloc[e0].values - 1
    out.append(dict(model="equal_weight_universe (benchmark, net)", periods=len(bt), **{"strat_" + k: v for k, v in stats(bt.bench).items()}))
    out.append(dict(model="NIFTY100 price index (no dividends, no costs)", periods=len(bt), **{"strat_" + k: v for k, v in stats(nret).items()}))
    W = pd.DataFrame(out).round(4); W.to_csv(REP / "checkpoint_5_3_walkforward_summary.csv", index=False)
    pd.concat(series.values()).to_csv(REP / "checkpoint_5_3_walkforward_periods.csv", index=False)
    print("=== B) walk-forward", str(bt.date.min().date()), "to", str(bt.date.max().date()), "==="); print(W.T.to_string())

if __name__ == "__main__":
    main()
