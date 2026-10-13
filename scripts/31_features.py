"""
Checkpoint 5.2 - cross-sectional feature panel and forward-return target.
Every feature at date t uses data up to the close of t only. The target is the total
return from the close of t+1 to the close of t+1+H (one-day execution lag), H = 21.
Features are ranked across the eligible stocks on each date and mapped to [-1, 1];
missing values become 0 (the cross-sectional median), following Gu, Kelly & Xiu (2020).
"""
from pathlib import Path
import numpy as np, pandas as pd, sys
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
P = ROOT / "data" / "panel_v2"
H, LAG, STEP = 21, 1, 5
DEV_END = "2025-03-31"          # holdout (April 2025 onward) is never loaded past this line

def rsi(px, n):
    d = px.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)

def main():
    tr = pd.read_parquet(P / "close_total_return.parquet").loc[:DEV_END]
    px = pd.read_parquet(P / "close_struct_adj.parquet").loc[:DEV_END]
    to = pd.read_parquet(P / "turnover_inr.parquet").loc[:DEV_END]
    el = pd.read_parquet(P / "eligible.parquet").loc[:DEV_END]
    idx = pd.read_parquet(P / "index.parquet").loc[:DEV_END, "NIFTY100"].ffill()
    ref = ROOT / "data" / "reference"
    lists = [pd.read_csv(p) for p in (ref / "ind_nifty500list.csv", ref / "ind_nifty100list.csv") if p.exists()]
    ind = pd.concat(lists).drop_duplicates("Symbol").set_index("Symbol")["Industry"]
    trf, pxf = tr.ffill(), px.ffill()
    r = trf.pct_change(fill_method=None); mr = idx.pct_change()
    F = {}
    F["mom_12_1"] = trf.shift(21) / trf.shift(252) - 1
    F["mom_6_1"] = trf.shift(21) / trf.shift(126) - 1
    F["mom_3_1"] = trf.shift(21) / trf.shift(63) - 1
    F["rev_1m"] = trf / trf.shift(21) - 1
    F["rev_1w"] = trf / trf.shift(5) - 1
    F["vol_20"] = r.rolling(20).std(); F["vol_60"] = r.rolling(60).std(); F["vol_252"] = r.rolling(252).std()
    F["mom_12_1_riskadj"] = F["mom_12_1"] / (F["vol_252"] * np.sqrt(252))
    F["dist_52w_high"] = pxf / pxf.rolling(252).max() - 1
    F["px_vs_sma200"] = pxf / pxf.rolling(200).mean() - 1
    F["sma50_vs_sma200"] = pxf.rolling(50).mean() / pxf.rolling(200).mean() - 1
    F["ema20_vs_ema50"] = pxf.ewm(span=20, min_periods=20).mean() / pxf.ewm(span=50, min_periods=50).mean() - 1
    F["rsi_14"] = rsi(pxf, 14); F["rsi_20"] = rsi(pxf, 20)
    macd = pxf.ewm(span=12, min_periods=12).mean() - pxf.ewm(span=26, min_periods=26).mean()
    F["macd_hist"] = (macd - macd.ewm(span=9, min_periods=9).mean()) / pxf
    m20, s20 = pxf.rolling(20).mean(), pxf.rolling(20).std()
    F["bollinger_pctb"] = (pxf - (m20 - 2 * s20)) / (4 * s20)
    F["max_ret_21"] = r.rolling(21).max()
    F["skew_60"] = r.rolling(60).skew()
    F["turnover_trend"] = to.rolling(20, min_periods=10).median() / to.rolling(252, min_periods=120).median() - 1
    F["amihud_60"] = (r.abs() / to).rolling(60, min_periods=30).mean()
    cov = r.rolling(252, min_periods=200).cov(mr); var = mr.rolling(252, min_periods=200).var()
    beta = cov.div(var, axis=0); F["beta_252"] = beta
    F["idio_vol_60"] = (r - beta.mul(mr, axis=0)).rolling(60).std()
    sec_mean = F["mom_6_1"].where(el).T.groupby(ind.reindex(tr.columns).values).transform("mean").T
    F["mom_6_1_vs_sector"] = F["mom_6_1"] - sec_mean
    fwd = trf.shift(-(LAG + H)) / trf.shift(-LAG) - 1
    to_med = to.rolling(126, min_periods=60).median()
    dates = tr.index[::STEP]
    rows = []
    for t in dates:
        e = el.loc[t]; syms = e.index[e.values]
        if len(syms) < 30: continue
        X = pd.DataFrame({k: v.loc[t, syms] for k, v in F.items()})
        Xr = (X.rank(pct=True) * 2 - 1).where(X.notna(), 0.0)
        Xr.insert(0, "symbol", syms); Xr.insert(0, "date", t)
        Xr["fwd_ret"] = fwd.loc[t, syms].values
        Xr["raw_mom_12_1"] = X["mom_12_1"].values
        Xr["turnover_rank"] = to_med.loc[t, syms].rank(ascending=False).values   # 1 = most traded, known at t
        rows.append(Xr)
    D = pd.concat(rows, ignore_index=True)
    D = D[D.fwd_ret.notna()].reset_index(drop=True)
    g = D.groupby("date").fwd_ret
    D["y_rank"] = g.rank(pct=True) - 0.5
    D["y_up"] = (D.fwd_ret > g.transform("median")).astype(int)
    D.to_parquet(P / "xs_panel.parquet")
    feats = list(F)
    pd.Series(feats).to_csv(ROOT / "reports" / "phase5" / "checkpoint_5_2_feature_list.csv", index=False, header=["feature"])
    chk = {"last feature date + label window inside dev window": bool(D.date.max() <= tr.index[-(LAG + H) - 1]),
           "no NaN in features": bool(D[feats].notna().all().all()),
           "features within [-1,1]": bool((D[feats].abs() <= 1).all().all()),
           "label base rate ~50%": bool(abs(D.y_up.mean() - 0.5) < 0.02)}
    # causality test: recompute one date's features after truncating the data at that date
    t = dates[len(dates) // 2]; a = trf.loc[:t]
    chk["truncation test (mom_12_1 unchanged when future is deleted)"] = bool(
        np.allclose((a.shift(21) / a.shift(252) - 1).loc[t].dropna(), F["mom_12_1"].loc[t].dropna()))
    print(dict(rows=len(D), dates=D.date.nunique(), first=str(D.date.min().date()), last=str(D.date.max().date()),
               stocks=D.symbol.nunique(), avg_stocks_per_date=round(len(D) / D.date.nunique(), 1), features=len(feats)))
    print(chk); assert all(chk.values())

if __name__ == "__main__":
    main()
