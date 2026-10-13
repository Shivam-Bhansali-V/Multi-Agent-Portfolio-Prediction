"""How accurate is each pattern at each holding period (1..60 trading days)?
And the honest version of 'pick the best day': choose each pattern's best day on 2015-2019 only,
then measure that same day on 2020 - Mar 2025 (a period the choice never saw).

Accuracy definitions (entry = next day's open, exit = close h trading days later):
  raw   : price closes on the pattern's side of entry (up for bullish, down for bearish)
  beat  : the stock beats (bullish) / lags (bearish) the equal-weight average of all stocks
Each is compared with the same definition on every stock-day of the same period (the base rate).
Also: follow-up tests suggested by the review (Descending Triangle as an exit rule; bearish tops
below the 200-day average), each split by time.
usage: python horizon_test.py   -> results/horizon_accuracy.csv, horizon_best_day.csv, followups.csv
"""
import sys, numpy as np, pandas as pd
from pathlib import Path
import common as cm, patterns as pt

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "raw" / "yahoo"
LST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "data" / "reference" / "ind_nifty100list.csv"
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)
HS = list(range(1, 21)) + [25, 30, 40, 60]
SPLIT = pd.Timestamp("2020-01-01")
MIN_EVENTS = 30

D = cm.load_panel(RAW, LST)
O, H, L, C, AC, ATR, idx = (D[k] for k in ["O", "H", "L", "C", "AC", "ATR", "idx"])
AO = O * (AC / C)
cols = list(C.columns); col_ix = {s: i for i, s in enumerate(cols)}
A, B = cm.halves(cols); Aset = set(A)

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
ev["si"] = ev.symbol.map(col_ix); ev["late"] = idx[ev.t.values] >= SPLIT; ev["inA"] = ev.symbol.isin(Aset)
order = [n for _, n, _ in pt.CHART_PATTERNS + pt.CANDLE_PATTERNS]

late_row = np.asarray(idx >= SPLIT)
rows = []
for h in HS:
    r = AC.shift(-h) / AO.shift(-1) - 1
    x = r.sub(r.mean(axis=1), axis=0)
    rv, xv = r.values, x.values
    ok = ~np.isnan(rv)
    base = {}
    for per, rmask in (("all", np.ones(len(idx), bool)), ("early", ~late_row), ("late", late_row)):
        m = ok & rmask[:, None]
        base[(per, "raw", 1)] = (rv[m] > 0).mean(); base[(per, "raw", -1)] = (rv[m] < 0).mean()
        base[(per, "beat", 1)] = (xv[m] > 0).mean(); base[(per, "beat", -1)] = (xv[m] < 0).mean()
    for (name, d), g in ev.groupby(["pattern", "dir"]):
        rr, xx = rv[g.t.values, g.si.values], xv[g.t.values, g.si.values]
        for per, pm in (("all", np.ones(len(g), bool)), ("early", ~g.late.values), ("late", g.late.values)):
            m = pm & ~np.isnan(rr)
            n = int(m.sum())
            if n == 0:
                continue
            raw = ((rr[m] > 0) if d > 0 else (rr[m] < 0)).mean()
            beat = ((xx[m] > 0) if d > 0 else (xx[m] < 0)).mean()
            bb = base[(per, "beat", d)]
            rec = dict(pattern=name, direction="bull" if d > 0 else "bear", period=per, horizon_days=h, n=n,
                       raw_acc=raw, raw_base=base[(per, "raw", d)], beat_acc=beat, beat_base=bb,
                       raw_lift_pp=100 * (raw - base[(per, "raw", d)]), beat_lift_pp=100 * (beat - bb),
                       beat_z=(beat - bb) / np.sqrt(bb * (1 - bb) / n),
                       mean_excess_pct=100 * d * np.nanmean(xx[m]), mean_return_pct=100 * np.nanmean(rr[m]))
            if per == "all":
                for nm, hm in (("A", g.inA.values), ("B", ~g.inA.values)):
                    mm = m & hm
                    rec[f"beat_lift{nm}_pp"] = 100 * (((xx[mm] > 0) if d > 0 else (xx[mm] < 0)).mean() - bb) if mm.sum() else np.nan
            rows.append(rec)
acc = pd.DataFrame(rows)
acc["pattern"] = pd.Categorical(acc.pattern, order, ordered=True)
acc = acc.sort_values(["pattern", "period", "horizon_days"])
acc.to_csv(OUT / "horizon_accuracy.csv", index=False)

