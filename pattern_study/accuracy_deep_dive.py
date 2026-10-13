"""Accuracy of each pattern under several definitions, testing the idea that a pattern
'turns out right after a few candles'.

Definitions (all from the event day t, entry at open t+1 unless stated):
  close_10d     : close after 10 days is on the pattern's side of entry (raw direction accuracy)
  beat_mkt_10d  : 10-day return beats (bull) / lags (bear) the equal-weight average of all stocks
  touch_1atr_10 : price TOUCHES 1xATR in the pattern's direction at any time within 10 days ("eventually right")
  touch_2pct_20 : price touches +/-2% in the pattern's direction at any time within 20 days
  first_1atr_10 : the 1xATR move in the pattern's direction comes BEFORE a 1xATR move against it (10 days)
  delay_k       : beat_mkt over 10 days if you enter k days later (k = 1, 3, 5)
  confirm       : only when the next candle closes in the pattern's direction; enter the day after
Every rate is compared with the SAME definition on every stock-day (the base rate).
usage: python accuracy_deep_dive.py   (writes results/accuracy_deep_dive.csv, results/accuracy_base_rates.csv)
"""
import sys, numpy as np, pandas as pd
from pathlib import Path
import common as cm, patterns as pt

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "raw" / "yahoo"
LST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "data" / "reference" / "ind_nifty100list.csv"
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)

D = cm.load_panel(RAW, LST)
O, H, L, C, AC, V, ATR, idx = (D[k] for k in ["O", "H", "L", "C", "AC", "V", "ATR", "idx"])
AO = O * (AC / C)
cols = list(C.columns)

# ---------------- events (chart patterns + candles) as (pattern, dir, symbol, t)
ev = []
for s in cols:
    h, l, c, a = H[s].values, L[s].values, C[s].values, ATR[s].values
    for e in pt.chart_events(s, h, l, c, a) + pt.flag_events(s, h, l, c, a):
        ev.append((e["pattern"], e["dir"], s, e["t"]))
cand = pt.candle_signals(O, H, L, C, ATR)
for _, name, d in pt.CANDLE_PATTERNS:
    st = cand[name].stack(); st = st[st]
    for dt, s in st.index:
        ev.append((name, d, s, idx.get_loc(dt)))
ev = pd.DataFrame(ev, columns=["pattern", "dir", "symbol", "t"])


def fwd_ret(k_delay, hold):
    """return from open of t+1+k to close of t+k+hold, and its excess over the cross-section"""
    r = AC.shift(-(k_delay + hold)) / AO.shift(-(1 + k_delay)) - 1
    return r, r.sub(r.mean(axis=1), axis=0)


r10, x10 = fwd_ret(0, 10)
entry = O.shift(-1)
fmaxH10 = H[::-1].rolling(10, min_periods=10).max()[::-1].shift(-1)
fminL10 = L[::-1].rolling(10, min_periods=10).min()[::-1].shift(-1)
fmaxH20 = H[::-1].rolling(20, min_periods=20).max()[::-1].shift(-1)
fminL20 = L[::-1].rolling(20, min_periods=20).min()[::-1].shift(-1)
up_touch_atr = (fmaxH10 - entry >= ATR); dn_touch_atr = (entry - fminL10 >= ATR)
up_touch_2 = (fmaxH20 / entry - 1 >= 0.02); dn_touch_2 = (1 - fminL20 / entry >= 0.02)
valid10 = fmaxH10.notna() & entry.notna() & ATR.notna()
valid20 = fmaxH20.notna() & entry.notna()

# first touch of +/-1 ATR within 10 days (same-day both -> counted as against)
dec_u = pd.DataFrame(False, index=idx, columns=cols); dec_d = dec_u.copy()
res_up = pd.DataFrame(np.nan, index=idx, columns=cols); res_dn = res_up.copy()
ub, db = entry + ATR, entry - ATR
for k in range(1, 11):
    hk, lk = H.shift(-k), L.shift(-k)
    d_hit = (lk <= db) & ~dec_u; u_hit = (hk >= ub) & ~dec_u & ~d_hit
    res_up = res_up.mask(d_hit, 0).mask(u_hit, 1); dec_u = dec_u | d_hit | u_hit
    u2 = (hk >= ub) & ~dec_d; d2 = (lk <= db) & ~dec_d & ~u2
    res_dn = res_dn.mask(u2, 0).mask(d2, 1); dec_d = dec_d | u2 | d2
res_up = res_up.where(dec_u | ~valid10, 0).where(valid10)   # neither touched = not right
res_dn = res_dn.where(dec_d | ~valid10, 0).where(valid10)

