"""
Checkpoint 5.5 - rebuild the low-tier baseline paper under honest rules and compare.

Baseline: Iskakov et al. (2026), "Machine Learning-Based Portfolio Optimization Using
Cross-Sectional Signals: Evidence from the NSE Market", ETASR 16(4). Their recipe, as
published: 20 large caps; 8 inputs (log return, RSI14, MACD, ATR14, Bollinger width, OBV,
SMA14, volume) min-max scaled; 60-day window -> next-day return; one model per stock;
forecasts averaged over the last 10; cross-sectional rank; "signal weighted" portfolio
rebalanced daily; no transaction costs; one chronological 80/20 split.

Differences forced on this rebuild (stated, not hidden):
  - Their window is 2020-01..2025-12. Ours stops at 2025-03-31 (sealed holdout), so
    protocol A is 2020-01..2025-03 with the same 80/20 rule, and protocol B is a longer
    walk-forward (train from 2015, yearly refit, test 2018-01..2025-03).
  - The scaler is fitted on training rows only.
  - Models: ridge, lasso, random forest, gradient boosting, MLP. LSTM runs only if PyTorch
    is importable (it was not installable in the sandbox where this was written, so the
    LSTM branch is UNTESTED there).
"""
from pathlib import Path
import numpy as np, pandas as pd, sys, warnings, time
from sklearn.linear_model import Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
import lightgbm as lgb
sys.path.insert(0, str(Path(__file__).resolve().parent)); import xs_lib as L
warnings.filterwarnings("ignore")
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else Path(__file__).resolve().parents[1]
REP = ROOT / "reports" / "phase5"; RAW = ROOT / "data" / "raw" / "yahoo"
PAPER20 = ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "TCS", "INFY", "HCLTECH", "WIPRO", "RELIANCE", "ONGC", "NTPC", "BPCL",
           "BRITANNIA", "ITC", "NESTLEIND", "TATACONSUM", "TMPV", "MARUTI", "M&M", "BAJAJ-AUTO"]   # TMPV = Tata Motors
WIN, SMOOTH, COST_SIDE = 60, 10, 0.00175
try:
    import torch; HAVE_TORCH = True
except Exception: HAVE_TORCH = False

def features(s):
    d = pd.read_csv(RAW / f"{s}.csv", parse_dates=["Date"]).set_index("Date").loc[:L.DEV_END]
    d = d[d.Volume > 0]
    c = d.Close; f = pd.DataFrame(index=d.index)
    f["logret"] = np.log(c).diff()
    dl = c.diff(); up = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    dn = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean(); f["rsi14"] = 100 - 100 / (1 + up / dn)
    f["macd"] = c.ewm(span=12, min_periods=12).mean() - c.ewm(span=26, min_periods=26).mean()
    tr = pd.concat([d.High - d.Low, (d.High - c.shift()).abs(), (d.Low - c.shift()).abs()], axis=1).max(axis=1)
    f["atr14"] = tr.rolling(14).mean()
    m, sd = c.rolling(20).mean(), c.rolling(20).std(); f["bbw"] = 4 * sd / m
    f["obv"] = (np.sign(dl).fillna(0) * d.Volume).cumsum(); f["sma14"] = c.rolling(14).mean(); f["volume"] = d.Volume
    f["y"] = f.logret.shift(-1)                      # next-day return, the paper's target
    return f.dropna(subset=[x for x in f.columns if x != "y"])

def windows(f, cols):
    X = f[cols].values; n = len(f)
    idx = np.arange(WIN - 1, n)
    W = np.stack([X[i - WIN + 1:i + 1] for i in idx])       # (rows, 60, 8)
    return W, f.index[idx], f.y.values[idx]

def make(name):
    if name == "ridge": return Ridge(alpha=1.0)
    if name == "lasso": return Lasso(alpha=1e-5, max_iter=5000)
    if name == "random_forest": return RandomForestRegressor(n_estimators=100, max_depth=10, max_features="sqrt", n_jobs=2, random_state=0)
    if name == "gradient_boosting": return lgb.LGBMRegressor(n_estimators=100, max_depth=10, num_leaves=31, learning_rate=0.05, colsample_bytree=0.3, random_state=0, n_jobs=2, verbose=-1)
    if name == "mlp": return MLPRegressor(hidden_layer_sizes=(64, 32), early_stopping=True, n_iter_no_change=10, max_iter=200, learning_rate_init=0.001, random_state=0)

