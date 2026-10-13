"""Pattern detectors. Every event is dated on the day the pattern COMPLETES (breakout close / last candle),
using only bars up to that day. Trades enter at the next day's open.

Chart patterns use a zig-zag of swing pivots. A pivot at bar i needs K bars on each side, so it only
becomes known at bar i+K ("confirmed"). The zig-zag is rebuilt in confirmation order, so a detector at
day t never sees a pivot confirmed after t.
"""
import numpy as np, pandas as pd

K = 5            # pivot half-width (bars each side)
TOL = 0.03       # "same level" tolerance for double/triple tops and bottoms (3%)
FLAT = 0.015     # flat line tolerance for ascending/descending triangles (1.5%)
WAIT = 30        # bars a completed setup may wait for its breakout
DEDUP = 10       # one event per symbol per pattern per 10 bars

CHART_PATTERNS = [
    ("Reversal", "Head and Shoulders", -1), ("Reversal", "Inverse Head and Shoulders", +1),
    ("Reversal", "Double Top", -1), ("Reversal", "Double Bottom", +1),
    ("Reversal", "Triple Top", -1), ("Reversal", "Triple Bottom", +1),
    ("Continuation", "Bullish Flag", +1), ("Continuation", "Bearish Flag", -1),
    ("Continuation", "Bullish Pennant", +1), ("Continuation", "Bearish Pennant", -1),
    ("Continuation", "Ascending Triangle", +1), ("Continuation", "Descending Triangle", -1),
    ("Continuation", "Symmetrical Triangle (up break)", +1), ("Continuation", "Symmetrical Triangle (down break)", -1),
    ("Continuation", "Cup and Handle", +1),
]
CANDLE_PATTERNS = [
    ("Candlestick", "Doji after uptrend", -1), ("Candlestick", "Doji after downtrend", +1),
    ("Candlestick", "Hammer", +1), ("Candlestick", "Hanging Man", -1),
    ("Candlestick", "Shooting Star", -1), ("Candlestick", "Inverted Hammer", +1),
    ("Candlestick", "Bullish Engulfing", +1), ("Candlestick", "Bearish Engulfing", -1),
    ("Candlestick", "Morning Star", +1), ("Candlestick", "Evening Star", -1),
]


# ---------------------------------------------------------------- pivots and zig-zag
def raw_pivots(h, l, k=K):
    n = len(h); out = []
    for i in range(k, n - k):
        wh, wl = h[i - k:i + k + 1], l[i - k:i + k + 1]
        if np.isnan(wh).any() or np.isnan(wl).any():
            continue
        if h[i] == wh.max():
            out.append((i + k, i, "H", h[i]))
        if l[i] == wl.min():
            out.append((i + k, i, "L", l[i]))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def line_at(i1, p1, i2, p2, t):
    return p1 + (p2 - p1) * (t - i1) / (i2 - i1) if i2 != i1 else p2


# ---------------------------------------------------------------- setup detectors on the zig-zag tail
def _prior_extreme(arr, i, lookback, kind):
    w = arr[max(0, i - lookback):i]
    w = w[~np.isnan(w)]
    if len(w) == 0:
        return False
    return arr[i] >= w.max() if kind == "H" else arr[i] <= w.min()


