#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02c_calendar.py -- Trading calendar construction, calendar alignment, index auditing,
and coverage accounting.

Addresses findings:
- F06 (HIGH): Calendar reindex silently dropped ~11 real trading dates per stock (Muhurat sessions).
  Fixed by building calendar from union of stock trading dates.
- F07 (HIGH): 'Halted' was mislabelled pre-listing padding. Fixed by never padding before first bar,
  and distinguishing PreListing, NoData (true halts), and PostDelisting.
- F11 (MEDIUM): Pandas enlargement bug on missing label assignment. Fixed by set_flag_safe via isin mask.
- F14 (MEDIUM): Index series never audited or cleaned. Fixed by audit_index_series.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
import pandas as pd

log = logging.getLogger("calendar")

#: Confirmed Diwali Muhurat 1-hour special evening sessions across 2015-2026.
#: Muhurat trading occurs on Diwali evening (Lakshmi Puja) for ~1 hour. Because trading volume
#: and duration are non-standard, inclusion is an explicit parameter.
MUHURAT_SESSIONS: frozenset[pd.Timestamp] = frozenset([
    pd.Timestamp("2015-11-11"),  # Samvat 2072
    pd.Timestamp("2016-10-30"),  # Samvat 2073 (Sunday)
    pd.Timestamp("2017-10-19"),  # Samvat 2074
    pd.Timestamp("2018-11-07"),  # Samvat 2075
    pd.Timestamp("2019-10-27"),  # Samvat 2076 (Sunday)
    pd.Timestamp("2020-11-14"),  # Samvat 2077 (Saturday)
    pd.Timestamp("2021-11-04"),  # Samvat 2078
    pd.Timestamp("2022-10-24"),  # Samvat 2079
    pd.Timestamp("2023-11-12"),  # Samvat 2080 (Sunday)
    pd.Timestamp("2024-11-01"),  # Samvat 2081
    pd.Timestamp("2025-10-21"),  # Samvat 2082
])

#: Other confirmed Saturday/Sunday live trading sessions outside Muhurat. Verified via
#: web search: NSE/BSE held a full live trading session on Saturday 2025-02-01 for the
#: Union Budget presentation (see e.g. business-standard.com, 2024-12-23 announcement).
SPECIAL_WEEKEND_SESSIONS: frozenset[pd.Timestamp] = frozenset([
    pd.Timestamp("2025-02-01"),  # Union Budget Saturday session
])

#: Must match the actual raw CSV stems in data/raw/yahoo/, not a Yahoo ticker spelling --
#: confirmed by listing the raw directory: NIFTY50.csv, NIFTY100.csv, INDIAVIX.csv (no "^").
#: The previous ("NIFTY50", "^CNX100", "^INDIAVIX") never matched NIFTY100.csv or
#: INDIAVIX.csv, so both were silently treated as ordinary stocks (run through
#: corporate-action adjustment) by any caller that trusts this constant to identify indices.
DEFAULT_INDEX_NAMES: tuple[str, ...] = ("NIFTY50", "NIFTY100", "INDIAVIX")


# --------------------------------------------------------------------------------------
# 1. Calendar Construction & Validation
# --------------------------------------------------------------------------------------

def build_calendar(
    raw_dir: Union[str, Path],
    index_names: Sequence[str] = DEFAULT_INDEX_NAMES,
    include_muhurat: bool = True,
) -> Tuple[pd.DatetimeIndex, Dict[str, Any]]:
    """Build master trading calendar as UNION of all stock trading dates.
    
    Fixes F06: Does not rely on a single index file (which can miss sessions).
    """
    raw_p = Path(raw_dir)
    all_dates: Set[pd.Timestamp] = set()
    stock_file_count = 0
    idx_set = set(index_names) | {f"^{name}" for name in index_names} | {name.lstrip("^") for name in index_names}

    for p in sorted(raw_p.glob("*.csv")):
        stem = p.stem
        # Skip index files when building stock calendar
        if stem in idx_set or stem.startswith("^") or stem == "NIFTY50":
            continue
        try:
            df = pd.read_csv(p, usecols=["Date"])
            if df.empty:
                continue
            dts = pd.to_datetime(df["Date"], errors="coerce").dropna().dt.normalize()
            all_dates.update(dts)
            stock_file_count += 1
        except Exception as e:
            log.warning("Could not read dates from %s: %s", p, e)

    if not all_dates:
        # Fallback if no stock files found: check all CSVs
        for p in sorted(raw_p.glob("*.csv")):
            try:
                df = pd.read_csv(p, usecols=["Date"])
                dts = pd.to_datetime(df["Date"], errors="coerce").dropna().dt.normalize()
                all_dates.update(dts)
            except Exception:
                pass

    if not include_muhurat:
        all_dates = all_dates - MUHURAT_SESSIONS

    sorted_dates = sorted(all_dates)
    cal = pd.DatetimeIndex(sorted_dates, name="Date")

    muhurat_count = sum(1 for d in cal if d in MUHURAT_SESSIONS)
    diagnostics = {
        "stock_files_scanned": stock_file_count,
        "total_sessions": len(cal),
        "first_session": str(cal[0].date()) if len(cal) else None,
        "last_session": str(cal[-1].date()) if len(cal) else None,
        "muhurat_included": include_muhurat,
        "muhurat_sessions_present": muhurat_count,
    }
    return cal, diagnostics


