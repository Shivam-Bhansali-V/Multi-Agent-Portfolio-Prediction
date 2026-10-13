"""Shared helpers for Phase 5 scripts: panel loading, daily-curve backtest, statistics."""
from pathlib import Path
import numpy as np, pandas as pd
DEV_END = "2025-03-31"
REBAL_EVERY, COST_SIDE = 4, 0.00175

def load(root):
    P = Path(root) / "data" / "panel_v2"
    D = pd.read_parquet(P / "xs_panel.parquet")
    TR = pd.read_parquet(P / "close_total_return.parquet").loc[:DEV_END].ffill()
    return D, TR

def daily_backtest(scores, TR, frac=0.20, offset=0, cost_side=COST_SIDE, min_names=3):
    """scores: DataFrame(date, symbol, score); one row per stock in the investable group
    on each sample date. Signal at close t, trade at close t+1, hold to the next rebalance.
    Returns daily net returns of the strategy and of the equal-weight benchmark of the
    same group (both pay costs), plus one-way turnover per rebalance."""
    cal = TR.index; pos = {d: i for i, d in enumerate(cal)}
    dates = np.array(sorted(scores.date.unique()))[offset::REBAL_EVERY]
    by = {d: g for d, g in scores.groupby("date")}
    R = TR.pct_change(fill_method=None).fillna(0.0)
    out = {"strat": pd.Series(0.0, index=cal), "bench": pd.Series(0.0, index=cal)}
    formed = pd.Series(pd.NaT, index=cal)            # sample date that formed each day's position
    w = {"strat": pd.Series(dtype=float), "bench": pd.Series(dtype=float)}; turn = []
    first = last = None
    for j, d in enumerate(dates):
        e0 = pos[d] + 1
        e1 = pos[dates[j + 1]] + 1 if j + 1 < len(dates) else min(e0 + 20, len(cal) - 1)
        if e0 >= len(cal) - 1 or e1 <= e0: continue
        g = by[d]; n = max(int(round(len(g) * frac)), min_names)
        tgt = {"strat": pd.Series(1.0 / n, index=g.nlargest(n, "score").symbol.values),
               "bench": pd.Series(1.0 / len(g), index=g.symbol.values)}
        first = e0 if first is None else first; last = e1
        formed.iloc[e0 + 1:e1 + 1] = d
        for k in ("strat", "bench"):
            traded = tgt[k].sub(w[k], fill_value=0).abs().sum()
            if k == "strat": turn.append(traded / 2)
            rr = R.iloc[e0 + 1:e1 + 1][tgt[k].index]
            val = (1 + rr).cumprod().mul(tgt[k], axis=1)
            pv = val.sum(axis=1); pr = pv / pv.shift(1).fillna(1.0) - 1
            pr.iloc[0] = (1 + pr.iloc[0]) * (1 - traded * cost_side) - 1     # pay to get into the target
            out[k].iloc[e0 + 1:e1 + 1] = pr.values
            w[k] = val.iloc[-1] / pv.iloc[-1]
    res = pd.DataFrame(out).iloc[first + 1:last + 1]
    res["formed"] = formed.iloc[first + 1:last + 1].values
    res.attrs["turnover"] = float(np.mean(turn[1:])) if len(turn) > 1 else np.nan
    return res

def perf(r):
    """r: daily returns (DatetimeIndex). Annualised by elapsed calendar time."""
    r = r.dropna(); eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25; per_year = len(r) / yrs
    return dict(cagr=float(eq.iloc[-1] ** (1 / yrs) - 1), vol=float(r.std() * np.sqrt(per_year)),
                sharpe=float(r.mean() / r.std() * np.sqrt(per_year)), max_dd=float((eq / eq.cummax() - 1).min()))

def excess_stats(strat, bench, block=21, B=4000, seed=0):
    """Annualised mean daily excess return with a circular block-bootstrap 90% interval."""
    ex = (strat - bench).dropna().values; n = len(ex)
    per_year = n / ((strat.index[-1] - strat.index[0]).days / 365.25)
    rng = np.random.default_rng(seed); k = int(np.ceil(n / block)); m = np.empty(B)
    for b in range(B):
        st = rng.integers(0, n, k); ii = (st[:, None] + np.arange(block)[None, :]).ravel()[:n] % n
        m[b] = ex[ii].mean()
    return dict(excess_ann=float(ex.mean() * per_year), ci05=float(np.quantile(m, .05) * per_year),
                ci95=float(np.quantile(m, .95) * per_year), p_gt0=float((m > 0).mean()))

def ic_table(df, score_col, ret_col="fwd_ret", step=4):
    """Per-date Spearman rank IC. Labels overlap, so the t-stat is computed on every
    `step`-th date and averaged over the `step` possible starting offsets."""
    g = df.groupby("date")
    ic = g.apply(lambda x: x[score_col].rank().corr(x[ret_col].rank()))
    ts = []
    for o in range(step):
        sub = ic.iloc[o::step].dropna()
        if len(sub) > 2: ts.append(sub.mean() / sub.std(ddof=1) * np.sqrt(len(sub)))
    return float(ic.mean()), float(np.mean(ts)), ic

def accuracy(df, score_col, ret_col="fwd_ret", tail=None):
    """Above/below-median hit rate. tail=0.2 scores only the top and bottom 20% of calls."""
    g = df.groupby("date")
    up = df[ret_col] > g[ret_col].transform("median")
    pr = g[score_col].rank(pct=True)
    if tail is None: return float(((pr > 0.5) == up).mean()), 1.0
    m = (pr > 1 - tail) | (pr <= tail)
    return float(((pr[m] > 0.5) == up[m]).mean()), float(m.mean())
