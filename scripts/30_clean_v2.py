"""
Checkpoint 5.1 - cleaning v2 (replaces the Phase 1.3 universe filter, not the raw data).

What changed versus 02_clean_adjust.py / 02d_universe.py, and why (all measured on the
raw Yahoo files, see reports/phase5/checkpoint_5_1_cleaning_report.md):
  1. A >=15% one-day move is NOT a data error. The old universe filter excluded 66 stocks
     for having one. Here only moves that are proven corporate-action artifacts (listed
     in ARTIFACT_EVENTS, each visible in the raw data as a gap with no market event) are
     repaired; every other move is kept as real history.
  2. Stale bars Yahoo emits on non-trading days (Volume == 0, flat OHLC) are removed.
  3. Returns are TOTAL returns (dividends included, from Yahoo's Adj Close factor), which
     is what an investor earns. Price-only series are kept for price-level indicators.
  4. Eligibility is point-in-time: a stock enters once it has MIN_HISTORY valid bars. No
     stock is dropped using information from its own future.
Known limitation NOT fixed here: the symbol list is today's NIFTY 100 (survivorship bias).
"""
from pathlib import Path
import numpy as np, pandas as pd, sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "yahoo"
OUT = ROOT / "data" / "panel_v2"; OUT.mkdir(parents=True, exist_ok=True)
REP = ROOT / "reports" / "phase5"; REP.mkdir(parents=True, exist_ok=True)
INDEX = {"NIFTY50", "NIFTY100", "INDIAVIX"}
DEMERGER_CHILDREN = {"ENRIN", "TMCV", "VAML"}
MIN_HISTORY = 273            # 252-day momentum lookback + 21-day skip

# Proven unadjusted corporate-action artifacts. The ex-day return is replaced by the
# NIFTY100 return of that day (an ESTIMATE: a holder kept both pieces, so the true
# return is close to a normal day, not the printed crash/jump).
ARTIFACT_EVENTS = {
    ("ADANIENT", "2015-06-03"): "demerger of ports/power/transmission arms, -38.7% unadjusted",
    ("ADANIENT", "2018-04-05"): "Adani Green demerger; Yahoo back-adjustment prints +15.0% (found by checker)",
    ("ADANIENT", "2018-09-06"): "Adani Gas demerger; Yahoo back-adjustment prints +21.0% (found by checker)",
    ("ITC", "2025-01-06"): "ITC Hotels demerger; Yahoo prints -4.55%, holder return from discovered prices is -2.68%",
    ("CGPOWER", "2016-03-15"): "consumer-products demerger, partly unadjusted",
    ("ABB", "2019-12-20"): "power-grids demerger, unadjusted",
    ("MOTHERSON", "2022-01-14"): "wiring-harness demerger, +28.6% mis-adjusted",
    ("TMPV", "2025-10-14"): "CV/PV demerger, -40.2% unadjusted (holdout period)",
    ("TRENT", "2026-01-01"): "-33.0% step = 3:2 bonus adjustment applied from wrong date (holdout period)",
    ("VEDL", "2026-04-30"): "demerger, -64.9% unadjusted (holdout period)",
}
# Where the true holder return is known from officially discovered prices, use it
# instead of the index-return estimate.
KNOWN_HOLDER_RETURN = {("ITC", "2025-01-06"): (442.65 + 27.00) / 482.60 - 1}

