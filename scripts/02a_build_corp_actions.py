#!/usr/bin/env python3
"""
02a_build_corp_actions.py -- authoritative NSE/BSE corporate-action table for the NIFTY100 universe.

WHY THIS MODULE EXISTS
----------------------
Price history for this project comes from Yahoo Finance via ``yfinance`` with
``auto_adjust=False``.  A prior audit of these NSE series established (by inference, not
by diagnostic) that:

  * ``Adj Close / Close`` captures CASH DIVIDENDS ONLY.
  * SPLITS appear to be pre-folded into ``Close`` itself.
  * BONUS ISSUES, DEMERGERS and SCHEMES OF ARRANGEMENT appear to be adjusted NOWHERE.
    They sit in the raw series as fake one-day crashes of -33% to -72%.

Therefore corporate actions MUST NOT be derived from ``AdjClose / Close``.  This module is
the source of truth instead: a hand-curated, source-cited CSV merged with whatever
``yfinance`` reports, with the hand-curated table winning every conflict.

=====================================================================================
THE RATIO CONVENTION  (read this before consuming the `ratio` column)
=====================================================================================
For every structural action (``split``, ``bonus``, ``demerger``, ``rights``) the
``ratio`` column holds a single number R, defined as::

    R = P_cum / P_ex

    P_cum = the last traded price on the session BEFORE the ex-date  (cum-entitlement)
    P_ex  = the adjusted base price from the ex-date onward          (ex-entitlement)

R is always >= 1 for a value-diluting action.  It is a MULTIPLICATIVE PRICE-ADJUSTMENT
DIVISOR: it is the factor by which the quoted price mechanically drops on the ex-date.

How R is computed per action type
---------------------------------
* ``split``, r-for-1  (1 old share becomes r new shares; e.g. face value 10 -> 2 is r=5)
      R = r
      A "1:5 split" in Indian market parlance means r = 5  ->  R = 5.
* ``bonus``, a:b  (shareholder receives `a` NEW shares for every `b` HELD)
      R = (a + b) / b
      A 1:1 bonus (1 new per 1 held) doubles the share count  ->  R = 2.
      A 1:2 bonus (1 new per 2 held)                          ->  R = 1.5.
      A 2:1 bonus (2 new per 1 held)                          ->  R = 3.
      A 1:3 bonus                                             ->  R = 4/3 = 1.333333.
* ``demerger`` / scheme of arrangement, where the PARENT retains fraction f of its
  pre-event market value (0 < f < 1) and the demerged entity carries (1 - f)
      R = 1 / f
      Example: parent retains f = 0.50  ->  R = 2.0  (price halves on the ex-date).
      Example: parent retains f = 0.6885 -> R = 1.4525.
      In India the exchange runs a special pre-open call auction on the ex-date of a
      demerger to discover P_ex for the parent.  Where that discovered price is on
      record, R = P_cum / P_ex_discovered is the authoritative divisor and is what this
      table carries.  NOTE: the discovered (market-value) split is NOT the same as the
      company's cost-of-acquisition apportionment announced for income-tax purposes.
      The market-value split is the correct one for price adjustment; this table uses it.
* ``rights``  R = P_cum / theoretical ex-rights price.  (No rights rows are currently
      carried; the column is defined for completeness.)
* ``dividend``  ``ratio`` is EMPTY.  Use ``dividend_amount`` instead.

HOW A CONSUMER APPLIES R
------------------------
To put a raw price series on a single, present-day-consistent scale, divide every price
strictly BEFORE an ex-date by that action's R -- i.e. accumulate all future actions::

    adjusted_close(t) = raw_close(t) / prod( R_i  for every action i with ex_date_i > t )

Equivalently, walking backwards from the most recent bar, multiply the running divisor by
R each time you step back across an ex-date.  Prices on and after the ex-date are
untouched.  Round-tripping: a series adjusted this way can be restored by multiplying by
the same cumulative product -- see ``_selftest_ratio_roundtrip``.

Because the audit found SPLITS already folded into Yahoo's ``Close``, a consumer of this
table for Yahoo data will typically apply only the ``bonus``, ``demerger`` and ``rights``
rows, and use the ``split`` rows purely as a cross-check that Yahoo really did fold them
in.  That decision belongs to the price-adjustment module, not here.  This module's job is
to state, with sources, WHAT happened and WHEN.

=====================================================================================
EX-DATE vs RECORD DATE
=====================================================================================
``ex_date`` is ALWAYS the ex-date, never the record date.  The ex-date is the first
session on which the price trades without the entitlement -- that is the session on which
the series breaks, so it is the only date a price-adjustment pipeline can use.

  * T+2 settlement era (before 2023-01-27): ex-date = one TRADING session before the
    record date.
  * T+1 settlement era (from 2023-01-27): ex-date and record date commonly COINCIDE.

Where a source gave only a record date, the ex-date here was derived by that rule and the
row carries ``confidence="DERIVED_FROM_RECORD_DATE"``.  The derivation is naive about
exchange holidays: it steps back one weekday, which can be wrong by a session around a
holiday.  Rows derived this way are flagged precisely so a consumer can widen the window.

=====================================================================================
CONFIDENCE
=====================================================================================
* ``VERIFIED``                  -- a retrieved source URL states this ex-date AND this
                                   ratio (or states the ex-date for an action whose ratio
                                   follows arithmetically from a stated share ratio).
* ``DERIVED_FROM_RECORD_DATE``  -- the source gave a record date; the ex-date was derived
                                   by the T+1/T+2 rule above.
* ``UNVERIFIED``                -- something in the row could not be confirmed from a
                                   retrieved source.  For several demergers the EX-DATE is
                                   solidly sourced but the RATIO is only approximate
                                   (taken from a news-reported intraday percentage move
                                   rather than an official discovered base price).  Those
                                   rows say so in the ``source`` field via the token
                                   ``EX_DATE_VERIFIED;RATIO_APPROX``.  A consumer that only
                                   needs to MASK or flag the ex-date can trust such a row's
                                   date; a consumer that needs to RESCALE prices must not
                                   trust its ratio without further work.

Never treat an ``UNVERIFIED`` ratio as fact.

=====================================================================================
YFINANCE SIDE, AND THE PRECEDENCE RULE
=====================================================================================
``yf.Ticker(sym + ".NS").splits`` and ``.dividends`` are pulled for every universe symbol.
Known problems with that feed on NSE tickers:

  * ``.splits`` CONFLATES BONUS ISSUES WITH SPLITS.  A 1:1 bonus frequently shows up as a
    2.0 "split" (sometimes on the wrong date, sometimes with the reciprocal factor).
  * ``.splits`` is INCOMPLETE -- whole bonus issues and essentially all demergers and
    schemes of arrangement are missing.
  * Dates can be off by a session, and are sometimes the record date rather than the
    ex-date.

That is exactly why the manual CSV exists.

PRECEDENCE RULE (deterministic, applied in ``merge_actions``):
  1. Manual rows always survive.
  2. A yfinance row is DROPPED if the manual table has any row for the same
     ``(symbol, ex_date)`` -- regardless of ``action_type``.  This is deliberate: because
     yfinance mislabels bonuses as splits, matching on ``action_type`` too would let a
     bogus ``split`` row slip in alongside the correct manual ``bonus`` row and
     double-count the adjustment.
  3. A yfinance row is also dropped if the manual table has a row for the same
     ``(symbol, action_type)`` within ``NEAR_DATE_DAYS`` calendar days, to absorb
     off-by-a-session feed errors.
  4. Surviving yfinance rows are tagged ``source="yfinance"`` and
     ``confidence="UNVERIFIED"``.  They are LEADS, not facts.

OUTPUTS
-------
* ``ROOT/data/reference/corp_actions.csv``            -- the merged table
* ``ROOT/data/reference/corp_actions_fetch_log.csv``  -- per-symbol fetch outcome.  A
  symbol that failed every retry is recorded with its error; it is NEVER allowed to
  silently look like "this symbol has no corporate actions".

SCOPE
-----
This module owns the corporate-action table and nothing else.  It does not adjust prices,
build calendars, select the universe, or validate bars.

Python 3, stdlib + pandas + numpy + yfinance only.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------------------

COLUMNS: list[str] = [
    "symbol",
    "ex_date",
    "action_type",
    "ratio",
    "dividend_amount",
    "source",
    "source_url",
    "confidence",
]

ACTION_TYPES: frozenset[str] = frozenset({"split", "bonus", "demerger", "dividend", "rights"})
STRUCTURAL_TYPES: frozenset[str] = frozenset({"split", "bonus", "demerger", "rights"})
CONFIDENCE_LEVELS: frozenset[str] = frozenset(
    {"VERIFIED", "DERIVED_FROM_RECORD_DATE", "UNVERIFIED"}
)

#: India moved from T+2 to T+1 rolling settlement for all equities on this date.
#: Before it, ex-date = one trading session before record date.  From it, they coincide.
T1_SETTLEMENT_START = pd.Timestamp("2023-01-27")

#: Window used by the precedence rule to absorb off-by-a-session yfinance dates.
NEAR_DATE_DAYS = 3

#: Project universe: NIFTY100 as used by this project.
UNIVERSE: tuple[str, ...] = (
    "ABB", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER",
    "AMBUJACEM", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV",
    "BAJAJHLDNG", "BAJFINANCE", "BANKBARODA", "BEL", "BHARTIARTL", "BOSCHLTD", "BPCL",
    "BRITANNIA", "BSE", "CANBK", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA",
    "CUMMINSIND", "DIVISLAB", "DLF", "DMART", "DRREDDY", "EICHERMOT", "ENRIN",
    "ETERNAL", "GAIL", "GODREJCP", "GRASIM", "HAL", "HCLTECH", "HDFCAMC", "HDFCBANK",
    "HDFCLIFE", "HINDALCO", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK", "IDEA",
    "INDIGO", "INFY", "IOC", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JSWSTEEL",
    "KOTAKBANK", "LT", "LTM", "M&M", "MARUTI", "MAXHEALTH", "MAZDOCK", "MOTHERSON",
    "MUTHOOTFIN", "NESTLEIND", "NTPC", "ONGC", "PFC", "PIDILITIND", "PNB", "POLYCAB",
    "POWERGRID", "POWERINDIA", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN", "SIEMENS",
    "SOLARINDS", "SUNPHARMA", "TATACAP", "TATACONSUM", "TATAPOWER", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TMCV", "TMPV", "TORNTPHARM", "TRENT", "TVSMOTOR", "ULTRACEMCO",
    "UNIONBANK", "VAML", "VBL", "VEDL", "WIPRO", "ZYDUSLIFE",
)

MANUAL_REL_PATH = Path("data") / "reference" / "corp_actions_manual.csv"
OUTPUT_REL_PATH = Path("data") / "reference" / "corp_actions.csv"
FETCH_LOG_REL_PATH = Path("data") / "reference" / "corp_actions_fetch_log.csv"

log = logging.getLogger("corp_actions")


class CorpActionSchemaError(ValueError):
    """Raised when a corporate-action table violates the schema contract."""


# --------------------------------------------------------------------------------------
# Ratio convention helpers (the single place the convention is implemented)
# --------------------------------------------------------------------------------------


def ratio_for_split(new_shares_per_old: float) -> float:
    """R for an r-for-1 split: 1 old share becomes ``new_shares_per_old`` new shares."""
    r = float(new_shares_per_old)
    if r <= 0:
        raise ValueError(f"split factor must be > 0, got {r!r}")
    return r


def ratio_for_bonus(new: float, held: float) -> float:
    """R for an ``new:held`` bonus -- ``new`` new shares for every ``held`` held."""
    new_f, held_f = float(new), float(held)
    if new_f <= 0 or held_f <= 0:
        raise ValueError(f"bonus ratio parts must be > 0, got {new!r}:{held!r}")
    return (new_f + held_f) / held_f


def ratio_for_demerger(parent_retained_fraction: float) -> float:
    """R for a demerger where the parent retains ``f`` of its pre-event value."""
    f = float(parent_retained_fraction)
    if not 0.0 < f < 1.0:
        raise ValueError(f"parent retained fraction must be in (0, 1), got {f!r}")
    return 1.0 / f


def ratio_from_prices(price_cum: float, price_ex: float) -> float:
    """R straight from the convention: last cum price / adjusted ex price."""
    pc, pe = float(price_cum), float(price_ex)
    if pc <= 0 or pe <= 0:
        raise ValueError(f"prices must be > 0, got cum={pc!r} ex={pe!r}")
    return pc / pe


def cumulative_divisor(
    actions: pd.DataFrame, as_of: pd.Timestamp, types: Iterable[str] = STRUCTURAL_TYPES
) -> float:
    """Product of R over every action of ``types`` whose ex-date is strictly after ``as_of``.

    This is the number a price on ``as_of`` must be DIVIDED by to sit on the
    present-day scale.  Returns 1.0 when no later action applies.
    """
    if actions.empty:
        return 1.0
    wanted = set(types)
    mask = actions["action_type"].isin(wanted) & (actions["ex_date"] > pd.Timestamp(as_of))
    vals = pd.to_numeric(actions.loc[mask, "ratio"], errors="coerce").dropna()
    if vals.empty:
        return 1.0
    return float(np.prod(vals.to_numpy(dtype=float)))


def apply_adjustment(
    prices: pd.Series, actions: pd.DataFrame, types: Iterable[str] = STRUCTURAL_TYPES
) -> pd.Series:
    """Divide each price by the cumulative divisor of all actions after its own date.

    ``prices`` must be indexed by date.  Convenience helper so consumers do not
    re-implement the convention; the price-adjustment module may or may not use it.
    """
    if prices.empty:
        return prices.copy()
    idx = pd.DatetimeIndex(prices.index)
    divisors = np.array([cumulative_divisor(actions, d, types) for d in idx], dtype=float)
    return pd.Series(prices.to_numpy(dtype=float) / divisors, index=prices.index, name=prices.name)


# --------------------------------------------------------------------------------------
# Ex-date derivation
# --------------------------------------------------------------------------------------


def ex_date_from_record_date(record_date) -> pd.Timestamp:
    """Derive the ex-date from a record date using the Indian settlement-regime rule.

    T+1 era (record date >= 2023-01-27): ex-date == record date.
    T+2 era: ex-date is the previous TRADING session.  Approximated as the previous
    weekday -- exchange holidays are not modelled here, so a row derived this way is
    flagged ``DERIVED_FROM_RECORD_DATE`` and may be off by one session near a holiday.
    """
    rd = pd.Timestamp(record_date).normalize()
    if rd >= T1_SETTLEMENT_START:
        return rd
    prev = rd - pd.Timedelta(days=1)
    while prev.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        prev -= pd.Timedelta(days=1)
    return prev


# --------------------------------------------------------------------------------------
# Schema validation
# --------------------------------------------------------------------------------------


def _empty_frame() -> pd.DataFrame:
    df = pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})
    df["ex_date"] = pd.Series(dtype="datetime64[ns]")
    df["ratio"] = pd.Series(dtype="float64")
    df["dividend_amount"] = pd.Series(dtype="float64")
    return df[COLUMNS]


def validate_schema(df: pd.DataFrame, where: str = "<frame>") -> pd.DataFrame:
    """Validate and normalise a corporate-action table.  Hard-fails on malformed rows.

    Returns a normalised copy: exact column order, ``ex_date`` as ``datetime64[ns]``,
    ``ratio``/``dividend_amount`` as float64 with NaN for blank, string columns stripped.
    """
    problems: list[str] = []

    if not isinstance(df, pd.DataFrame):
        raise CorpActionSchemaError(f"{where}: expected a DataFrame, got {type(df).__name__}")

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise CorpActionSchemaError(
            f"{where}: missing required column(s): {missing}. "
            f"Expected exactly {COLUMNS}, got {list(df.columns)}"
        )
    extra = [c for c in df.columns if c not in COLUMNS]
    if extra:
        raise CorpActionSchemaError(
            f"{where}: unexpected extra column(s): {extra}. Expected exactly {COLUMNS}"
        )

    out = df.loc[:, COLUMNS].copy()
    if out.empty:
        return _empty_frame()

    # --- strings -----------------------------------------------------------------
    for col in ("symbol", "action_type", "source", "source_url", "confidence"):
        out[col] = out[col].fillna("").astype(str).str.strip()

    # --- symbol ------------------------------------------------------------------
    bad = out.index[out["symbol"] == ""]
    if len(bad):
        problems.append(f"empty `symbol` at row(s) {list(bad)[:10]}")

    # --- ex_date -----------------------------------------------------------------
    parsed = pd.to_datetime(out["ex_date"], format="%Y-%m-%d", errors="coerce")
    retry = parsed.isna() & out["ex_date"].notna()
    if retry.any():
        parsed.loc[retry] = pd.to_datetime(out.loc[retry, "ex_date"], errors="coerce")
    bad_dates = out.index[parsed.isna()]
    if len(bad_dates):
        shown = out.loc[bad_dates, "ex_date"].astype(str).tolist()[:10]
        problems.append(
            f"unparseable `ex_date` (expected ISO YYYY-MM-DD) at row(s) "
            f"{list(bad_dates)[:10]} -> {shown}"
        )
    out["ex_date"] = parsed.dt.normalize()

    # --- action_type -------------------------------------------------------------
    bad_types = out.index[~out["action_type"].isin(ACTION_TYPES)]
    if len(bad_types):
        shown = out.loc[bad_types, "action_type"].tolist()[:10]
        problems.append(
            f"invalid `action_type` at row(s) {list(bad_types)[:10]} -> {shown}; "
            f"allowed: {sorted(ACTION_TYPES)}"
        )

    # --- confidence --------------------------------------------------------------
    bad_conf = out.index[~out["confidence"].isin(CONFIDENCE_LEVELS)]
    if len(bad_conf):
        shown = out.loc[bad_conf, "confidence"].tolist()[:10]
        problems.append(
            f"invalid `confidence` at row(s) {list(bad_conf)[:10]} -> {shown}; "
            f"allowed: {sorted(CONFIDENCE_LEVELS)}"
        )

    # --- numerics ----------------------------------------------------------------
    for col in ("ratio", "dividend_amount"):
        raw = out[col]
        if raw.dtype == object:
            raw = raw.astype(str).str.strip().replace({"": None, "nan": None, "None": None})
        coerced = pd.to_numeric(raw, errors="coerce")
        was_present = out[col].notna() & (out[col].astype(str).str.strip() != "")
        broke = out.index[was_present & coerced.isna()]
        if len(broke):
            problems.append(
                f"non-numeric `{col}` at row(s) {list(broke)[:10]} -> "
                f"{out.loc[broke, col].astype(str).tolist()[:10]}"
            )
        out[col] = coerced.astype("float64")

    is_div = out["action_type"] == "dividend"
    is_struct = out["action_type"].isin(STRUCTURAL_TYPES)

    bad = out.index[is_div & out["ratio"].notna()]
    if len(bad):
        problems.append(f"`ratio` must be empty for action_type='dividend' at row(s) {list(bad)[:10]}")

    bad = out.index[is_div & (out["dividend_amount"].isna() | (out["dividend_amount"] <= 0))]
    if len(bad):
        problems.append(
            f"`dividend_amount` must be present and > 0 for action_type='dividend' "
            f"at row(s) {list(bad)[:10]}"
        )

    bad = out.index[is_struct & out["dividend_amount"].notna()]
    if len(bad):
        problems.append(
            f"`dividend_amount` must be empty for structural actions at row(s) {list(bad)[:10]}"
        )

    bad = out.index[is_struct & out["ratio"].notna() & (out["ratio"] <= 0)]
    if len(bad):
        problems.append(f"`ratio` must be > 0 for structural actions at row(s) {list(bad)[:10]}")

    # A missing structural ratio is tolerated ONLY on an explicitly UNVERIFIED row.
    bad = out.index[is_struct & out["ratio"].isna() & (out["confidence"] != "UNVERIFIED")]
    if len(bad):
        problems.append(
            f"`ratio` is required for structural actions unless confidence='UNVERIFIED' "
            f"at row(s) {list(bad)[:10]}"
        )

    # --- citation --------------------------------------------------------------
    bad = out.index[(out["confidence"] != "UNVERIFIED") & (out["source_url"] == "")]
    if len(bad):
        problems.append(
            f"`source_url` is required unless confidence='UNVERIFIED' at row(s) {list(bad)[:10]}"
        )

    if problems:
        raise CorpActionSchemaError(
            f"{where}: {len(problems)} schema violation(s):\n  - " + "\n  - ".join(problems)
        )

    return out[COLUMNS]


# --------------------------------------------------------------------------------------
# Manual CSV
# --------------------------------------------------------------------------------------


def manual_path(root: Path) -> Path:
    return Path(root) / MANUAL_REL_PATH


def load_manual(root: Path) -> pd.DataFrame:
    """Read and validate the hand-curated, source-cited corporate-action CSV."""
    path = manual_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"manual corporate-action CSV not found at {path}. This file is the source of "
            f"truth for bonuses/demergers and cannot be regenerated from price data."
        )
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    raw = raw.replace({"": None})
    df = validate_schema(raw, where=str(path))
    log.info("manual CSV: %d row(s) from %s", len(df), path)
    return df


# --------------------------------------------------------------------------------------
# yfinance side
# --------------------------------------------------------------------------------------


def fetch_yfinance_actions(
    symbols: Sequence[str] = UNIVERSE,
    *,
    suffix: str = ".NS",
    retries: int = 3,
    backoff: float = 1.5,
    include_dividends: bool = True,
    sleep: Optional[callable] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pull ``.splits`` and ``.dividends`` for every symbol.

    Returns ``(actions, fetch_log)``.  ``fetch_log`` has one row per symbol with the
    outcome (``ok`` / ``failed``), the counts found and the last error string.  A symbol
    that failed every retry is recorded as ``failed`` -- it is never allowed to look
    indistinguishable from a symbol that genuinely has no actions.

    Every row produced here is ``confidence="UNVERIFIED"``: ``.splits`` on NSE tickers
    conflates bonus issues with splits and is incomplete (see module docstring).
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "yfinance is required by fetch_yfinance_actions(). Install it, or call "
            "build(root, use_yfinance=False) to build from the manual CSV alone."
        ) from exc

    napper = sleep if sleep is not None else time.sleep
    rows: list[dict] = []
    logrows: list[dict] = []

    for sym in symbols:
        ticker = f"{sym}{suffix}"
        last_err = ""
        n_splits = n_divs = 0
        status = "failed"

        for attempt in range(1, max(1, retries) + 1):
            try:
                t = yf.Ticker(ticker)
                splits = t.splits
                divs = t.dividends if include_dividends else None

                if splits is not None and len(splits):
                    for ts, factor in splits.items():
                        try:
                            f = float(factor)
                        except (TypeError, ValueError):
                            continue
                        if not np.isfinite(f) or f <= 0:
                            continue
                        n_splits += 1
                        rows.append(
                            {
                                "symbol": sym,
                                "ex_date": pd.Timestamp(ts).tz_localize(None).normalize(),
                                "action_type": "split",
                                "ratio": f,
                                "dividend_amount": np.nan,
                                "source": "yfinance;.splits;MAY_CONFLATE_BONUS_WITH_SPLIT",
                                "source_url": f"https://finance.yahoo.com/quote/{ticker}",
                                "confidence": "UNVERIFIED",
                            }
                        )

                if divs is not None and len(divs):
                    for ts, amt in divs.items():
                        try:
                            a = float(amt)
                        except (TypeError, ValueError):
                            continue
                        if not np.isfinite(a) or a <= 0:
                            continue
                        n_divs += 1
                        rows.append(
                            {
                                "symbol": sym,
                                "ex_date": pd.Timestamp(ts).tz_localize(None).normalize(),
                                "action_type": "dividend",
                                "ratio": np.nan,
                                "dividend_amount": a,
                                "source": "yfinance;.dividends",
                                "source_url": f"https://finance.yahoo.com/quote/{ticker}",
                                "confidence": "UNVERIFIED",
                            }
                        )

                status = "ok"
                last_err = ""
                break
            except Exception as exc:  # noqa: BLE001 - we must log, not crash the run
                last_err = f"{type(exc).__name__}: {exc}"
                log.warning("fetch %s attempt %d/%d failed: %s", ticker, attempt, retries, last_err)
                if attempt < retries:
                    napper(backoff * attempt)

        if status == "failed":
            log.error("fetch %s FAILED after %d attempt(s): %s", ticker, retries, last_err)

        logrows.append(
            {
                "symbol": sym,
                "ticker": ticker,
                "status": status,
                "n_splits": n_splits,
                "n_dividends": n_divs,
                "attempts": retries if status == "failed" else attempt,
                "error": last_err,
                "fetched_at_utc": pd.Timestamp.utcnow().tz_localize(None).isoformat(timespec="seconds"),
            }
        )

    actions = pd.DataFrame(rows, columns=COLUMNS) if rows else _empty_frame()
    if not actions.empty:
        actions = validate_schema(actions, where="yfinance fetch")
    fetch_log = pd.DataFrame(
        logrows,
        columns=[
            "symbol", "ticker", "status", "n_splits", "n_dividends",
            "attempts", "error", "fetched_at_utc",
        ],
    )
    n_failed = int((fetch_log["status"] == "failed").sum()) if len(fetch_log) else 0
    log.info("yfinance: %d action row(s); %d symbol(s) failed", len(actions), n_failed)
    return actions, fetch_log


# --------------------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------------------


def merge_actions(
    yf_actions: pd.DataFrame,
    manual_actions: pd.DataFrame,
    *,
    near_date_days: int = NEAR_DATE_DAYS,
) -> pd.DataFrame:
    """Merge the yfinance-derived table with the manual table. Manual always wins.

    See PRECEDENCE RULE in the module docstring.  Pure function: no IO, no network.
    """
    man = validate_schema(yf_actions if False else manual_actions, where="manual_actions")
    yfa = validate_schema(yf_actions, where="yf_actions")

    if yfa.empty:
        merged = man.copy()
    elif man.empty:
        merged = yfa.copy()
    else:
        # Rule 2: drop any yfinance row colliding with manual on (symbol, ex_date).
        man_sym_date = set(zip(man["symbol"], man["ex_date"]))
        drop = pd.Series(
            [(s, d) in man_sym_date for s, d in zip(yfa["symbol"], yfa["ex_date"])],
            index=yfa.index,
        )

        # Rule 3: drop yfinance rows near a manual row of the same (symbol, action_type).
        if near_date_days > 0:
            tol = pd.Timedelta(days=near_date_days)
            by_key: dict[tuple[str, str], np.ndarray] = {}
            for (sym, atype), grp in man.groupby(["symbol", "action_type"], sort=False):
                by_key[(sym, atype)] = grp["ex_date"].to_numpy()
            for i, (sym, atype, exd) in enumerate(
                zip(yfa["symbol"], yfa["action_type"], yfa["ex_date"])
            ):
                if drop.iat[i]:
                    continue
                cand = by_key.get((sym, atype))
                if cand is None or len(cand) == 0:
                    continue
                if bool(np.any(np.abs(cand - np.datetime64(exd)) <= tol.to_timedelta64())):
                    drop.iat[i] = True

        kept = yfa.loc[~drop]
        n_dropped = int(drop.sum())
        if n_dropped:
            log.info("precedence: dropped %d yfinance row(s) superseded by manual rows", n_dropped)
        merged = pd.concat([man, kept], ignore_index=True)

    # Exact-duplicate removal, preferring the stronger confidence then the manual source.
    rank = {"VERIFIED": 0, "DERIVED_FROM_RECORD_DATE": 1, "UNVERIFIED": 2}
    merged = merged.assign(_r=merged["confidence"].map(rank).fillna(9).astype(int))
    merged = (
        merged.sort_values(["symbol", "ex_date", "action_type", "_r"], kind="mergesort")
        .drop_duplicates(subset=["symbol", "ex_date", "action_type", "ratio", "dividend_amount"],
                         keep="first")
        .drop(columns="_r")
        .sort_values(["symbol", "ex_date", "action_type"], kind="mergesort")
        .reset_index(drop=True)
    )
    return merged[COLUMNS]


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["ex_date"] = out["ex_date"].dt.strftime("%Y-%m-%d")
    for col in ("ratio", "dividend_amount"):
        out[col] = out[col].map(lambda v: "" if pd.isna(v) else f"{float(v):.6f}".rstrip("0").rstrip("."))
    out.to_csv(path, index=False)


def build(
    root: Path,
    *,
    symbols: Sequence[str] = UNIVERSE,
    use_yfinance: bool = True,
    retries: int = 3,
) -> pd.DataFrame:
    """Merge yfinance actions with the manual CSV, dedupe, sort, write, return.

    Writes ``<root>/data/reference/corp_actions.csv`` and, when ``use_yfinance`` is on,
    ``<root>/data/reference/corp_actions_fetch_log.csv``.
    """
    root = Path(root)
    manual = load_manual(root)

    if use_yfinance:
        yfa, fetch_log = fetch_yfinance_actions(symbols, retries=retries)
        log_path = root / FETCH_LOG_REL_PATH
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fetch_log.to_csv(log_path, index=False)
        failed = fetch_log.loc[fetch_log["status"] == "failed", "symbol"].tolist()
        if failed:
            log.error(
                "%d symbol(s) failed to fetch and have NO yfinance actions in this build: %s "
                "(see %s)", len(failed), ", ".join(failed), log_path,
            )
    else:
        yfa = _empty_frame()

    merged = merge_actions(yfa, manual)
    out_path = root / OUTPUT_REL_PATH
    _write(merged, out_path)
    log.info("wrote %d row(s) to %s", len(merged), out_path)
    return merged


def load_corp_actions(root: Path) -> pd.DataFrame:
    """Read the merged ``corp_actions.csv``, validate schema and dtypes, hard-fail if bad."""
    path = Path(root) / OUTPUT_REL_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python {Path(__file__).name}` (or call build(root)) first."
        )
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    raw = raw.replace({"": None})
    df = validate_schema(raw, where=str(path))
    return df.sort_values(["symbol", "ex_date", "action_type"], kind="mergesort").reset_index(drop=True)


def actions_for(df: pd.DataFrame, symbol: str, start=None, end=None) -> pd.DataFrame:
    """Rows for ``symbol``, optionally restricted to ex-dates in ``[start, end]`` inclusive."""
    out = df.loc[df["symbol"].astype(str) == str(symbol)].copy()
    if start is not None:
        out = out.loc[out["ex_date"] >= pd.Timestamp(start).normalize()]
    if end is not None:
        out = out.loc[out["ex_date"] <= pd.Timestamp(end).normalize()]
    return out.sort_values(["ex_date", "action_type"], kind="mergesort").reset_index(drop=True)


# ======================================================================================
# Self-test -- SYNTHETIC in-memory data only.  No network, no real files.
# ======================================================================================

_PASS = 0
_FAIL = 0


def _check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS  {name}")
    else:
        _FAIL += 1
        print(f"FAIL  {name}" + (f"  -- {detail}" if detail else ""))


def _syn(symbol, ex_date, action_type, ratio=None, dividend_amount=None,
         source="synthetic", source_url="https://example.invalid/x", confidence="VERIFIED"):
    return {
        "symbol": symbol, "ex_date": ex_date, "action_type": action_type,
        "ratio": ratio, "dividend_amount": dividend_amount,
        "source": source, "source_url": source_url, "confidence": confidence,
    }


def _frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=COLUMNS)


def _selftest_schema() -> None:
    print("\n--- schema validation ---")

    good = _frame([
        _syn("AAA", "2024-10-28", "bonus", ratio=2.0),
        _syn("AAA", "2023-07-20", "demerger", ratio=1.101492),
        _syn("BBB", "2022-07-28", "split", ratio=10.0),
        _syn("BBB", "2021-06-10", "dividend", dividend_amount=6.5),
        _syn("CCC", "2019-12-20", "demerger", confidence="UNVERIFIED", source_url=""),
    ])
    try:
        v = validate_schema(good, where="good")
        ok = (
            list(v.columns) == COLUMNS
            # resolution-agnostic: pandas >= 3.0 normalises to datetime64[us]
            and pd.api.types.is_datetime64_any_dtype(v["ex_date"])
            and str(v["ratio"].dtype) == "float64"
            and str(v["dividend_amount"].dtype) == "float64"
            and pd.isna(v.loc[v["action_type"] == "dividend", "ratio"]).all()
        )
        _check("accepts a well-formed frame with correct dtypes", ok, f"cols={list(v.columns)}")
    except CorpActionSchemaError as exc:
        _check("accepts a well-formed frame with correct dtypes", False, str(exc))

    _check("empty frame normalises to the exact schema",
           list(validate_schema(_frame([]), where="empty").columns) == COLUMNS)

    bad_cases = {
        "rejects unknown action_type":
            _frame([_syn("AAA", "2024-01-01", "spinoff", ratio=2.0)]),
        "rejects unknown confidence":
            _frame([_syn("AAA", "2024-01-01", "bonus", ratio=2.0, confidence="PROBABLY")]),
        "rejects non-ISO ex_date":
            _frame([_syn("AAA", "28-10-2024-xx", "bonus", ratio=2.0)]),
        "rejects empty symbol":
            _frame([_syn("", "2024-01-01", "bonus", ratio=2.0)]),
        "rejects ratio on a dividend row":
            _frame([_syn("AAA", "2024-01-01", "dividend", ratio=2.0, dividend_amount=5.0)]),
        "rejects dividend row with no amount":
            _frame([_syn("AAA", "2024-01-01", "dividend")]),
        "rejects dividend_amount on a structural row":
            _frame([_syn("AAA", "2024-01-01", "bonus", ratio=2.0, dividend_amount=5.0)]),
        "rejects non-positive ratio":
            _frame([_syn("AAA", "2024-01-01", "split", ratio=0.0)]),
        "rejects non-numeric ratio":
            _frame([_syn("AAA", "2024-01-01", "split", ratio="two")]),
        "rejects missing ratio when confidence is not UNVERIFIED":
            _frame([_syn("AAA", "2024-01-01", "bonus", confidence="VERIFIED")]),
        "rejects missing source_url when confidence is not UNVERIFIED":
            _frame([_syn("AAA", "2024-01-01", "bonus", ratio=2.0, source_url="")]),
    }
    for name, frame in bad_cases.items():
        try:
            validate_schema(frame, where="bad")
            _check(name, False, "no exception raised")
        except CorpActionSchemaError:
            _check(name, True)

    missing_col = _frame([_syn("AAA", "2024-01-01", "bonus", ratio=2.0)]).drop(columns=["confidence"])
    try:
        validate_schema(missing_col, where="bad")
        _check("rejects a missing column", False, "no exception raised")
    except CorpActionSchemaError as exc:
        _check("rejects a missing column", "confidence" in str(exc), str(exc))

    extra_col = _frame([_syn("AAA", "2024-01-01", "bonus", ratio=2.0)]).assign(notes="hi")
    try:
        validate_schema(extra_col, where="bad")
        _check("rejects an extra column", False, "no exception raised")
    except CorpActionSchemaError:
        _check("rejects an extra column", True)


def _selftest_ex_date_derivation() -> None:
    print("\n--- ex-date / record-date derivation ---")

    # T+2 era: ex-date is the previous trading session.
    _check("T+2: record Wed 2022-09-14 -> ex Tue 2022-09-13 (BAJAJFINSV shape)",
           ex_date_from_record_date("2022-09-14") == pd.Timestamp("2022-09-13"))
    _check("T+2: record Mon 2016-10-19 -> ex prior weekday",
           ex_date_from_record_date("2016-10-19") == pd.Timestamp("2016-10-18"))
    _check("T+2: record Mon 2016-08-29 -> ex Fri 2016-08-26 (weekend skipped)",
           ex_date_from_record_date("2016-08-29") == pd.Timestamp("2016-08-26"))
    _check("T+2: ex-date never lands on a weekend",
           ex_date_from_record_date("2019-09-23").weekday() < 5)

    # T+1 era: they coincide.
    _check("T+1: record 2025-10-14 -> ex 2025-10-14 (TMPV shape)",
           ex_date_from_record_date("2025-10-14") == pd.Timestamp("2025-10-14"))
    _check("T+1: record 2025-06-16 -> ex 2025-06-16 (BAJFINANCE shape)",
           ex_date_from_record_date("2025-06-16") == pd.Timestamp("2025-06-16"))
    _check("regime boundary 2023-01-27 is already T+1",
           ex_date_from_record_date("2023-01-27") == pd.Timestamp("2023-01-27"))
    _check("day before the boundary is still T+2",
           ex_date_from_record_date("2023-01-26") < pd.Timestamp("2023-01-26"))
    _check("derived ex-date is never after the record date",
           ex_date_from_record_date("2018-03-17") <= pd.Timestamp("2018-03-17"))


def _selftest_precedence() -> None:
    print("\n--- precedence on conflict ---")

    manual = _frame([
        # Manual says this 2024-10-28 event is a 1:1 BONUS (R=2).
        _syn("RELX", "2024-10-28", "bonus", ratio=2.0, source="manual"),
        _syn("TSTL", "2022-07-28", "split", ratio=10.0, source="manual"),
        _syn("SIEX", "2025-04-07", "demerger", ratio=2.0115, source="manual"),
    ])
    yfa = _frame([
        # yfinance mislabels the same event as a SPLIT of 2.0 -- must be dropped.
        _syn("RELX", "2024-10-28", "split", ratio=2.0,
             source="yfinance", confidence="UNVERIFIED"),
        # Same symbol+type one session off -- must also be dropped (near-date rule).
        _syn("TSTL", "2022-07-29", "split", ratio=10.0,
             source="yfinance", confidence="UNVERIFIED"),
        # Genuinely new lead on an untouched symbol -- must survive.
        _syn("NEWC", "2020-08-24", "split", ratio=10.0,
             source="yfinance", confidence="UNVERIFIED"),
        # Dividends are never suppressed by a structural manual row on another date.
        _syn("SIEX", "2024-02-15", "dividend", dividend_amount=12.0,
             source="yfinance", confidence="UNVERIFIED"),
    ])

    merged = merge_actions(yfa, manual)

    relx = actions_for(merged, "RELX")
    _check("conflicting yfinance 'split' dropped in favour of manual 'bonus'",
           len(relx) == 1 and relx.loc[0, "action_type"] == "bonus",
           f"got {relx[['action_type', 'source']].to_dict('records')}")
    _check("manual row keeps its own source/confidence",
           relx.loc[0, "confidence"] == "VERIFIED" and relx.loc[0, "source"] == "manual")

    tstl = actions_for(merged, "TSTL")
    _check("off-by-one-session yfinance duplicate dropped (near-date rule)",
           len(tstl) == 1 and tstl.loc[0, "ex_date"] == pd.Timestamp("2022-07-28"),
           f"got {len(tstl)} row(s)")

    _check("a genuinely new yfinance lead survives and stays UNVERIFIED",
           len(actions_for(merged, "NEWC")) == 1
           and actions_for(merged, "NEWC").loc[0, "confidence"] == "UNVERIFIED")

    siex = actions_for(merged, "SIEX")
    _check("unrelated yfinance dividend is not suppressed",
           set(siex["action_type"]) == {"demerger", "dividend"},
           f"got {sorted(set(siex['action_type']))}")

    _check("merged table is sorted by (symbol, ex_date, action_type)",
           merged[["symbol", "ex_date", "action_type"]].equals(
               merged.sort_values(["symbol", "ex_date", "action_type"],
                                  kind="mergesort")[["symbol", "ex_date", "action_type"]]))

    _check("merging an empty yfinance table is a no-op on manual",
           len(merge_actions(_frame([]), manual)) == len(manual))
    _check("merging into an empty manual table keeps all yfinance rows",
           len(merge_actions(yfa, _frame([]))) == len(yfa))
    _check("merged table still passes schema validation",
           len(validate_schema(merged, where="merged")) == len(merged))

    # actions_for date windowing
    win = actions_for(merged, "SIEX", start="2025-01-01", end="2025-12-31")
    _check("actions_for respects the start/end window",
           len(win) == 1 and win.loc[0, "action_type"] == "demerger",
           f"got {win['action_type'].tolist()}")
    _check("actions_for on an unknown symbol returns an empty frame",
           actions_for(merged, "NOPE").empty)


def _selftest_ratio_roundtrip() -> None:
    print("\n--- ratio convention round-tripping ---")

    _check("ratio_for_split(5) == 5 (a '1:5 split', 1 share -> 5)", ratio_for_split(5) == 5.0)
    _check("ratio_for_bonus(1, 1) == 2 (1:1 bonus halves the price)", ratio_for_bonus(1, 1) == 2.0)
    _check("ratio_for_bonus(1, 2) == 1.5 (1:2 bonus, -33.33%)", ratio_for_bonus(1, 2) == 1.5)
    _check("ratio_for_bonus(2, 1) == 3 (2:1 bonus, -66.67%)", ratio_for_bonus(2, 1) == 3.0)
    _check("ratio_for_bonus(1, 3) == 4/3 (1:3 bonus, -25%)",
           abs(ratio_for_bonus(1, 3) - 4 / 3) < 1e-12)
    _check("ratio_for_bonus(1, 4) == 1.25 (1:4 bonus, -20%)", ratio_for_bonus(1, 4) == 1.25)
    _check("ratio_for_demerger(0.5) == 2 (parent retains half)",
           abs(ratio_for_demerger(0.5) - 2.0) < 1e-12)
    _check("ratio_for_demerger(f) == 1/f for f=0.6885",
           abs(ratio_for_demerger(0.6885) - 1 / 0.6885) < 1e-12)
    _check("ratio_from_prices agrees with ratio_for_demerger (RELIANCE/JIOFIN shape)",
           abs(ratio_from_prices(2841.85, 2580.0) - ratio_for_demerger(2580.0 / 2841.85)) < 1e-12)
    _check("a diluting action always gives R >= 1",
           min(ratio_for_split(2), ratio_for_bonus(1, 10), ratio_for_demerger(0.99)) >= 1.0)

    for bad_call, label in (
        (lambda: ratio_for_split(0), "ratio_for_split(0)"),
        (lambda: ratio_for_bonus(0, 1), "ratio_for_bonus(0, 1)"),
        (lambda: ratio_for_demerger(1.0), "ratio_for_demerger(1.0)"),
        (lambda: ratio_for_demerger(0.0), "ratio_for_demerger(0.0)"),
        (lambda: ratio_from_prices(100, 0), "ratio_from_prices(100, 0)"),
    ):
        try:
            bad_call()
            _check(f"{label} raises", False, "no exception raised")
        except ValueError:
            _check(f"{label} raises", True)

    # --- end-to-end: synthetic price path with a known combined reset -----------
    # BAJAJFINSV-shaped event: 1:5 split (R=5) AND 1:1 bonus (R=2) on one ex-date -> 10x.
    actions = _frame([
        _syn("SYN", "2022-09-13", "split", ratio=ratio_for_split(5)),
        _syn("SYN", "2022-09-13", "bonus", ratio=ratio_for_bonus(1, 1)),
        _syn("SYN", "2024-10-28", "bonus", ratio=ratio_for_bonus(1, 1)),
    ])
    actions = validate_schema(actions, where="roundtrip")

    _check("combined same-day split+bonus multiplies to a 10x divisor",
           abs(cumulative_divisor(actions, pd.Timestamp("2022-09-12"),
                                  types={"split", "bonus"}) / 2.0 - 10.0) < 1e-12,
           f"got {cumulative_divisor(actions, pd.Timestamp('2022-09-12'), types={'split','bonus'})}")
    _check("divisor after every action is 1.0",
           cumulative_divisor(actions, pd.Timestamp("2025-01-01")) == 1.0)
    _check("divisor on the ex-date itself excludes that action (strictly-after rule)",
           abs(cumulative_divisor(actions, pd.Timestamp("2024-10-28")) - 1.0) < 1e-12)

    # Build an economically flat series: raw price resets mechanically on each ex-date.
    dates = pd.to_datetime([
        "2022-09-12", "2022-09-13", "2024-10-27", "2024-10-28", "2025-01-02",
    ])
    raw = pd.Series([20000.0, 2000.0, 2000.0, 1000.0, 1000.0], index=dates, name="Close")
    adj = apply_adjustment(raw, actions)
    _check("adjustment flattens a purely mechanical series to a constant",
           float(adj.max() - adj.min()) < 1e-9,
           f"adjusted = {adj.round(6).tolist()}")
    _check("the most recent bar is left untouched by adjustment",
           abs(float(adj.iloc[-1]) - float(raw.iloc[-1])) < 1e-12)

    restored = adj * np.array(
        [cumulative_divisor(actions, d) for d in pd.DatetimeIndex(adj.index)], dtype=float
    )
    _check("round-trip: adjust then re-apply the divisor restores the raw series",
           bool(np.allclose(restored.to_numpy(), raw.to_numpy(), rtol=0, atol=1e-9)),
           f"restored = {restored.round(6).tolist()}")

    # A -33.87% observed drop should be explained by a 1:2 bonus (R=1.5 -> -33.33%).
    implied = 1.0 - 1.0 / ratio_for_bonus(1, 2)
    _check("1:2 bonus implies a ~-33.3% one-day price drop (TRENT shape)",
           abs(implied - 0.3333) < 0.001, f"implied {implied:.4%}")
    # A 1:5 split implies -80% (ADANIPOWER shape).
    _check("1:5 split implies a -80% one-day price drop (ADANIPOWER shape)",
           abs((1.0 - 1.0 / ratio_for_split(5)) - 0.80) < 1e-12)
    # A 4:1 bonus + 1:2 split implies -90% (BAJFINANCE shape).
    _check("4:1 bonus with a 1:2 split implies a -90% drop (BAJFINANCE shape)",
           abs((1.0 - 1.0 / (ratio_for_bonus(4, 1) * ratio_for_split(2))) - 0.90) < 1e-12)


def _selftest() -> int:
    print("=" * 78)
    print("02a_build_corp_actions.py self-test (SYNTHETIC in-memory data; no network, no files)")
    print("=" * 78)
    _selftest_schema()
    _selftest_ex_date_derivation()
    _selftest_precedence()
    _selftest_ratio_roundtrip()
    print("\n" + "-" * 78)
    print(f"{_PASS} passed, {_FAIL} failed")
    print("-" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if "--build" in sys.argv:
        offline = "--no-yfinance" in sys.argv
        df = build(ROOT, use_yfinance=not offline)
        print(f"\ncorp_actions.csv: {len(df)} row(s)")
        print(df.groupby(["action_type", "confidence"]).size().to_string())
        sys.exit(0)
    sys.exit(_selftest())