def detect_setups(Z, t0, h, l, c, atr):
    """Return setups completed by the newest pivot. Each setup waits for a breakout after t0."""
    S = []

    # ---- triple top / bottom (checked first; a triple suppresses the double on the same bars)
    triple = False
    if len(Z) >= 5:
        a, b, cc, d, e = Z[-5:]
        for top in (True, False):
            pk = "H" if top else "L"
            if [a[1], b[1], cc[1], d[1], e[1]] != [pk, "L" if top else "H", pk, "L" if top else "H", pk]:
                continue
            peaks = np.array([a[2], cc[2], e[2]]); m = peaks.mean()
            if (peaks.max() - peaks.min()) / m > TOL or e[0] - a[0] < 15:
                continue
            A = atr[e[0]]
            if not np.isfinite(A):
                continue
            if top:
                neck = min(b[2], d[2])
                if peaks.min() - max(b[2], d[2]) < 2 * A or not _prior_extreme(h, a[0], 40, "H"):
                    continue
                S.append(dict(name="Triple Top", dir=-1, kind="level", level=neck, inval=peaks.max(),
                              stop=peaks.max(), height=peaks.max() - neck, start=a[0], piv=Z[-5:]))
            else:
                neck = max(b[2], d[2])
                if min(b[2], d[2]) - peaks.max() < 2 * A or not _prior_extreme(l, a[0], 40, "L"):
                    continue
                S.append(dict(name="Triple Bottom", dir=+1, kind="level", level=neck, inval=peaks.min(),
                              stop=peaks.min(), height=neck - peaks.min(), start=a[0], piv=Z[-5:]))
            triple = True

    # ---- head and shoulders / inverse
    if len(Z) >= 5:
        a, b, cc, d, e = Z[-5:]
        if [a[1], b[1], cc[1], d[1], e[1]] == ["H", "L", "H", "L", "H"]:
            A = atr[cc[0]]
            if (np.isfinite(A) and cc[2] - max(a[2], e[2]) >= A and abs(a[2] - e[2]) / cc[2] <= 0.05
                    and _prior_extreme(h, cc[0], 60, "H")):
                neck_head = line_at(b[0], b[2], d[0], d[2], cc[0])
                S.append(dict(name="Head and Shoulders", dir=-1, kind="line", line=(b[0], b[2], d[0], d[2]),
                              inval=e[2], stop=e[2], height=cc[2] - neck_head, start=a[0], piv=Z[-5:]))
        if [a[1], b[1], cc[1], d[1], e[1]] == ["L", "H", "L", "H", "L"]:
            A = atr[cc[0]]
            if (np.isfinite(A) and min(a[2], e[2]) - cc[2] >= A and abs(a[2] - e[2]) / cc[2] <= 0.05
                    and _prior_extreme(l, cc[0], 60, "L")):
                neck_head = line_at(b[0], b[2], d[0], d[2], cc[0])
                S.append(dict(name="Inverse Head and Shoulders", dir=+1, kind="line", line=(b[0], b[2], d[0], d[2]),
                              inval=e[2], stop=e[2], height=neck_head - cc[2], start=a[0], piv=Z[-5:]))

    # ---- double top / bottom
    if len(Z) >= 3 and not triple:
        a, b, cc = Z[-3:]
        A = atr[cc[0]]
        if np.isfinite(A) and cc[0] - a[0] >= 10:
            if [a[1], b[1], cc[1]] == ["H", "L", "H"]:
                top = max(a[2], cc[2])
                if (abs(a[2] - cc[2]) / top <= TOL and min(a[2], cc[2]) - b[2] >= 2 * A
                        and _prior_extreme(h, a[0], 40, "H")):
                    S.append(dict(name="Double Top", dir=-1, kind="level", level=b[2], inval=top, stop=top,
                                  height=top - b[2], start=a[0], piv=Z[-3:]))
            if [a[1], b[1], cc[1]] == ["L", "H", "L"]:
                bot = min(a[2], cc[2])
                if (abs(a[2] - cc[2]) / b[2] <= TOL and b[2] - max(a[2], cc[2]) >= 2 * A
                        and _prior_extreme(l, a[0], 40, "L")):
                    S.append(dict(name="Double Bottom", dir=+1, kind="level", level=b[2], inval=bot, stop=bot,
                                  height=b[2] - bot, start=a[0], piv=Z[-3:]))

    # ---- triangles (last two swing highs and last two swing lows)
    if len(Z) >= 4:
        tail = Z[-4:]
        hs = [z for z in tail if z[1] == "H"]; ls = [z for z in tail if z[1] == "L"]
        if len(hs) == 2 and len(ls) == 2:
            span = tail[-1][0] - tail[0][0]
            A = atr[tail[-1][0]]
            (h1, h2), (l1, l2) = hs, ls
            height = max(h1[2], h2[2]) - min(l1[2], l2[2])
            if np.isfinite(A) and 10 <= span <= 60 and height >= 2 * A:
                flat_h = abs(h1[2] - h2[2]) / max(h1[2], h2[2]) <= FLAT
                flat_l = abs(l1[2] - l2[2]) / max(l1[2], l2[2]) <= FLAT
                rising_l = l2[2] > l1[2] + 0.5 * A
                falling_h = h2[2] < h1[2] - 0.5 * A
                if flat_h and rising_l:
                    S.append(dict(name="Ascending Triangle", dir=+1, kind="level", level=max(h1[2], h2[2]),
                                  inval=l2[2], stop=l2[2], height=max(h1[2], h2[2]) - l1[2], start=tail[0][0], piv=tail))
                elif flat_l and falling_h:
                    S.append(dict(name="Descending Triangle", dir=-1, kind="level", level=min(l1[2], l2[2]),
                                  inval=h2[2], stop=h2[2], height=h1[2] - min(l1[2], l2[2]), start=tail[0][0], piv=tail))
                elif falling_h and rising_l:
                    S.append(dict(name="Symmetrical Triangle", dir=0, kind="two_lines",
                                  up=(h1[0], h1[2], h2[0], h2[2]), lo=(l1[0], l1[2], l2[0], l2[2]),
                                  height=h1[2] - l1[2], start=tail[0][0], piv=tail))

    # ---- cup and handle: newest pivot is the right rim
    if len(Z) >= 3 and Z[-1][1] == "H":
        cR = Z[-1]
        for j in range(len(Z) - 3, -1, -1):
            a = Z[j]
            if a[1] != "H":
                continue
            dur = cR[0] - a[0]
            if dur > 150:
                break
            if dur < 30 or abs(a[2] - cR[2]) / max(a[2], cR[2]) > 0.05:
                continue
            rim_lo = min(a[2], cR[2]); rim = max(a[2], cR[2])
            seg_h, seg_l = h[a[0] + 1:cR[0]], l[a[0] + 1:cR[0]]
            if np.isnan(seg_l).any() or np.nanmax(seg_h) > rim_lo * 1.01:
                continue
            ib = a[0] + 1 + int(np.nanargmin(seg_l)); B = l[ib]
            depth = (rim_lo - B) / rim_lo
            pos = (ib - a[0]) / dur
            rounded = np.mean(seg_l <= B + 0.25 * (rim_lo - B)) >= 0.15   # U, not V
            prior = a[0] >= 120 and a[2] >= 1.15 * np.nanmin(l[a[0] - 120:a[0]])
            if 0.10 <= depth <= 0.40 and 0.3 <= pos <= 0.7 and rounded and prior:
                S.append(dict(name="Cup and Handle", dir=+1, kind="level", level=rim,
                              inval=cR[2] - 0.5 * (cR[2] - B), stop=None, height=rim - B, start=a[0],
                              min_t=cR[0] + 5, piv=[a, (ib, "L", B), cR]))
            break
    return S