def validate_calendar(calendar: pd.DatetimeIndex) -> List[str]:
    """Validate calendar sanity. Returns list of problem strings (empty if clean).
    
    Bounds justification: NSE averages ~248-252 trading sessions per year.
    For ~11.75 years (2015-01 to 2026-10), expected length is ~2850-2950 sessions.
    Max holiday cluster in India is ~5 calendar days (e.g. Diwali / Holi + weekend).
    """
    problems: List[str] = []
    if len(calendar) == 0:
        return ["Calendar is empty"]

    if calendar.has_duplicates:
        problems.append(f"Calendar contains {calendar.duplicated().sum()} duplicate dates")

    if not calendar.is_monotonic_increasing:
        problems.append("Calendar is not monotonically increasing")

    # Weekend check: weekday >= 5 is Sat/Sun
    weekend_mask = calendar.weekday >= 5
    # Exception: Muhurat sessions can land on Sat/Sun
    non_muhurat_weekends = [d for d in calendar[weekend_mask]
                            if d not in MUHURAT_SESSIONS and d not in SPECIAL_WEEKEND_SESSIONS]
    if non_muhurat_weekends:
        problems.append(f"Calendar has {len(non_muhurat_weekends)} non-Muhurat weekend dates: {non_muhurat_weekends[:5]}")

    if calendar[0] > pd.Timestamp("2015-01-05"):
        problems.append(f"Calendar start date too late: {calendar[0].date()} (expected <= 2015-01-05)")

    if len(calendar) < 2800 or len(calendar) > 3050:
        problems.append(f"Calendar length {len(calendar)} outside plausible range [2800, 3050] for ~11.75 years")

    # Check for excessive gaps (> 6 calendar days)
    diffs = (calendar[1:] - calendar[:-1]).days
    max_gap_idx = np.argmax(diffs)
    if diffs[max_gap_idx] > 6:
        problems.append(f"Implausible gap of {diffs[max_gap_idx]} days between {calendar[max_gap_idx].date()} and {calendar[max_gap_idx+1].date()}")

    return problems


# --------------------------------------------------------------------------------------
# 2. Alignment & Coverage Accounting (Fixes F06, F07)
# --------------------------------------------------------------------------------------

