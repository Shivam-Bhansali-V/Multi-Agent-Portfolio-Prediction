"""Shared data loading and scoring for the pattern study (same rules as scripts/40_indicator_truth_test.py).

Data   : raw Yahoo daily bars, today's NIFTY-100 list (survivor-biased).
Window : 2015-01-01 .. 2025-03-31 by default. The April 2025+ holdout is cut before anything is computed,
         unless load_panel(..., end=None) is called (holdout opened 12 Oct 2026 for run_seven.py).
Entry  : signal known at close of day t, bought at open of t+1. Total-return prices.
"""
import numpy as np, pandas as pd
from pathlib import Path

DEV_START, DEV_END = "2015-01-01", "2025-03-31"
HORIZONS = [1, 5, 10, 20, 60]
COST = 0.0035
SEED = 20261012
# Phase-5 verified corporate-action errors inside the dev window: replace that day's return with
# NIFTY50's (an estimate) and rescale earlier prices.
REPAIRS = [("ADANIENT", "2015-06-03"), ("ADANIENT", "2018-04-05"), ("ADANIENT", "2018-09-06"),
           ("CGPOWER", "2016-03-15"), ("ABB", "2019-12-20"), ("MOTHERSON", "2022-01-14"),
           ("ITC", "2025-01-06")]