def scan_setup(s, t0, c, l, n):
    """Find the breakout day for a setup. Returns list of (t, direction, trigger_level, stop)."""
    if s["kind"] == "two_lines":
        for t in range(t0 + 1, min(n, t0 + WAIT + 1)):
            if np.isnan(c[t]):
                continue
            up, lo = line_at(*s["up"], t), line_at(*s["lo"], t)
            if up <= lo:
                return []                                   # past the apex
            if t == t0 + 1:
                if not (lo <= c[t0] <= up):
                    return []
            if c[t] > up:
                return [(t, +1, up, lo)]
            if c[t] < lo:
                return [(t, -1, lo, up)]
        return []
    d = s["dir"]
    lvl = (lambda t: line_at(*s["line"], t)) if s["kind"] == "line" else (lambda t: s["level"])
    # pattern must not already be broken when it becomes known
    if (d < 0 and c[t0] < lvl(t0)) or (d > 0 and c[t0] > lvl(t0)):
        return []
    for t in range(t0 + 1, min(n, t0 + WAIT + 1)):
        if np.isnan(c[t]):
            continue
        if (d < 0 and c[t] > s["inval"]) or (d > 0 and c[t] < s["inval"]):
            return []
        if t < s.get("min_t", 0):
            continue
        L_ = lvl(t)
        if (d < 0 and c[t] < L_) or (d > 0 and c[t] > L_):
            stop = s["stop"]
            if stop is None:                                 # cup & handle: handle low
                stop = np.nanmin(l[s["piv"][-1][0]:t + 1])
            return [(t, d, L_, stop)]
    return []


