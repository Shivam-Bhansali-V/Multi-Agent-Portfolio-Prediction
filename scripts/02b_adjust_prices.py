#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02b_adjust_prices.py -- rebuild a correct adjusted OHLCV series from an explicit
corporate-action table.

This module owns ONE job: turn raw yfinance OHLCV (``auto_adjust=False``) plus the
authoritative action table written by ``02a_build_corp_actions.py`` into a
**structurally adjusted** price/volume series, plus a **separate dated dividend cash
series**.  It does not build the action table, the trading calendar, the universe or
exclusion logic, or the validation harness.

======================================================================================
WHAT IS BEING FIXED
======================================================================================

F03 (BLOCKER) -- the previous pipeline computed ``Factor = Adj Close / Close`` and
    multiplied OHLC by it.  On these NSE series that factor captures CASH DIVIDENDS
    ONLY.  Splits are (per the audit's *inference*) already folded into ``Close``
    itself, and bonus issues / demergers are adjusted NOWHERE, so they sit in the raw
    series as fake one-day crashes.  This module NEVER looks at ``Adj Close / Close``
    to infer an action.  Every structural divisor comes from the action table.

F08 (HIGH) -- labels/indicators were computed on a dividend-REINVESTED series while
    fills used raw prices, a unit mismatch worth the same order as the whole 0.35%
    cost budget on high-yield names (COALINDIA PFC BPCL HINDZINC VEDL).  This module
    emits exactly ONE price series -- structural-only, dividends EXCLUDED -- and that
    single series is intended for ATR, indicators, barrier levels, barrier-touch tests
    AND P&L.  Dividends are never folded into a price.  They are exposed as a separate
    dated per-share cash column (``DividendCash``) for the P&L to credit on its own.
    There is deliberately no dividend-reinvested price column in the output.

F12 (MEDIUM) -- volume was passed through raw, so every share-count event left a
    permanent step that broke OBV, volume z-scores, turnover and Amihud illiquidity.
    This module emits ``AdjVolume`` restated into current share-count terms.

======================================================================================
THE TWO SERIES, NAMED UNAMBIGUOUSLY
======================================================================================

* ``AdjOpen AdjHigh AdjLow AdjClose``  -- STRUCTURAL-ONLY adjusted prices.  Splits,
  bonuses, demergers (and rights, if ever present) removed; dividends NOT in here.
  ``StructAdjOpen/High/Low/Close`` are emitted as exact-duplicate aliases so that a
  consumer reading only the column name cannot mistake these for a total-return
  series.  Use these for everything: features, ATR, barriers, touch tests, fills.
* ``DividendCash`` -- per-share cash, in the SAME units as the ``Adj*`` prices, dated
  on the ex-date bar.  Zero on every other bar.  Credit it in the P&L separately.
* The input ``Adj Close`` column is passed through untouched for provenance ONLY.
  Do not build features from it: it is Yahoo's retro-adjusted dividend-reinvested
  series and is not reproducible across re-downloads.

======================================================================================
RATIO CONVENTION (fixed upstream by 02a -- not redefined here)
======================================================================================

``ratio`` = R = P_cum / P_ex: last traded price on the session BEFORE the ex-date
divided by the adjusted base price from the ex-date onward.  R >= 1 for any
value-diluting action.  r-for-1 split -> R = r.  a:b bonus -> R = (a+b)/b, so
1:1 -> 2, 1:2 -> 1.5, 2:1 -> 3, 1:4 -> 1.25.  Demerger where the parent retains
fraction f of pre-event value -> R = 1/f.  Blank for ``dividend``.

CONSUMER RULE, honored exactly:

    adjusted(t) = raw(t) / prod{ R_i : ex_date_i > t }        # STRICTLY AFTER

So the ex-date bar itself is UNTOUCHED and the session before it is scaled.  A
one-session error here mislabels a -50% bar, so the boundary is unit-tested below.

When an ``ex_date`` is not itself a bar in the price index (holiday, missing bar), the
divisor is anchored at the first bar with ``Date >= ex_date``.  That reproduces the
strictly-after rule exactly, because no bar exists in the gap.

Actions whose ex_date falls AFTER the last bar of the supplied series are excluded
from the divisor: no in-sample bar is post-event, so applying them would only rescale
the whole series and make its levels differ from the raw tail for no benefit.  They
are reported by ``pending_future_actions``.

======================================================================================
VOLUME DIRECTION (explicit, and unit-tested)
======================================================================================

A split or a bonus INCREASES the share count by factor R.  Volumes printed BEFORE the
ex-date are quoted in the OLD (smaller) share count, so to restate them into current,
post-event share terms they must be MULTIPLIED:

    AdjVolume(t) = Volume(t) * prod{ R_i : ex_date_i > t, i changes share count }

i.e. the same cumulative product as the price divisor, but MULTIPLYING rather than
dividing.  Pre-event volume therefore goes UP, which is the only direction that
removes the step.

Only ``split`` and ``bonus`` change the parent's share count.  A ``demerger`` does
NOT: holders keep their existing shares and additionally receive shares of the new
entity, so the parent's share count is unchanged and the demerger R must NOT enter
the volume ratio even though it does enter the price divisor.  ``rights`` issues do
change the share count, but under this table's convention their R is a *price*
dilution factor which is not equal to the share-count ratio, so rights are excluded
from the volume ratio and flagged (see LIMITATIONS).

======================================================================================
AUTO PREFOLDED-SPLIT DETECTION (the mechanism that settles F03 empirically)
======================================================================================

The audit's claim that Yahoo pre-folds splits into ``Close`` on these NSE series is an
INFERENCE, not a confirmed diagnostic.  This module is written to be correct either
way.  ``detect_prefolded_splits`` measures the actual raw-Close move across each split
ex-date and tests two hypotheses per ex-date:

    observed  = Close(prev bar) / Close(anchor bar)
    H_NOT_FOLDED : observed ~ R_all          (the full same-day composite R)
    H_PREFOLDED  : observed ~ R_all / R_split(same day)

Hypotheses are per ex-DATE, not per row, because same-day actions compound: on
BAJAJFINSV 2022-09-13 a 1:5 split (R=5) and a 1:1 bonus (R=2) share the ex-date, so
R_all = 10.  If the raw series shows a ~10x reset the split is not folded; if it shows
a ~2x reset (bonus only) the split is folded and only the bonus divisor must be
applied; if it shows no move at all, both are folded.

``build_adjusted(split_policy=...)`` takes ``"auto"`` (default), ``"always"`` or
``"never"``.  Under ``"auto"`` a split's divisor is applied only where the evidence
says it is not already folded into ``Close``.  Bonuses and demergers are always
applied, because the audit found them adjusted nowhere and no plausible data source
folds a bonus into ``Close`` while leaving the price break visible.

Evidence threshold: a hypothesis matches when the observed ratio is within
``prefold_tol`` (default 0.10, i.e. +/-10%) of its expectation in relative terms, and
the two hypotheses must themselves differ by at least ``prefold_margin`` (default
0.25, i.e. 25%) to be distinguishable.  10% is chosen because the signal being
detected is enormous relative to noise: the smallest plausible split R is 2, a 100%
separation, while an ordinary single-session move on a NIFTY100 name is well inside
10%.  If neither or both hypotheses match, the verdict is ``AMBIGUOUS``, the
log-closer hypothesis is used, and every affected row is flagged
``AMBIGUOUS_PREFOLD`` in ``AdjQuality`` so a consumer can drop it.

======================================================================================
DATA QUALITY SURFACED TO CONSUMERS
======================================================================================

* BLANK / UNUSABLE RATIO (known cases: ABB 2019-12-20, MOTHERSON 2022-01-14).  A
  series cannot be rescaled across an action whose ratio is unknown.  This module does
  NOT guess a ratio and does NOT silently skip the action.  The ex-date becomes an
  UNCROSSABLE BOUNDARY: ``uncrossable_boundaries()`` returns it, every bar before it
  is flagged ``UNCROSSABLE_BEFORE``, and ``SegmentId`` increments at the boundary so
  the universe/labelling module -- which owns truncation and purging -- can keep only
  the latest segment or purge windows that straddle it.  Truncation is NOT done here.
* RATIO_APPROX rows are APPLIED (an approximate divisor beats a fake 60% crash), but
  the uncertainty propagates: affected bars are flagged ``APPROX_RATIO`` and
  ``approx_ratio_dates()`` lists the ex-dates.
* ``confidence == DERIVED_FROM_RECORD_DATE`` means the ex-date itself was inferred.
  Those bars are flagged ``DERIVED_EX_DATE`` within +/-1 bar of the anchor, because a
  one-session date error is exactly the failure mode that mislabels a big bar.

======================================================================================
LIMITATIONS AND UNRESOLVED ITEMS (read before publishing)
======================================================================================

1. Yahoo's ``Adj Close`` is RETRO-ADJUSTED: it is recomputed on every download, so any
   quantity derived from it is not reproducible across re-downloads and must not be
   part of a published, reproducible pipeline.  It is used here only by the OPTIONAL
   dividend fallback (``dividend_source="adjclose"`` / ``"auto"``), never to infer a
   structural action.  The reproducible path is ``dividend_source="actions"``.
2. Whether Yahoo also pre-folds splits into ``Volume`` on these series is unconfirmed.
   The default assumption is that volume follows price: a split judged prefolded in
   ``Close`` is assumed prefolded in ``Volume`` too and is skipped in the volume ratio.
   ``volume_follows_split_policy=False`` forces the opposite (always apply splits to
   volume).  This assumption is a legitimate target for review.
3. ``rights`` rows are excluded from the volume ratio (see VOLUME DIRECTION).  The
   table currently contains none; if any appear, their share-count effect is unhandled
   and is reported by ``unhandled_volume_actions()``.
4. A cash dividend sharing its ex-date with a structural action is credited using the
   cum-date divisor (the mathematically consistent choice, derived below) but the
   per-share basis of such a dividend is genuinely ambiguous in the source data; those
   rows are flagged ``DIVIDEND_ON_STRUCTURAL_DATE``.
5. No real price data was available while writing this module.  Every test below is
   SYNTHETIC.  Nothing here has been checked against the user's actual NSE series.

Dividend cash scaling, derived (why ``CumDivisor`` at the CUM bar, not the ex bar):
let C(t) be the divisor at bar t and A(t) = raw(t)/C(t).  For an action with ex-date t
and share multiplier R_t we have C(t-1) = R_t*C(t).  A holder of one real share at
t-1 ends with R_t shares worth raw(t) each plus cash D, so the real total return is
(R_t*raw(t) + D)/raw(t-1) - 1.  The adjusted price leg already reproduces
A(t)/A(t-1) = R_t*raw(t)/raw(t-1), so the cash leg must satisfy
cash_adj/A(t-1) = D/raw(t-1), giving cash_adj = D / C(t-1).  Hence the cum-date
divisor.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

# ======================================================================================
# Paths and constants
# ======================================================================================

ROOT = Path(__file__).resolve().parents[1]

ACTIONS_REL_PATH = Path("data") / "reference" / "corp_actions.csv"

ACTION_COLUMNS = [
    "symbol", "ex_date", "action_type", "ratio", "dividend_amount",
    "source", "source_url", "confidence",
]

#: Action types that dilute per-share value and therefore enter the PRICE divisor.
STRUCTURAL_TYPES = ("split", "bonus", "demerger", "rights")

#: Action types that change the parent's SHARE COUNT and therefore enter the volume
#: ratio.  Demergers do not (holders keep their shares).  Rights do, but their R is a
#: price factor under this convention, so they are excluded and reported instead.
SHARE_COUNT_TYPES = ("split", "bonus")

#: Token used by 02a to mark a verified ex-date with an approximate ratio.
APPROX_TOKEN = "RATIO_APPROX"

#: AdjQuality tokens.
Q_OK = "OK"
Q_APPROX = "APPROX_RATIO"
Q_AMBIG = "AMBIGUOUS_PREFOLD"
Q_UNCROSSABLE = "UNCROSSABLE_BEFORE"
Q_DERIVED_DATE = "DERIVED_EX_DATE"
Q_DIV_ON_STRUCT = "DIVIDEND_ON_STRUCTURAL_DATE"

#: Default evidence thresholds for the prefolded-split detector.  See module docstring.
DEFAULT_PREFOLD_TOL = 0.10
DEFAULT_PREFOLD_MARGIN = 0.25

#: Sanity bounds for the optional Adj Close dividend fallback.
_MAX_IMPLIED_YIELD = 0.25
_MIN_IMPLIED_YIELD = 1e-4


# ======================================================================================
# Loading / normalising the action table
# ======================================================================================

def load_actions(root: Path | str = ROOT) -> pd.DataFrame:
    """Read ``<root>/data/reference/corp_actions.csv`` and normalise it.

    Reads as strings and coerces explicitly so that a blank ``ratio`` survives as NaN
    rather than being silently turned into something else by pandas type inference.
    """
    path = Path(root) / ACTIONS_REL_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run 02a_build_corp_actions.py (or call its build()) first."
        )
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    raw = raw.replace({"": None})
    return normalise_actions(raw)