def fit_lstm(Wtr, ytr, Wte):                                    # UNTESTED where torch is absent
    torch.manual_seed(0)
    net = torch.nn.LSTM(Wtr.shape[2], 32, batch_first=True); head = torch.nn.Linear(32, 1)
    opt = torch.optim.Adam(list(net.parameters()) + list(head.parameters()), lr=0.001)
    Xt, yt = torch.tensor(Wtr, dtype=torch.float32), torch.tensor(ytr, dtype=torch.float32)
    nv = max(int(len(Xt) * 0.1), 1); Xa, ya, Xv, yv = Xt[:-nv], yt[:-nv], Xt[-nv:], yt[-nv:]
    best, bad, state = 1e9, 0, None
    for ep in range(100):
        for i in range(0, len(Xa), 64):
            opt.zero_grad(); o, _ = net(Xa[i:i + 64]); loss = ((head(o[:, -1]).squeeze(-1) - ya[i:i + 64]) ** 2).mean(); loss.backward(); opt.step()
        with torch.no_grad(): o, _ = net(Xv); v = float(((head(o[:, -1]).squeeze(-1) - yv) ** 2).mean())
        if v < best - 1e-9: best, bad, state = v, 0, (net.state_dict(), head.state_dict())
        else:
            bad += 1
            if bad >= 10: break
    net.load_state_dict(state[0]); head.load_state_dict(state[1])
    with torch.no_grad(): o, _ = net(torch.tensor(Wte, dtype=torch.float32)); return head(o[:, -1]).squeeze(-1).numpy()

MODELS = ["ridge", "lasso", "random_forest", "gradient_boosting", "mlp"] + (["lstm"] if HAVE_TORCH else [])
COLS = ["logret", "rsi14", "macd", "atr14", "bbw", "obv", "sma14", "volume"]

def run_protocol(F, folds, tag):
    """folds: list of (train_start, train_end, test_start, test_end). Returns predictions."""
    preds = []
    for s in PAPER20:
        W, dates, y = windows(F[s], COLS)
        for (a, b, c, d) in folds:
            tr = (dates >= a) & (dates < b) & ~np.isnan(y); te = (dates >= c) & (dates <= d)
            tr[np.where(tr)[0][-1:]] = False                    # last train row's label is the first test day
            if tr.sum() < 250 or te.sum() == 0: continue
            lo = W[tr].min(axis=(0, 1)); hi = W[tr].max(axis=(0, 1)); sc = lambda Z: (Z - lo) / np.where(hi > lo, hi - lo, 1)
            Wtr, Wte = sc(W[tr]), sc(W[te]); out = pd.DataFrame({"date": dates[te], "symbol": s, "y": y[te]})
            for m in MODELS:
                if m == "lstm": out[m] = fit_lstm(Wtr, y[tr], Wte)
                else: out[m] = make(m).fit(Wtr.reshape(len(Wtr), -1), y[tr]).predict(Wte.reshape(len(Wte), -1))
            preds.append(out)
    return pd.concat(preds, ignore_index=True).assign(protocol=tag)

def portfolio(score, R, lag, cost_side):
    """score: date x symbol signal known at close of date. Signal-weighted: w ∝ cross-sectional rank.
    lag=0 trades at the close the signal is formed (the paper's frictionless reading); lag=1 the next close."""
    rk = score.rank(axis=1); w = rk.div(rk.sum(axis=1), axis=0).shift(lag).dropna(how="all")
    R = R.reindex(w.index).fillna(0.0); nxt = R.shift(-1)       # return earned over the following day
    gross = (w * nxt).sum(axis=1)
    drift = w * (1 + nxt); drift = drift.div(drift.sum(axis=1), axis=0)
    traded = (w - drift.shift(1)).abs().sum(axis=1); traded.iloc[0] = 1.0
    net = ((1 - traded * cost_side) * (1 + gross) - 1).iloc[:-1]
    net.index = w.index[1:]                                     # label each return by the day it is earned
    return net, float(traded.iloc[1:].mean() / 2)

def smooth_signal(P, m, R):
    """Forecasts on the cleaned-panel calendar; short gaps carried forward so a stock missing
    one day is not dropped from the portfolio for ten."""
    S = P.pivot(index="date", columns="symbol", values=m)
    cal = R.index[(R.index >= S.index.min()) & (R.index <= S.index.max())]
    return S.reindex(cal).ffill(limit=5).rolling(SMOOTH).mean().dropna(how="any")

