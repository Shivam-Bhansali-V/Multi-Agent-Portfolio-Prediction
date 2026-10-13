"""Score the 7 kept patterns on all 100 stocks, 2015 to the latest data (holdout opened 12 Oct 2026).
usage: python run_seven.py  ->  results/seven_pattern_stats.csv  (read by scan_stock.py)
                               results/seven_pattern_days.csv   (which candle the move came on)
"""
import sys, numpy as np, pandas as pd
from pathlib import Path
import common as cm, seven as sv

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "raw" / "yahoo"
LST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "data" / "reference" / "ind_nifty100list.csv"
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)

D = cm.load_panel(RAW, LST, end=None)            # holdout opened
O, H, L, C, ATR, idx = (D[k] for k in ["O", "H", "L", "C", "ATR", "idx"])
# drop market-wide empty dates (Yahoo zero-volume holiday/glitch rows: 6 in 2026, 2025-03-18 with
# 1 of 100 stocks). Left in, they count as a 'candle' in every shift-based window (20-candle window
# becomes 19), kill the stock-day whose candle 20 lands on them, hide >20% jumps from the guard
# (pct_change is NaN across them) and drop the gap from the next day's true range. Then rebuild ATR
# exactly as common.load_panel does, on the cleaned dates.
nday = C.notna().sum(axis=1)
keep = nday >= 0.5 * nday.max()
O, H, L, C = (x[keep] for x in (O, H, L, C))
idx = C.index
prevC = C.shift(1)
TR = pd.concat([H - L, (H - prevC).abs(), (L - prevC).abs()]).groupby(level=0).max().reindex(idx)
ATR = cm.wilder(TR.where(C.notna()), 14)
# guard: drop any stock-day whose next 20 candles contain a >20% one-day close move (unrepaired
# corporate actions in the holdout, e.g. demergers); applied to patterns and base alike
r1 = C.pct_change(fill_method=None).abs()
jump = r1[::-1].rolling(sv.N_CANDLES, min_periods=1).max()[::-1].shift(-1) > 0.20
OUT_F = sv.outcome_frames(O, H, L, C, ATR)
for d in OUT_F:
    OUT_F[d] = tuple(f.where(~jump) for f in OUT_F[d])
sig = sv.detect_seven(O, H, L, C, ATR)
A, B = cm.halves(list(C.columns))

rows, days = [], []
for name, d, says in sv.SEVEN:
    res, day, ret = OUT_F[d]
    for per, a, b in sv.PERIODS:
        rows_m = (idx >= a) & (idx <= b)
        R = res[rows_m]; S = sig[name][rows_m] & R.notna()
        allv = R.stack().dropna()
        base_w = (allv == 1).mean(); base_f = (allv == -1).mean()
        ev = R[S].stack().dropna()
        n = len(ev)
        if n == 0:
            continue
        w = (ev == 1).mean(); f = (ev == -1).mean()
        rt = ret[rows_m][S].stack().dropna()
        dy = day[rows_m][S & (R == 1)].stack().dropna()
        halves = {}
        for nm, cols in (("A", A), ("B", B)):
            e2 = R[cols][S[cols]].stack().dropna()
            b2 = R[cols].stack().dropna()
            halves[nm] = 100 * ((e2 == 1).mean() - (b2 == 1).mean()) if len(e2) else np.nan
        rows.append(dict(pattern=name, says=says, direction="bull" if d > 0 else "bear", period=per,
                         cases=n, stocks=int(S.any().sum()),
                         worked_pct=100 * w, failed_pct=100 * f, no_move_pct=100 * (1 - w - f),
                         base_worked_pct=100 * base_w, base_failed_pct=100 * base_f,
                         lift_pp=100 * (w - base_w), z=(w - base_w) / np.sqrt(base_w * (1 - base_w) / n),
                         lift_halfA_pp=halves["A"], lift_halfB_pp=halves["B"],
                         avg_trade_pct=100 * rt.mean(), base_avg_trade_pct=100 * ret[rows_m].stack().dropna().mean(),
                         median_candle_when_worked=dy.median() if len(dy) else np.nan,
                         worked_by_candle5_pct=100 * (dy <= 5).sum() / n, worked_by_candle10_pct=100 * (dy <= 10).sum() / n))
        for j in range(1, sv.N_CANDLES + 1):
            days.append(dict(pattern=name, period=per, candle=j, share_of_cases_pct=100 * (dy == j).sum() / n))
st = pd.DataFrame(rows)


def verdict(g):
    """latest period decides (user rule); holdout is the final word when it has >= 30 cases"""
    g = g.set_index("period")
    sel = g.loc["2020-Mar25"] if "2020-Mar25" in g.index else None
    ho = g.loc["Apr25-now (holdout)"] if "Apr25-now (holdout)" in g.index else None
    if ho is not None and ho.cases >= 30:
        key = ho
    else:
        key = sel
    if key is None:
        return "no data"
    if key.lift_pp >= 2 and key.z >= 1.5:
        return "works (better than a random day)"
    if key.lift_pp >= 1:
        return "slightly better than random, not reliable"
    if key.lift_pp <= -2 and key.z <= -2:
        return "worse than a random day"
    return "no better than a random day"


v = st.groupby("pattern").apply(verdict).rename("verdict")
st = st.merge(v, left_on="pattern", right_index=True)
st.to_csv(OUT / "seven_pattern_stats.csv", index=False)
pd.DataFrame(days).to_csv(OUT / "seven_pattern_days.csv", index=False)
pd.set_option("display.width", 250)
print(st[["pattern", "period", "cases", "worked_pct", "base_worked_pct", "lift_pp", "z", "lift_halfA_pp", "lift_halfB_pp",
          "failed_pct", "avg_trade_pct", "base_avg_trade_pct", "median_candle_when_worked", "verdict"]].round(2).to_string(index=False))
print("last date in data:", idx[-1].date())
