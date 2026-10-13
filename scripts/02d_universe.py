#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02d_universe.py -- Universe selection, point-in-time eligibility, truncation,
event-window purging, and cross-fold embargoing.

Addresses findings:
- F05 (BLOCKER): Survivorship bias & holdout-only listings (VAML, ENRIN, TATACAP, TMCV).
  Gating symbols at first_bar + warmup + horizon; point_in_time_universe contract.
- F10 (HIGH): One opaque boolean conflated multiple exclusion causes.
  Replaced with an explicit enum `exclude_reason` and traceable `exclude_detail`.
- F15 (MEDIUM): Whole-stock exclusion lookahead & label window poisoning.
  Implements truncation at uncrossable boundaries and pre-event purge windows [e - horizon, e].
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
import pandas as pd

log = logging.getLogger("universe")

#: Frozen project parameters
HOLDOUT_START = pd.Timestamp("2025-04-01")
DEFAULT_HORIZON = 10
DEFAULT_WARMUP = 200

#: Allowed enum strings for exclude_reason (Fixes F10)
EXCLUDE_REASONS = frozenset({
    "",  # Eligible / included
    "unexplained_factor_step",
    "unadjusted_big_move",
    "manual_corporate_action",
    "insufficient_history",
    "holdout_only_listing",
    "demerger_child_overlaps_parent",
})

#: Known demerger children that overlap parent exposure without pre-holdout training history
DEMERGER_CHILDREN: frozenset[str] = frozenset({"VAML", "ENRIN", "TMCV"})


# --------------------------------------------------------------------------------------
# 1. Truncation and Purging (Fixes F15)
# --------------------------------------------------------------------------------------

def purge_windows(
    actions_df: pd.DataFrame,
    symbol: str,
    horizon: int = DEFAULT_HORIZON,
) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    """Compute label-poisoned sample date intervals [e - horizon sessions, e] to drop.
    
    Fixes F15: Any label spanning a corporate action artifact at date e produces
    a fabricated Down or Up return. We drop all sample dates whose forward window covers e.
    """
    if actions_df is None or actions_df.empty:
        return []

    sym_acts = actions_df.loc[
        (actions_df["symbol"].astype(str) == str(symbol)) &
        (actions_df["action_type"].isin({"split", "bonus", "demerger", "rights"})) &
        (actions_df["ex_date"].notna())
    ].copy()

    if sym_acts.empty:
        return []

    windows = []
    # Calendar days approx: horizon trading days is ~1.5 * horizon calendar days
    cal_delta = pd.Timedelta(days=int(np.ceil(horizon * 1.6)) + 2)
    for ex_date in sorted(pd.to_datetime(sym_acts["ex_date"]).dt.normalize().unique()):
        # Purge window: start is ex_date minus approximate horizon calendar days, end is ex_date
        start = ex_date - cal_delta
        windows.append((start, ex_date))

    return windows


def embargo_folds(
    fold_boundaries: Sequence[Tuple[pd.Timestamp, pd.Timestamp]],
    calendar: pd.DatetimeIndex,
    horizon: int = DEFAULT_HORIZON,
) -> List[Tuple[pd.Timestamp, pd.Timestamp]]:
    """Compute embargo intervals around walk-forward fold boundaries.
    
    Prevents a training label's forward horizon from peeking into the test fold,
    and a test fold's warmup from peeking across the boundary.
    """
    embargoes = []
    cal_series = pd.Series(np.arange(len(calendar)), index=calendar)

    for train_end, test_start in fold_boundaries:
        # Embargo horizon bars before and after boundary
        t_end = pd.Timestamp(train_end).normalize()
        if t_end in cal_series:
            pos = cal_series.loc[t_end]
            start_pos = max(0, pos - horizon + 1)
            end_pos = min(len(calendar) - 1, pos + horizon)
            embargoes.append((calendar[start_pos], calendar[end_pos]))
        else:
            embargoes.append((t_end - pd.Timedelta(days=horizon * 2), t_end + pd.Timedelta(days=horizon * 2)))

    return embargoes


# --------------------------------------------------------------------------------------
# 2. Universe Construction & Gating (Fixes F05, F10)
# --------------------------------------------------------------------------------------

