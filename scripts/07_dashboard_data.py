"""
07_dashboard_data.py -- assemble every verified checkpoint result into one JSON
payload for the project dashboard.

This script computes nothing new. It reads the artefacts the checkpoint scripts
already wrote and the frozen clean/label data, and emits
`reports/dashboard_data.json`. Anything not yet verified is recorded as such, with the
reason -- the dashboard shows pending and failed work rather than hiding it.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
P1 = ROOT / "reports" / "phase1"
P2 = ROOT / "reports" / "phase2"
OUT = ROOT / "reports" / "dashboard_data.json"


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bt = _load("04_backtest")
SYMS = bt.PILOT_SYMBOLS
DEV_END = pd.Timestamp("2025-03-31")

SECTORS = {
    "TCS": "Information Technology",
    "RELIANCE": "Oil Gas & Consumable Fuels",
    "BAJAJFINSV": "Financial Services",
    "ITC": "Fast Moving Consumer Goods",
    "SIEMENS": "Capital Goods",
    "VEDL": "Metals & Mining",
    "ADANIENT": "Metals & Mining",
    "IDEA": "Telecommunication",
}
WHY_CHOSEN = {
    "TCS": "Clean baseline, no corporate actions",
    "RELIANCE": "Bonuses + Jio demerger, web-verified as near-zero price impact",
    "BAJAJFINSV": "Same-day split+bonus — the fabricated +108% jump fixed in Phase 1.2",
    "ITC": "Demerger matching the sourced ratio",
    "SIEMENS": "Demerger with a web-confirmed WRONG sourced ratio (real 1:1, table said ~2.0)",
    "VEDL": "Demerger correctly applied, large real discontinuity",
    "IDEA": "Noisiest name: 33 uncaught moves, no corporate actions",
    "ADANIENT": "17 uncaught moves, Hindenburg/DOJ news-driven, different sector",
}


def jnum(x):
    if x is None:
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(float(x)) else float(x)
    return x


def clean_df(x: pd.DataFrame) -> list:
    return json.loads(x.replace({np.nan: None}).to_json(orient="records"))


# ======================================================================================

def build() -> dict:
    payload: dict = {
        "generated_utc": pd.Timestamp.now('UTC').strftime("%Y-%m-%d %H:%M UTC"),
        "spec": {
            "universe": "NIFTY 100 (pilot: 8 stocks)",
            "history": "2015-01-01 to present",
            "dev_window": "2015-01-01 to 2025-03-31",
            "holdout": "2025-04-01 onward — SEALED, opened once in Phase 9",
            "labels": "Triple barrier: +2xATR Up / -1xATR Down / 10-day timeout Sideways (ATR 14, min_periods 14)",
            "execution": "Signal through Close[t], executed at Open[t+1]; no fill on non-tradeable days",
            "cost": "0.35% per round trip (0.25% verified Zerodha charges + 0.10% assumed slippage)",
            "direction": "Long-only (no cash-segment shorting)",
            "base_paper": "Kotekar, Mohan, Kolukuluri — 'Can News Sentiment Improve Deep Learning Models for Nifty 50 Index Forecasting?', IEEE Access vol. 14, 2026, DOI 10.1109/ACCESS.2025.3644013",
            "success": "Beat the base paper on accuracy OR alpha",
        },
    }

    # ---- Phase / checkpoint status -----------------------------------------------
    payload["checkpoints"] = [
        {"id": "0.1", "name": "Base paper and baselines chosen", "status": "done",
         "note": "Base paper frozen. Only page 1 read; full PDF still needed in docs/papers/."},
        {"id": "0.2", "name": "NSE costs and trading rules verified", "status": "done",
         "note": "0.25% charges verified from Zerodha; 0.10% slippage is an explicit assumption."},
        {"id": "0.3", "name": "Universe, horizon, metrics, holdout frozen", "status": "done", "note": ""},
        {"id": "1.1", "name": "Prices with historical constituents", "status": "partial",
         "note": "No gaps for the 8 pilot stocks. SURVIVORSHIP BIAS UNFIXED: today's NIFTY100 list is used for all of 2015-2026. point_in_time_universe() deliberately raises NotImplementedError."},
        {"id": "1.2", "name": "Split and bonus adjustment", "status": "partial",
         "note": "Core 3-hypothesis prefold detector fixed and proven (96 self-tests). 296 uncaught moves project-wide; only 4 individually web-verified. IDEA (33) and ADANIENT (15 of 17) remain unverified — deprioritised by the user."},
        {"id": "1.3", "name": "Sector mapping and sector index data", "status": "blocked",
         "note": "Sector map read from ind_nifty100list.csv. 01b_download_sector_indices.py NOT YET RUN — needs real internet; the sandbox cannot reach Yahoo Finance. Most candidate tickers in it are unverified guesses; only ^NSEBANK was confirmed."},
        {"id": "1.4", "name": "Quality report and frozen data snapshot", "status": "partial",
         "note": "SHA-256 snapshot manifest was generated in a previous session but never reached the PC. Needs regenerating."},
        {"id": "2.1", "name": "Target/stop/time labels", "status": "done",
         "note": "Triple-barrier labels built for all 8. Class balance tabulated; 20 labels verified by hand on charts in a previous session (chart PNG never reached the PC)."},
        {"id": "2.2", "name": "Backtest engine with costs and next-day execution", "status": "done",
         "note": "51/51 checks pass on real data. Rewritten this session: the previous draft marked the entry day close-to-close, handing the strategy the overnight gap for free."},
        {"id": "2.3", "name": "Walk-forward splits", "status": "done",
         "note": "256/256 checks pass. Purged + embargoed expanding-window folds; 2,083 labels removed that a naive date cut would have leaked."},
        {"id": "2.4", "name": "Baselines run — the numbers to beat", "status": "done",
         "note": "Buy-and-hold, 252d momentum, RSI(14) 30/50, MACD(12,26,9). Indicators not yet validated against TA-Lib (that is checkpoint 3.1)."},
        {"id": "3.x", "name": "Indicator families", "status": "todo", "note": "Not started."},
        {"id": "4.x", "name": "Technical model", "status": "todo", "note": "Not started."},
        {"id": "5.x", "name": "Sector and regime", "status": "todo", "note": "Not started."},
        {"id": "6.x", "name": "News agent", "status": "todo", "note": "Not started."},
        {"id": "7.x", "name": "Risk agent", "status": "todo", "note": "Not started."},
        {"id": "8.x", "name": "Fusion / stacking", "status": "todo", "note": "Not started."},
        {"id": "9.x", "name": "Final validation on the holdout", "status": "todo",
         "note": "Open decision: the base paper reports MAPE/R2 on price regression, this project does classification + alpha. The metric mismatch is unresolved; the user has final say."},
        {"id": "10", "name": "Dashboard and paper", "status": "partial", "note": "This dashboard."},
    ]

    # ---- Per-symbol data quality --------------------------------------------------
    uni = pd.read_csv(P1 / "checkpoint_1_3_universe.csv") if (P1 / "checkpoint_1_3_universe.csv").is_file() else pd.DataFrame()
    sym_rows = []
    for s in SYMS:
        df = bt.load_clean(s, allow_holdout=True)
        dev = df.loc[df.index <= DEV_END]
        u = uni.loc[uni["symbol"] == s]
        urow = u.iloc[0].to_dict() if len(u) else {}
        phantom = int((~dev["Tradeable"]).sum())
        lab_p = ROOT / "data" / "labels" / f"{s}.csv"
        lab_stats = {}
        if lab_p.is_file():
            lab = pd.read_csv(lab_p)
            lab["date"] = pd.to_datetime(lab["date"])
            lab = lab.loc[lab["date"] <= DEV_END]
            kept = lab.loc[lab["dropped_reason"].isna() & lab["label"].notna()]
            vc = kept["label"].value_counts()
            n = max(len(kept), 1)
            lab_stats = {
                "labels_kept": int(len(kept)),
                "up": int(vc.get("Up", 0)), "down": int(vc.get("Down", 0)),
                "sideways": int(vc.get("Sideways", 0)),
                "up_pct": round(100 * vc.get("Up", 0) / n, 2),
                "down_pct": round(100 * vc.get("Down", 0) / n, 2),
                "sideways_pct": round(100 * vc.get("Sideways", 0) / n, 2),
                "dropped": int(lab["dropped_reason"].notna().sum()),
            }
        sym_rows.append({
            "symbol": s, "sector": SECTORS.get(s, ""), "why_chosen": WHY_CHOSEN.get(s, ""),
            "first_bar": str(dev.index.min().date()), "last_dev_bar": str(dev.index.max().date()),
            "dev_sessions": int(len(dev)),
            "non_tradeable_sessions": phantom,
            "truncate_at": urow.get("truncate_at") if isinstance(urow.get("truncate_at"), str) else None,
            "exclude_reason": urow.get("exclude_reason") if isinstance(urow.get("exclude_reason"), str) else None,
            **lab_stats,
        })
    payload["symbols"] = clean_df(pd.DataFrame(sym_rows))

    # ---- Known data anomalies -----------------------------------------------------
    payload["anomalies"] = [
        {"issue": "7 flat zero-volume phantom sessions in 2025-2026",
         "dates": "2025-03-18, 2026-01-15, 2026-05-01, 2026-05-28, 2026-06-26, 2026-09-14, 2026-10-02",
         "status": "verified, excluded from execution",
         "detail": "2025-03-18 was a REAL NSE trading day (March 2025 holidays were only the 14th and 31st) with missing Yahoo data. 2026-05-01 and 2026-10-02 ARE real holidays wrongly admitted to the trading calendar. The backtest marks all 7 non-tradeable so no fill can occur on them; 02c_calendar.py still needs fixing."},
        {"issue": "Survivorship bias", "dates": "2015-2026",
         "status": "open, blocks publication",
         "detail": "Today's NIFTY100 constituents are used for the whole history. No headline alpha should be published until point-in-time index circulars are loaded."},
        {"issue": "296 uncaught large price moves project-wide", "dates": "various",
         "status": "open, deprioritised by the user",
         "detail": "Only 4 web-verified (SIEMENS wrong ratio, RELIANCE/Jio, ADANIENT Dec-2023 election, ADANIENT Nov-2024 DOJ). IDEA has 33 unverified, ADANIENT 15."},
        {"issue": "NIFTY100 index mark-to-market bug", "dates": "15 NoData sessions",
         "status": "fixed this session",
         "detail": "The engine marked positions against Close[t-1] rather than the last valid close, so each unpriced session broke the return chain. NIFTY100 buy-and-hold was understated by 23 percentage points (167.06% vs the correct 189.83%)."},
    ]

    # ---- Phase 2.3 folds ----------------------------------------------------------
    fp = P2 / "checkpoint_2_3_folds.csv"
    if fp.is_file():
        folds = pd.read_csv(fp)
        agg = folds.groupby("fold").agg(
            test_start=("test_start", "first"), test_end=("test_end", "first"),
            n_train=("n_train", "sum"), n_test=("n_test", "sum"),
            purged=("purged_vs_naive_cut", "sum"),
            train_up=("train_up", "sum"), train_down=("train_down", "sum"),
            train_sideways=("train_sideways", "sum"),
            test_up=("test_up", "sum"), test_down=("test_down", "sum"),
            test_sideways=("test_sideways", "sum"),
        ).reset_index()
        payload["folds"] = clean_df(agg)
        payload["folds_total_purged"] = int(folds["purged_vs_naive_cut"].sum())

    # ---- Phase 2.4 baselines ------------------------------------------------------
    pp = P2 / "checkpoint_2_4_baselines_portfolio.csv"
    if pp.is_file():
        payload["baselines_portfolio"] = clean_df(pd.read_csv(pp))
    sp = P2 / "checkpoint_2_4_baselines_per_symbol.csv"
    if sp.is_file():
        per = pd.read_csv(sp)
        payload["baselines_per_symbol"] = clean_df(per)
        pooled = per.groupby("strategy").apply(
            lambda g: pd.Series({
                "up_base_rate": (g["up_base_rate"] * g["n_labels"]).sum() / g["n_labels"].sum(),
                "up_precision": (g["up_precision"] * g["n_long_calls"]).sum() / g["n_long_calls"].sum(),
                "up_recall": (g["up_recall"] * g["n_labels"]).sum() / g["n_labels"].sum(),
                "down_rate_when_long": (g["down_rate_when_long"] * g["n_long_calls"]).sum() / g["n_long_calls"].sum(),
                "n_long_calls": g["n_long_calls"].sum(),
                "n_round_trips": g["n_round_trips"].sum(),
            }), include_groups=False
        ).reset_index()
        pooled["up_lift"] = pooled["up_precision"] / pooled["up_base_rate"]
        payload["classification_floor"] = clean_df(pooled)

    # ---- Equity curves ------------------------------------------------------------
    cp = P2 / "checkpoint_2_4_equity_curves_monthly.csv"
    if cp.is_file():
        c = pd.read_csv(cp)
        c["date"] = pd.to_datetime(c["date"]).dt.strftime("%Y-%m")
        payload["equity_curves"] = clean_df(c)

    # ---- Worked examples: one Up and one Down label, bar by bar -------------------
    # The dashboard is abstract without these. Both are drawn from the checkpoint 2.1
    # hand-check sample, so they are labels that were already verified by eye.
    examples = []
    for sym, date_str in (("RELIANCE", "2024-12-31"), ("ITC", "2022-04-19")):
        lab = pd.read_csv(ROOT / "data" / "labels" / f"{sym}.csv")
        lab["date"] = pd.to_datetime(lab["date"])
        row = lab.loc[lab["date"] == pd.Timestamp(date_str)]
        if row.empty:
            continue
        r = row.iloc[0]
        px = bt.load_clean(sym, allow_holdout=True)
        i = px.index.searchsorted(pd.Timestamp(date_str))
        win = px.iloc[max(0, i - 5): i + 13]
        bars = [{
            "date": str(d.date()),
            "o": round(float(b.AdjOpen), 2), "h": round(float(b.AdjHigh), 2),
            "l": round(float(b.AdjLow), 2), "c": round(float(b.AdjClose), 2),
        } for d, b in win.iterrows()]
        examples.append({
            "symbol": sym, "sector": SECTORS.get(sym, ""),
            "signal_date": date_str,
            "label": r["label"],
            "touch_date": None if pd.isna(r["touch_date"]) else str(pd.Timestamp(r["touch_date"]).date()),
            "atr": round(float(r["atr"]), 2),
            "upper": round(float(r["upper_barrier"]), 2),
            "lower": round(float(r["lower_barrier"]), 2),
            "close_at_signal": round(float(px.loc[pd.Timestamp(date_str), "AdjClose"]), 2),
            "exec_open": round(float(px.iloc[i + 1]["AdjOpen"]), 2) if i + 1 < len(px) else None,
            "exec_date": str(px.index[i + 1].date()) if i + 1 < len(px) else None,
            "bars": bars,
        })
    payload["worked_examples"] = examples

    # ---- Self-test tallies --------------------------------------------------------
    payload["test_tallies"] = [
        {"module": "02b_adjust_prices.py", "passed": 96, "failed": 0,
         "what": "Price adjustment, incl. the BAJAJFINSV same-day split+bonus regression test"},
        {"module": "02c_calendar.py", "passed": 11, "failed": 0, "what": "Trading calendar and special sessions"},
        {"module": "02d_universe.py", "passed": 8, "failed": 0, "what": "Universe gating, purge windows, embargo (synthetic data)"},
        {"module": "04_backtest.py", "passed": 51, "failed": 0,
         "what": "Phase 2.2: costs, next-day-open execution, gap-leak regression, holdout seal (real data)"},
        {"module": "05_splits.py", "passed": 256, "failed": 0,
         "what": "Phase 2.3: no label window straddles a train/test boundary (real labels)"},
        {"module": "06_baselines.py", "passed": 22, "failed": 0,
         "what": "Phase 2.4: indicator causality leak test + costed baseline results"},
    ]
    return payload


if __name__ == "__main__":
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1024:.1f} KB)")
    print(f"symbols: {len(data['symbols'])}, folds: {len(data.get('folds', []))}, "
          f"baselines: {len(data.get('baselines_portfolio', []))}, "
          f"curve points: {len(data.get('equity_curves', []))}")
