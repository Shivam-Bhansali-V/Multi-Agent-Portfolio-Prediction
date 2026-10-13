"""Pattern scanner for one stock: what patterns appear on its latest candles, what each one says
(gain or loss), and how often that has actually worked.

usage: python scan_stock.py <csv> [SYMBOL] [lookback_candles]
  csv: Yahoo-format daily file (Date,Open,High,Low,Close,Adj Close,Volume), e.g. scan_data/ABCAPITAL.csv
  lookback_candles: how many of the latest candles to scan (default 5; chart patterns complete on a breakout day)
Writes results/scan_<SYMBOL>.md and prints the same report.

'Worked' = within 20 candles price moves 1 x ATR the pattern's way before 1 x ATR against (no cost).
Win rates come from results/seven_pattern_stats.csv (100 NIFTY 100 stocks; latest period decides) and,
separately, from this stock's own history. Patterns outside the kept 7 are listed as information only.
A pattern is a probability, not a promise: news can override it (that is the sentiment agent's job).
"""
import sys, numpy as np, pandas as pd
from pathlib import Path
import common as cm, patterns as pt, seven as sv

HERE = Path(__file__).resolve().parent
CSV = Path(sys.argv[1])
SYM = sys.argv[2] if len(sys.argv) > 2 else CSV.stem
LOOK = int(sys.argv[3]) if len(sys.argv) > 3 else 5
STATS = HERE / "results" / "seven_pattern_stats.csv"
LATEST = "Apr25-now (holdout)"

df = pd.read_csv(CSV, parse_dates=["Date"]).set_index("Date").sort_index()
df = df[~df.index.duplicated(keep="last")]
df = df[(df["Volume"].fillna(0) > 0) & df["Close"].notna()]
F = {k: df[[c]].rename(columns={c: SYM}) for k, c in
     zip("OHLC", ["Open", "High", "Low", "Close"])}
O, H, L, C = F["O"], F["H"], F["L"], F["C"]
prevC = C.shift(1)
TR = pd.concat([H - L, (H - prevC).abs(), (L - prevC).abs()]).groupby(level=0).max().reindex(C.index)
ATR = cm.wilder(TR, 14)
idx = C.index; n = len(idx)

# ---- every pattern on every candle (all 25; the kept 7 are marked)
kept = {name: (d, says) for name, d, says in sv.SEVEN}
found = []
cand = pt.candle_signals(O, H, L, C, ATR)
for _, name, d in pt.CANDLE_PATTERNS:
    for t in np.where(cand[name][SYM].values)[0]:
        found.append((t, name, d))
h, l, c, a = H[SYM].values, L[SYM].values, C[SYM].values, ATR[SYM].values
for e in pt.chart_events(SYM, h, l, c, a) + pt.flag_events(SYM, h, l, c, a):
    found.append((e["t"], e["pattern"], e["dir"]))
found = pd.DataFrame(found, columns=["t", "pattern", "dir"]).sort_values("t")

# ---- this stock's own track record for the kept 7
OF = sv.outcome_frames(O, H, L, C, ATR)
own = []
for name, d, says in sv.SEVEN:
    res = OF[d][0][SYM].values
    ts = found[(found.pattern == name)].t.values
    r = res[ts]; r = r[~np.isnan(r)]
    allr = res[~np.isnan(res)]
    own.append(dict(pattern=name, says=says, cases=len(r),
                    worked_pct=100 * (r == 1).mean() if len(r) else np.nan,
                    random_day_pct=100 * (allr == 1).mean()))
own = pd.DataFrame(own).set_index("pattern")

stats = pd.read_csv(STATS) if STATS.exists() else None


def market_line(name):
    if stats is None:
        return "no market-wide stats file (run run_seven.py)"
    g = stats[stats.pattern == name].set_index("period")
    if LATEST not in g.index:
        return "no recent market-wide data"
    x = g.loc[LATEST]
    return (f"worked {x.worked_pct:.0f}% vs {x.base_worked_pct:.0f}% on a random day "
            f"({int(x.cases)} cases, Apr 2025 onward); verdict: {x.verdict}; "
            f"when it worked, median candle {x.median_candle_when_worked:.0f}")


