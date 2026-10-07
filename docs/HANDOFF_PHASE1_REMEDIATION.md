# Task brief — complete the Phase 1 data-cleaning remediation

Paste this whole document to the agent as its instructions. It assumes no
prior context and assumes the agent can read and write the project folder.

---

## 0. Who you are and the rules you work under

You are a quantitative data engineer with expertise in Indian equity markets
(NSE/BSE) and in building survivorship-bias-free datasets for backtesting.
You are picking up a half-finished remediation of a data-cleaning pipeline.

**Three standing rules from the project owner. These are non-negotiable and
they override any instinct to look productive.**

1. **Never state an unverified thing as fact.** If you infer, label it
   INFERRED. If you verified it against a source or against the actual data,
   label it VERIFIED and name the source. If you cannot tell, say
   "CANNOT VERIFY" and say what check would settle it. Do not claim you tested
   something you did not run.
2. **Disclose assumptions and real limitations explicitly**, including your own
   access limitations. If you could not read a file, say so rather than
   reasoning around it silently.
3. **No fabricated numbers, ever.** This project exists because a previous
   version of it had invented backtest results. Every number you report must
   come from code you actually ran. If a script fails, report the failure.

A fourth rule, specific to this task: **do not mark anything complete that you
have not verified by running it.** The defect that caused most of this
remediation was a report claiming a pipeline had been re-run when it had not.

---

## 1. The project, in one page

**Goal.** Predict Up / Sideways / Down for each stock over the next 10 trading
days, for NSE-listed Indian equities. Intended for academic publication — it
must beat a base paper on accuracy and/or alpha (risk-adjusted excess return).

**Owner.** Final-year B.Tech CS student plus one teammate. The project folder
is `C:\Users\BhansaLi\Desktop\Market Prediction Model`.

**Frozen specification — do not change any of this without asking:**

| Parameter | Value |
|---|---|
| Universe | NIFTY 100 |
| Bar frequency | Daily |
| History | 2015-01-01 → present (Oct 2026) |
| Holdout | 2025-04-01 onward |
| Labels | Triple-barrier: +2×ATR up, −1×ATR down, 10-day timeout = Sideways |
| Label horizon | 10 trading days |
| Costs | 0.35% per round trip (0.25% real + 0.10% assumed slippage) |
| Direction | Long-only (no cash-segment shorting) |
| Settlement | T+1 (T+2 before Jan 2023) |
| Data source | Yahoo Finance via `yfinance`, `auto_adjust=False` |

**Architecture (later phases, context only).** A technical agent + a
BERT-based news/fundamental agent + a risk agent, fused by a stacking model on
calibrated per-agent probabilities.

**Two standing data policies set by the owner:**

- **"Assume the Yahoo source is true."** No NSE cross-verification of price
  levels in this pass. This does *not* mean assume Yahoo's *adjustments* are
  correct — the whole problem below is that they are not.
- **Real news-driven moves stay in as genuine signal.** Fraud, tax raids,
  elections, Hindenburg, COVID, DOJ indictments — all of it is real market
  history and valuable training signal. Only **unadjusted corporate-action
  artifacts** (a mechanical price reset that Yahoo failed to adjust for) are
  defects to be corrected or excluded. Never "clean away" a real crash.

---

## 2. What is in the folder, and what to read first

```
Market Prediction Model/
├─ CLAUDE.md                                  project context for a fresh session
├─ scripts/
│  ├─ 01_download_prices.py                   checkpoint 1.1 — RUN, outputs exist
│  ├─ 02_clean_adjust.py                       checkpoint 1.2 — BROKEN, see §3 F02
│  ├─ 02a_build_corp_actions.py                NEW, done, self-tests pass
│  └─ 02b_adjust_prices.py                     NEW, done, self-tests pass
├─ data/
│  ├─ raw/yahoo/*.csv                          103 files: 100 stocks + 3 indices
│  ├─ clean/*.csv                              100 files — STALE, see §3 F01
│  └─ reference/
│     ├─ ind_nifty100list.csv                  100 rows, has an `Industry` column
│     └─ corp_actions_manual.csv               NEW, 58 sourced actions
├─ docs/
│  ├─ Phase0_Report.md
│  ├─ Stock_MultiAgent_Phase_Plan.pdf          the frozen phase plan, ~43 checkpoints
│  └─ HANDOFF_PHASE1_REMEDIATION.md            this document
└─ reports/phase1/
   ├─ 01_download_log.csv, 01_download_summary.txt
   ├─ checkpoint_1_2_report.md                 STALE — contradicts 1.2b
   ├─ checkpoint_1_2_summary.csv               STALE — all 100 rows exclude=False
   ├─ checkpoint_1_2_corp_action_events.csv    STALE
   ├─ checkpoint_1_2b_discontinuity_report.md  claims a re-run that did not happen
   └─ checkpoint_1_2c_audit_report.md          THE AUDIT. Read this first.
```

