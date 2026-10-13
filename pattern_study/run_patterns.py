"""Run the pattern study.

usage: python run_patterns.py [raw_dir] [nifty100_list] [out_dir]
defaults assume this folder sits inside "Market Prediction Model".
"""
import sys, json, time, numpy as np, pandas as pd
from pathlib import Path
import common as cm, patterns as pt

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "raw" / "yahoo"
LST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "data" / "reference" / "ind_nifty100list.csv"
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)
MM_DAYS = 60

t0 = time.time()
D = cm.load_panel(RAW, LST)
O, H, L, C, ATR, idx = D["O"], D["H"], D["L"], D["C"], D["ATR"], D["idx"]
print(f"loaded {C.shape[1]} stocks x {len(idx)} days in {time.time()-t0:.0f}s")

# ---------------- detect
events = []
for s in C.columns:
    h, l, c, a = H[s].values, L[s].values, C[s].values, ATR[s].values
    events += pt.chart_events(s, h, l, c, a)
    events += pt.flag_events(s, h, l, c, a)
ev = pd.DataFrame(events)
ev["date"] = idx[ev["t"].values]
print(f"chart events: {len(ev)} in {time.time()-t0:.0f}s")
candles = pt.candle_signals(O, H, L, C, ATR)

# ---------------- score (same metrics as the indicator test)
rows = []
for fam, name, d in pt.CHART_PATTERNS:
    e = ev[ev.pattern == name]
    sig = pd.DataFrame(False, index=idx, columns=C.columns)
    for sym, g in e.groupby("symbol"):
        sig.loc[idx[g.t.values], sym] = True
    rows += cm.score_signal(D, sig, d, dict(family=fam, pattern=name))
for fam, name, d in pt.CANDLE_PATTERNS:
    rows += cm.score_signal(D, candles[name], d, dict(family=fam, pattern=name))
scores = pd.DataFrame(rows)
scores.to_csv(OUT / "pattern_scores.csv", index=False)

# ---------------- measured-move test for chart patterns: target before stop within 60 days
def simulate(o, hh, ll, cc, t, d, stop, target, n_days):
    """Enter open t+1; first of stop / target within n_days (stop wins a same-day double touch)."""
    entry = o[t + 1]
    last = t + n_days
    for j in range(t + 1, last + 1):
        if not np.isfinite(hh[j]):
            continue
        oj = o[j]
        if j > t + 1 and ((oj >= target) if d > 0 else (oj <= target)):
            return "target", (oj - entry) * d / entry, j - t
        if (ll[j] <= stop) if d > 0 else (hh[j] >= stop):
            fill = min(oj, stop) if d > 0 else max(oj, stop)
            return "stop", (fill - entry) * d / entry, j - t
        if (hh[j] >= target) if d > 0 else (ll[j] <= target):
            return "target", (target - entry) * d / entry, j - t
    lc = cc[last] if np.isfinite(cc[last]) else np.nan
    return "timeout", (lc - entry) * d / entry, n_days


# placebo: same stock, same direction, same % stop and % target distances, random entry dates
prng = np.random.default_rng(11)
N_PLACEBO = 5
mm = []
for r in ev.itertuples():
    s, t, d = r.symbol, r.t, r.dir
    if t + 1 >= len(idx):
        continue
    o = O[s].values; hh = H[s].values; ll = L[s].values; cc = C[s].values
    entry = o[t + 1]
    if not np.isfinite(entry) or not np.isfinite(r.stop) or not np.isfinite(r.target):
        continue
    risk = (entry - r.stop) * d; reward = (r.target - entry) * d
    if risk <= 0 or reward <= 0:
        mm.append(dict(symbol=s, pattern=r.pattern, date=r.date, outcome="gapped past stop or target", ret=np.nan,
                       risk_pct=np.nan, reward_pct=np.nan, days=np.nan))
        continue
    if t + MM_DAYS >= len(idx):
        continue                                            # window would run past the dev window
    out, ret, days = simulate(o, hh, ll, cc, t, d, r.stop, r.target, MM_DAYS)
    rk, rw = risk / entry, reward / entry
    pl = []
    valid = np.where(np.isfinite(o[1:len(idx) - MM_DAYS]) & np.isfinite(cc[:len(idx) - MM_DAYS - 1]))[0]
    valid = valid[np.abs(valid - t) > MM_DAYS]
    for tp in prng.choice(valid, size=min(N_PLACEBO, len(valid)), replace=False):
        e_ = o[tp + 1]
        _, pr, _ = simulate(o, hh, ll, cc, tp, d, e_ * (1 - d * rk), e_ * (1 + d * rw), MM_DAYS)
        pl.append(pr)
    mm.append(dict(symbol=s, pattern=r.pattern, date=r.date, outcome=out, ret=ret,
                   risk_pct=100 * rk, reward_pct=100 * rw, days=days, placebo_ret=np.nanmean(pl)))