recent = found[found.t >= n - LOOK]
last = idx[-1].date(); atr_now = a[-1]; close_now = c[-1]
lines = [f"# Pattern scan: {SYM}", "",
         f"Data to {last}. Last close {close_now:.2f}. ATR(14) {atr_now:.2f} ({100 * atr_now / close_now:.1f}% of price).",
         f"Scanned the last {LOOK} candles ({idx[max(0, n - LOOK)].date()} to {last}).", ""]
if recent.empty:
    lines += ["**No pattern observed.**", ""]
else:
    lines += ["| Candle date | Pattern | Says | Kept pattern? | Entry | Target (1xATR) | Stop (1xATR) | Status so far | Market-wide record | This stock's record |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    o_ = O[SYM].values
    for r in recent.itertuples():
        d = r.dir; says = "gain" if d > 0 else "loss"
        at = a[r.t]
        if r.t + 1 < n:                      # next open known: same entry as the scoring rule
            ref = o_[r.t + 1]; ent = f"{ref:.2f} (open {idx[r.t + 1].date()})"
        else:                                # signal on the last candle: entry is tomorrow's open
            ref = c[r.t]; ent = f"next open (est. {ref:.2f} = last close)"
        tgt, stp = ref + d * at, ref - d * at
        status = "open: waiting for entry" if r.t + 1 >= n else f"open: neither level hit in {n - 1 - r.t} candle(s)"
        for j in range(1, min(sv.N_CANDLES, n - 1 - r.t) + 1):
            oj, hj, lj = o_[r.t + j], h[r.t + j], l[r.t + j]
            if j > 1 and d * (oj - tgt) >= 0:
                status = f"WORKED at open {idx[r.t + j].date()} (candle {j})"; break
            if (lj <= stp) if d > 0 else (hj >= stp):
                status = f"FAILED {idx[r.t + j].date()} (candle {j})"; break
            if (hj >= tgt) if d > 0 else (lj <= tgt):
                status = f"WORKED {idx[r.t + j].date()} (candle {j})"; break
        else:
            if n - 1 - r.t >= sv.N_CANDLES:
                status = "NO MOVE in 20 candles"
        if r.pattern in kept:
            mk = market_line(r.pattern)
            o = own.loc[r.pattern]
            ow = (f"worked {o.worked_pct:.0f}% vs {o.random_day_pct:.0f}% random ({int(o.cases)} cases)"
                  if o.cases else "no past cases")
            kp = "yes"
        else:
            mk, ow, kp = "not in the kept 7 (no edge found)", "-", "no"
        lines.append(f"| {idx[r.t].date()} | {r.pattern} | {says} | {kp} | {ent} | {tgt:.2f} | {stp:.2f} | {status} | {mk} | {ow} |")
    lines += ["", "Entry = the open after the pattern candle; target and stop are 1 x ATR(14) of the pattern candle from",
              "that entry. For a pattern on the last candle the entry is not known yet, so the last close stands in."]
lines += ["", "## Kept 7 patterns on this stock's full history", "",
          "| Pattern | Says | Cases | Worked | Random day |", "| --- | --- | --- | --- | --- |"]
for name, o in own.iterrows():
    w = f"{o.worked_pct:.0f}%" if o.cases else "-"
    lines.append(f"| {name} | {o.says} | {int(o.cases)} | {w} | {o.random_day_pct:.0f}% |")
lines += ["", "Reading: a pattern is useful only if 'Worked' is clearly above 'Random day' on many cases.",
          "On the 100-stock test (Apr 2025 onward) none of the 7 was; treat any signal here as one input for the",
          "sentiment and risk agents, not as a prediction on its own."]
report = "\n".join(lines)
outp = HERE / "results" / f"scan_{SYM}.md"; outp.parent.mkdir(exist_ok=True)
outp.write_text(report, encoding="utf-8")
print(report)