delay = {k: fwd_ret(k, 10)[1] for k in (1, 3, 5)}
_, x10_conf = fwd_ret(1, 10)                                   # confirmation: enter t+2
next_up = (C.shift(-1) > O.shift(-1)); next_dn = (C.shift(-1) < O.shift(-1))

sma200 = C.rolling(200, min_periods=200).mean()
mkt = D["mkt"]; mkt_up = (mkt > mkt.rolling(200, min_periods=200).mean())
volr = V / V.rolling(20, min_periods=20).mean().shift(1)

A, B = cm.halves(cols)
Aset = set(A)
col_ix = {s: i for i, s in enumerate(cols)}

DEFS = {
    "close_10d": (r10 > 0, r10 < 0, r10.notna()),
    "beat_mkt_10d": (x10 > 0, x10 < 0, x10.notna()),
    "touch_1atr_10": (up_touch_atr, dn_touch_atr, valid10),
    "touch_2pct_20": (up_touch_2, dn_touch_2, valid20),
    "first_1atr_10": (res_up == 1, res_dn == 1, res_up.notna()),
    "delay1_beat_mkt": (delay[1] > 0, delay[1] < 0, delay[1].notna()),
    "delay3_beat_mkt": (delay[3] > 0, delay[3] < 0, delay[3].notna()),
    "delay5_beat_mkt": (delay[5] > 0, delay[5] < 0, delay[5].notna()),
}
base = {}
for k, (bu, be, va) in DEFS.items():
    base[(k, 1)] = bu[va].sum().sum() / va.sum().sum()
    base[(k, -1)] = be[va].sum().sum() / va.sum().sum()

out = []
for (name, d), g in ev.groupby(["pattern", "dir"], sort=False):
    ti = g.t.values; si = np.array([col_ix[s] for s in g.symbol]); inA = np.array([s in Aset for s in g.symbol])
    rec = dict(pattern=name, direction="bull" if d > 0 else "bear", events=len(g))
    for k, (bu, be, va) in DEFS.items():
        fr = (bu if d > 0 else be).values[ti, si]; vv = va.values[ti, si]
        n = vv.sum(); acc = fr[vv].mean() if n else np.nan
        bse = base[(k, d)]
        rec[f"{k}_acc"] = acc; rec[f"{k}_base"] = bse; rec[f"{k}_lift_pp"] = 100 * (acc - bse)
        for nm, msk in (("A", inA), ("B", ~inA)):
            m2 = vv & msk
            rec[f"{k}_lift{nm}_pp"] = 100 * (fr[m2].mean() - bse) if m2.sum() else np.nan
        rec[f"{k}_z"] = (acc - bse) / np.sqrt(bse * (1 - bse) / n) if n else np.nan
    for k, fx in (("0", x10), ("1", delay[1]), ("3", delay[3]), ("5", delay[5])):
        v = fx.values[ti, si]; v = v[~np.isnan(v)]
        rec[f"excess10_delay{k}_pct"] = 100 * d * v.mean() if len(v) else np.nan   # positive = pattern right
    conf = (next_up if d > 0 else next_dn).values[ti, si].astype(bool)
    xc = x10_conf.values[ti, si]; ok = conf & ~np.isnan(xc)
    rec["confirmed_share"] = conf.mean()
    rec["confirm_beat_mkt_acc"] = ((xc[ok] > 0) if d > 0 else (xc[ok] < 0)).mean() if ok.sum() else np.nan
    rec["confirm_excess_pct"] = 100 * d * xc[ok].mean() if ok.sum() else np.nan
    rec["confirm_n"] = int(ok.sum())
    fx = x10.values[ti, si]
    with_trend = ((C.values[ti, si] > sma200.values[ti, si]) if d > 0 else (C.values[ti, si] < sma200.values[ti, si]))
    regime = mkt_up.values[ti] if d > 0 else ~mkt_up.values[ti]
    vol_ok = volr.values[ti, si] >= 1.5
    for fn, msk in (("with_trend", with_trend), ("market_agrees", regime), ("volume_1p5x", vol_ok)):
        m2 = msk & ~np.isnan(fx)
        rec[f"{fn}_n"] = int(m2.sum())
        rec[f"{fn}_beat_mkt_acc"] = ((fx[m2] > 0) if d > 0 else (fx[m2] < 0)).mean() if m2.sum() else np.nan
        rec[f"{fn}_excess_pct"] = 100 * d * np.nanmean(fx[m2]) if m2.sum() else np.nan
    out.append(rec)
res = pd.DataFrame(out)
res.to_csv(OUT / "accuracy_deep_dive.csv", index=False)
pd.Series({f"{k}|{'bull' if d > 0 else 'bear'}": v for (k, d), v in base.items()}).to_csv(OUT / "accuracy_base_rates.csv")
print(pd.Series({f"{k}|{d}": round(v, 4) for (k, d), v in base.items()}).to_string())