def main():
    raw = {p.stem: pd.read_csv(p, parse_dates=["Date"]).set_index("Date").sort_index()
           for p in sorted(RAW.glob("*.csv"))}
    stocks = [s for s in raw if s not in INDEX and s not in DEMERGER_CHILDREN]
    # --- calendar: a date is a session if most listed stocks actually traded ---
    vol = pd.concat({s: raw[s]["Volume"] for s in stocks}, axis=1)
    traded_share = (vol > 0).sum(axis=1) / vol.notna().sum(axis=1)
    non_sessions = traded_share.index[traded_share <= 0.5]
    cal = traded_share.index[traded_share > 0.5]
    idx = raw["NIFTY100"]["Close"].reindex(cal).ffill()   # index file lacks 9 special sessions
    idx_ret = idx.pct_change()

    close, tr, turnover, log = {}, {}, {}, []
    for s in stocks:
        d = raw[s].copy()
        n0 = len(d)
        stale = (d["Volume"] <= 0) & (d["High"] == d["Low"])    # flat AND untraded: no real data
        d = d[~stale]
        bad = (d[["Open", "High", "Low", "Close", "Adj Close"]] <= 0).any(axis=1)
        d = d[~bad]
        d = d[d.index.isin(cal)]
        px, adj = d["Close"].copy(), d["Adj Close"].copy()
        turnover[s] = d["Close"] * d["Volume"]          # rupee turnover, adjustment-invariant
        n_art = 0
        for (sym, day), why in ARTIFACT_EVENTS.items():
            t = pd.Timestamp(day)
            if sym != s or t not in px.index: continue
            i = px.index.get_loc(t)
            if i == 0: continue
            target = idx_ret.get(t, 0.0); target = 0.0 if pd.isna(target) else target
            target = KNOWN_HOLDER_RETURN.get((sym, day), target)
            f = (px.iloc[i - 1] * (1 + target)) / px.iloc[i]     # scale so ex-day return == index return
            px.iloc[:i] = px.iloc[:i] / f
            fa = (adj.iloc[i - 1] * (1 + target)) / adj.iloc[i]
            adj.iloc[:i] = adj.iloc[:i] / fa
            n_art += 1
        close[s], tr[s] = px, adj
        r = adj.pct_change()
        log.append(dict(symbol=s, raw_rows=n0, stale_zero_volume_rows_removed=int(stale.sum()),
                        nonpositive_rows_removed=int(bad.sum()), valid_bars=len(px),
                        first_bar=str(px.index[0].date()), last_bar=str(px.index[-1].date()),
                        artifacts_repaired=n_art, real_moves_ge15pct_kept=int((r.abs() >= 0.15).sum()),
                        max_abs_daily_return=round(float(r.abs().max()), 4),
                        dividend_share_of_total_return_factor=round(float(1 - (d["Adj Close"] / d["Close"]).iloc[0]), 3)))
    close = pd.DataFrame(close).reindex(cal); tr = pd.DataFrame(tr).reindex(cal)
    turnover = pd.DataFrame(turnover).reindex(cal)
    nbars = close.notna().cumsum()
    eligible = (nbars >= MIN_HISTORY) & close.notna()
    close.to_parquet(OUT / "close_struct_adj.parquet"); tr.to_parquet(OUT / "close_total_return.parquet")
    turnover.to_parquet(OUT / "turnover_inr.parquet"); eligible.to_parquet(OUT / "eligible.parquet")
    idx.to_frame("NIFTY100").to_parquet(OUT / "index.parquet")
    L = pd.DataFrame(log); L.to_csv(REP / "checkpoint_5_1_cleaning_per_symbol.csv", index=False)
    pd.DataFrame([dict(symbol=k[0], ex_date=k[1], note=v) for k, v in ARTIFACT_EVENTS.items()]).to_csv(
        REP / "checkpoint_5_1_artifact_events.csv", index=False)
    # --- checks ---
    resid = tr.pct_change(fill_method=None).abs()
    checks = {
        "no artifact-sized move left on a listed artifact date": all(
            resid.loc[pd.Timestamp(d), s] < 0.10 for (s, d) in ARTIFACT_EVENTS if pd.Timestamp(d) in resid.index),
        "ITC ex-demerger return equals the known holder return": bool(
            abs(tr.pct_change(fill_method=None).loc["2025-01-06", "ITC"] - KNOWN_HOLDER_RETURN[("ITC", "2025-01-06")]) < 1e-9),
        "index has no missing session": bool(idx.loc["2015-01-05":].notna().all()),
        "no non-positive price": bool((close.min().min() > 0) and (tr.min().min() > 0)),
        "calendar has no duplicate dates and is sorted": bool(cal.is_unique and cal.is_monotonic_increasing),
    }
    dev = eligible.loc[:"2025-03-31"]
    summ = dict(symbols=len(stocks), sessions=len(cal), non_session_dates_removed=[str(x.date()) for x in non_sessions],
                stale_rows_removed=int(L.stale_zero_volume_rows_removed.sum()), artifacts_repaired=int(L.artifacts_repaired.sum()),
                real_moves_ge15pct_kept=int(L.real_moves_ge15pct_kept.sum()),
                eligible_symbols_at_some_point_in_dev_window=int(dev.any().sum()),
                eligible_on_2016_02_01=int(eligible.loc["2016-02-01"].sum()), eligible_on_2025_03_28=int(eligible.loc["2025-03-28"].sum()))
    print(summ); print(checks)
    pd.Series({**summ, **{f"CHECK {k}": v for k, v in checks.items()}}).astype(str).to_csv(REP / "checkpoint_5_1_summary.csv", header=["value"])
    assert all(checks.values())

if __name__ == "__main__":
    main()