def align_to_calendar(
    df: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    symbol: str,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Align one stock's OHLCV series to the master calendar.
    
    Fixes F07:
    - Never pads rows prior to the stock's first observed trading bar (no PreListing rows).
    - If a stock is missing a bar during its active trading lifetime, flags as NoData (genuine halt).
    - Returns dropped dates (if any) as dates_dropped_by_calendar_align.
    """
    if df.empty:
        raise ValueError(f"Cannot align empty DataFrame for symbol {symbol}")

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        if "Date" in out.columns:
            out["Date"] = pd.to_datetime(out["Date"]).dt.normalize()
            out = out.set_index("Date")
        else:
            raise ValueError(f"{symbol}: DataFrame must have a DatetimeIndex or 'Date' column")
    out.index = pd.DatetimeIndex(out.index).normalize()
    out = out.sort_index()

    first_bar_date = out.index[0]
    last_bar_date = out.index[-1]

    # Check for stock dates dropped by calendar
    stock_dates_set = set(out.index)
    cal_dates_set = set(calendar)
    dropped_dates = sorted(stock_dates_set - cal_dates_set)

    # Active calendar: only from first_bar_date to last calendar session
    # Truncate calendar to start at first_bar_date (Fixes F07 leading NaN padding)
    active_cal = calendar[calendar >= first_bar_date]
    if len(active_cal) == 0:
        active_cal = calendar[-1:]  # Safety fallback

    # Reindex onto active calendar
    aligned = out.reindex(active_cal)

    # Classify coverage explicitly
    # 1. PreListing: exactly 0 rows emitted (not present in aligned frame)
    # 2. NoData: calendar dates between first_bar_date and last_bar_date with NaN close
    in_life_mask = (aligned.index >= first_bar_date) & (aligned.index <= last_bar_date)
    aligned["NoData"] = in_life_mask & aligned["Close"].isna()

    # 3. PostDelisting: calendar dates strictly after last_bar_date
    aligned["PostDelisting"] = aligned.index > last_bar_date

    aligned["PreListing"] = False  # By design: 0 PreListing rows in output

    diag = {
        "symbol": symbol,
        "first_bar_date": str(first_bar_date.date()),
        "last_bar_date": str(last_bar_date.date()),
        "raw_bars": len(out),
        "aligned_bars": len(aligned),
        "no_data_days": int(aligned["NoData"].sum()),
        "post_delisting_days": int(aligned["PostDelisting"].sum()),
        "pre_listing_days_omitted": int((calendar < first_bar_date).sum()),
        "dates_dropped_by_calendar_align": [str(d.date()) for d in dropped_dates],
    }
    return aligned, diag


# --------------------------------------------------------------------------------------
# 3. Safe Flag Assignment (Fixes F11)
# --------------------------------------------------------------------------------------

def set_flag_safe(
    df: pd.DataFrame,
    dates: Sequence[Any],
    column: str,
    true_value: Any = 1,
    default_value: Any = 0,
) -> Tuple[pd.DataFrame, List[pd.Timestamp]]:
    """Safely set flag column using boolean mask. Never performs setitem-with-enlargement.
    
    Fixes F11: Avoids df.loc[missing_date] = 1 which appends unaligned NaN rows in pandas.
    Returns (modified_df, missing_dates_not_in_index).
    """
    out = df.copy()
    if column not in out.columns:
        out[column] = default_value

    parsed_dates = []
    missing_dates = []
    for d in dates:
        if pd.isna(d):
            continue
        ts = pd.to_datetime(d, errors="coerce")
        if pd.notna(ts):
            parsed_dates.append(pd.Timestamp(ts).normalize())
        else:
            missing_dates.append(d)

    idx_set = set(out.index)
    present_dates = [d for d in parsed_dates if d in idx_set]
    missing_dates.extend([d for d in parsed_dates if d not in idx_set])

    if present_dates:
        mask = out.index.isin(present_dates)
        out.loc[mask, column] = true_value

    return out, missing_dates


# --------------------------------------------------------------------------------------
# 4. Index Audit (Fixes F14)
# --------------------------------------------------------------------------------------

def audit_index_series(
    raw_dir: Union[str, Path],
    index_names: Sequence[str] = DEFAULT_INDEX_NAMES,
    calendar: Optional[pd.DatetimeIndex] = None,
) -> pd.DataFrame:
    """Audit index series files without cleaning or altering them.
    
    Reports row count, start/end dates, duplicates, NaNs, weekends, and calendar coverage.
    """
    raw_p = Path(raw_dir)
    records = []

    for name in index_names:
        # Search candidate filenames
        candidates = [
            raw_p / f"{name}.csv",
            raw_p / f"^{name}.csv",
            raw_p / f"{name.lstrip('^')}.csv",
        ]
        target = next((c for c in candidates if c.is_file()), None)
        if not target:
            records.append({
                "index_name": name,
                "file_found": False,
                "rows": 0,
                "first_date": None,
                "last_date": None,
                "duplicate_dates": 0,
                "nan_close_count": 0,
                "weekend_dates": 0,
                "missing_cal_dates": 0,
            })
            continue

        df = pd.read_csv(target)
        dts = pd.to_datetime(df["Date"], errors="coerce").dropna().dt.normalize()
        dup_count = int(dts.duplicated().sum())
        nan_close = int(df["Close"].isna().sum()) if "Close" in df.columns else -1
        weekend_count = int((dts.dt.weekday >= 5).sum())

        missing_cal = 0
        if calendar is not None:
            idx_date_set = set(dts)
            missing_cal = len([d for d in calendar if d not in idx_date_set])

        records.append({
            "index_name": name,
            "file_found": True,
            "rows": len(df),
            "first_date": str(dts.min().date()) if len(dts) else None,
            "last_date": str(dts.max().date()) if len(dts) else None,
            "duplicate_dates": dup_count,
            "nan_close_count": nan_close,
            "weekend_dates": weekend_count,
            "missing_cal_dates": missing_cal,
        })

    return pd.DataFrame(records)


# --------------------------------------------------------------------------------------
# 5. Sanity Checks: Detect ffill Damage
# --------------------------------------------------------------------------------------

def assert_no_ffill_damage(df: pd.DataFrame, max_identical_bars: int = 3) -> List[str]:
    """Detect runs of identical consecutive OHLC bars, the fingerprint of an ffill.
    
    An ffill of OHLC bars damages ATR calculations (ATR -> 0) and creates degenerate
    triple-barrier labels.
    """
    problems: List[str] = []
    cols = [c for c in ["Open", "High", "Low", "Close"] if c in df.columns]
    if len(cols) < 4:
        return problems

    identical = (
        (df["Open"] == df["Open"].shift(1)) &
        (df["High"] == df["High"].shift(1)) &
        (df["Low"] == df["Low"].shift(1)) &
        (df["Close"] == df["Close"].shift(1))
    )
    # Count consecutive runs
    run_length = 0
    run_start = None
    for date, is_ident in identical.items():
        if is_ident:
            if run_length == 0:
                run_start = date
            run_length += 1
            if run_length >= max_identical_bars:
                problems.append(f"Identical OHLC bar run of {run_length+1} sessions starting at {run_start} to {date}")
        else:
            run_length = 0
            run_start = None

    return problems


# ======================================================================================
# Self-test -- SYNTHETIC in-memory data only
# ======================================================================================

def _selftest() -> int:
    import tempfile
    passed = 0
    failed = 0

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"PASS  {name}")
        else:
            failed += 1
            print(f"FAIL  {name} -- {detail}")

    print("=" * 70)
    print("02c_calendar.py Self-Test (SYNTHETIC in-memory / temp files)")
    print("=" * 70)

    # 1. Calendar validation
    good_dates = pd.date_range("2015-01-01", periods=2900, freq="B")
    probs = validate_calendar(good_dates)
    check("validate_calendar accepts valid Business day range", len(probs) == 0, str(probs))

    bad_weekend = pd.DatetimeIndex(["2015-01-02", "2015-01-03", "2015-01-04"])  # Sat, Sun
    check("validate_calendar flags weekends", any("weekend" in p.lower() for p in validate_calendar(bad_weekend)))

    # 2. Alignment without pre-listing padding (F07)
    cal = pd.date_range("2015-01-01", "2015-01-10", freq="B")
    stock_dates = pd.date_range("2015-01-06", "2015-01-10", freq="B")  # Listed mid-window
    raw_stock = pd.DataFrame({
        "Open": 100.0, "High": 105.0, "Low": 95.0, "Close": 102.0, "Volume": 1000
    }, index=stock_dates)
    aligned, diag = align_to_calendar(raw_stock, cal, "NEWCO")

    check("aligned frame starts on first bar date (no leading NaN rows)", aligned.index[0] == pd.Timestamp("2015-01-06"))
    check("PreListing column is False for all emitted rows", not aligned["PreListing"].any())
    check("diagnostics records omitted pre-listing sessions", diag["pre_listing_days_omitted"] > 0)

    # 3. Safe flag setting (F11)
    df_flag = pd.DataFrame({"Close": [10.0, 20.0]}, index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    flagged, missing = set_flag_safe(df_flag, ["2020-01-02", "2020-01-99"], "Flag")
    check("set_flag_safe does not enlarge frame on missing date (F11)", len(flagged) == 2)
    check("set_flag_safe correctly flags present date", flagged.loc[pd.Timestamp("2020-01-02"), "Flag"] == 1)
    check("missing date reported", len(missing) == 1)

    # 4. ffill damage detection
    ffill_df = pd.DataFrame({
        "Open": [100.0, 100.0, 100.0, 100.0],
        "High": [105.0, 105.0, 105.0, 105.0],
        "Low": [95.0, 95.0, 95.0, 95.0],
        "Close": [100.0, 100.0, 100.0, 100.0]
    }, index=pd.date_range("2020-01-01", periods=4))
    damage = assert_no_ffill_damage(ffill_df, max_identical_bars=2)
    check("assert_no_ffill_damage flags runs of identical OHLC", len(damage) > 0)

    # 5. Union calendar from mock CSV directory (F06)
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        df1 = pd.DataFrame({"Date": ["2020-01-01", "2020-01-02"]})
        df1.to_csv(tdp / "SYM1.csv", index=False)
        df2 = pd.DataFrame({"Date": ["2020-01-02", "2020-01-03"]})
        df2.to_csv(tdp / "SYM2.csv", index=False)

        built_cal, d_diag = build_calendar(tdp, index_names=[])
        check("build_calendar takes UNION of dates across stocks (F06)", len(built_cal) == 3)
        check("built_cal has 2020-01-01, 2020-01-02, 2020-01-03",
              set(built_cal) == {pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03")})

    print("-" * 70)
    print(f"{passed} passed, {failed} failed")
    print("-" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