def chart_events(sym, h, l, c, atr):
    n = len(c); Z = []; events = []; last = {}
    for conf, i, typ, price in raw_pivots(h, l):
        changed = False
        if Z and Z[-1][1] == typ:
            if (typ == "H" and price > Z[-1][2]) or (typ == "L" and price < Z[-1][2]):
                Z[-1] = (i, typ, price); changed = True
        else:
            Z.append((i, typ, price)); changed = True
        if not changed or conf >= n:
            continue
        for s in detect_setups(Z, conf, h, l, c, atr):
            for t, d, trig, stop in scan_setup(s, conf, c, l, n):
                name = s["name"]
                if name == "Symmetrical Triangle":
                    name += " (up break)" if d > 0 else " (down break)"
                target = trig + d * s["height"]
                events.append(dict(symbol=sym, pattern=name, dir=d, t=t, trigger=trig, stop=stop,
                                   target=target, height=s["height"], start=s["start"], conf=conf,
                                   pivots=[(p[0], p[2]) for p in s["piv"]]))
    # dedup in event-time order (discovery order let a later-confirmed setup suppress an earlier breakout)
    out = []
    for e in sorted(events, key=lambda e: (e["t"], e["conf"])):
        if e["t"] - last.get(e["pattern"], -10**9) < DEDUP:
            continue
        last[e["pattern"]] = e["t"]
        out.append(e)
    return out


# ---------------------------------------------------------------- flags and pennants (rolling regressions)
def _rolling_fit(y, L):
    """slope and fitted values at x=L (day t) and x=L-1 (day t-1) for the window ending at t-1."""
    x = np.arange(L); xm = x.mean(); w = (x - xm) / ((x - xm) ** 2).sum()
    n = len(y)
    slope = np.full(n, np.nan); mean = np.full(n, np.nan)
    sl = np.convolve(y, w[::-1], "valid"); mn = np.convolve(y, np.ones(L) / L, "valid")
    slope[L - 1:] = sl; mean[L - 1:] = mn                    # index = window end
    # shift so index t refers to window ending at t-1
    slope = np.r_[np.nan, slope[:-1]]; mean = np.r_[np.nan, mean[:-1]]
    return slope, mean + slope * (L - xm), mean + slope * (L - 1 - xm)


def flag_events(sym, h, l, c, atr, POLE=10):
    n = len(c); ev = []; last = {}
    found = {}
    for L in range(5, 16):
        sh, fh_t, fh_p = _rolling_fit(h, L)
        sl, fl_t, fl_p = _rolling_fit(l, L)
        for t in range(L + POLE + 2, n):
            pe = t - L - 1; ps = pe - POLE
            if not np.isfinite(sh[t]) or not np.isfinite(atr[pe]) or np.isnan(c[t]) or np.isnan(c[t - 1]):
                continue
            pole = c[pe] - c[ps]
            fh, fl = h[t - L:t], l[t - L:t]
            if np.isnan(fh).any() or np.isnan(fl).any():
                continue
            frange = fh.max() - fl.min()
            # bullish
            if pole >= 3 * atr[pe]:
                top = np.nanmax(h[ps:pe + 1])
                if fh.max() <= top * 1.005 and fl.min() >= c[pe] - 0.5 * pole and c[t] > fh_t[t] and c[t - 1] <= fh_p[t]:
                    if sh[t] < 0 and sl[t] < 0 and 0.33 <= sl[t] / sh[t] <= 3:
                        found.setdefault((t, "Bullish Flag"), (L, +1, fh_t[t], fl.min(), pole, ps))
                    elif sh[t] < 0 and sl[t] > 0 and frange <= 0.5 * pole:
                        found.setdefault((t, "Bullish Pennant"), (L, +1, fh_t[t], fl.min(), pole, ps))
            # bearish
            if -pole >= 3 * atr[pe]:
                bot = np.nanmin(l[ps:pe + 1])
                if fl.min() >= bot * 0.995 and fh.max() <= c[pe] - 0.5 * pole and c[t] < fl_t[t] and c[t - 1] >= fl_p[t]:
                    if sh[t] > 0 and sl[t] > 0 and 0.33 <= sh[t] / sl[t] <= 3:
                        found.setdefault((t, "Bearish Flag"), (L, -1, fl_t[t], fh.max(), -pole, ps))
                    elif sh[t] < 0 and sl[t] > 0 and frange <= 0.5 * (-pole):
                        found.setdefault((t, "Bearish Pennant"), (L, -1, fl_t[t], fh.max(), -pole, ps))
    for (t, name), (L, d, trig, stop, height, ps) in sorted(found.items()):
        if t - last.get(name, -10**9) < DEDUP:
            continue
        last[name] = t
        ev.append(dict(symbol=sym, pattern=name, dir=d, t=t, trigger=trig, stop=stop, target=trig + d * height,
                       height=height, start=ps, pivots=[(ps, c[ps]), (t - L - 1, c[t - L - 1])], flag_len=L))
    return ev