def _load(raw, sym, end=DEV_END):
    df = pd.read_csv(Path(raw) / f"{sym}.csv", parse_dates=["Date"]).set_index("Date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.loc[:end] if end else df


def wilder(x, n):
    return x.ewm(alpha=1 / n, adjust=False, ignore_na=True).mean()


def load_panel(raw, listfile, end=DEV_END):
    """end=None loads everything (opens the April 2025+ holdout)."""
    symbols = sorted(pd.read_csv(listfile)["Symbol"].astype(str))
    symbols = [s for s in symbols if (Path(raw) / f"{s}.csv").exists()]
    nifty = _load(raw, "NIFTY50", end)
    cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    keys = ["O", "H", "L", "C", "AC", "V"]
    f = {k: {} for k in keys}
    for s in symbols:
        d = _load(raw, s, end)
        bad = (d["Volume"].fillna(0) <= 0) | d["Close"].isna()
        d.loc[bad, :] = np.nan
        for k, c in zip(keys, cols):
            f[k][s] = d[c]
    P = {k: pd.DataFrame(v).sort_index() for k, v in f.items()}
    idx = P["C"].index[P["C"].index >= DEV_START]
    P = {k: v.reindex(idx) for k, v in P.items()}
    mkt = nifty["Close"].reindex(idx)
    for s, dt in REPAIRS:
        if s not in P["C"] or pd.Timestamp(dt) not in idx:
            continue
        i = idx.get_loc(pd.Timestamp(dt)); c = P["C"][s]
        prev = c.iloc[:i].last_valid_index()
        f_ = (c.iloc[i] / c.loc[prev]) / (mkt.iloc[i] / mkt.loc[prev])
        for k in ["O", "H", "L", "C", "AC"]:
            P[k].loc[:prev, s] *= f_
    O, H, L, C, AC = (P[k] for k in ["O", "H", "L", "C", "AC"])
    AO = O * (AC / C)
    prevC = C.shift(1)
    TR = pd.concat([H - L, (H - prevC).abs(), (L - prevC).abs()]).groupby(level=0).max().reindex(idx)
    ATR = wilder(TR.where(C.notna()), 14)
    fwd, fwdx = {}, {}
    for h in HORIZONS:
        r = AC.shift(-h) / AO.shift(-1) - 1
        fwd[h] = r
        fwdx[h] = r.sub(r.mean(axis=1), axis=0)
    # 10-day triple-barrier label: 2xATR target, 1xATR stop from next open; double touch -> Down
    entry = O.shift(-1)
    up_b, dn_b = entry + 2 * ATR, entry - ATR
    label = pd.DataFrame(np.nan, index=idx, columns=C.columns)
    dec = pd.DataFrame(False, index=idx, columns=C.columns)
    for k in range(1, 11):
        hd = (L.shift(-k) <= dn_b) & ~dec
        hu = (H.shift(-k) >= up_b) & ~dec & ~hd
        label = label.mask(hd, -1).mask(hu, 1)
        dec = dec | hd | hu
    label = label.where(dec, 0).where(entry.notna() & ATR.notna() & C.shift(-10).notna())
    return dict(O=O, H=H, L=L, C=C, AC=AC, V=P["V"], ATR=ATR, fwd=fwd, fwdx=fwdx,
                label=label, idx=idx, mkt=mkt)


def nonoverlap_t(series, h):
    s = series; ts, ms = [], []          # stride over trading days THEN drop no-signal days,
    for o in range(h):                   # so kept h-day windows never overlap (also for sparse events)
        x = s.iloc[o::h].dropna()
        if len(x) > 10 and x.std() > 0:
            ts.append(x.mean() / x.std() * np.sqrt(len(x))); ms.append(x.mean())
    return (np.mean(ms) if ms else np.nan), (np.mean(ts) if ts else np.nan)


def halves(columns):
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(np.array(columns))
    A = set(perm[: len(perm) // 2])
    return [c for c in columns if c in A], [c for c in columns if c not in A]


def score_signal(D, sig, dirn, meta):
    """sig: boolean DataFrame (date x symbol) of event days. Returns one row per horizon."""
    C, label = D["C"], D["label"]
    sig = sig.reindex_like(C).fillna(False).astype(bool) & C.notna()
    A, B = halves(list(C.columns))
    lab_n = label.notna().sum().sum()
    rows = []
    for h in HORIZONS:
        f, fx = D["fwd"][h], D["fwdx"][h]
        m = sig & f.notna(); n = int(m.sum().sum())
        if n == 0:
            continue
        av = f.notna(); xv = fx.notna()
        right = (f > 0) if dirn > 0 else (f < 0)
        right_x = (fx > 0) if dirn > 0 else (fx < 0)
        base = right[av].sum().sum() / av.sum().sum()
        base_x = right_x[xv].sum().sum() / xv.sum().sum()
        lifts = {}
        for nm, cols in (("A", A), ("B", B)):
            mm = m[cols]; nn = mm.sum().sum(); xc = xv[cols]
            bc = right_x[cols][xc].sum().sum() / xc.sum().sum()
            lifts[nm] = (right_x[cols][mm].sum().sum() / nn - bc) if nn else np.nan
        mean_x, t_x = nonoverlap_t(fx.where(m).mean(axis=1), h)
        rec = dict(meta, direction="bull" if dirn > 0 else "bear", horizon_days=h, n_signals=n,
                   stocks=int(m.any().sum()), hit_rate=right[m].sum().sum() / n, base_rate=base,
                   beat_mkt_rate=right_x[m].sum().sum() / n, beat_mkt_base=base_x,
                   lift_halfA_pp=100 * lifts["A"], lift_halfB_pp=100 * lifts["B"],
                   mean_ret_pct=100 * f[m].stack().dropna().mean(),
                   mean_excess_pct=100 * fx[m].stack().dropna().mean(),
                   date_mean_excess_pct=100 * mean_x, t_excess=t_x)
        ex = fx[m].stack().dropna()
        rec["t_pooled"] = ex.mean() / ex.std() * np.sqrt(len(ex)) if len(ex) > 2 else np.nan  # sparse events
        if dirn < 0:
            rec["t_pooled"] = -rec["t_pooled"]                               # positive = signal was right
        if h == 10:
            ml = sig & label.notna(); nl = ml.sum().sum()
            if nl:
                rec["tb_P_up"] = (label[ml] == 1).sum().sum() / nl
                rec["tb_P_down"] = (label[ml] == -1).sum().sum() / nl
            rec["tb_base_up"] = (label == 1).sum().sum() / lab_n
            rec["tb_base_down"] = (label == -1).sum().sum() / lab_n
        rows.append(rec)
    return rows