def normalise_actions(actions_df: pd.DataFrame) -> pd.DataFrame:
    """Coerce an action table (from disk or in memory) into canonical dtypes.

    Accepts ``ex_date`` as string or Timestamp and ``ratio`` as string or float, so the
    module works whether it is handed a freshly parsed CSV or 02a's validated frame.
    """
    if actions_df is None:
        return pd.DataFrame(columns=ACTION_COLUMNS)
    df = pd.DataFrame(actions_df).copy()
    for col in ACTION_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df["symbol"] = df["symbol"].astype("string").str.strip()
    df["action_type"] = df["action_type"].astype("string").str.strip().str.lower()
    df["ex_date"] = pd.to_datetime(df["ex_date"], errors="coerce").dt.normalize()
    df["ratio"] = pd.to_numeric(df["ratio"], errors="coerce").astype("float64")
    df["dividend_amount"] = pd.to_numeric(df["dividend_amount"], errors="coerce").astype("float64")
    for col in ("source", "source_url", "confidence"):
        df[col] = df[col].astype("string").fillna("")
    df["confidence"] = df["confidence"].str.strip().str.upper()
    return df[ACTION_COLUMNS].sort_values(
        ["symbol", "ex_date", "action_type"], kind="mergesort"
    ).reset_index(drop=True)