def evaluate(P, R, tag):
    rows = []; dates = np.array(sorted(P.date.unique())); Rt = R.reindex(dates)
    ew = pd.DataFrame(1.0, index=dates, columns=PAPER20)
    ok = P.y.notna() & (P.y != 0); up = (P.y[ok] > 0).mean()
    for m in MODELS:
        acc = float((np.sign(P[m]) == np.sign(P.y))[ok].mean())
        S = smooth_signal(P, m, R)
        r = dict(protocol=tag, method=f"baseline: {m}", next_day_direction_accuracy=acc, share_of_up_days=float(up),
                 always_up_accuracy=float(max(up, 1 - up)))
        for lab, lag, cs in (("paper_rules_no_cost_no_lag", 0, 0.0), ("no_lag_with_cost", 0, COST_SIDE), ("lag1_with_cost", 1, COST_SIDE)):
            net, to = portfolio(S, R, lag, cs); b, _ = portfolio(ew.loc[S.index], R, lag, cs)
            p = L.perf(net); e = L.excess_stats(net, b.reindex(net.index))
            r.update({f"{lab}__cagr": p["cagr"], f"{lab}__sharpe": p["sharpe"], f"{lab}__bench_sharpe": L.perf(b)["sharpe"],
                      f"{lab}__excess_ann": e["excess_ann"], f"{lab}__ci05": e["ci05"], f"{lab}__ci95": e["ci95"]})
        r["one_way_turnover_per_day"] = to; rows.append(r)
    return rows

def ours(R, TRp, start, end, tag):
    """Our simplest method on the SAME 20 stocks and dates: 12-1 total-return momentum,
    monthly, one-day lag, costs. Two portfolio shapes: signal-weighted (their shape) and top third."""
    TR20 = TRp[PAPER20]; mom = TR20.shift(21) / TR20.shift(252) - 1
    cal = TR20.index; sd = cal[(cal >= start) & (cal <= end)][::5]
    sc = pd.DataFrame({"date": np.repeat(sd, 20), "symbol": PAPER20 * len(sd), "score": mom.loc[sd].values.ravel()}).dropna()
    rows = []
    runs = [L.daily_backtest(sc, TR20, 1 / 3, o) for o in range(4)]
    es = [L.excess_stats(x.strat, x.bench, seed=i) for i, x in enumerate(runs)]
    rows.append({"protocol": tag, "method": "ours: 12-1 momentum, top third, 20-day rebalance",
                 "lag1_with_cost__cagr": np.mean([L.perf(x.strat)["cagr"] for x in runs]), "lag1_with_cost__sharpe": np.mean([L.perf(x.strat)["sharpe"] for x in runs]),
                 "lag1_with_cost__bench_sharpe": np.mean([L.perf(x.bench)["sharpe"] for x in runs]), "lag1_with_cost__excess_ann": np.mean([e["excess_ann"] for e in es]),
                 "lag1_with_cost__ci05": np.mean([e["ci05"] for e in es]), "lag1_with_cost__ci95": np.mean([e["ci95"] for e in es]),
                 "one_way_turnover_per_day": np.mean([x.attrs["turnover"] for x in runs]) / 20})
    return rows

def main():
    t0 = time.time()
    F = {s: features(s) for s in PAPER20}
    TRp = pd.read_parquet(ROOT / "data" / "panel_v2" / "close_total_return.parquet").loc[:L.DEV_END].ffill()
    R = TRp[PAPER20].pct_change(fill_method=None)
    alld = TRp.loc["2020-01-01":].index; cut = alld[int(len(alld) * 0.8)]
    saved = ROOT / "data" / "panel_v2" / "baseline_predictions.parquet"
    if "--reuse" in sys.argv and saved.exists():                # skip the 10-minute refit, re-score saved forecasts
        Q = pd.read_parquet(saved); A = Q[Q.protocol.str.startswith("A")]; B = Q[Q.protocol.str.startswith("B")]
    else:
        A = run_protocol(F, [(pd.Timestamp("2020-01-01"), cut, cut, alld[-1])], "A: paper split 2020-01..2025-03, last 20% test")
        foldsB = [(pd.Timestamp("2015-01-01"), pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y}-12-31")) for y in range(2018, 2026)]
        B = run_protocol(F, foldsB, "B: walk-forward 2018-01..2025-03, yearly refit")
        pd.concat([A, B]).to_parquet(saved)
    rows = evaluate(A, R, A.protocol.iloc[0]) + ours(R, TRp, A.date.min(), A.date.max(), A.protocol.iloc[0])
    rows += evaluate(B, R, B.protocol.iloc[0]) + ours(R, TRp, B.date.min(), B.date.max(), B.protocol.iloc[0])
    T = pd.DataFrame(rows).round(4); T.to_csv(REP / "checkpoint_5_5_baseline_comparison.csv", index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
    for tag, g in T.groupby("protocol"):
        print("\n==", tag, "| test days:", (A if tag.startswith("A") else B).date.nunique())
        print(g.drop(columns="protocol").set_index("method").T.to_string())
    print("torch available:", HAVE_TORCH, "| seconds:", round(time.time() - t0))

if __name__ == "__main__":
    main()