# ---------------------------------------------------------------- candlesticks (vectorised on frames)
def candle_signals(O, H, L, C, ATR):
    body = (C - O).abs(); rng = H - L; up = H - np.maximum(O, C); lo = np.minimum(O, C) - L
    sma20 = C.rolling(20, min_periods=20).mean()
    down_ctx = (C < C.shift(5)) & (C < sma20)          # evaluated on the bar BEFORE the pattern starts
    up_ctx = (C > C.shift(5)) & (C > sma20)
    pre1_dn, pre1_up = down_ctx.shift(1), up_ctx.shift(1)          # one-bar patterns
    pre2_dn, pre2_up = down_ctx.shift(2), up_ctx.shift(2)          # two-bar
    pre3_dn, pre3_up = down_ctx.shift(3), up_ctx.shift(3)          # three-bar
    real = (rng > 0) & (rng >= 0.5 * ATR.shift(1))                 # ignore near-empty bars
    doji = real & (body <= 0.1 * rng)
    hammer_shape = real & (lo >= 2 * body) & (lo >= 0.6 * rng) & (up <= 0.1 * rng)
    star_shape = real & (up >= 2 * body) & (up >= 0.6 * rng) & (lo <= 0.1 * rng)
    O1, C1, b1 = O.shift(1), C.shift(1), body.shift(1)
    bull_eng = (C1 < O1) & (C > O) & (O <= C1) & (C >= O1) & (body > b1)
    bear_eng = (C1 > O1) & (C < O) & (O >= C1) & (C <= O1) & (body > b1)
    O2, C2, b2 = O.shift(2), C.shift(2), body.shift(2)
    A3 = ATR.shift(3)
    mstar = ((C2 < O2) & (b2 >= 0.6 * A3) & (b1 <= 0.3 * b2) & (np.maximum(O1, C1) < C2)
             & (C > O) & (C > (O2 + C2) / 2))
    estar = ((C2 > O2) & (b2 >= 0.6 * A3) & (b1 <= 0.3 * b2) & (np.minimum(O1, C1) > C2)
             & (C < O) & (C < (O2 + C2) / 2))
    f = lambda x: x.fillna(False).astype(bool)
    return {
        "Doji after uptrend": f(doji & pre1_up), "Doji after downtrend": f(doji & pre1_dn),
        "Hammer": f(hammer_shape & pre1_dn), "Hanging Man": f(hammer_shape & pre1_up),
        "Shooting Star": f(star_shape & pre1_up), "Inverted Hammer": f(star_shape & pre1_dn),
        "Bullish Engulfing": f(bull_eng & pre2_dn), "Bearish Engulfing": f(bear_eng & pre2_up),
        "Morning Star": f(mstar & pre3_dn), "Evening Star": f(estar & pre3_up),
    }