# ---- pick best day on 2015-19, check it on 2020-25 (for both accuracy definitions)
best = []
for name in order:
    e = acc[(acc.pattern == name) & (acc.period == "early") & (acc.n >= MIN_EVENTS)]
    l_ = acc[(acc.pattern == name) & (acc.period == "late")]
    if e.empty:
        continue
    rec = dict(pattern=name, direction=e.direction.iloc[0],
               early_events=int(acc[(acc.pattern == name) & (acc.period == "early") & (acc.horizon_days == 1)].n.iloc[0]),
               late_events=int(l_[l_.horizon_days == 1].n.iloc[0]) if len(l_) else 0)
    for m in ("beat", "raw"):
        b = e.loc[e[f"{m}_lift_pp"].idxmax()]
        lr = l_[l_.horizon_days == b.horizon_days]
        rec[f"{m}_best_day"] = int(b.horizon_days)
        rec[f"{m}_early_acc"] = b[f"{m}_acc"]; rec[f"{m}_early_base"] = b[f"{m}_base"]
        rec[f"{m}_early_lift_pp"] = b[f"{m}_lift_pp"]
        if len(lr):
            lr = lr.iloc[0]
            rec[f"{m}_late_acc"] = lr[f"{m}_acc"]; rec[f"{m}_late_base"] = lr[f"{m}_base"]
            rec[f"{m}_late_lift_pp"] = lr[f"{m}_lift_pp"]; rec[f"{m}_late_n"] = int(lr.n)
    best.append(rec)
best = pd.DataFrame(best)
best.to_csv(OUT / "horizon_best_day.csv", index=False)

# ---- follow-ups
fu = []
# 1) Descending Triangle as an EXIT rule for a long holder: raw return after the breakdown vs any day
dt_ev = ev[ev.pattern == "Descending Triangle"]
for h in (1, 2, 3, 5, 10, 20):
    r = (AC.shift(-h) / AO.shift(-1) - 1).values
    for per, pm in (("all", np.ones(len(dt_ev), bool)), ("early", ~dt_ev.late.values), ("late", dt_ev.late.values)):
        v = r[dt_ev.t.values[pm], dt_ev.si.values[pm]]; v = v[~np.isnan(v)]
        rmask = (np.ones(len(idx), bool) if per == "all" else (~late_row if per == "early" else late_row))
        bv = r[rmask][~np.isnan(r[rmask])]
        fu.append(dict(test="Descending Triangle exit: return of a holder who stays", period=per, horizon_days=h,
                       n=len(v), mean_return_pct=100 * v.mean(), base_mean_return_pct=100 * bv.mean(),
                       saved_by_exiting_pct=100 * (bv.mean() - v.mean()),
                       saved_after_cost_pct=100 * (bv.mean() - v.mean()) - 100 * cm.COST,
                       t=(v.mean() - bv.mean()) / (v.std() / np.sqrt(len(v))) if len(v) > 2 else np.nan))
# 2) Bearish tops when the stock is already below its 200-day average, 10-day beat-market, by period
sma200 = C.rolling(200, min_periods=200).mean().values
r10 = AC.shift(-10) / AO.shift(-1) - 1; x10 = r10.sub(r10.mean(axis=1), axis=0).values
below = C.values < sma200
for name in ("Head and Shoulders", "Double Top", "Triple Top", "Descending Triangle"):
    g = ev[ev.pattern == name]
    for per, pm in (("all", np.ones(len(g), bool)), ("early", ~g.late.values), ("late", g.late.values)):
        f = below[g.t.values, g.si.values] & pm
        v = x10[g.t.values[f], g.si.values[f]]; v = v[~np.isnan(v)]
        rmask = (np.ones(len(idx), bool) if per == "all" else (~late_row if per == "early" else late_row))
        bx = x10[rmask]; bmask = below[rmask] & ~np.isnan(bx)
        fu.append(dict(test=f"{name} below 200-day avg: lags market over 10 days", period=per, horizon_days=10,
                       n=len(v), hit=(v < 0).mean() if len(v) else np.nan,
                       base_any_day=(bx[~np.isnan(bx)] < 0).mean(),
                       base_below_200=(bx[bmask] < 0).mean(), mean_excess_pct=100 * v.mean() if len(v) else np.nan))
pd.DataFrame(fu).to_csv(OUT / "followups.csv", index=False)
print("done")