def actions_for_symbol(actions_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalised rows for one symbol, sorted by ex_date then action_type."""
    df = normalise_actions(actions_df)
    out = df.loc[df["symbol"].astype(str) == str(symbol)].copy()
    return out.sort_values(["ex_date", "action_type"], kind="mergesort").reset_index(drop=True)


def _is_usable_ratio(value) -> bool:
    """A ratio is usable iff it is finite and >= 1 (the convention's diluting range).

    A missing, non-finite, zero/negative or sub-1 ratio is NOT silently repaired; it
    makes the ex-date an uncrossable boundary.
    """
    try:
        r = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(r):
        return False
    return r >= 1.0


def _is_approx(row) -> bool:
    src = str(row.get("source") or "")
    return APPROX_TOKEN in src


def uncrossable_boundaries(actions_df: pd.DataFrame, symbol: str) -> List[pd.Timestamp]:
    """Ex-dates this module CANNOT rescale across, because the ratio is unusable.

    Covers blank ratios (ABB 2019-12-20, MOTHERSON 2022-01-14 are the known cases),
    non-finite ratios, and ratios that violate the R >= 1 dilution convention.  The
    action is neither guessed nor skipped: the caller must treat the returned dates as
    hard boundaries and handle truncation/purging itself (this module does not).

    Returns a sorted list of unique normalised ``pd.Timestamp``.
    """
    acts = actions_for_symbol(actions_df, symbol)
    if acts.empty:
        return []
    mask = acts["action_type"].isin(STRUCTURAL_TYPES) & ~acts["ratio"].map(_is_usable_ratio)
    dates = acts.loc[mask & acts["ex_date"].notna(), "ex_date"]
    return sorted(pd.Series(pd.unique(dates)).tolist())


def approx_ratio_dates(actions_df: pd.DataFrame, symbol: str) -> List[pd.Timestamp]:
    """Ex-dates applied with an APPROXIMATE ratio (``EX_DATE_VERIFIED;RATIO_APPROX``).

    These ARE applied; the uncertainty is propagated via ``AdjQuality == APPROX_RATIO``.
    Returns a sorted list of unique normalised ``pd.Timestamp``.
    """
    acts = actions_for_symbol(actions_df, symbol)
    if acts.empty:
        return []
    mask = (
        acts["action_type"].isin(STRUCTURAL_TYPES)
        & acts["ratio"].map(_is_usable_ratio)
        & acts.apply(_is_approx, axis=1)
    )
    dates = acts.loc[mask & acts["ex_date"].notna(), "ex_date"]
    return sorted(pd.Series(pd.unique(dates)).tolist())


def derived_ex_date_dates(actions_df: pd.DataFrame, symbol: str) -> List[pd.Timestamp]:
    """Ex-dates whose DATE was inferred (``confidence == DERIVED_FROM_RECORD_DATE``)."""
    acts = actions_for_symbol(actions_df, symbol)
    if acts.empty:
        return []
    mask = (
        acts["action_type"].isin(STRUCTURAL_TYPES)
        & (acts["confidence"] == "DERIVED_FROM_RECORD_DATE")
    )
    dates = acts.loc[mask & acts["ex_date"].notna(), "ex_date"]
    return sorted(pd.Series(pd.unique(dates)).tolist())


def unhandled_volume_actions(actions_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Actions that change the share count but whose volume effect is NOT modelled.

    Currently only ``rights`` (see module LIMITATIONS note 3).  Returned so a caller can
    fail loudly rather than trust a silently wrong volume series.
    """
    acts = actions_for_symbol(actions_df, symbol)
    if acts.empty:
        return acts
    return acts.loc[acts["action_type"] == "rights"].reset_index(drop=True)


# ======================================================================================
# Raw frame normalisation
# ======================================================================================

_REQUIRED_RAW = ("Open", "High", "Low", "Close", "Volume")


def _normalise_raw(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise one symbol's raw OHLCV frame.

    Expects a Date index (or a ``Date`` column) and columns Open/High/Low/Close/Volume,
    with ``Adj Close`` optional.  Returns a copy with a sorted, normalised
    ``DatetimeIndex`` named ``Date`` and float64 price/volume columns.
    """
    if raw_df is None or len(raw_df) == 0:
        raise ValueError("raw_df is empty; nothing to adjust.")
    df = pd.DataFrame(raw_df).copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df = df.set_index("Date")
        else:
            raise ValueError("raw_df needs a DatetimeIndex or a 'Date' column.")
    df.index = pd.to_datetime(df.index).normalize()
    df.index.name = "Date"
    missing = [c for c in _REQUIRED_RAW if c not in df.columns]
    if missing:
        raise ValueError(f"raw_df missing required column(s): {missing}")
    if df.index.has_duplicates:
        raise ValueError("raw_df has duplicate dates; de-duplicate upstream.")
    df = df.sort_index()
    for col in _REQUIRED_RAW:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    if "Adj Close" in df.columns:
        df["Adj Close"] = pd.to_numeric(df["Adj Close"], errors="coerce").astype("float64")
    return df


def _anchor(index: pd.DatetimeIndex, ex_date: pd.Timestamp) -> Optional[pd.Timestamp]:
    """First bar with ``Date >= ex_date``; None if the action is after the last bar.

    Anchoring here is what makes ``adjusted(t) = raw(t)/prod{R : ex > t}`` exact even
    when the ex-date is not itself a trading bar: bars at or after the anchor are
    untouched, bars before it are divided, and no bar exists in between.
    """
    pos = index.searchsorted(pd.Timestamp(ex_date).normalize(), side="left")
    if pos >= len(index):
        return None
    return index[pos]


def pending_future_actions(raw_df: pd.DataFrame, actions_df: pd.DataFrame,
                           symbol: str) -> pd.DataFrame:
    """Structural actions whose ex_date is after the last bar, hence not applied."""
    df = _normalise_raw(raw_df)
    acts = actions_for_symbol(actions_df, symbol)
    if acts.empty:
        return acts
    last = df.index[-1]
    mask = acts["action_type"].isin(STRUCTURAL_TYPES) & (acts["ex_date"] > last)
    return acts.loc[mask].reset_index(drop=True)


# ======================================================================================
# Prefolded-split detection
# ======================================================================================

_VERDICTS = ("NOT_FOLDED", "PREFOLDED", "AMBIGUOUS", "INSUFFICIENT_DATA",
             "NOT_DISTINGUISHABLE")

DETECT_COLUMNS = [
    "symbol", "ex_date", "anchor_date", "prev_date", "action_type", "ratio",
    "R_all_same_day", "R_split_same_day", "R_if_split_prefolded",
    "observed_ratio", "rel_err_not_folded", "rel_err_prefolded",
    "verdict", "apply_divisor",
]


def detect_prefolded_splits(
    raw_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    symbol: str,
    tol: float = DEFAULT_PREFOLD_TOL,
    margin: float = DEFAULT_PREFOLD_MARGIN,
    include_all_types: bool = False,
) -> pd.DataFrame:
    """Measure the raw-Close move across each split ex-date and judge whether the split
    is ALREADY folded into ``Close``.

    This is the mechanism that empirically settles the audit's unconfirmed F03
    inference.  For each ex-DATE (not row -- same-day actions compound) it compares

        observed = Close(prev bar) / Close(anchor bar)

    against ``R_all`` (nothing folded) and ``R_all / R_split`` (the day's splits folded,
    the day's bonuses/demergers not).  A hypothesis matches when its relative error is
    within ``tol``; the two must differ by at least ``margin`` to be distinguishable.

    ``verdict`` is one of NOT_FOLDED, PREFOLDED, AMBIGUOUS (neither or both matched --
    the log-closer hypothesis is used and the rows are flagged), INSUFFICIENT_DATA (no
    usable bar before the anchor, or the action is outside the series), or
    NOT_DISTINGUISHABLE (the day has no usable split, so the question does not arise).

    ``apply_divisor`` is what ``split_policy="auto"`` would do with that row.
    Rows with an unusable ratio are excluded -- they are uncrossable boundaries, not a
    detection problem.

    Returns a DataFrame with columns ``DETECT_COLUMNS`` (empty frame if nothing to test).
    """
    df = _normalise_raw(raw_df)
    acts = actions_for_symbol(actions_df, symbol)
    out: List[dict] = []
    if acts.empty:
        return pd.DataFrame(out, columns=DETECT_COLUMNS)

    usable = acts.loc[
        acts["action_type"].isin(STRUCTURAL_TYPES)
        & acts["ratio"].map(_is_usable_ratio)
        & acts["ex_date"].notna()
    ].copy()
    if usable.empty:
        return pd.DataFrame(out, columns=DETECT_COLUMNS)

    index = df.index
    close = df["Close"]

    for ex_date, grp in usable.groupby("ex_date", sort=True):
        r_all = float(np.prod(grp["ratio"].to_numpy(dtype="float64")))
        split_mask = grp["action_type"] == "split"
        r_split = float(np.prod(grp.loc[split_mask, "ratio"].to_numpy(dtype="float64"))) \
            if split_mask.any() else 1.0
        r_prefolded = r_all / r_split

        anchor = _anchor(index, ex_date)
        prev_date = None
        observed = np.nan
        if anchor is not None:
            pos = index.get_loc(anchor)
            if pos > 0:
                prev_date = index[pos - 1]
                c_prev, c_anchor = close.iloc[pos - 1], close.iloc[pos]
                if np.isfinite(c_prev) and np.isfinite(c_anchor) and c_anchor > 0:
                    observed = float(c_prev / c_anchor)

        if not np.isfinite(observed) or observed <= 0:
            verdict = "INSUFFICIENT_DATA"
            err_nf = err_pf = np.nan
        elif not split_mask.any() or abs(r_split - 1.0) < 1e-12:
            verdict = "NOT_DISTINGUISHABLE"
            err_nf = abs(observed - r_all) / r_all
            err_pf = err_nf
        else:
            err_nf = abs(observed - r_all) / r_all
            err_pf = abs(observed - r_prefolded) / r_prefolded
            separation = abs(r_all - r_prefolded) / min(r_all, r_prefolded)
            if separation < margin:
                verdict = "NOT_DISTINGUISHABLE"
            else:
                hit_nf = err_nf <= tol
                hit_pf = err_pf <= tol
                if hit_nf and not hit_pf:
                    verdict = "NOT_FOLDED"
                elif hit_pf and not hit_nf:
                    verdict = "PREFOLDED"
                else:
                    verdict = "AMBIGUOUS"

        # Log-space tie-break, used for AMBIGUOUS and as the auto decision.
        if np.isfinite(observed) and observed > 0:
            d_nf = abs(math.log(observed) - math.log(r_all))
            d_pf = abs(math.log(observed) - math.log(r_prefolded))
            closer_not_folded = d_nf <= d_pf
        else:
            closer_not_folded = True  # no evidence -> keep the action (see auto policy)

        for _, row in grp.iterrows():
            is_split = row["action_type"] == "split"
            if verdict == "NOT_FOLDED":
                apply_divisor = True
            elif verdict == "PREFOLDED":
                apply_divisor = not is_split
            elif verdict in ("INSUFFICIENT_DATA", "NOT_DISTINGUISHABLE"):
                apply_divisor = True
            else:  # AMBIGUOUS
                apply_divisor = True if closer_not_folded else (not is_split)
            if not include_all_types and not is_split:
                continue
            out.append({
                "symbol": symbol,
                "ex_date": ex_date,
                "anchor_date": anchor,
                "prev_date": prev_date,
                "action_type": str(row["action_type"]),
                "ratio": float(row["ratio"]),
                "R_all_same_day": r_all,
                "R_split_same_day": r_split,
                "R_if_split_prefolded": r_prefolded,
                "observed_ratio": observed,
                "rel_err_not_folded": err_nf,
                "rel_err_prefolded": err_pf,
                "verdict": verdict,
                "apply_divisor": bool(apply_divisor),
            })

    res = pd.DataFrame(out, columns=DETECT_COLUMNS)
    if not res.empty:
        res = res.sort_values(["ex_date", "action_type"], kind="mergesort").reset_index(drop=True)
    return res


# ======================================================================================
# Divisor construction
# ======================================================================================

def _validate_split_policy(split_policy: str) -> None:
    if split_policy not in ("auto", "always", "never"):
        raise ValueError(
            f"split_policy must be one of 'auto', 'always', 'never'; got {split_policy!r}."
        )


def _applied_actions(df: pd.DataFrame, acts: pd.DataFrame, symbol: str,
                     split_policy: str, tol: float, margin: float):
    """Decide which structural rows get applied, and gather the quality date sets.

    Returns ``(applied, ambiguous_dates, detect)`` where ``applied`` is a frame of rows
    with an in-sample anchor and a usable ratio that the policy says to apply.
    """
    _validate_split_policy(split_policy)

    detect = detect_prefolded_splits(df, acts, symbol, tol=tol, margin=margin,
                                     include_all_types=True)

    structural = acts.loc[
        acts["action_type"].isin(STRUCTURAL_TYPES)
        & acts["ratio"].map(_is_usable_ratio)
        & acts["ex_date"].notna()
    ].copy()

    last = df.index[-1]
    structural = structural.loc[structural["ex_date"] <= last].copy()

    ambiguous_dates: List[pd.Timestamp] = []
    if not detect.empty:
        ambiguous_dates = sorted(pd.Series(pd.unique(
            detect.loc[detect["verdict"] == "AMBIGUOUS", "ex_date"]
        )).tolist())

    if structural.empty:
        structural["apply"] = pd.Series(dtype=bool)
        return structural, ambiguous_dates, detect

    if split_policy == "always":
        structural["apply"] = True
    elif split_policy == "never":
        structural["apply"] = structural["action_type"] != "split"
    else:  # auto -- splits gated by the detector, everything else always applied
        auto = {}
        if not detect.empty:
            for _, r in detect.iterrows():
                auto[(r["ex_date"], r["action_type"], float(r["ratio"]))] = bool(r["apply_divisor"])
        structural["apply"] = [
            auto.get((row["ex_date"], row["action_type"], float(row["ratio"])), True)
            if row["action_type"] == "split" else True
            for _, row in structural.iterrows()
        ]

    return structural.loc[structural["apply"]].copy(), ambiguous_dates, detect


def _reverse_cumprod_strictly_after(index: pd.DatetimeIndex,
                                    per_date_factor: pd.Series) -> pd.Series:
    """prod of factors at dates STRICTLY AFTER each bar.

    ``per_date_factor`` is indexed by anchor date.  Taking the reverse cumulative
    product gives the product over ``d >= t``; dividing out the bar's own factor gives
    ``d > t``, which is the contract's strictly-after rule -- so the ex-date bar is
    untouched and the bar before it is scaled.
    """
    f = pd.Series(1.0, index=index, dtype="float64")
    for d, v in per_date_factor.items():
        f.loc[d] *= float(v)
    incl = f.iloc[::-1].cumprod().iloc[::-1]
    return incl / f


def structural_divisors(raw_df: pd.DataFrame, actions_df: pd.DataFrame, symbol: str,
                        split_policy: str = "auto",
                        tol: float = DEFAULT_PREFOLD_TOL,
                        margin: float = DEFAULT_PREFOLD_MARGIN,
                        volume_follows_split_policy: bool = True):
    """Return ``(CumDivisor, CumShareRatio, applied, ambiguous_dates, detect)``.

    ``CumDivisor`` divides prices; ``CumShareRatio`` multiplies volume.  Both are the
    strictly-after cumulative product of R, over the price-diluting set and the
    share-count-changing set respectively.
    """
    _validate_split_policy(split_policy)
    df = _normalise_raw(raw_df)
    acts = actions_for_symbol(actions_df, symbol)
    index = df.index

    if acts.empty:
        ones = pd.Series(1.0, index=index, dtype="float64")
        return ones, ones.copy(), acts.assign(apply=pd.Series(dtype=bool)), [], \
            pd.DataFrame(columns=DETECT_COLUMNS)

    applied, ambiguous_dates, detect = _applied_actions(
        df, acts, symbol, split_policy, tol, margin
    )

    price_factor: dict = {}
    share_factor: dict = {}
    for _, row in applied.iterrows():
        anchor = _anchor(index, row["ex_date"])
        if anchor is None:
            continue
        r = float(row["ratio"])
        price_factor[anchor] = price_factor.get(anchor, 1.0) * r
        if row["action_type"] in SHARE_COUNT_TYPES:
            share_factor[anchor] = share_factor.get(anchor, 1.0) * r

    # Volume may diverge from price policy only for splits (see LIMITATIONS note 2).
    if not volume_follows_split_policy:
        skipped = acts.loc[
            (acts["action_type"] == "split")
            & acts["ratio"].map(_is_usable_ratio)
            & acts["ex_date"].notna()
        ]
        applied_keys = set(
            zip(applied["ex_date"], applied["action_type"], applied["ratio"].astype(float))
        )
        for _, row in skipped.iterrows():
            key = (row["ex_date"], row["action_type"], float(row["ratio"]))
            if key in applied_keys:
                continue
            anchor = _anchor(index, row["ex_date"])
            if anchor is None:
                continue
            share_factor[anchor] = share_factor.get(anchor, 1.0) * float(row["ratio"])

    cum_divisor = _reverse_cumprod_strictly_after(
        index, pd.Series(price_factor, dtype="float64")
    )
    cum_share = _reverse_cumprod_strictly_after(
        index, pd.Series(share_factor, dtype="float64")
    )
    return cum_divisor, cum_share, applied, ambiguous_dates, detect


# ======================================================================================
# Dividend cash series
# ======================================================================================

def dividend_cash_series(raw_df: pd.DataFrame, actions_df: pd.DataFrame, symbol: str,
                         cum_divisor: pd.Series,
                         source: str = "actions") -> pd.DataFrame:
    """Per-share cash dividends as a SEPARATE dated series -- never folded into prices.

    ``source``:
      * ``"actions"`` (default, REPRODUCIBLE) -- use ``dividend`` rows' ``dividend_amount``.
      * ``"adjclose"`` -- reconstruct implied dividends from ``Adj Close``/``Close``.
      * ``"auto"`` -- action-table rows if any exist, otherwise the Adj Close fallback.

    The Adj Close path exists because the action table presently carries ZERO
    ``dividend`` rows, and crediting nothing on COALINDIA/PFC/BPCL/HINDZINC/VEDL would
    understate total return by the same order as the whole cost budget.  It is sound
    only because of the audit's finding that on these series ``Adj Close / Close``
    captures cash dividends ONLY: with
    ``AdjClose(t) = Close(t) * prod{1 - D/Close(ex-1) : ex > t}``, writing
    ``r(t) = AdjClose(t)/Close(t)`` gives ``D = Close(t-1) * (1 - r(t-1)/r(t))``.
    LIMITATION: Yahoo's Adj Close is RETRO-ADJUSTED and recomputed on every download,
    so dividends derived this way are NOT reproducible across re-downloads and must be
    labelled as such in any published result.  Dates within one bar of a structural
    action are skipped on this path (a structural break in Close that is absent from
    Adj Close would otherwise masquerade as a huge dividend), and implied yields above
    25% are rejected.

    Scaling: cash is divided by ``CumDivisor`` at the CUM bar (the bar before the
    ex-date), which is the unit-consistent choice derived in the module docstring, so
    ``DividendCash`` is in the same units as the ``Adj*`` prices.

    Returns a DataFrame indexed like ``raw_df`` with ``DividendCashRaw``,
    ``DividendCash`` and ``DividendSource``.
    """
    if source not in ("actions", "adjclose", "auto"):
        raise ValueError("source must be one of 'actions', 'adjclose', 'auto'.")

    df = _normalise_raw(raw_df)
    acts = actions_for_symbol(actions_df, symbol)
    index = df.index
    out = pd.DataFrame(
        {
            "DividendCashRaw": pd.Series(0.0, index=index, dtype="float64"),
            "DividendCash": pd.Series(0.0, index=index, dtype="float64"),
            "DividendSource": pd.Series("", index=index, dtype="object"),
        }
    )

    div_rows = acts.loc[
        (acts["action_type"] == "dividend")
        & acts["dividend_amount"].notna()
        & acts["ex_date"].notna()
    ] if not acts.empty else acts

    use = source
    if source == "auto":
        use = "actions" if (div_rows is not None and len(div_rows) > 0) else "adjclose"

    def _credit(anchor: pd.Timestamp, amount: float, tag: str) -> None:
        pos = index.get_loc(anchor)
        cum_bar = index[pos - 1] if pos > 0 else anchor
        divisor = float(cum_divisor.loc[cum_bar]) if cum_bar in cum_divisor.index else 1.0
        if not np.isfinite(divisor) or divisor <= 0:
            divisor = 1.0
        out.loc[anchor, "DividendCashRaw"] += float(amount)
        out.loc[anchor, "DividendCash"] += float(amount) / divisor
        prev = out.at[anchor, "DividendSource"]
        out.loc[anchor, "DividendSource"] = tag if not prev else f"{prev};{tag}"

    if use == "actions":
        if div_rows is not None and len(div_rows) > 0:
            for _, row in div_rows.iterrows():
                anchor = _anchor(index, row["ex_date"])
                if anchor is None:
                    continue
                amt = float(row["dividend_amount"])
                if amt <= 0 or not np.isfinite(amt):
                    continue
                _credit(anchor, amt, "actions")
        return out

    # ---- Adj Close fallback -----------------------------------------------------
    if "Adj Close" not in df.columns:
        return out
    close = df["Close"].to_numpy(dtype="float64")
    adj = df["Adj Close"].to_numpy(dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(close > 0, adj / close, np.nan)

    struct_dates = set()
    if not acts.empty:
        for _, row in acts.loc[acts["action_type"].isin(STRUCTURAL_TYPES)].iterrows():
            if pd.isna(row["ex_date"]):
                continue
            anchor = _anchor(index, row["ex_date"])
            if anchor is None:
                continue
            pos = index.get_loc(anchor)
            for p in (pos - 1, pos, pos + 1):
                if 0 <= p < len(index):
                    struct_dates.add(index[p])

    for pos in range(1, len(index)):
        date = index[pos]
        if date in struct_dates:
            continue
        r_prev, r_cur = ratio[pos - 1], ratio[pos]
        if not (np.isfinite(r_prev) and np.isfinite(r_cur)) or r_cur <= 0:
            continue
        k = r_prev / r_cur                      # = 1 - D/Close(t-1)
        if not np.isfinite(k) or k >= 1.0 or k <= 0.0:
            continue
        yield_ = 1.0 - k
        if yield_ < _MIN_IMPLIED_YIELD or yield_ > _MAX_IMPLIED_YIELD:
            continue
        c_prev = close[pos - 1]
        if not np.isfinite(c_prev) or c_prev <= 0:
            continue
        _credit(date, c_prev * yield_, "adjclose_implied")

    return out


# ======================================================================================
# Main entry point
# ======================================================================================

OUTPUT_COLUMNS = [
    "AdjOpen", "AdjHigh", "AdjLow", "AdjClose", "AdjVolume",
    "StructAdjOpen", "StructAdjHigh", "StructAdjLow", "StructAdjClose",
    "CumDivisor", "CumShareRatio",
    "DividendCashRaw", "DividendCash", "DividendSource",
    "CorpActionExDate", "CorpActionTypes",
    "AdjQuality", "QualityApproxRatio", "QualityAmbiguousPrefold",
    "QualityUncrossable", "QualityDateUncertain", "SegmentId",
]


def build_adjusted(
    raw_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    symbol: str,
    split_policy: str = "auto",
    dividend_source: str = "actions",
    prefold_tol: float = DEFAULT_PREFOLD_TOL,
    prefold_margin: float = DEFAULT_PREFOLD_MARGIN,
    volume_follows_split_policy: bool = True,
) -> pd.DataFrame:
    """Build the structurally adjusted OHLCV series for one symbol.

    ``raw_df``: one stock's raw OHLCV, Date-indexed, columns Open/High/Low/Close/Volume
    and optionally ``Adj Close`` (``auto_adjust=False`` download).
    ``actions_df``: the action table (any symbol mix; filtered here).

    ``split_policy``:
      * ``"auto"`` (default) -- apply a split's divisor only where
        ``detect_prefolded_splits`` says it is NOT already folded into ``Close``.  This
        keeps the module correct whether or not the audit's unconfirmed F03 inference
        about Yahoo's NSE series holds.
      * ``"always"`` -- apply every split divisor (correct if nothing is prefolded).
      * ``"never"`` -- apply no split divisor (correct if everything is prefolded).
    Bonuses and demergers are always applied.

    ``dividend_source``: see ``dividend_cash_series``.  Dividends are NEVER folded into
    the price series -- that is the F08 fix.

    Returns ``raw_df``'s columns plus ``OUTPUT_COLUMNS``.
    """
    df = _normalise_raw(raw_df)
    acts = actions_for_symbol(actions_df, symbol)
    index = df.index

    cum_divisor, cum_share, applied, ambiguous_dates, _detect = structural_divisors(
        df, acts, symbol, split_policy=split_policy, tol=prefold_tol,
        margin=prefold_margin, volume_follows_split_policy=volume_follows_split_policy,
    )

    out = df.copy()
    out["CumDivisor"] = cum_divisor.astype("float64")
    out["CumShareRatio"] = cum_share.astype("float64")

    for src, dst in (("Open", "AdjOpen"), ("High", "AdjHigh"),
                     ("Low", "AdjLow"), ("Close", "AdjClose")):
        out[dst] = (out[src] / out["CumDivisor"]).astype("float64")
    # Unambiguous aliases: identical values, names that cannot be mistaken for a
    # dividend-reinvested (total-return) series.
    for a, b in (("AdjOpen", "StructAdjOpen"), ("AdjHigh", "StructAdjHigh"),
                 ("AdjLow", "StructAdjLow"), ("AdjClose", "StructAdjClose")):
        out[b] = out[a]

    # Volume: MULTIPLY by the share-count ratio (pre-event bars restated upward into
    # current share terms).  See VOLUME DIRECTION in the module docstring.
    out["AdjVolume"] = (out["Volume"] * out["CumShareRatio"]).astype("float64")

    div = dividend_cash_series(df, acts, symbol, cum_divisor=out["CumDivisor"],
                               source=dividend_source)
    out["DividendCashRaw"] = div["DividendCashRaw"]
    out["DividendCash"] = div["DividendCash"]
    out["DividendSource"] = div["DividendSource"]

    # ---- ex-date markers --------------------------------------------------------
    ex_flag = pd.Series(False, index=index, dtype=bool)
    ex_types: dict = {}
    if not acts.empty:
        for _, row in acts.iterrows():
            if pd.isna(row["ex_date"]):
                continue
            anchor = _anchor(index, row["ex_date"])
            if anchor is None:
                continue
            ex_flag.loc[anchor] = True
            ex_types.setdefault(anchor, []).append(str(row["action_type"]))
    out["CorpActionExDate"] = ex_flag
    out["CorpActionTypes"] = pd.Series(
        {d: ";".join(sorted(set(v))) for d, v in ex_types.items()},
        dtype="object",
    ).reindex(index).fillna("").astype("object")

    # ---- quality flags ----------------------------------------------------------
    approx_dates = approx_ratio_dates(acts, symbol)
    uncross_dates = uncrossable_boundaries(acts, symbol)
    derived_dates = derived_ex_date_dates(acts, symbol)

    q_approx = pd.Series(False, index=index, dtype=bool)
    q_ambig = pd.Series(False, index=index, dtype=bool)
    q_uncross = pd.Series(False, index=index, dtype=bool)
    q_date = pd.Series(False, index=index, dtype=bool)

    # An action at ex-date E rescales every bar STRICTLY BEFORE E, so the uncertainty
    # attaches to those bars.
    for d in approx_dates:
        q_approx.loc[index < pd.Timestamp(d)] = True
    for d in ambiguous_dates:
        q_ambig.loc[index < pd.Timestamp(d)] = True
    for d in uncross_dates:
        q_uncross.loc[index < pd.Timestamp(d)] = True
    for d in derived_dates:
        anchor = _anchor(index, d)
        if anchor is None:
            continue
        pos = index.get_loc(anchor)
        for p in (pos - 1, pos, pos + 1):
            if 0 <= p < len(index):
                q_date.iloc[p] = True

    q_div_struct = out["CorpActionExDate"].to_numpy() & (
        out["DividendCashRaw"].to_numpy() > 0
    ) & np.array([
        any(t in STRUCTURAL_TYPES for t in str(s).split(";") if s)
        for s in out["CorpActionTypes"]
    ])

    out["QualityApproxRatio"] = q_approx
    out["QualityAmbiguousPrefold"] = q_ambig
    out["QualityUncrossable"] = q_uncross
    out["QualityDateUncertain"] = q_date

    tokens = []
    for i in range(len(index)):
        t = []
        if q_uncross.iloc[i]:
            t.append(Q_UNCROSSABLE)
        if q_approx.iloc[i]:
            t.append(Q_APPROX)
        if q_ambig.iloc[i]:
            t.append(Q_AMBIG)
        if q_date.iloc[i]:
            t.append(Q_DERIVED_DATE)
        if q_div_struct[i]:
            t.append(Q_DIV_ON_STRUCT)
        tokens.append(";".join(t) if t else Q_OK)
    out["AdjQuality"] = pd.Series(tokens, index=index, dtype="object")

    # SegmentId: increments at each uncrossable boundary so the universe/labelling
    # module can keep the latest segment or purge straddling windows.  No truncation
    # happens here -- that module owns it.
    seg = pd.Series(0, index=index, dtype="int64")
    for d in uncross_dates:
        anchor = _anchor(index, d)
        if anchor is None:
            continue
        seg.loc[index >= anchor] += 1
    out["SegmentId"] = seg

    return out


# ======================================================================================
# Self-validation
# ======================================================================================

def assert_no_residual_discontinuity(adj_df: pd.DataFrame, actions_df: pd.DataFrame,
                                     symbol: str, threshold: float = 0.15) -> pd.DataFrame:
    """Find one-day moves in the STRUCTURALLY ADJUSTED close that exceed ``threshold``.

    A correctly adjusted series has no step at an ex-date, so a surviving big move is
    either a real market move, a missing action, or a wrong ratio.  Dates that are
    ex-dates in the action table, and uncrossable boundaries, are EXEMPT -- an
    approximate or deliberately unapplied ratio can legitimately leave residue there.

    Does NOT raise: returns the offending dates so a caller can report them.  The
    returned DataFrame is indexed by the offending dates (``Date``) with columns
    ``prev_close``, ``close``, ``ret``, ``abs_ret``, ``AdjQuality``.
    """
    df = pd.DataFrame(adj_df).copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df = df.set_index("Date")
        else:
            raise ValueError("adj_df needs a DatetimeIndex or a 'Date' column.")
    df.index = pd.to_datetime(df.index).normalize()
    col = "StructAdjClose" if "StructAdjClose" in df.columns else "AdjClose"
    if col not in df.columns:
        raise ValueError("adj_df needs AdjClose/StructAdjClose; run build_adjusted first.")

    close = pd.to_numeric(df[col], errors="coerce").astype("float64")
    ret = close.pct_change()

    acts = actions_for_symbol(actions_df, symbol)
    exempt = set()
    if not acts.empty:
        for d in acts["ex_date"].dropna():
            anchor = _anchor(df.index, d)
            if anchor is not None:
                exempt.add(anchor)
    for d in uncrossable_boundaries(acts, symbol):
        anchor = _anchor(df.index, d)
        if anchor is not None:
            exempt.add(anchor)

    bad = ret.abs() > float(threshold)
    bad &= ~pd.Series(df.index.isin(sorted(exempt)), index=df.index)
    bad &= ret.notna()

    res = pd.DataFrame({
        "prev_close": close.shift(1)[bad],
        "close": close[bad],
        "ret": ret[bad],
        "abs_ret": ret.abs()[bad],
        "AdjQuality": (df["AdjQuality"][bad] if "AdjQuality" in df.columns
                       else pd.Series("", index=close[bad].index)),
    })
    res.index.name = "Date"
    return res


# ======================================================================================
# Self-test -- SYNTHETIC data only.  No network, no real price files.
# ======================================================================================

_PASS = 0
_FAIL = 0


def _check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if bool(cond):
        _PASS += 1
        print(f"PASS  {name}")
    else:
        _FAIL += 1
        print(f"FAIL  {name}" + (f"  -- {detail}" if detail else ""))


def _syn_act(symbol, ex_date, action_type, ratio=None, dividend_amount=None,
             source="synthetic", confidence="VERIFIED"):
    return {
        "symbol": symbol, "ex_date": ex_date, "action_type": action_type,
        "ratio": ratio, "dividend_amount": dividend_amount, "source": source,
        "source_url": "https://example.invalid/x", "confidence": confidence,
    }


def _syn_prices(dates, closes, volumes=None, adj_close=None) -> pd.DataFrame:
    """Build a synthetic OHLCV frame: High/Low straddle Close, Open == Close."""
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    c = np.asarray(closes, dtype="float64")
    v = np.asarray(volumes if volumes is not None else [1_000.0] * len(c), dtype="float64")
    df = pd.DataFrame(
        {
            "Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
            "Adj Close": (np.asarray(adj_close, dtype="float64")
                          if adj_close is not None else c),
            "Volume": v,
        },
        index=idx,
    )
    df.index.name = "Date"
    return df


def _flat_then_step(n_pre, n_post, pre_level, post_level, start="2022-01-03"):
    """A flat series that steps at the boundary: a raw, unadjusted corporate action."""
    dates = pd.bdate_range(start, periods=n_pre + n_post)
    closes = [pre_level] * n_pre + [post_level] * n_post
    return dates, closes


def _selftest_bonus_1_1() -> None:
    print("\n--- 1:1 bonus (R=2): discontinuous raw -> continuous adjusted ---")
    dates, closes = _flat_then_step(5, 5, 200.0, 100.0)
    raw = _syn_prices(dates, closes)
    ex = dates[5]
    acts = pd.DataFrame([_syn_act("SYN", ex.strftime("%Y-%m-%d"), "bonus", ratio=2.0)])

    adj = build_adjusted(raw, acts, "SYN")
    ret = adj["AdjClose"].pct_change().abs()
    _check("bonus: adjusted close is flat everywhere",
           float(np.nanmax(ret.to_numpy())) < 1e-12,
           f"max |ret| = {float(np.nanmax(ret.to_numpy())):.6g}")
    _check("bonus: raw close WAS discontinuous (test is meaningful)",
           abs(raw['Close'].pct_change().iloc[5] + 0.5) < 1e-12)
    _check("bonus: ex-date bar untouched (strictly-after)",
           abs(float(adj.loc[ex, 'AdjClose']) - 100.0) < 1e-12,
           f"got {float(adj.loc[ex, 'AdjClose'])}")
    _check("bonus: bar BEFORE ex-date divided by R=2",
           abs(float(adj.loc[dates[4], 'AdjClose']) - 100.0) < 1e-12,
           f"got {float(adj.loc[dates[4], 'AdjClose'])}")
    _check("bonus: CumDivisor is 2 before and 1 from the ex-date on",
           abs(float(adj.loc[dates[4], 'CumDivisor']) - 2.0) < 1e-12
           and abs(float(adj.loc[ex, 'CumDivisor']) - 1.0) < 1e-12)
    _check("bonus: OHLC all adjusted consistently",
           np.allclose(adj['AdjHigh'] / adj['AdjClose'], 1.01)
           and np.allclose(adj['AdjLow'] / adj['AdjClose'], 0.99))
    _check("bonus: Struct* aliases equal Adj*",
           np.allclose(adj['StructAdjClose'], adj['AdjClose'])
           and np.allclose(adj['StructAdjOpen'], adj['AdjOpen']))
    _check("bonus: no dividend-reinvested price column emitted (F08)",
           not any("Total" in c or "Reinv" in c for c in adj.columns))
    _check("bonus: CorpActionExDate marks exactly the ex-date",
           adj['CorpActionExDate'].sum() == 1 and bool(adj.loc[ex, 'CorpActionExDate']))


def _selftest_split_1_5() -> None:
    print("\n--- 1:5 split (R=5) ---")
    dates, closes = _flat_then_step(4, 6, 500.0, 100.0)
    raw = _syn_prices(dates, closes)
    ex = dates[4]
    acts = pd.DataFrame([_syn_act("SYN", ex.strftime("%Y-%m-%d"), "split", ratio=5.0)])

    adj = build_adjusted(raw, acts, "SYN", split_policy="always")
    _check("split always: adjusted close flat",
           float(np.nanmax(adj['AdjClose'].pct_change().abs().to_numpy())) < 1e-12)
    _check("split always: pre-ex bar = 100", abs(float(adj.loc[dates[3], 'AdjClose']) - 100.0) < 1e-12)

    auto = build_adjusted(raw, acts, "SYN", split_policy="auto")
    _check("split auto: detector sees the unfolded break and applies it",
           float(np.nanmax(auto['AdjClose'].pct_change().abs().to_numpy())) < 1e-12)

    never = build_adjusted(raw, acts, "SYN", split_policy="never")
    _check("split never: divisor NOT applied, break survives",
           abs(float(never['AdjClose'].pct_change().iloc[4]) + 0.8) < 1e-12,
           f"got {float(never['AdjClose'].pct_change().iloc[4])}")


def _selftest_bajajfinsv_same_day() -> None:
    print("\n--- BAJAJFINSV: same-day 1:5 split (R=5) + 1:1 bonus (R=2) -> R=10 ---")
    dates = pd.bdate_range("2022-09-05", periods=10)
    ex = pd.Timestamp("2022-09-13")
    closes = [16000.0 if d < ex else 1600.0 for d in dates]
    raw = _syn_prices(dates, closes)
    acts = pd.DataFrame([
        _syn_act("BAJAJFINSV", "2022-09-13", "split", ratio=5.0),
        _syn_act("BAJAJFINSV", "2022-09-13", "bonus", ratio=2.0),
    ])
    _check("bajajfinsv: ex-date is a bar in the synthetic index", ex in raw.index)

    adj = build_adjusted(raw, acts, "BAJAJFINSV", split_policy="always")
    pre = adj.index[adj.index < ex][-1]
    _check("bajajfinsv: same-day divisors MULTIPLY to 10",
           abs(float(adj.loc[pre, 'CumDivisor']) - 10.0) < 1e-12,
           f"got {float(adj.loc[pre, 'CumDivisor'])}")
    _check("bajajfinsv: adjusted close continuous across the 10x reset",
           float(np.nanmax(adj['AdjClose'].pct_change().abs().to_numpy())) < 1e-12)
    _check("bajajfinsv: ex-date bar untouched at 1600",
           abs(float(adj.loc[ex, 'AdjClose']) - 1600.0) < 1e-12)

    # Split prefolded into Close, bonus not: raw shows only the 2x bonus break.
    closes_pf = [3200.0 if d < ex else 1600.0 for d in dates]
    raw_pf = _syn_prices(dates, closes_pf)
    det = detect_prefolded_splits(raw_pf, acts, "BAJAJFINSV")
    _check("bajajfinsv: detector verdict PREFOLDED when only the bonus break is visible",
           len(det) == 1 and det.iloc[0]['verdict'] == "PREFOLDED",
           f"got {list(det['verdict'])}")
    adj_pf = build_adjusted(raw_pf, acts, "BAJAJFINSV", split_policy="auto")
    _check("bajajfinsv: auto applies only the bonus divisor (2, not 10)",
           abs(float(adj_pf.loc[pre, 'CumDivisor']) - 2.0) < 1e-12,
           f"got {float(adj_pf.loc[pre, 'CumDivisor'])}")
    _check("bajajfinsv: auto leaves the prefolded series continuous",
           float(np.nanmax(adj_pf['AdjClose'].pct_change().abs().to_numpy())) < 1e-12)


def _selftest_demerger() -> None:
    print("\n--- demerger R=1.613553 (TMPV-shaped) ---")
    R = 1.613553
    dates = pd.bdate_range("2025-10-08", periods=8)
    ex = dates[4]
    closes = [660.75 if d < ex else 660.75 / R for d in dates]
    raw = _syn_prices(dates, closes)
    acts = pd.DataFrame([
        _syn_act("TMPV", ex.strftime("%Y-%m-%d"), "demerger", ratio=R,
                 source="synthetic;EX_DATE_VERIFIED;RATIO_APPROX", confidence="UNVERIFIED")
    ])
    adj = build_adjusted(raw, acts, "TMPV")
    _check("demerger: adjusted close continuous",
           float(np.nanmax(adj['AdjClose'].pct_change().abs().to_numpy())) < 1e-9)
    _check("demerger: CumDivisor == R before the ex-date",
           abs(float(adj.loc[dates[3], 'CumDivisor']) - R) < 1e-12)
    _check("demerger: share count UNCHANGED -> volume ratio stays 1",
           abs(float(adj.loc[dates[3], 'CumShareRatio']) - 1.0) < 1e-12
           and np.allclose(adj['AdjVolume'], adj['Volume']))
    _check("demerger: RATIO_APPROX propagated to AdjQuality on pre-ex bars",
           bool(adj.loc[dates[3], 'QualityApproxRatio'])
           and Q_APPROX in str(adj.loc[dates[3], 'AdjQuality'])
           and not bool(adj.loc[ex, 'QualityApproxRatio']))
    _check("demerger: approx_ratio_dates lists the ex-date",
           approx_ratio_dates(acts, "TMPV") == [ex.normalize()])


def _selftest_strictly_after_boundary() -> None:
    print("\n--- strictly-after boundary, incl. ex-date on a non-trading day ---")
    dates = pd.bdate_range("2023-03-06", periods=6)
    raw = _syn_prices(dates, [100.0] * 6)
    ex = dates[3]
    acts = pd.DataFrame([_syn_act("SYN", ex.strftime("%Y-%m-%d"), "bonus", ratio=2.0)])
    adj = build_adjusted(raw, acts, "SYN")
    div = adj['CumDivisor'].to_numpy()
    _check("boundary: divisor is 2,2,2 before and 1,1,1 from the ex-date on",
           np.allclose(div[:3], 2.0) and np.allclose(div[3:], 1.0),
           f"got {div}")

    # Ex-date on a Saturday -> must anchor at the next trading bar, not the previous one.
    sat = dates[2] + pd.Timedelta(days=0)
    weekend_ex = pd.Timestamp("2023-03-11")  # Saturday
    acts2 = pd.DataFrame([_syn_act("SYN", "2023-03-11", "bonus", ratio=2.0)])
    adj2 = build_adjusted(raw, acts2, "SYN")
    anchor = _anchor(raw.index, weekend_ex)
    _check("boundary: non-trading ex-date anchors to the next bar",
           anchor == pd.Timestamp("2023-03-13"), f"anchor={anchor}")
    _check("boundary: bars before the anchor divided, anchor onward untouched",
           np.allclose(adj2.loc[:pd.Timestamp('2023-03-10'), 'CumDivisor'], 2.0)
           and np.allclose(adj2.loc[pd.Timestamp('2023-03-13'):, 'CumDivisor'], 1.0))
    del sat


def _selftest_volume_direction() -> None:
    print("\n--- volume direction ---")
    dates, closes = _flat_then_step(4, 4, 500.0, 100.0)
    # Constant turnover: a 5x share count means 5x the share volume post-event.
    volumes = [1_000.0] * 4 + [5_000.0] * 4
    raw = _syn_prices(dates, closes, volumes=volumes)
    ex = dates[4]
    acts = pd.DataFrame([_syn_act("SYN", ex.strftime("%Y-%m-%d"), "split", ratio=5.0)])
    adj = build_adjusted(raw, acts, "SYN", split_policy="always")

    _check("volume: pre-event volume MULTIPLIED by R (scaled UP to post-event shares)",
           abs(float(adj.loc[dates[3], 'AdjVolume']) - 5_000.0) < 1e-9,
           f"got {float(adj.loc[dates[3], 'AdjVolume'])}")
    _check("volume: post-event volume unchanged",
           abs(float(adj.loc[ex, 'AdjVolume']) - 5_000.0) < 1e-9)
    _check("volume: step removed (flat AdjVolume)",
           float(np.nanmax(adj['AdjVolume'].pct_change().abs().to_numpy())) < 1e-12)
    _check("volume: direction is UP not DOWN for pre-event bars",
           float(adj.loc[dates[3], 'AdjVolume']) > float(raw.loc[dates[3], 'Volume']))
    _check("volume: CumShareRatio == CumDivisor for a pure split",
           np.allclose(adj['CumShareRatio'], adj['CumDivisor']))


def _selftest_blank_ratio() -> None:
    print("\n--- blank ratio -> uncrossable boundary, NOT a silent skip ---")
    dates = pd.bdate_range("2019-12-16", periods=8)
    ex = pd.Timestamp("2019-12-20")
    closes = [1500.0 if d < ex else 900.0 for d in dates]   # unexplained real break
    raw = _syn_prices(dates, closes)
    acts = pd.DataFrame([
        _syn_act("ABB", "2019-12-20", "demerger", ratio=None,
                 source="synthetic;EX_DATE_VERIFIED;RATIO_UNKNOWN", confidence="UNVERIFIED")
    ])
    _check("blank: uncrossable_boundaries returns the ex-date",
           uncrossable_boundaries(acts, "ABB") == [ex], f"got {uncrossable_boundaries(acts, 'ABB')}")
    _check("blank: returns a list of pd.Timestamp",
           all(isinstance(d, pd.Timestamp) for d in uncrossable_boundaries(acts, "ABB")))

    adj = build_adjusted(raw, acts, "ABB")
    _check("blank: no ratio invented (CumDivisor stays 1 everywhere)",
           np.allclose(adj['CumDivisor'], 1.0))
    _check("blank: NOT silently skipped -- pre-boundary bars flagged",
           bool(adj.loc[dates[0], 'QualityUncrossable'])
           and Q_UNCROSSABLE in str(adj.loc[dates[0], 'AdjQuality']))
    _check("blank: SegmentId increments at the boundary",
           int(adj.loc[dates[0], 'SegmentId']) == 0 and int(adj.loc[ex, 'SegmentId']) == 1)
    _check("blank: post-boundary bars are clean",
           str(adj.loc[ex, 'AdjQuality']).startswith(Q_OK)
           or Q_UNCROSSABLE not in str(adj.loc[ex, 'AdjQuality']))
    offenders = assert_no_residual_discontinuity(adj, acts, "ABB", threshold=0.15)
    _check("blank: the boundary itself is EXEMPT from the discontinuity check",
           ex not in offenders.index, f"offenders={list(offenders.index)}")


def _selftest_detector_both_ways() -> None:
    print("\n--- prefolded-split detector: folded and unfolded synthetic series ---")
    dates = pd.bdate_range("2024-12-20", periods=10)
    ex = pd.Timestamp("2024-12-27")
    acts = pd.DataFrame([_syn_act("MAZDOCK", "2024-12-27", "split", ratio=2.0)])

    unfolded = _syn_prices(dates, [4000.0 if d < ex else 2000.0 for d in dates])
    d1 = detect_prefolded_splits(unfolded, acts, "MAZDOCK")
    _check("detector: unfolded series -> NOT_FOLDED",
           len(d1) == 1 and d1.iloc[0]['verdict'] == "NOT_FOLDED", f"got {list(d1['verdict'])}")
    _check("detector: unfolded observed ratio ~ R",
           abs(float(d1.iloc[0]['observed_ratio']) - 2.0) < 1e-9)
    _check("detector: unfolded -> apply_divisor True", bool(d1.iloc[0]['apply_divisor']))

    folded = _syn_prices(dates, [2000.0] * 10)
    d2 = detect_prefolded_splits(folded, acts, "MAZDOCK")
    _check("detector: folded series -> PREFOLDED",
           len(d2) == 1 and d2.iloc[0]['verdict'] == "PREFOLDED", f"got {list(d2['verdict'])}")
    _check("detector: folded -> apply_divisor False", not bool(d2.iloc[0]['apply_divisor']))
    adj_folded = build_adjusted(folded, acts, "MAZDOCK", split_policy="auto")
    _check("detector: auto on a folded series leaves prices untouched",
           np.allclose(adj_folded['AdjClose'], folded['Close']))

    # Neither hypothesis matches: a real market move on top of nothing explicable.
    weird = _syn_prices(dates, [2000.0 if d < ex else 1400.0 for d in dates])
    d3 = detect_prefolded_splits(weird, acts, "MAZDOCK")
    _check("detector: unexplainable move -> AMBIGUOUS",
           len(d3) == 1 and d3.iloc[0]['verdict'] == "AMBIGUOUS", f"got {list(d3['verdict'])}")
    adj_w = build_adjusted(weird, acts, "MAZDOCK", split_policy="auto")
    pre = adj_w.index[adj_w.index < ex][-1]
    _check("detector: AMBIGUOUS flagged in AdjQuality on affected bars",
           bool(adj_w.loc[pre, 'QualityAmbiguousPrefold'])
           and Q_AMBIG in str(adj_w.loc[pre, 'AdjQuality']))

    # Ex-date at the very first bar: nothing to compare against.
    short = _syn_prices(pd.bdate_range("2024-12-27", periods=4), [2000.0] * 4)
    d4 = detect_prefolded_splits(short, acts, "MAZDOCK")
    _check("detector: no prior bar -> INSUFFICIENT_DATA",
           len(d4) == 1 and d4.iloc[0]['verdict'] == "INSUFFICIENT_DATA",
           f"got {list(d4['verdict'])}")


def _selftest_residual_discontinuity() -> None:
    print("\n--- assert_no_residual_discontinuity catches a MISSING action ---")
    dates = pd.bdate_range("2022-05-02", periods=12)
    ex_known = dates[3]
    ex_missing = dates[8]
    closes = []
    for d in dates:
        px = 1000.0
        if d >= ex_known:
            px /= 2.0
        if d >= ex_missing:
            px /= 2.0           # a bonus that is NOT in the table
        closes.append(px)
    raw = _syn_prices(dates, closes)
    acts = pd.DataFrame([_syn_act("SYN", ex_known.strftime("%Y-%m-%d"), "bonus", ratio=2.0)])

    adj = build_adjusted(raw, acts, "SYN")
    offenders = assert_no_residual_discontinuity(adj, acts, "SYN", threshold=0.15)
    _check("residual: returns (not raises) a frame of offending dates",
           isinstance(offenders, pd.DataFrame))
    _check("residual: the MISSING action's date is reported",
           ex_missing in offenders.index, f"offenders={list(offenders.index)}")
    _check("residual: the KNOWN, correctly applied action is NOT reported",
           ex_known not in offenders.index)
    _check("residual: exactly one offender here", len(offenders) == 1, f"len={len(offenders)}")

    fixed_acts = pd.DataFrame([
        _syn_act("SYN", ex_known.strftime("%Y-%m-%d"), "bonus", ratio=2.0),
        _syn_act("SYN", ex_missing.strftime("%Y-%m-%d"), "bonus", ratio=2.0),
    ])
    adj2 = build_adjusted(raw, fixed_acts, "SYN")
    off2 = assert_no_residual_discontinuity(adj2, fixed_acts, "SYN", threshold=0.15)
    _check("residual: clean once the action is added to the table", len(off2) == 0,
           f"offenders={list(off2.index)}")
    _check("residual: and the series is then continuous",
           float(np.nanmax(adj2['AdjClose'].pct_change().abs().to_numpy())) < 1e-12)

    big_move = _syn_prices(pd.bdate_range("2021-01-04", periods=5),
                           [100.0, 100.0, 70.0, 70.0, 70.0])
    adj3 = build_adjusted(big_move, pd.DataFrame(columns=ACTION_COLUMNS), "SYN")
    off3 = assert_no_residual_discontinuity(adj3, pd.DataFrame(columns=ACTION_COLUMNS),
                                            "SYN", threshold=0.15)
    _check("residual: a -30% bar with an empty action table is reported", len(off3) == 1)


def _selftest_dividends() -> None:
    print("\n--- dividend cash: separate series, never in the price (F08) ---")
    dates = pd.bdate_range("2023-06-05", periods=6)
    ex = dates[3]
    raw = _syn_prices(dates, [100.0] * 6)
    acts = pd.DataFrame([_syn_act("SYN", ex.strftime("%Y-%m-%d"), "dividend",
                                  dividend_amount=5.0)])
    adj = build_adjusted(raw, acts, "SYN", dividend_source="actions")
    _check("dividend: prices NOT touched by the dividend",
           np.allclose(adj['AdjClose'], raw['Close']) and np.allclose(adj['CumDivisor'], 1.0))
    _check("dividend: cash dated on the ex-date bar only",
           abs(float(adj.loc[ex, 'DividendCash']) - 5.0) < 1e-12
           and abs(float(adj['DividendCash'].sum()) - 5.0) < 1e-12)
    _check("dividend: DividendSource tagged", adj.loc[ex, 'DividendSource'] == "actions")

    # Cash scaled into adjusted units via the CUM-bar divisor.
    dates2 = pd.bdate_range("2023-06-05", periods=8)
    ex_div = dates2[2]
    ex_split = dates2[5]
    closes2 = [500.0 if d < ex_split else 100.0 for d in dates2]
    raw2 = _syn_prices(dates2, closes2)
    acts2 = pd.DataFrame([
        _syn_act("SYN", ex_div.strftime("%Y-%m-%d"), "dividend", dividend_amount=10.0),
        _syn_act("SYN", ex_split.strftime("%Y-%m-%d"), "split", ratio=5.0),
    ])
    adj2 = build_adjusted(raw2, acts2, "SYN", split_policy="always", dividend_source="actions")
    _check("dividend: pre-split cash divided by the cum-bar divisor (10 -> 2)",
           abs(float(adj2.loc[ex_div, 'DividendCash']) - 2.0) < 1e-12,
           f"got {float(adj2.loc[ex_div, 'DividendCash'])}")
    _check("dividend: raw cash preserved alongside",
           abs(float(adj2.loc[ex_div, 'DividendCashRaw']) - 10.0) < 1e-12)
    _check("dividend: cash/price yield preserved after adjustment",
           abs(float(adj2.loc[ex_div, 'DividendCash']) / float(adj2.loc[ex_div, 'AdjClose'])
               - 10.0 / 500.0) < 1e-12)

    # Adj Close fallback: yfinance-shaped retro-adjusted series, dividends only.
    k = 1.0 - 4.0 / 100.0
    adjclose = [100.0 * k, 100.0 * k, 100.0, 100.0, 100.0, 100.0]
    raw3 = _syn_prices(pd.bdate_range("2024-02-05", periods=6), [100.0] * 6,
                       adj_close=adjclose)
    acts3 = pd.DataFrame(columns=ACTION_COLUMNS)
    adj3 = build_adjusted(raw3, acts3, "SYN", dividend_source="adjclose")
    implied = float(adj3['DividendCash'].sum())
    _check("dividend: Adj Close fallback recovers ~Rs 4.00",
           abs(implied - 4.0) < 1e-6, f"got {implied}")
    _check("dividend: fallback dates the cash on the ex-date bar",
           abs(float(adj3['DividendCash'].iloc[2]) - 4.0) < 1e-6)
    _check("dividend: fallback leaves prices untouched",
           np.allclose(adj3['AdjClose'], raw3['Close']))
    _check("dividend: 'auto' prefers the action table when rows exist",
           abs(float(build_adjusted(raw, acts, 'SYN', dividend_source='auto')
                     ['DividendCash'].sum()) - 5.0) < 1e-12)


def _selftest_misc_contract() -> None:
    print("\n--- interface contract / dtypes / edge cases ---")
    dates = pd.bdate_range("2020-01-06", periods=6)
    raw = _syn_prices(dates, [100.0] * 6)
    empty = pd.DataFrame(columns=ACTION_COLUMNS)
    adj = build_adjusted(raw, empty, "SYN")
    _check("contract: all promised columns present",
           all(c in adj.columns for c in OUTPUT_COLUMNS),
           f"missing {[c for c in OUTPUT_COLUMNS if c not in adj.columns]}")
    _check("contract: price/volume columns are float64",
           all(adj[c].dtype == np.float64 for c in
               ["AdjOpen", "AdjHigh", "AdjLow", "AdjClose", "AdjVolume",
                "CumDivisor", "CumShareRatio", "DividendCash", "DividendCashRaw"]))
    _check("contract: quality columns are bool, SegmentId int64",
           all(adj[c].dtype == np.bool_ for c in
               ["CorpActionExDate", "QualityApproxRatio", "QualityAmbiguousPrefold",
                "QualityUncrossable", "QualityDateUncertain"])
           and adj["SegmentId"].dtype == np.int64)
    _check("contract: empty action table is a no-op",
           np.allclose(adj['AdjClose'], raw['Close'])
           and np.allclose(adj['AdjVolume'], raw['Volume'])
           and (adj['AdjQuality'] == Q_OK).all())
    _check("contract: raw columns passed through untouched",
           np.allclose(adj['Close'], raw['Close'])
           and np.allclose(adj['Adj Close'], raw['Adj Close']))
    _check("contract: index preserved, sorted, named Date",
           adj.index.equals(raw.index) and adj.index.name == "Date")

    # Actions for another symbol must not leak in.
    other = pd.DataFrame([_syn_act("OTHER", dates[3].strftime("%Y-%m-%d"), "bonus", ratio=2.0)])
    adj_o = build_adjusted(raw, other, "SYN")
    _check("contract: other symbols' actions ignored", np.allclose(adj_o['CumDivisor'], 1.0))

    # Action after the last bar: reported, not applied.
    future = pd.DataFrame([_syn_act("SYN", "2026-12-31", "bonus", ratio=2.0)])
    adj_f = build_adjusted(raw, future, "SYN")
    _check("contract: post-sample action not applied",
           np.allclose(adj_f['CumDivisor'], 1.0))
    _check("contract: post-sample action reported by pending_future_actions",
           len(pending_future_actions(raw, future, "SYN")) == 1)

    # Sub-1 ratio violates the convention -> uncrossable, not applied.
    bad = pd.DataFrame([_syn_act("SYN", dates[3].strftime("%Y-%m-%d"), "bonus", ratio=0.5)])
    _check("contract: R < 1 treated as unusable -> uncrossable boundary",
           uncrossable_boundaries(bad, "SYN") == [dates[3].normalize()])
    _check("contract: R < 1 not applied", np.allclose(build_adjusted(raw, bad, "SYN")['CumDivisor'], 1.0))

    # DERIVED_FROM_RECORD_DATE flagging.
    derived = pd.DataFrame([_syn_act("SYN", dates[3].strftime("%Y-%m-%d"), "bonus", ratio=2.0,
                                     confidence="DERIVED_FROM_RECORD_DATE")])
    adj_d = build_adjusted(raw, derived, "SYN")
    _check("contract: derived ex-date flags the anchor +/- 1 bar",
           bool(adj_d.loc[dates[2], 'QualityDateUncertain'])
           and bool(adj_d.loc[dates[3], 'QualityDateUncertain'])
           and bool(adj_d.loc[dates[4], 'QualityDateUncertain'])
           and not bool(adj_d.loc[dates[1], 'QualityDateUncertain']))

    # Unsorted / Date-column input is accepted and normalised.
    shuffled = raw.iloc[::-1].reset_index()
    adj_s = build_adjusted(shuffled, empty, "SYN")
    _check("contract: accepts a 'Date' column and re-sorts", adj_s.index.equals(raw.index))

    try:
        build_adjusted(raw.drop(columns=["Close"]), empty, "SYN")
        ok = False
    except ValueError:
        ok = True
    _check("contract: missing Close raises ValueError", ok)

    try:
        build_adjusted(raw, empty, "SYN", split_policy="nonsense")
        ok2 = False
    except ValueError:
        ok2 = True
    _check("contract: bad split_policy raises ValueError", ok2)


def _selftest_volume_policy_flag() -> None:
    print("\n--- volume_follows_split_policy ---")
    dates = pd.bdate_range("2024-12-20", periods=8)
    ex = pd.Timestamp("2024-12-27")
    # Split prefolded in Close; volume also prefolded (flat) -- the default assumption.
    raw = _syn_prices(dates, [2000.0] * 8, volumes=[5_000.0] * 8)
    acts = pd.DataFrame([_syn_act("SYN", "2024-12-27", "split", ratio=2.0)])
    a_follow = build_adjusted(raw, acts, "SYN", split_policy="auto",
                              volume_follows_split_policy=True)
    _check("volume policy: default assumes volume follows price (no extra scaling)",
           np.allclose(a_follow['AdjVolume'], raw['Volume']))
    a_force = build_adjusted(raw, acts, "SYN", split_policy="auto",
                             volume_follows_split_policy=False)
    pre = a_force.index[a_force.index < ex][-1]
    _check("volume policy: False still applies the split to volume",
           abs(float(a_force.loc[pre, 'AdjVolume']) - 10_000.0) < 1e-9,
           f"got {float(a_force.loc[pre, 'AdjVolume'])}")
    _check("volume policy: prices unaffected by the volume flag",
           np.allclose(a_follow['AdjClose'], a_force['AdjClose']))


def _selftest_multi_action_chain() -> None:
    print("\n--- multiple actions compounding (MOTHERSON-shaped chain) ---")
    dates = pd.bdate_range("2015-07-20", periods=14)
    ex1, ex2 = dates[3], dates[9]
    closes = []
    for d in dates:
        px = 450.0
        if d >= ex1:
            px /= 1.5
        if d >= ex2:
            px /= 1.5
        closes.append(px)
    raw = _syn_prices(dates, closes, volumes=[1000.0] * 14)
    acts = pd.DataFrame([
        _syn_act("MOTHERSON", ex1.strftime("%Y-%m-%d"), "bonus", ratio=1.5),
        _syn_act("MOTHERSON", ex2.strftime("%Y-%m-%d"), "bonus", ratio=1.5),
    ])
    adj = build_adjusted(raw, acts, "MOTHERSON")
    _check("chain: adjusted close continuous across both bonuses",
           float(np.nanmax(adj['AdjClose'].pct_change().abs().to_numpy())) < 1e-12)
    _check("chain: earliest divisor is 1.5*1.5 = 2.25",
           abs(float(adj['CumDivisor'].iloc[0]) - 2.25) < 1e-12,
           f"got {float(adj['CumDivisor'].iloc[0])}")
    _check("chain: divisor is 1.5 between the two ex-dates",
           abs(float(adj.loc[dates[5], 'CumDivisor']) - 1.5) < 1e-12)
    _check("chain: divisor is 1 from the last ex-date on",
           abs(float(adj['CumDivisor'].iloc[-1]) - 1.0) < 1e-12)
    _check("chain: volume share ratio compounds the same way",
           abs(float(adj['CumShareRatio'].iloc[0]) - 2.25) < 1e-12)
    _check("chain: no residual discontinuity",
           len(assert_no_residual_discontinuity(adj, acts, "MOTHERSON")) == 0)

    # A blank-ratio action in the middle of the chain: boundary, chain still built.
    acts_b = pd.concat([acts, pd.DataFrame([
        _syn_act("MOTHERSON", dates[6].strftime("%Y-%m-%d"), "demerger", ratio=None,
                 source="synthetic;RATIO_UNKNOWN", confidence="UNVERIFIED")])],
        ignore_index=True)
    adj_b = build_adjusted(raw, acts_b, "MOTHERSON")
    _check("chain: blank-ratio row adds a boundary without breaking the other divisors",
           abs(float(adj_b['CumDivisor'].iloc[0]) - 2.25) < 1e-12
           and int(adj_b['SegmentId'].iloc[0]) == 0
           and int(adj_b['SegmentId'].iloc[-1]) == 1)


def _main() -> int:
    print("02b_adjust_prices.py self-test")
    print("SYNTHETIC in-memory data ONLY. No network, no real price files, and NOTHING")
    print("here has been verified against the user's actual NSE series.")
    _selftest_bonus_1_1()
    _selftest_split_1_5()
    _selftest_bajajfinsv_same_day()
    _selftest_demerger()
    _selftest_strictly_after_boundary()
    _selftest_volume_direction()
    _selftest_volume_policy_flag()
    _selftest_blank_ratio()
    _selftest_detector_both_ways()
    _selftest_residual_discontinuity()
    _selftest_dividends()
    _selftest_multi_action_chain()
    _selftest_misc_contract()
    print(f"\n{_PASS} passed, {_FAIL} failed")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(_main())