def build_universe(
    summary_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    horizon: int = DEFAULT_HORIZON,
    warmup: int = DEFAULT_WARMUP,
    holdout_start: pd.Timestamp = HOLDOUT_START,
) -> pd.DataFrame:
    """Build universe eligibility table with explicit exclusion enums and truncation dates.
    
    Fixes:
    - F05: Flags holdout-only listings and insufficient history names.
    - F10: Emits single enum `exclude_reason` and detailed `exclude_detail`.
    - F15: Records `truncate_at` date for uncrossable demergers/actions.
    """
    rows = []
    cal_len = len(calendar)

    for _, row in summary_df.iterrows():
        sym = str(row["symbol"])
        first_bar = pd.Timestamp(row.get("first_bar_date", calendar[0])).normalize()
        last_bar = pd.Timestamp(row.get("last_bar_date", calendar[-1])).normalize()

        # Find session index in calendar for first bar
        pos = calendar.searchsorted(first_bar)
        eligible_pos = pos + warmup + horizon
        eligible_from = calendar[eligible_pos] if eligible_pos < cal_len else None

        # Pre-holdout sessions
        pre_holdout_mask = (calendar >= first_bar) & (calendar < holdout_start) & (calendar <= last_bar)
        pre_holdout_count = int(pre_holdout_mask.sum())

        # Total active sessions
        active_mask = (calendar >= first_bar) & (calendar <= last_bar)
        total_sessions = int(active_mask.sum())

        # Estimated labelled samples
        n_labelled_est = max(0, total_sessions - warmup - horizon)

        # Check for uncrossable actions (demergers without clean ratios, or forced truncations)
        truncate_at = None
        if actions_df is not None and not actions_df.empty:
            sym_acts = actions_df.loc[actions_df["symbol"] == sym]
            # Known uncrossable or demergers needing truncation
            uncrossable = sym_acts.loc[
                sym_acts["action_type"].isin({"demerger"}) &
                (sym_acts["ratio"].isna() | (sym_acts["confidence"] == "UNVERIFIED"))
            ]
            if not uncrossable.empty:
                first_uncrossable = uncrossable["ex_date"].min()
                truncate_at = pd.Timestamp(first_uncrossable).normalize()

        # Specific decision logic for exclusions
        exclude_reason = ""
        exclude_detail = ""

        if sym in DEMERGER_CHILDREN:
            exclude_reason = "demerger_child_overlaps_parent"
            exclude_detail = f"Demerger child entity; listed post-event with {total_sessions} bars; overlaps parent exposure"
        elif first_bar >= holdout_start:
            exclude_reason = "holdout_only_listing"
            exclude_detail = f"Listed on {first_bar.date()} after holdout start {holdout_start.date()}; 0 pre-holdout history"
        elif pre_holdout_count < (warmup + horizon):
            exclude_reason = "insufficient_history"
            exclude_detail = f"Only {pre_holdout_count} pre-holdout sessions (need {warmup + horizon} for warmup+horizon)"
        elif row.get("flagged_big_moves", 0) > 0 and row.get("unexplained_events", 0) > 0:
            exclude_reason = "unadjusted_big_move"
            exclude_detail = f"Unexplained moves: {row.get('flagged_big_moves')} big moves, {row.get('unexplained_events')} factor steps"

        rows.append({
            "symbol": sym,
            "first_bar_date": str(first_bar.date()),
            "last_bar_date": str(last_bar.date()),
            "eligible_from": str(eligible_from.date()) if eligible_from is not None else "",
            "truncate_at": str(truncate_at.date()) if truncate_at is not None else "",
            "exclude_reason": exclude_reason,
            "exclude_detail": exclude_detail,
            "total_sessions": total_sessions,
            "pre_holdout_sessions": pre_holdout_count,
            "n_labelled_samples_est": n_labelled_est,
        })

    out = pd.DataFrame(rows)
    return out.sort_values("symbol").reset_index(drop=True)


# --------------------------------------------------------------------------------------
# 3. Point-in-time Universe Selection Interface (Fixes F05)
# --------------------------------------------------------------------------------------