**Read in this order before writing a line of code:**

1. `reports/phase1/checkpoint_1_2c_audit_report.md` — the full audit, 16
   findings with severities, consequences and confidence tags. Everything in
   §3 below is a condensation of it.
2. `scripts/02_clean_adjust.py` — the broken script you are replacing.
3. `scripts/02a_build_corp_actions.py` and `scripts/02b_adjust_prices.py` —
   the two modules already written. Read their module docstrings and their
   public function signatures. **Do not modify these two files** unless you
   find a genuine bug, and if you do, say so explicitly rather than quietly
   rewriting them.
4. `data/reference/corp_actions_manual.csv` — 58 rows, the new source of truth.
5. `reports/phase1/checkpoint_1_2_summary.csv` — the stale output, useful
   because several audit findings are proved from its arithmetic.

---

## 3. The problem, in detail

A pipeline was built in two checkpoints. Checkpoint 1.1 (download) works.
Checkpoint 1.2 (clean and adjust) has fifteen defects, five of them blockers.
An independent audit found them; two have been fixed; the rest are yours.

### Already fixed — do not redo

**F03 (BLOCKER) — the adjustment was fundamentally wrong.** The old script
computed `Factor = Adj Close / Close` and multiplied OHLC by it to build an
"adjusted" series. On these NSE series that factor captures **cash dividends
only**. Splits appear to be pre-folded into `Close` itself. Bonus issues and
demergers are adjusted **nowhere** — they sit in the series as fake one-day
crashes of −33% to −72%.

The proof: Bajaj Finserv executed a 1:5 split *and* a 1:1 bonus on ex-date
2022-09-13 — a combined 10× price reset. The old pipeline detected **zero**
corporate-action events and **zero** big moves for `BAJAJFINSV`. If `Close`
were raw, one or the other would have fired.

Why it matters: every bonus ex-date is a permanent fabricated crash in both
series. Triple-barrier labelling stamps a hard Down on the 10 sessions before
every such date, the technical agent learns to "predict" bonus ex-dates, and a
long-only backtest books a 33–90% fictitious loss. Reliance — the largest
index weight — has two 1:1 bonuses and a demerger in the window.

*Fixed by:* `02a_build_corp_actions.py` (builds an explicit, source-cited
corporate-action table — 58 verified actions across 32 symbols) and
`02b_adjust_prices.py` (rebuilds the adjusted series from that table instead
of from `AdjClose/Close`). **F08** (label/execution series mismatch) and
**F12** (unadjusted volume) are fixed in the same module.

**Important caveat you must handle:** the F03 conclusion is **INFERRED**, not
confirmed against the real data — the auditor could not read the price CSVs.
`02b_adjust_prices.py` ships `detect_prefolded_splits()` precisely to settle
it empirically. Running that is your first task (§4, step 1).

### Your work — the thirteen remaining findings

Grouped into four work packages. Each package is one new module file, so
nothing you write collides with anything else.

---

#### PACKAGE A — trading calendar and coverage accounting
**New file: `scripts/02c_calendar.py`**

**F06 (HIGH) — the calendar reindex silently deletes ~11 real trading sessions
per stock.** The old code built the master calendar from a single Yahoo index
file (`NIFTY50.csv`) and then did `df.reindex(calendar)` per stock, which drops
any stock trading date absent from that index series.

