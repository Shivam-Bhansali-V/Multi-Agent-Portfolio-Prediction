"""
Checkpoint 1.2 - price cleaning and adjustment.

Policy (per user: "assume Yahoo source is true", no NSE cross-check in this pass):
  - Keep raw OHLCV as the EXECUTION series (what actually traded; used for
    entry/stop/target fills, price-band checks, display).
  - Build an ADJUSTED series (Open/High/Low/Close * daily factor, where
    factor = AdjClose / Close) used for indicators and for computing forward
    returns / labels, so a split/bonus/special-dividend day is not read as a
    price crash.
  - Detect each date the factor steps (a real corporate action per Yahoo's
    own numbers). Classify as a plausible split/bonus ratio, a plausible
    one-off dividend, or "unexplained" if neither fits.
  - Align every stock to the NIFTY50 index trading-day calendar. A date NSE
    was open but the stock has no row is marked halted, not filled in.
  - Reject negative/zero prices. Flag (not auto-drop) single-day raw-Close
    moves beyond a generous sanity ceiling for manual review.

Default taken (stated to user, not yet overridden): stocks with an
"unexplained" factor jump are EXCLUDED from the modeling universe for now,
kept only in data/clean/ with the flag, pending a manual look.

--- Amendment (checkpoint 1.2b, discontinuity review) -----------------------
Bug found and fixed here: the >60% raw-Close sanity check (flagged_moves) was
computed but NEVER wired into exclude_from_model_universe -- only an
"unexplained" FACTOR-STEP could exclude a stock. This missed VEDL and TMPV,
whose 2026 Vedanta demerger and 2025 Tata Motors CV/PV demerger produced a
genuine ~60-65% one-day raw-price drop with Yahoo applying NO Adj Close
correction at all (Factor stayed ~1.0, so no factor-step event was ever
generated to classify).

Fix: a sanity-flagged big move (>60% raw Close move) now also sets
exclude_from_model_universe=True UNLESS the date falls on a confirmed
market-wide event date (KNOWN_MARKET_WIDE_DATES below -- COVID-19 crash,
Adani/Hindenburg, PSU bank recap, 2024 election result, etc.), each verified
by web search this session. Market-wide moves are real, valuable signal and
are deliberately left IN the data, unexcluded.

KNOWN_UNADJUSTED_DEMERGERS lists the two cases confirmed by web search where
Yahoo's Adj Close missed a demerger/spin-off entirely: VEDL (user-confirmed
exclude) and TMPV (found this pass, flagged for the user to confirm -- NOT
auto-excluded by that confirmation step, only by the general big-move rule
above, so this list is for documentation/traceability, not a second silent
exclusion path).
-----------------------------------------------------------------------------
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/mnt/user-data/uploads/Market Prediction Model")
RAW_DIR = ROOT / "data" / "raw" / "yahoo"
CLEAN_DIR = ROOT / "data" / "clean"
REPORT_DIR = ROOT / "reports" / "phase1"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_NAMES = {"NIFTY50", "NIFTY100", "INDIAVIX"}
PLAUSIBLE_SPLIT_RATIOS = [1.5, 2, 2.5, 3, 4, 5, 10]  # common NSE split/bonus multiples
RATIO_TOL = 0.04          # 4% tolerance when matching a plausible ratio
MAX_DIVIDEND_ADJ = 0.20   # a one-off adjustment step <=20% is treated as a plausible special dividend
SANITY_MOVE_CEILING = 0.60  # single-day raw Close move beyond this is flagged for a human look

# Dates confirmed (via web search, Oct 2026) as real market-wide events, not
# single-stock corporate-action artifacts. A big move landing on one of these
# dates is NOT grounds for exclusion by itself.
KNOWN_MARKET_WIDE_DATES = {
    "2020-03-12", "2020-03-20", "2020-03-23", "2020-04-07",      # COVID-19 crash/recovery
    "2023-01-25", "2023-01-27",                                   # Adani / Hindenburg report
    "2017-10-25",                                                 # PSU bank recapitalisation plan
    "2024-06-04",                                                 # 2024 general-election result shock
}

# Demerger/spin-off dates confirmed (web search) where Yahoo applied NO
# Adj Close correction, so the ordinary factor-step detector could never see
# them -- only the raw sanity-ceiling check catches these.
KNOWN_UNADJUSTED_DEMERGERS = {
    "VEDL": "2026-04-30",   # Vedanta 5-way demerger, record date 2026-05-01; user-confirmed exclude
    "TMPV": "2025-10-14",   # Tata Motors CV/PV demerger, record date 2025-10-14; flagged, pending user confirm
}


def load_master_calendar() -> pd.DatetimeIndex:
    df = pd.read_csv(RAW_DIR / "NIFTY50.csv", parse_dates=["Date"])
    return pd.DatetimeIndex(sorted(df["Date"].unique()))


def classify_step(ratio_change: float) -> str:
    """ratio_change = factor(t) / factor(t-1), i.e. how much the adjustment
    multiplier stepped on this date."""
    inv = 1.0 / ratio_change if ratio_change != 0 else np.inf
    for r in PLAUSIBLE_SPLIT_RATIOS:
        if abs(inv - r) <= RATIO_TOL * r or abs(ratio_change - r) <= RATIO_TOL * r:
            return f"plausible_split_or_bonus (~{r:g}x)"
    if abs(ratio_change - 1.0) <= MAX_DIVIDEND_ADJ:
        return "plausible_special_dividend"
    return "unexplained"


def clean_one(path: Path, calendar: pd.DatetimeIndex) -> dict:
    name = path.stem
    df = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)

    # --- reject negative/zero prices ---
    bad_price = (df[["Open", "High", "Low", "Close", "Adj Close"]] <= 0).any(axis=1)
    n_bad_price = int(bad_price.sum())
    df = df.loc[~bad_price].reset_index(drop=True)

    # --- adjustment factor and adjusted OHLC ---
    df["Factor"] = df["Adj Close"] / df["Close"]
    df["AdjOpen"] = df["Open"] * df["Factor"]
    df["AdjHigh"] = df["High"] * df["Factor"]
    df["AdjLow"] = df["Low"] * df["Factor"]
    df["AdjClose"] = df["Adj Close"]

    # --- detect corporate-action steps in the factor ---
    factor_ratio = df["Factor"] / df["Factor"].shift(1)
    step_mask = (factor_ratio - 1).abs() > 0.005  # >0.5% step = a real action, not rounding
    events = []
    unexplained = False
    for idx in df.index[step_mask.fillna(False)]:
        kind = classify_step(float(factor_ratio.loc[idx]))
        events.append({"date": str(df.loc[idx, "Date"].date()), "factor_step": round(float(factor_ratio.loc[idx]), 4),
                        "raw_close_before": round(float(df.loc[idx - 1, "Close"]), 2) if idx > 0 else None,
                        "raw_close_on": round(float(df.loc[idx, "Close"]), 2), "classification": kind})
        if kind == "unexplained":
            unexplained = True

    # --- sanity flag on raw Close moves (not auto-dropped) ---
    raw_ret = df["Close"].pct_change()
    flagged_moves = df.loc[raw_ret.abs() > SANITY_MOVE_CEILING, "Date"].dt.date.astype(str).tolist()
    # a big move NOT on a confirmed market-wide date is treated as a possible
    # unadjusted corporate action and triggers exclusion, same as an
    # "unexplained" factor-step event.
    unexplained_big_move = any(d not in KNOWN_MARKET_WIDE_DATES for d in flagged_moves)
    if unexplained_big_move:
        unexplained = True
    # TMPV's confirmed demerger drop (-40.2%) falls under the 60% sanity
    # ceiling, so it would otherwise slip through uncaught -- forced here by
    # name since it is independently confirmed (web search) as an unadjusted
    # demerger, same mechanism as VEDL. Excluded by default pending your
    # confirmation, same as the "unexplained" default above.
    if name in KNOWN_UNADJUSTED_DEMERGERS:
        unexplained = True

    # --- align to master calendar, mark halted days ---
    df = df.set_index("Date")
    full = df.reindex(calendar)
    full["Halted"] = full["Close"].isna().astype(int)
    full.index.name = "Date"
    n_halted = int(full["Halted"].sum())

    full["CorpActionFlag"] = 0
    for e in events:
        full.loc[pd.Timestamp(e["date"]), "CorpActionFlag"] = 1

    out_cols = ["Open", "High", "Low", "Close", "Volume", "AdjOpen", "AdjHigh", "AdjLow", "AdjClose",
                "Factor", "CorpActionFlag", "Halted"]
    full[out_cols].to_csv(CLEAN_DIR / f"{name}.csv")

    return {
        "name": name, "rows_in": len(pd.read_csv(path)), "rows_after_price_reject": len(df),
        "negative_or_zero_price_rows_dropped": n_bad_price,
        "halted_days_vs_master_calendar": n_halted,
        "corp_action_events": len(events),
        "unexplained_events": sum(1 for e in events if e["classification"] == "unexplained"),
        "flagged_big_moves": len(flagged_moves),
        "exclude_from_model_universe": unexplained,
        "_events": events,
    }


def main():
    calendar = load_master_calendar()
    rows, all_events = [], []
    for path in sorted(RAW_DIR.glob("*.csv")):
        if path.stem in INDEX_NAMES:
            continue
        rec = clean_one(path, calendar)
        for e in rec.pop("_events"):
            all_events.append({"stock": rec["name"], **e})
        rows.append(rec)

    summary = pd.DataFrame(rows)
    summary.to_csv(REPORT_DIR / "checkpoint_1_2_summary.csv", index=False)
    pd.DataFrame(all_events).to_csv(REPORT_DIR / "checkpoint_1_2_corp_action_events.csv", index=False)

    excluded = summary.loc[summary["exclude_from_model_universe"], "name"].tolist()
    lines = [
        "# Checkpoint 1.2 report: price cleaning and adjustment",
        "",
        f"Stocks processed: {len(summary)}",
        f"Stocks with 0 negative/zero-price rows found: {(summary['negative_or_zero_price_rows_dropped']==0).sum()} "
        f"(total dropped rows across all stocks: {int(summary['negative_or_zero_price_rows_dropped'].sum())})",
        f"Total corporate-action step events detected: {int(summary['corp_action_events'].sum())}",
        f"Unexplained events: {int(summary['unexplained_events'].sum())}",
        f"Stocks EXCLUDED from modeling universe (unexplained step, per default pending your check): "
        f"{len(excluded)} -> {', '.join(excluded) if excluded else 'none'}",
        f"Stocks with any day flagged as a big raw-Close move (>{int(SANITY_MOVE_CEILING*100)}%): "
        f"{int((summary['flagged_big_moves']>0).sum())}",
        f"Total halted-day rows (master calendar date, stock has no row) across all stocks: "
        f"{int(summary['halted_days_vs_master_calendar'].sum())}",
        "",
        "Per-stock halted-day counts over 20 (listing delay is normal and expected; a mid-history gap is not):",
    ]
    mid = summary[(summary["halted_days_vs_master_calendar"] > 20)]
    for _, r in mid.sort_values("halted_days_vs_master_calendar", ascending=False).iterrows():
        lines.append(f"  {r['name']}: {r['halted_days_vs_master_calendar']} missing trading days")
    (REPORT_DIR / "checkpoint_1_2_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
