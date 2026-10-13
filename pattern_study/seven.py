"""The 7 patterns kept after the best-day check, scored with the rule chosen on 12 Oct 2026:

  WORKED  = within the next 20 candles, price moves 1 x ATR in the pattern's direction
            BEFORE it moves 1 x ATR against it (entry = next day's open; no trading cost).
  FAILED  = the 1 x ATR move against comes first (a same-candle touch of both counts as failed).
  NO MOVE = neither level is touched in 20 candles.

Every number is compared with the same rule applied to EVERY stock-day (the base rate), because a
random day also 'works' fairly often. Periods: 2015-19, 2020 - Mar 2025, and the holdout Apr 2025 onward.
Rule agreed with the user: where the periods disagree, the latest period decides.
"""
import numpy as np, pandas as pd
import patterns as pt

N_CANDLES = 20
K_ATR = 1.0
SEVEN = [  # (pattern, direction, what it says)
    ("Hammer", +1, "gain"),
    ("Bullish Engulfing", +1, "gain"),
    ("Doji after downtrend", +1, "gain"),
    ("Inverted Hammer", +1, "gain"),
    ("Head and Shoulders", -1, "loss"),
    ("Bearish Flag", -1, "loss"),
    ("Descending Triangle", -1, "loss"),
]
CHART = {"Head and Shoulders", "Bearish Flag", "Descending Triangle"}
PERIODS = [("2015-19", "2015-01-01", "2019-12-31"),
           ("2020-Mar25", "2020-01-01", "2025-03-31"),
           ("Apr25-now (holdout)", "2025-04-01", "2100-01-01")]


def outcome_frames(O, H, L, C, ATR, n=N_CANDLES, k=K_ATR):
    """For every stock-day, the bull and bear outcome of the rule.
    Returns dict d -> (res, day, ret): res +1 worked / -1 failed / 0 no move / NaN not enough data;
    day = candle (1..n) on which it was decided; ret = % return of the trade (no cost)."""
    entry = O.shift(-1)
    # a stock-day needs its own candle t (ATR is carried forward over missing days, so it alone
    # would let suspended days into the base rate) and all n forward candles
    have = entry.notna() & ATR.notna() & C.notna()
    for j in range(1, n + 1):
        have &= H.shift(-j).notna() & L.shift(-j).notna() & O.shift(-j).notna()
    out = {}
    for d in (+1, -1):
        tgt, stp = entry + d * k * ATR, entry - d * k * ATR
        res = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
        day = res.copy(); ret = res.copy()
        dec = pd.DataFrame(False, index=C.index, columns=C.columns)
        for j in range(1, n + 1):
            Oj, Hj, Lj = O.shift(-j), H.shift(-j), L.shift(-j)
            gap_win = ((Oj >= tgt) if d > 0 else (Oj <= tgt)) & (j > 1) & ~dec
            stop = ((Lj <= stp) if d > 0 else (Hj >= stp)) & ~dec & ~gap_win
            win = ((Hj >= tgt) if d > 0 else (Lj <= tgt)) & ~dec & ~gap_win & ~stop
            res = res.mask(gap_win | win, 1).mask(stop, -1)
            day = day.mask(gap_win | win | stop, j)
            fill_gap = Oj
            fill_stop = np.minimum(Oj, stp) if d > 0 else np.maximum(Oj, stp)
            ret = ret.mask(gap_win, d * (fill_gap / entry - 1)).mask(win, d * (tgt / entry - 1)) \
                     .mask(stop, d * (fill_stop / entry - 1))
            dec = dec | gap_win | win | stop
        res = res.where(dec, 0); day = day.where(dec, np.nan)
        ret = ret.where(dec, d * (C.shift(-n) / entry - 1))
        out[d] = (res.where(have), day.where(have), ret.where(have))
    return out


def detect_seven(O, H, L, C, ATR):
    """Boolean frame per pattern: True on the candle the pattern completes."""
    cand = pt.candle_signals(O, H, L, C, ATR)
    sig = {name: cand[name] for name, _, _ in SEVEN if name not in CHART}
    chart = {name: pd.DataFrame(False, index=C.index, columns=C.columns) for name in CHART}
    for s in C.columns:
        h, l, c, a = H[s].values, L[s].values, C[s].values, ATR[s].values
        for e in pt.chart_events(s, h, l, c, a) + pt.flag_events(s, h, l, c, a):
            if e["pattern"] in CHART:
                chart[e["pattern"]].iat[e["t"], C.columns.get_loc(s)] = True
    sig.update(chart)
    return sig