Proved from the committed summary's arithmetic: `rows_after_price_reject +
halted_days` should equal `len(calendar)`, but it varies with history length —
2899 for VAML (83 rows), 2902 for several mid-history names, up to
2910 + 0 = 2910 for every full-history stock. The only consistent reading is
`len(calendar) = 2899`, so **every full-history stock lost 11 of its own real
trading dates**, silently, uncounted.

~One lost session per year points at the Diwali **Muhurat** special sessions
(one per Samvat year; 2020-11-14, 2021-11-04, 2022-10-24, 2023-11-12,
2024-11-01, 2025-10-21 are confirmed — verify the rest yourself).
*Consequence:* returns spanning a deleted session become silent two-session
returns, ATR and every rolling window are computed over an unaudited calendar,
and the "execution series" is missing sessions on which trades were possible.

**F07 (HIGH) — `Halted` is a mislabelled "not yet listed" flag.** The old code
reindexed every stock onto the full calendar and set `Halted = Close.isna()`.
The 23 per-stock counts in the report sum to **exactly 29,623**, equal to the
reported total — so the other 77 stocks have exactly 0, and every one of those
29,623 "halted" rows is **pre-listing padding**. Zero are real trading
suspensions. The headline figure is meaningless and there is no suspension
detection anywhere in the pipeline.

Those padded rows also carry NaN in `Open/High/Low/Close/Volume/Factor/
AdjClose`. *The dangerous consequence:* if anything downstream calls `ffill()`
before computing ATR — the obvious thing to write — the leading NaN block
becomes a run of identical synthetic bars, ATR collapses toward zero, and the
±ATR triple barriers go degenerate, labelling Up/Down on microscopic noise.

Short-history symbols, for reference: VAML 83 rows, TMCV 229, TATACAP 249,
ENRIN 328, HYUNDAI 491, JIOFIN 778, ETERNAL 1293, IRFC 1411, MAZDOCK 1487,
MAXHEALTH 1522, POWERINDIA 1619, POLYCAB 1853, HDFCAMC 2021, ADANIGREEN 2056,
HAL 2110, HDFCLIFE 2200, SBILIFE 2232, DMART 2365, BSE 2395, VBL 2456,
LTM 2528, INDIGO 2697, ADANIENSOL 2766. Full history is 2910 rows.

**F11 (MEDIUM) — a pandas enlargement bug that can append a corrupt row.** The
old code did `full.loc[pd.Timestamp(date), "CorpActionFlag"] = 1` on a
reindexed `DatetimeIndex`. With a label **not present** in the index, pandas
performs *setitem-with-enlargement*: it appends a new row at the end, NaN in
every other column, chronologically out of order, with `Halted = NaN` because
it is written after `Halted` is computed. It lands in the output CSV, and a
later `sort_index()` inserts an all-NaN bar mid-series. F06 proves up to 11
event dates per stock can be absent from the calendar, so this is reachable.

**F14 (MEDIUM) — the index series are never validated and never cleaned.**
`NIFTY50.csv` becomes the master calendar with zero validation: no row-count
assertion, no start-date check, no duplicate check, no weekend check. One
bogus date injects a spurious padded row into all 100 stocks. Worse,
`^CNX100` (NIFTY100) and `^INDIAVIX` are downloaded and then **skipped
entirely** by the cleaning script (`INDEX_NAMES` → `continue`), so they are
never aligned, never audited and never available — yet the project's
relative-strength and regime indicator families and its risk agent depend on
them. Also, 01's late-start check filters `kind=="stock"`, so an index
returning only two years of history would never be reported. `^CNX100` is a
legacy pre-2015 Yahoo symbol from before NSE's CNX→NIFTY rebranding; its
2015–2026 coverage is **unverified** — check it.

**Required interface** (the orchestrator imports these exact names):

- `build_calendar(raw_dir, index_names, include_muhurat=False) -> (pd.DatetimeIndex, dict)`
  Build the calendar as the **union of all stock trading dates**, not from one
  index file. Return diagnostics. Make the Muhurat choice an explicit
  documented parameter, not an accident — a one-hour session with atypical
  volume is defensible to exclude, but it must be a recorded decision, and if
  excluded the adjacent return must be marked as spanning a gap. Carry a
  `MUHURAT_SESSIONS` constant with sources in a comment.
- `validate_calendar(calendar) -> list[str]` — returns problems, empty if
  clean. Check at minimum: no duplicates; monotonic increasing; no Saturdays
  or Sundays; first date ≤ 2015-01-05; plausible length (justify your bounds
  in a comment for ~11.75 years of NSE sessions); no implausible mid-history
  gap (justify the threshold — NSE has multi-day holiday clusters).
- `align_to_calendar(df, calendar, symbol) -> (pd.DataFrame, dict)` — must
  **not** silently drop stock dates: count them and return the actual dates as
  `dates_dropped_by_calendar_align`. Must **not** emit pre-listing padded rows
  at all — truncate to the stock's first observed bar and record
  `first_bar_date`. Replace the single `Halted` column with three explicit,
  separately-reported columns: `PreListing`, `NoData` (a calendar date inside
  the stock's listed life with no row — the only genuine halt/suspension
  candidate and the only one that is actually news), `PostDelisting`. Never
  sum them into one number.
- `set_flag_safe(df, dates, column) -> (pd.DataFrame, list)` — the F11 fix.
  Use a membership mask (`df.index.isin(...)`), never label-based `.loc`
  assignment. Return the dates that were **not** found so a caller can
  hard-fail rather than corrupt the frame.
- `audit_index_series(raw_dir, index_names) -> pd.DataFrame` — per index
  series report rows, first_date, last_date, duplicates, NaNs, weekend dates,
  and master-calendar dates missing from it. Report honestly; do not clean.
- `assert_no_ffill_damage(df) -> list[str]` — detect runs of identical
  consecutive OHLC bars (the signature of an ffill) and return the offending
  ranges. Document in the module docstring why ATR needs `min_periods` equal
  to the full window and why ffilled OHLC destroys triple-barrier labels.

---

#### PACKAGE B — universe selection, exclusion and label purging
**New file: `scripts/02d_universe.py`**

**F05 (BLOCKER) — survivorship bias; checkpoint 1.1's own pass criterion is
unmet; four stocks exist only inside the holdout.** Checkpoint 1.1 uses
**today's** NIFTY 100 list for the whole 2015–2026 window. Its own stated pass
criterion is "prices for the universe with HISTORICAL constituents", which is
not met, and nothing downstream addresses it.

Two biases point the same way. *(a)* Classic survivorship: the 2015–2024
training set contains only names still in the NIFTY100 in Oct 2026 —
pre-selected winners — which inflates any momentum or trend edge and makes the
alpha claim indefensible to a reviewer. *(b)* Reverse selection in the
holdout: **VAML** (Vedanta Aluminium & Metal, 83 bars), **ENRIN** (Siemens
Energy India, 328), **TATACAP** (Tata Capital, 249) and **TMCV** (Tata Motors
CV, listed 2025-11-12, 229 bars) have **zero pre-holdout history** — the
holdout is ~378 sessions. They cannot appear in any training fold and cannot
complete an indicator warm-up. Three of them exist *because* a demerger
completed — information from the future of the sample. HYUNDAI (491 bars) has
~110 pre-holdout sessions, not enough for warm-up plus a fold.

**F10 (HIGH) — one boolean conflates three causes, and the docstring
contradicts the code.** In the old script `unexplained` is set by (a) an
unexplained factor-step, (b) any >60% move not on a hardcoded market-wide date
list, or (c) membership in a hardcoded demerger name list — then reported as
`exclude_from_model_universe` alongside `unexplained_events` (which counts
only cause (a)) and `flagged_big_moves` (only (b)). A stock excluded by (b) or
(c) shows `unexplained_events=0` next to `exclude=True`, which reads as a bug
and makes the exclusion untraceable. Separately, the docstring states
`KNOWN_UNADJUSTED_DEMERGERS` is "for documentation/traceability, not a second
silent exclusion path" while the code three lines later does exactly
`if name in KNOWN_UNADJUSTED_DEMERGERS: unexplained = True`. The prose and the
code disagree and **the prose is what goes in the paper.**

**F15 (MEDIUM) — whole-stock exclusion is itself look-ahead selection, and the
pre-event label window is never purged.** Two separate problems. First,
`exclude_from_model_universe` is all-or-nothing: VEDL's clean 2015 → 2026-04-29
history was to be discarded over a single artifact day. Second, and worse:
with a 10-day forward label, an artifact at date `t` poisons the labels of
`t−10 … t−1`, not just `t`. Nothing purges that window — for any stock,
including the ones kept. For every un-caught artifact, ten labelled samples
per event are silently wrong in the direction of a large fake Down.

**The decision already taken on VEDL and TMPV — implement this, do not
relitigate it.** **Truncate, do not drop.** Dropping removes a decade of clean
history on the basis of a 2026 corporate action that no investor at any
training-time date could know about, and it changes holdout composition on
forward-looking information — a reviewer will correctly call that look-ahead.

So: keep bars up to and including the session **before** the ex-date; drop
label-bearing samples with `t ≥ ex_date − horizon` so the last labelled
sample's forward window closes before the artifact; discard all bars from the
ex-date onward (a post-demerger entity is structurally different, so a feature
or label crossing that boundary is meaningless even with the level adjusted).
Apply this **uniformly to every structural action in the table**, not just the
two that happened to be noticed — SIEMENS 2025-04-07 and TRENT 2026-06-04 are
the same defect. Do **not** carry VAML, ENRIN or TMCV as independent names in
this pass.

**Required interface:**

- `build_universe(summary_df, actions_df, calendar, horizon=10, warmup=200) -> pd.DataFrame`
  One row per symbol with at minimum: `symbol`, `first_bar_date`,
  `eligible_from` (= `first_bar + warmup + horizon`), `truncate_at`
  (ex-date of the first uncrossable structural action, or empty),
  `exclude_reason`, `exclude_detail`, `n_labelled_samples_est`,
  `pre_holdout_sessions`.
- `exclude_reason` must be an **enum string**, never a boolean:
  `""` | `"unexplained_factor_step"` | `"unadjusted_big_move"` |
  `"manual_corporate_action"` | `"insufficient_history"` |
  `"holdout_only_listing"` | `"demerger_child_overlaps_parent"`.
  `exclude_detail` carries the offending dates or the specific reason. Emit
  one row per reason — never a single opaque flag.
- `purge_windows(actions_df, symbol, horizon=10) -> list[tuple[Timestamp, Timestamp]]`
  — for each structural ex-date `e`, the closed interval `[e − horizon, e]` of
  label-bearing sample dates to drop.
- `embargo_folds(fold_boundaries, horizon=10) -> list[tuple]` — embargo
  `horizon` sessions on **both sides** of every walk-forward boundary, so a
  training label's forward window cannot overlap the test fold.
- `point_in_time_universe(membership_panel, as_of) -> list[str]` — consumes a
  `(date, symbol, in_universe)` panel. **You are not required to reconstruct
  the historical membership panel in this pass** (it needs NSE
  index-maintenance circulars back to Jan 2015 plus downloading the
  removed/delisted names). Write the function and the loader, emit a clear
  `NotImplementedError`-style status or an explicit stub flag if the panel is
  absent, and **state in your report that survivorship bias remains open and
  that no headline alpha number may be published until it is closed.** Do not
  paper over it.

Import the action table with `load_corp_actions()` from
`02a_build_corp_actions.py`, and get the uncrossable boundaries from
`uncrossable_boundaries()` in `02b_adjust_prices.py` — do not re-derive either.

---

#### PACKAGE C — provenance, validation and honest reporting
**New files: `scripts/_provenance.py` and `scripts/02e_validate.py`**

**F01 (BLOCKER) — the committed outputs were produced by pre-fix code and
nothing can tell you that.** The 1.2b report claims a full pipeline re-run
excluding 2 stocks; the committed summary has all 100 rows `exclude=False`.
Both reports describe the same filesystem and contradict each other, so
neither is citable. **The root cause is that no report records what code
produced it.**

**F13 (MEDIUM) — the results are not reproducible, and there is a mild
look-ahead.** Yahoo's `Adj Close` is retro-adjusted: the value at date `t`
depends on every dividend *after* `t`. Re-download next month and every
historical `Factor` and `AdjClose` in `data/clean/` changes. Nothing records
the download timestamp, the `yfinance` version, or a hash of the raw CSVs.
`get_constituents()` in 01 silently falls back to a cached list with no record
of which snapshot was used — and on an NSE HTML error page returned with HTTP
200, `read_csv` parses garbage before the `Symbol` check catches it. The
look-ahead: a feature at `t` computed on the retro-adjusted series
incorporates knowledge that a dividend occurs after `t`.

**F09 (HIGH) — "Unexplained events: 0" is a property of the thresholds, not
evidence of data quality, and it was reported as a pass.** In the old script
`MAX_DIVIDEND_ADJ = 0.20` accepts any factor step up to an implied payout of
`1 − 1/1.20 = 16.7% of the price in a single ex-date` as a "plausible special
dividend". Real NIFTY100 single payouts are 0.1–2%, 4–8% at the extreme. The
band is ~8× too wide, leaving `"unexplained"` reachable only on
`ratio ∈ (1.20, 1.44) ∪ (1.56, 1.92) ∪ …` — a set essentially nothing lands
in. The detector is also under-powered: 924 events / 100 stocks / 11.75 years
= **0.79 detected actions per stock-year** against a norm of 1–2 cash
dividends, because the `0.005` step floor drops every payout under ~0.5%
yield. So the old `CorpActionFlag` is a biased, incomplete **dividend-yield**
indicator (HINDZINC 21, COALINDIA 27, PFC 30 vs KOTAKBANK/BAJAJFINSV/CHOLAFIN
0) — not a corporate-action flag, and it must not be fed to the model as one.

**F16 (LOW) — report no metric that no code computes.** Checkpoint 1.1's
summary claims "0 OHLC violations", but **no committed code tests**
`High ≥ max(Open, Close)`, `Low ≤ min(Open, Close)`, or `High ≥ Low`. Add the
three inequality checks so the reported metric is real. Also:
`pd.to_datetime(df.index).tz_localize(None)` in 01 raises `TypeError` on an
already-naive index — guard it. And `rows_in = len(pd.read_csv(path))` parses
the whole CSV a second time; use the length already in hand.

**Required interface:**

- `_provenance.py`: `provenance_header(script_path, inputs: list[Path]) -> dict`
  capturing the git commit SHA of the script (or a file hash if not a repo),
  UTC timestamp, Python version, pandas/numpy/yfinance versions, and the
  SHA-256 of every input file. Plus `write_report(path, title, header, body)`
  that stamps the header into **every** report as a machine-readable block —
  so a report can never again fail to say what produced it.
- `02e_validate.py`: a validation harness with each check a named function
  returning a list of problems, plus a `run_all(root) -> pd.DataFrame` and a
  non-zero exit code on any failure. Checks, at minimum:
  - the three OHLC inequalities, per stock, with offending dates
  - no negative or zero prices
  - no duplicate dates, index monotonic
  - every stock date present in the master calendar (the F06 regression guard)
  - zero `PreListing` rows emitted anywhere (the F07 guard)
  - row count unchanged by flag-setting (the F11 guard)
  - **action-table coverage** — the replacement for the meaningless
    "unexplained: 0". Report: the fraction of structural actions in the table
    whose ex-date shows the expected discontinuity in the raw series; the
    count of raw one-day moves beyond ±15% with **no** corresponding table
    entry (these are the un-caught artifacts, and this number is the real
    quality metric); and the residual discontinuity count in the adjusted
    series, which should be zero outside table dates.
  - no identical-consecutive-OHLC runs (the ffill guard)

---

#### PACKAGE D — the orchestrator
**Rewrite: `scripts/02_clean_adjust.py`**

**F02 (BLOCKER) — the script cannot run at all.** Line ~48 reads
`ROOT = Path("/mnt/user-data/uploads/Market Prediction Model")` — an ephemeral
cloud-sandbox path hardcoded into a script that lives on a Windows machine,
while `01_download_prices.py` correctly uses
`Path(__file__).resolve().parents[1]`. On Windows that POSIX string resolves
drive-relative: `mkdir(parents=True, exist_ok=True)` happily creates
`C:\mnt\user-data\uploads\...\data\clean`, `RAW_DIR.glob("*.csv")` yields
nothing, the loop body never executes, `summary` becomes an empty column-less
DataFrame, and `summary.loc[summary["exclude_from_model_universe"], "name"]`
raises `KeyError`. This is the mechanical cause of F01.

**Do not simply patch the one `ROOT` line.** Patching it alone would make a
script with a fundamentally wrong adjustment method (F03) *runnable*, which is
worse than leaving it broken — it would produce confidently wrong output.
Rewrite the orchestrator so it is a thin driver that calls the five modules in
order and owns no cleaning logic of its own.

**Required shape:**

- `ROOT = Path(__file__).resolve().parents[1]`, and a fail-fast assertion at
  the top of `main()`: `RAW_DIR` exists and contains ≥ 103 CSVs, else
  `sys.exit` printing the resolved path. Never write outputs outside the repo.
- Call order: load the action table (02a) → build and validate the calendar
  (02c) → per stock: align (02c), adjust (02b), set flags via `set_flag_safe`
  (02c) → build the universe, truncations and purge windows (02d) → validate
  everything (02e) → write reports with a provenance header (`_provenance`).
- Keep the one design decision the audit explicitly cleared: a raw execution
  series and an adjusted series side by side is **correct architecture**. It
  was the contents that were wrong.
- Keep `raw_ret = df["Close"].pct_change()` computed **before** calendar
  alignment — the audit cleared this as the right choice, because it measures
  consecutive *traded* sessions rather than spanning calendar gaps with NaN.
- Delete `KNOWN_MARKET_WIDE_DATES` entirely (per F04 it can only create false
  negatives), and demote `KNOWN_UNADJUSTED_DEMERGERS` to a provenance-only
  column rather than a decision input.
- Lower the big-move **flag** threshold from 0.60 to 0.15. Context: NSE F&O
  stocks have no operating range (a dummy 10% filter, flexing 5% at a time),
  non-F&O index names have a hard 10%/20% band, so a genuine single-session
  −60% in a NIFTY100 cash-segment stock cannot occur. The old 0.60 ceiling
  could only ever catch corporate-action artifacts, and it sat **above** the
  common artifact sizes (−33% bonus, −50% bonus, −40% demerger). Flagging is
  for review; **exclusion must come from action-table reconciliation, not from
  a magnitude threshold.**

---

## 4. Order of work

**Step 1, before writing anything — settle F03 empirically.** The audit's
central finding is INFERRED, not confirmed. Run `detect_prefolded_splits()`
from `02b_adjust_prices.py` across the real series, and separately print raw
`Close`, `Adj Close` and `Volume` for these windows:

| symbol | window | tests |
|---|---|---|
| BAJAJFINSV | 2022-09-09 → 2022-09-16 | split + bonus, R=10 |
| RELIANCE | 2024-10-24 → 2024-10-30 | 1:1 bonus, R=2 |
| RELIANCE | 2023-07-18 → 2023-07-24 | Jio demerger — NSE's special pre-open settled RIL at ₹2,580 and JFSL at ₹261.85, so the expected base is exact |
| ITC | 2025-01-02 → 2025-01-08 | ITC Hotels demerger, ₹482.60 → ₹455.60 discovered — also exact |
| TRENT | 2026-06-02 → 2026-06-06 | 1:2 bonus, R=1.5 |
| SIEMENS | 2025-04-03 → 2025-04-09 | demerger, R≈2.01 |
| BAJFINANCE | 2025-06-12 → 2025-06-18 | 4:1 bonus + 1:2 split = −90%, the largest distortion found |

The RELIANCE 2023-07-20 and ITC 2025-01-06 rows are the highest-value checks
because both have officially discovered pre-open base prices — they prove or
disprove what Yahoo does with demergers. **Report the actual numbers.** If the
inference is wrong, say so and stop to flag it before building on it.

**Step 2 — run `02a_build_corp_actions.py` locally with yfinance available.**
It was written in an environment without `yfinance`, so its yfinance path has
**never executed**. The merged `data/reference/corp_actions.csv` does not exist
yet; only `corp_actions_manual.csv` does. Critically, **the manual table
contains zero `dividend` rows** — the dividend cash series depends on the
yfinance pull. Run it, check `corp_actions_fetch_log.csv` for per-symbol
failures, and report how many symbols failed.

**Step 3 — delete the stale artifacts.** `reports/phase1/checkpoint_1_2_*` and
`data/clean/*`. They are mutually contradictory and keeping them risks a
downstream read. Preserve `checkpoint_1_2b_discontinuity_report.md` and
`checkpoint_1_2c_audit_report.md` as the audit trail.

**Step 4 — build the packages.** C first (`_provenance.py` is a dependency of
everything that writes a report), then A, then B, then D. Each module needs a
`if __name__ == "__main__":` self-test on **synthetic** data printing PASS/FAIL
per assertion, with a regression test for each numbered finding it fixes.

**Step 5 — run the whole pipeline and the validation harness.** Report the
real numbers. If a check fails, report the failure rather than loosening the
check.

---

## 5. Interface contracts already fixed — match these exactly

**Corporate-action table** at `data/reference/corp_actions.csv`:
```
symbol, ex_date, action_type, ratio, dividend_amount, source, source_url, confidence
```
- `ex_date` — ISO `YYYY-MM-DD`, **always the ex-date, never the record date.**
  In the T+2 era (before Jan 2023) the ex-date is one session before the record
  date; from T+1 (Jan 2023) they commonly coincide. A one-session error here
  mislabels a −50% bar.
- `action_type` — exactly one of `split`, `bonus`, `demerger`, `dividend`,
  `rights`.
- `confidence` — `VERIFIED` | `DERIVED_FROM_RECORD_DATE` | `UNVERIFIED`.
- Some rows carry a verified ex-date with an **approximate** ratio, marked in
  `source` with the token `EX_DATE_VERIFIED;RATIO_APPROX`. Some rows have a
  **blank** ratio with `confidence=UNVERIFIED` — ABB 2019-12-20 and MOTHERSON
  2022-01-14 are the known cases. A consumer that only masks the ex-date can
  trust those dates; one that rescales must not trust those ratios.

**Ratio convention — already fixed, do not redefine it.**
`ratio` = R = P_cum / P_ex: the last traded price on the session **before** the
ex-date divided by the adjusted base from the ex-date onward. R ≥ 1 for any
value-diluting action.

| action | R |
|---|---|
| split, r-for-1 | `R = r` (a "1:5 split" → R = 5) |
| bonus a:b (a new per b held) | `R = (a+b)/b` → 1:1 = 2, 1:2 = 1.5, 2:1 = 3, 1:4 = 1.25 |
| demerger, parent retains fraction f | `R = 1/f` |
| dividend | empty |

Consumer rule: `adjusted(t) = raw(t) / Π{R_i : ex_date_i > t}` — **strictly
after**, so the ex-date bar itself is untouched and the bar before it is
scaled.

One trap, already documented in 02a: a company's **cost-of-acquisition
apportionment** announced for income tax is *not* the price divisor. Tata
Motors' was 68.85/31.15 while the market-value split was ~60/40. Use market
value.

**Public functions you may import and must not re-derive:**
- From `02a_build_corp_actions.py`: `load_corp_actions(root)`, `build(root)`,
  `actions_for(df, symbol, start, end)`
- From `02b_adjust_prices.py`: `build_adjusted(raw_df, actions_df, symbol)`,
  `uncrossable_boundaries(actions_df, symbol)`,
  `approx_ratio_dates(actions_df, symbol)`,
  `detect_prefolded_splits(raw_df, actions_df, symbol)`,
  `assert_no_residual_discontinuity(adj_df, actions_df, symbol, threshold=0.15)`

`02b` emits structural-only adjusted prices (`AdjOpen/AdjHigh/AdjLow/AdjClose`,
aliased `StructAdj*`), `AdjVolume`, `CumDivisor`, `CumShareRatio`,
`DividendCash`, `CorpActionExDate`, `AdjQuality`, `SegmentId` and boolean
quality columns. **There is deliberately no dividend-reinvested price column
— that is the F08 fix.** One price series for ATR, barrier levels, touch tests
and P&L; dividends are credited as separate cash.

---

## 6. Facts already established — do not re-investigate

**Closed open items (all VERIFIED, do not reopen):**
- **HINDZINC 2024-05-21 (+25.6%) is genuine news** — a zinc/silver rally to a
  record high, up ~13–20% intraday. Leave it in as signal.
- **TRENT's ~−33% is the 2026-06-04 ex-bonus** — a 1:2 bonus (−33.33%) plus a
  ₹6 dividend going ex the same session. The old report's "~2026-01-01" date
  was wrong.
- **Both Adani dates are genuine news, not corporate actions.** 2023-12-05:
  group stocks rallied up to 15% on the 2023-12-04 BJP state-election results.
  2024-11-21: US DOJ indictment and SEC fraud charges over an alleged $250m
  bribery scheme, stocks down up to 20%. Both stay in per project policy.
- **CGPOWER 2016-03-15 is a corporate action** — the Crompton Greaves
  consumer-products demerger, **−71.81%**, now in the action table.
- **TMPV's ex-date is 2025-10-14**, the same as the record date.
- **VEDL: ex-date 2026-04-30, record 2026-05-01**, ₹773.60 → ₹289.50 ≈
  **−62.6%**. The 1.2b report's −64.9% does not match the published prices.
- **TMCV listed 2025-11-12**; the demerger predates its series, so it correctly
  shows no discontinuity.
- Symbol identities: **VAML** = Vedanta Aluminium & Metal, **ENRIN** = Siemens
  Energy India, **ETERNAL** = renamed Zomato (full history from the 2021-07-23
  listing, 1293 bars, not truncated), **LTM** = the LTIMindtree lineage from
  the July 2016 L&T Infotech IPO (2528 bars is a continuous series, not a
  splice loss). **HINDZINC has never split.**

**Still genuinely unresolved — flag, do not invent an answer:**
- **CGPOWER's 2017–2018 drops.** Not explained by anything found. CG Power was
  selling off overseas power businesses and later hit the 2019–20 accounting
  fraud. Uninvestigated.
- **ABB 2019-12-20 ratio** — ex-date solid (a scheme of arrangement spinning
  off ABB Power Products & Systems India, later Hitachi Energy India /
  POWERINDIA, which listed March 2020), ratio unknown.
- **MOTHERSON 2022-01-14 ratio** — ex-date solid, but MSWIL listed only
  2022-03-28 so no same-day discovered base price exists. The shakiest row in
  the table.
- **MAZDOCK 2024-12-27 ratio** is an assumption (FV ₹10 → ₹5, R=2), not
  sourced.
- **PFC 2023-09-21** — one source says ex 09-21, another 09-20. Widen any
  window by a day.
- **SHRIRAMFIN** — a split went ex in the week of 2025-01-06, date not
  resolved. **HAL** — a 1:1 bonus and a split are referenced in secondary
  sources, neither pinned.
- **~64 of the 100 symbols were never cleared for corporate actions at all.**
  Absence from the table is **not** a verified claim of no action. The
  un-cleared list is in the 02a agent's report; the highest-risk gaps are the
  remaining top-20 index weights and the PSU/high-yield cluster, which are
  repeat bonus issuers (GAIL had four bonuses, BEL four actions totalling
  ~109× cumulative, IOC three, BPCL three).
- **`^CNX100` and `^INDIAVIX` 2015–2026 coverage** is unverified.

**The largest distortion found, for calibration:** BAJFINANCE 2025-06-16 — a
4:1 bonus **plus** a 1:2 split, **−90% in one session**, which the old pipeline
never flagged because it sat under the 60% ceiling and produced no factor step.

---

## 7. What to report back

Structure your final report exactly like this, and keep every claim tagged:

1. **Step 1 diagnostic results** — the actual printed numbers for each window,
   and your verdict on F03: is `Close` split-folded? Are bonuses and demergers
   unadjusted? VERIFIED or still uncertain, and on what evidence.
2. **Files written**, with each module's self-test pass/fail counts.
3. **Per-finding status table**: finding ID → `FIXED` / `PARTIAL` / `DEFERRED`
   / `CANNOT FIX`, with one line of evidence each. Cover F01, F02, F05, F06,
   F07, F09, F10, F11, F13, F14, F15, F16.
4. **Pipeline run results** — real numbers from the real data: stocks
   processed, calendar length, dates recovered by the union calendar that the
   old code dropped, per-cause coverage counts (`PreListing` / `NoData` /
   `PostDelisting`), symbols truncated and at which ex-dates, symbols excluded
   with the enum reason, and the **action-table coverage metric** replacing
   "unexplained: 0".
5. **The un-caught artifact count** — raw one-day moves beyond ±15% with no
   corresponding action-table entry. This is the honest quality number; report
   it even if it is embarrassing, and list the symbol/date pairs.
6. **Validation harness output**, pass or fail, with failures listed.
7. **What remains open**, named explicitly — survivorship bias / the
   point-in-time membership panel above all, plus anything in §6's unresolved
   list you could not close.
8. **Anything you believe the audit got wrong**, with your reasoning. The
   audit is not scripture; two of its findings are explicitly INFERRED. If the
   Step 1 diagnostic contradicts F03, that changes the whole remediation and
   you should say so loudly rather than building on a false premise.

Do not report a checkpoint as complete unless you ran it and the validation
harness passed. If you run out of budget mid-way, say exactly where you
stopped and what the next action is.