mm = pd.DataFrame(mm)
A, B = cm.halves(list(C.columns))
summ = []
for fam, name, d in pt.CHART_PATTERNS:
    g = mm[(mm.pattern == name)]
    gv = g[g.outcome != "gapped past stop or target"]
    if len(gv) == 0:
        continue
    be = (gv.risk_pct / (gv.risk_pct + gv.reward_pct)).mean()
    def half(cols):
        x = gv[gv.symbol.isin(cols)]
        return 100 * (x.ret.mean() - cm.COST) if len(x) else np.nan
    summ.append(dict(family=fam, pattern=name, direction="bull" if d > 0 else "bear", trades=len(gv),
                     skipped_gap=int((g.outcome == "gapped past stop or target").sum()),
                     target_first=(gv.outcome == "target").mean(), stop_first=(gv.outcome == "stop").mean(),
                     timeout=(gv.outcome == "timeout").mean(), breakeven_win_rate=be,
                     median_risk_pct=gv.risk_pct.median(), median_reward_pct=gv.reward_pct.median(),
                     median_days_to_target=gv[gv.outcome == "target"].days.median(),
                     avg_trade_pct=100 * gv.ret.mean(), avg_after_cost_pct=100 * (gv.ret.mean() - cm.COST),
                     after_cost_halfA_pct=half(A), after_cost_halfB_pct=half(B),
                     t_avg_trade=gv.ret.mean() / gv.ret.std() * np.sqrt(len(gv)) if len(gv) > 2 else np.nan,
                     placebo_avg_pct=100 * gv.placebo_ret.mean(),
                     edge_vs_placebo_pct=100 * (gv.ret - gv.placebo_ret).mean(),
                     edge_halfA_pct=100 * (lambda x: (x.ret - x.placebo_ret).mean())(gv[gv.symbol.isin(A)]),
                     edge_halfB_pct=100 * (lambda x: (x.ret - x.placebo_ret).mean())(gv[gv.symbol.isin(B)]),
                     t_edge=(lambda z: z.mean() / z.std() * np.sqrt(len(z)))((gv.ret - gv.placebo_ret).dropna())))
mms = pd.DataFrame(summ)
mms.to_csv(OUT / "measured_move_test.csv", index=False)
ev.drop(columns=["pivots"]).to_csv(OUT / "chart_pattern_events.csv", index=False)
cnt = {k: int(v.sum().sum()) for k, v in candles.items()}
json.dump(dict(stocks=C.shape[1], first=str(idx[0].date()), last=str(idx[-1].date()),
               chart_events=ev.pattern.value_counts().to_dict(), candle_events=cnt,
               label_base_up=float((D["label"] == 1).sum().sum() / D["label"].notna().sum().sum())),
          open(OUT / "meta.json", "w"), indent=1)

# ---------------- visual check: 3 random examples per pattern
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
rng = np.random.default_rng(7)
names = [n for _, n, _ in pt.CHART_PATTERNS]
fig, axes = plt.subplots(len(names), 3, figsize=(15, 2.6 * len(names)))
for r_, name in enumerate(names):
    e = ev[ev.pattern == name]
    pick = e.sample(min(3, len(e)), random_state=int(rng.integers(1e9))) if len(e) else e
    for c_ in range(3):
        ax = axes[r_, c_]; ax.tick_params(labelsize=6)
        if c_ >= len(pick):
            ax.axis("off"); continue
        x = pick.iloc[c_]; s = x.symbol
        a0, a1 = max(0, x.start - 15), min(len(idx) - 1, x.t + 30)
        rngx = np.arange(a0, a1 + 1)
        ax.vlines(rngx, L[s].values[a0:a1 + 1], H[s].values[a0:a1 + 1], color="0.75", lw=0.8)
        ax.plot(rngx, C[s].values[a0:a1 + 1], color="0.25", lw=0.9)
        pv = x.pivots
        ax.plot([p[0] for p in pv], [p[1] for p in pv], "o-", color="tab:blue", ms=3, lw=0.8)
        ax.axhline(x.trigger, color="tab:orange", lw=0.7, ls="--")
        ax.axhline(x.target, color="tab:green", lw=0.7, ls=":")
        ax.axhline(x.stop, color="tab:red", lw=0.7, ls=":")
        ax.axvline(x.t, color="tab:purple", lw=0.7)
        ax.set_title(f"{name} | {s} {idx[x.t].date()}", fontsize=7)
plt.tight_layout(); plt.savefig(OUT / "examples_chart_patterns.png", dpi=80); plt.close()

cnames = [n for _, n, _ in pt.CANDLE_PATTERNS]
fig, axes = plt.subplots(len(cnames), 3, figsize=(12, 2.2 * len(cnames)))
for r_, name in enumerate(cnames):
    st = candles[name].stack(); st = st[st]
    pick = st.sample(min(3, len(st)), random_state=int(rng.integers(1e9))).index if len(st) else []
    for c_ in range(3):
        ax = axes[r_, c_]; ax.tick_params(labelsize=6)
        if c_ >= len(pick):
            ax.axis("off"); continue
        dt, s = pick[c_]; t = idx.get_loc(dt); a0, a1 = max(0, t - 12), min(len(idx) - 1, t + 3)
        for j in range(a0, a1 + 1):
            o_, h_, l_, c__ = O[s].iat[j], H[s].iat[j], L[s].iat[j], C[s].iat[j]
            col = "tab:green" if c__ >= o_ else "tab:red"
            ax.vlines(j, l_, h_, color="k", lw=1.0, zorder=3)
            ax.add_patch(plt.Rectangle((j - 0.3, min(o_, c__)), 0.6, max(abs(c__ - o_), 1e-9), color=col,
                                       alpha=0.9 if j != t else 1, ec="k" if j == t else col, lw=0.8))
        ax.axvline(t, color="tab:purple", lw=0.5, ls="--")
        ax.set_title(f"{name} | {s} {dt.date()}", fontsize=7); ax.autoscale_view()
plt.tight_layout(); plt.savefig(OUT / "examples_candles.png", dpi=80); plt.close()
print(f"done in {time.time()-t0:.0f}s")
