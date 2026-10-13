"""
02_clean_adjust.py -- Phase 1 orchestrator (REWRITTEN per HANDOFF_PHASE1_REMEDIATION.md,
Package D).

Chains the remediation modules in order:

    02a_build_corp_actions  -> data/reference/corp_actions.csv   (reused if present)
    02c_calendar             -> master trading calendar (union of all raw files)
    02b_adjust_prices        -> per-symbol adjusted OHLCV, corporate-action divisors
                                 gated by the empirical prefold detector (F03 fix)
    02e_validate              -> OHLC/calendar/coverage checks over every clean file
    02d_universe              -> per-symbol eligibility table (survivorship/history)
    _provenance                -> SHA-256 + environment header stamped on every report

Fixes applied relative to the pre-remediation script (see checkpoint_1_2c_audit_report.md):
    F02  ROOT is resolved from this file's location, not a hardcoded sandbox path.
    F03  Factor is no longer inferred as Adj Close / Close; corporate actions are
         applied via 02b's empirically-gated divisor logic.
    F04  KNOWN_MARKET_WIDE_DATES deleted outright -- no hand-maintained exemption list.
    F07  02c_calendar's align_to_calendar() replaces the old Halted-via-NaN heuristic;
         pre-listing bars are never padded, genuine no-data days are flagged NoData.
    F09  The old "unexplained: 0" metric is replaced by 02e's action-table coverage
         audit (uncaught raw moves >= 15% with no table entry, and residual moves in
         the adjusted series).
    F10  KNOWN_UNADJUSTED_DEMERGERS is demoted to provenance-only commentary; actual
         truncation decisions come from 02d_universe's exclude_reason/truncate_at.
    F11  CorpActionExDate / other flags are set via 02c's set_flag_safe(), never a
         raw .loc[label]=value enlargement.

Usage:
    python 02_clean_adjust.py                  # run full pipeline, all raw symbols
    python 02_clean_adjust.py --symbols X,Y     # restrict to a subset (debugging)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import importlib.util as _ilu  # noqa: E402


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


prov = _load("_provenance")
a02a = _load("02a_build_corp_actions")
a02b = _load("02b_adjust_prices")
a02c = _load("02c_calendar")
a02d = _load("02d_universe")
a02e = _load("02e_validate")

RAW_DIR = ROOT / "data" / "raw" / "yahoo"
CLEAN_DIR = ROOT / "data" / "clean"
REF_DIR = ROOT / "data" / "reference"
REPORTS_DIR = ROOT / "reports" / "phase1"
ACTIONS_CSV = REF_DIR / "corp_actions.csv"

MIN_RAW_FILES = 90  # fail fast if the raw data directory looks wrong/partial


def _fail_fast_checks() -> None:
    if not RAW_DIR.is_dir():
        raise SystemExit(f"FATAL: raw data directory not found: {RAW_DIR}")
    n_raw = len(list(RAW_DIR.glob("*.csv")))
    if n_raw < MIN_RAW_FILES:
        raise SystemExit(
            f"FATAL: only {n_raw} raw CSVs found in {RAW_DIR} (expected >= {MIN_RAW_FILES}). "
            "Refusing to run the pipeline on what looks like a partial/missing download -- "
            "re-run 01_download_prices.py first."
        )


def run_pipeline(symbols=None, rebuild_actions: bool = False) -> dict:
    t0 = time.time()
    _fail_fast_checks()
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/5] Corporate-action table ...")
    if rebuild_actions or not ACTIONS_CSV.is_file():
        a02a.build(ROOT)
    actions_df = a02a.load_corp_actions(ROOT)
    print(f"      {len(actions_df)} action rows, "
          f"{actions_df['symbol'].nunique() if not actions_df.empty else 0} symbols")

    print("[2/5] Master trading calendar ...")
    calendar, cal_diag = a02c.build_calendar(RAW_DIR)
    cal_problems = a02c.validate_calendar(calendar)
    print(f"      {cal_diag['total_sessions']} sessions "
          f"({cal_diag['first_session']} .. {cal_diag['last_session']}); "
          f"{len(cal_problems)} calendar problems")

    index_names = set(a02c.DEFAULT_INDEX_NAMES)  # NIFTY50, NIFTY100, INDIAVIX -- not equities
    all_files = sorted(RAW_DIR.glob("*.csv"))
    index_files = [p for p in all_files if p.stem in index_names]
    raw_files = [p for p in all_files if p.stem not in index_names]
    if symbols:
        wanted = set(symbols)
        raw_files = [p for p in raw_files if p.stem in wanted]
        index_files = [p for p in index_files if p.stem in wanted]

    # Index series never go through corporate-action adjustment (splits/bonuses/demergers
    # don't apply to an index) -- align to the calendar and pass Close/Volume through as-is.
    for p in index_files:
        sym = p.stem
        try:
            raw_df = pd.read_csv(p)
            raw_df["Date"] = pd.to_datetime(raw_df["Date"]).dt.normalize()
            raw_df = raw_df.set_index("Date").sort_index()
            aligned, _ = a02c.align_to_calendar(raw_df, calendar, sym)
            # No structural adjustment applies to an index -- alias AdjClose/AdjOpen/etc to
            # the raw columns so 02e_validate's schema expectations (AdjClose present) hold.
            for col in ("Open", "High", "Low", "Close", "Volume"):
                if col in aligned.columns:
                    aligned[f"Adj{col}"] = aligned[col]
            (CLEAN_DIR / f"{sym}.csv").write_text(
                aligned.reset_index().rename(columns={"index": "Date"}).to_csv(index=False)
            )
        except Exception as e:
            print(f"      index {sym} FAILED: {type(e).__name__}: {e}")
    print(f"      {len(index_files)} index series calendar-aligned (no corp-action adjustment applied)")

    print(f"[3/5] Adjusting {len(raw_files)} symbols ...")
    per_symbol_summary = []
    failures = []
    for i, p in enumerate(raw_files, 1):
        sym = p.stem
        try:
            raw_df = pd.read_csv(p)
            raw_df["Date"] = pd.to_datetime(raw_df["Date"]).dt.normalize()
            raw_df = raw_df.set_index("Date").sort_index()
            if raw_df.empty or "Close" not in raw_df.columns:
                failures.append((sym, "empty or missing Close column"))
                continue

            adj_df = a02b.build_adjusted(raw_df, actions_df, sym, split_policy="auto")
            aligned, align_diag = a02c.align_to_calendar(adj_df, calendar, sym)

            out_path = CLEAN_DIR / f"{sym}.csv"
            aligned.reset_index().rename(columns={"index": "Date"}).to_csv(out_path, index=False)

            ffill_problems = a02c.assert_no_ffill_damage(aligned)
            per_symbol_summary.append({
                "symbol": sym,
                "first_bar_date": align_diag["first_bar_date"],
                "last_bar_date": align_diag["last_bar_date"],
                "raw_bars": align_diag["raw_bars"],
                "aligned_bars": align_diag["aligned_bars"],
                "no_data_days": align_diag["no_data_days"],
                "dates_dropped_by_calendar_align": len(align_diag["dates_dropped_by_calendar_align"]),
                "ffill_problems": len(ffill_problems),
            })
        except Exception as e:
            failures.append((sym, f"{type(e).__name__}: {e}"))
        if i % 20 == 0 or i == len(raw_files):
            print(f"      {i}/{len(raw_files)} done ({len(failures)} failures so far)")

    if failures:
        print(f"      FAILURES ({len(failures)}):")
        for sym, msg in failures:
            print(f"        {sym}: {msg}")

    print("[4/5] Validating clean/ against raw/ + action table ...")
    val_summary, val_problems = a02e.run_all(CLEAN_DIR, RAW_DIR, ACTIONS_CSV, calendar)

    print("[5/5] Universe eligibility table ...")
    merged = pd.DataFrame(per_symbol_summary)
    if not merged.empty and not val_summary.empty:
        merged = merged.merge(
            val_summary[["symbol", "raw_moves_ge_15pct", "uncaught_count"]]
            .rename(columns={"raw_moves_ge_15pct": "flagged_big_moves",
                              "uncaught_count": "unexplained_events"}),
            on="symbol", how="left",
        )
    universe_df = a02d.build_universe(merged, actions_df, calendar) if not merged.empty else pd.DataFrame()

    # ---- Reports, with mandatory provenance headers ----
    header = prov.provenance_header(__file__, inputs=[RAW_DIR, ACTIONS_CSV])

    val_summary.to_csv(REPORTS_DIR / "checkpoint_1_3_validation_summary.csv", index=False)
    val_problems.to_csv(REPORTS_DIR / "checkpoint_1_3_validation_problems.csv", index=False)
    universe_df.to_csv(REPORTS_DIR / "checkpoint_1_3_universe.csv", index=False)

    n_pass = int(val_summary["passed"].sum()) if not val_summary.empty else 0
    n_total = len(val_summary)
    total_uncaught = int(val_summary["uncaught_count"].sum()) if not val_summary.empty else 0
    total_residual = int(val_summary["residual_count"].sum()) if not val_summary.empty else 0
    n_excluded = int((universe_df["exclude_reason"] != "").sum()) if not universe_df.empty else 0

    body = (
        f"## Run summary\n\n"
        f"- Symbols processed: {len(raw_files)}\n"
        f"- Clean files written: {len(per_symbol_summary)}\n"
        f"- Hard failures (exception during adjust/align): {len(failures)}\n"
        f"- Calendar: {cal_diag['total_sessions']} sessions, {len(cal_problems)} problems\n"
        f"- Validation: {n_pass}/{n_total} symbols passed with zero problems\n"
        f"- Action-table coverage: {total_uncaught} uncaught raw moves >= 15% across all "
        f"symbols (no action-table entry within +/-3 sessions); {total_residual} residual "
        f">= 15% moves remaining in the adjusted series\n"
        f"- Universe: {n_excluded}/{len(universe_df) if not universe_df.empty else 0} "
        f"symbols flagged with an exclude_reason (survivorship/history/demerger-child)\n"
        f"- Elapsed: {time.time() - t0:.1f}s\n\n"
        f"## Hard failures\n\n" + (
            "\n".join(f"- `{s}`: {m}" for s, m in failures) if failures else "(none)"
        ) + "\n\n"
        f"## Known, documented limitations carried forward\n\n"
        f"- Survivorship bias: point_in_time_universe() in 02d_universe.py explicitly "
        f"raises NotImplementedError -- reconstructing the historical (not current) "
        f"NIFTY100 membership was out of scope for this remediation pass.\n"
        f"- A handful of UNVERIFIED demerger ratios in corp_actions_manual.csv do not "
        f"match observed price action (see this run's validation problems for the "
        f"specific symbols/dates); the detector in 02b now withholds applying them "
        f"rather than fabricating a discontinuity, but the correct ratio (if any) is "
        f"still unresolved for those names.\n"
    )
    prov.write_report(REPORTS_DIR / "checkpoint_1_3_report.md", "Checkpoint 1.3 -- Remediated Pipeline Run", header, body)

    print(f"\nDone in {time.time() - t0:.1f}s. "
          f"{n_pass}/{n_total} symbols clean, {len(failures)} hard failures. "
          f"Report: {REPORTS_DIR / 'checkpoint_1_3_report.md'}")

    return {
        "n_total": n_total,
        "n_pass": n_pass,
        "failures": failures,
        "total_uncaught": total_uncaught,
        "total_residual": total_residual,
        "val_summary": val_summary,
        "val_problems": val_problems,
        "universe": universe_df,
    }


def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="Comma-separated subset for debugging")
    ap.add_argument("--rebuild-actions", action="store_true",
                     help="Force rebuilding corp_actions.csv via a live yfinance pull")
    args = ap.parse_args()
    symbols = args.symbols.split(",") if args.symbols else None
    result = run_pipeline(symbols=symbols, rebuild_actions=args.rebuild_actions)
    return 0 if not result["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