def point_in_time_universe(
    membership_panel: Optional[pd.DataFrame],
    as_of: pd.Timestamp,
) -> List[str]:
    """Retrieve universe constituents as of a specific point-in-time date.
    
    Fixes F05:
    Consumes a panel with columns (date, symbol, in_universe).
    If panel is None or absent, raises NotImplementedError noting that historical
    index circulars back to 2015 must be reconstructed before publication.
    """
    if membership_panel is None or (isinstance(membership_panel, pd.DataFrame) and membership_panel.empty):
        raise NotImplementedError(
            "Point-in-time membership panel is not yet reconstructed for 2015-2026. "
            "Using today's NIFTY 100 constituents embeds survivorship bias. "
            "No headline alpha may be published until point-in-time circulars are loaded."
        )

    as_of_dt = pd.Timestamp(as_of).normalize()
    sub = membership_panel.loc[
        (membership_panel["date"] == as_of_dt) &
        (membership_panel["in_universe"] == True)
    ]
    return sorted(sub["symbol"].astype(str).unique().tolist())


# ======================================================================================
# Self-test -- SYNTHETIC in-memory data only
# ======================================================================================

def _selftest() -> int:
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
    print("02d_universe.py Self-Test (SYNTHETIC in-memory)")
    print("=" * 70)

    # 1. Enum verification
    check("EXCLUDE_REASONS contains all required enums (F10)",
          {"insufficient_history", "holdout_only_listing", "demerger_child_overlaps_parent"}.issubset(EXCLUDE_REASONS))

    # 2. Purge window computation (F15)
    mock_acts = pd.DataFrame([
        {"symbol": "SYM", "ex_date": "2024-10-28", "action_type": "bonus", "ratio": 2.0}
    ])
    p_wins = purge_windows(mock_acts, "SYM", horizon=10)
    check("purge_windows returns interval ending on ex-date (F15)", len(p_wins) == 1 and p_wins[0][1] == pd.Timestamp("2024-10-28"))
    check("purge_window start precedes ex-date by horizon span", p_wins[0][0] < pd.Timestamp("2024-10-28"))

    # 3. Gating and exclusion reasons (F05, F10)
    cal = pd.date_range("2015-01-01", "2026-10-01", freq="B")
    mock_summary = pd.DataFrame([
        {"symbol": "FULLCO", "first_bar_date": "2015-01-01", "last_bar_date": "2026-10-01"},
        {"symbol": "VAML", "first_bar_date": "2026-06-01", "last_bar_date": "2026-10-01"},  # Demerger child
        {"symbol": "LATECO", "first_bar_date": "2025-05-01", "last_bar_date": "2026-10-01"},  # Holdout only
        {"symbol": "SHORTCO", "first_bar_date": "2025-02-01", "last_bar_date": "2026-10-01"}, # Insufficient pre-holdout (<210 sessions)
    ])
    u_df = build_universe(mock_summary, None, cal)

    row_vaml = u_df.loc[u_df["symbol"] == "VAML"].iloc[0]
    check("VAML flagged as demerger_child_overlaps_parent (F05)", row_vaml["exclude_reason"] == "demerger_child_overlaps_parent")

    row_late = u_df.loc[u_df["symbol"] == "LATECO"].iloc[0]
    check("LATECO flagged as holdout_only_listing (F05)", row_late["exclude_reason"] == "holdout_only_listing")

    row_short = u_df.loc[u_df["symbol"] == "SHORTCO"].iloc[0]
    check("SHORTCO flagged as insufficient_history (F05)", row_short["exclude_reason"] == "insufficient_history")

    row_full = u_df.loc[u_df["symbol"] == "FULLCO"].iloc[0]
    check("FULLCO eligible without exclusion reason", row_full["exclude_reason"] == "")

    # 4. Point-in-time universe contract (F05)
    try:
        point_in_time_universe(None, pd.Timestamp("2020-01-01"))
        check("point_in_time_universe raises NotImplementedError when panel absent", False)
    except NotImplementedError:
        check("point_in_time_universe raises NotImplementedError when panel absent (F05)", True)

    # 5. Embargo folds
    embargoes = embargo_folds([(pd.Timestamp("2020-01-10"), pd.Timestamp("2020-01-13"))], cal, horizon=5)
    check("embargo_folds returns non-empty list of intervals", len(embargoes) == 1)

    print("-" * 70)
    print(f"{passed} passed, {failed} failed")
    print("-" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
