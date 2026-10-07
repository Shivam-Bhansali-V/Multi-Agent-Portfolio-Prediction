# Checkpoint 1.2c — independent audit of the data-cleaning pipeline

Date: 2026-10-07. Produced by an adversarial audit agent given the verbatim
text of `01_download_prices.py` and `02_clean_adjust.py`, the committed
`checkpoint_1_2_report.md`, `checkpoint_1_2_summary.csv`, and the claims of
`checkpoint_1_2b_discontinuity_report.md`.

## Scope limitation — stated plainly

The auditor did **not** read `data/raw/yahoo/*.csv` or `data/clean/*.csv`.
The device bridge timed out on those reads. Every finding below is derived
from the scripts, the committed report/summary numbers, and web verification
of Indian-market facts. Findings tagged INFERRED are **not confirmed against
your actual data** and carry a named diagnostic to settle them.

Confidence tags: VERIFIED = a source was retrieved or the arithmetic is
decisive. INFERRED = the only hypothesis consistent with the evidence, not
confirmed. CANNOT VERIFY = insufficient material.

---

## BLOCKERS

### F01 — The committed 1.2 outputs were produced by the pre-fix code
`checkpoint_1_2b_discontinuity_report.md` claims a full re-run yielding
"2 stocks now excluded: TMPV and VEDL". The committed artifacts disagree:
`checkpoint_1_2_report.md` says `Stocks EXCLUDED ... 0 -> none`, and all 100
rows of `checkpoint_1_2_summary.csv` carry `exclude_from_model_universe=False`
— including `VEDL` (`flagged_big_moves=1`) and `TMPV`.

Under the amended code both must be `True`: VEDL's flagged date is not in
`KNOWN_MARKET_WIDE_DATES`, and TMPV is forced by name. The statements cannot
both describe the same filesystem.

**Consequence.** The summary and report are stale artifacts of superseded
code. Anything building the modeling universe from `exclude_from_model_universe`
silently includes VEDL and TMPV with uncorrected artifacts. The two committed
reports contradict each other, so neither is citable.

**Fix.** Delete `reports/phase1/*` and `data/clean/*`, re-run after F02, and
write a provenance header (script commit SHA, UTC timestamp, yfinance version,
SHA-256 of each input CSV) into every report. VERIFIED.

### F02 — `ROOT` in `02_clean_adjust.py` is hardcoded to an ephemeral sandbox path
`ROOT = Path("/mnt/user-data/uploads/Market Prediction Model")`, while
`01_download_prices.py` correctly uses `Path(__file__).resolve().parents[1]`.
The two scripts do not point at the same tree. On Windows that POSIX string
resolves drive-relative: `mkdir` happily creates `C:\mnt\user-data\...`,
`RAW_DIR.glob("*.csv")` yields nothing, the loop body never runs, `summary` is
an empty column-less DataFrame, and `summary.loc[summary["exclude_from_model_universe"], "name"]`
raises `KeyError`.

**Consequence.** The mechanical explanation for F01, and the cleaning step is
unreproducible by anyone — fatal for publication. VERIFIED (path divergence
and the KeyError); INFERRED that this is why the outputs are stale.

### F03 — `Factor = AdjClose/Close` captures cash dividends only; bonuses and demergers are adjusted nowhere
Three verified corporate actions, cross-checked against the committed row
counts, pin this down:

- Bajaj Finserv executed a 1:5 split **and** a 1:1 bonus, ex-date 2022-09-13
  — a combined ~10x price reset. `BAJAJFINSV` shows 2910 rows,
  **0 corp_action_events, 0 flagged_big_moves**. If `Close` were raw, either
  the factor would step 10x (an event) or raw Close would drop ~90% (a flag).
  Neither fired, so `Close` is not raw.
- Adani Power executed a 1:5 split; `ADANIPOWER` likewise shows 0 and 0.
- Trent's first-ever bonus reset the price −33.87% on ex-date 2026-06-04. The
  1.2b report lists a ~−33% TRENT discontinuity as *unresolved* and misdates
  it to ~2026-01-01 — so the bonus sits in the series unadjusted.

So: splits are silently pre-folded into `Close` (making the docstring's "raw
OHLCV = what actually traded" false — pre-Sep-2022 BAJAJFINSV "raw" Close is
~1/10 of the traded price), while bonuses and demergers/schemes of arrangement
are adjusted in **neither** series. `classify_step`'s entire
`PLAUSIBLE_SPLIT_RATIOS` branch is dead code that can never fire.

**Consequence.** Every bonus ex-date in 2015–2026 is a permanent fabricated
one-day crash of −33% (1:2), −50% (1:1) or worse, in both series. Reliance
alone has two 1:1 bonuses (Sep 2017, ex-2024-10-28); a 50% drop is under the
60% ceiling so it was never even flagged. Triple-barrier stamps a hard Down on
the 10 sessions preceding every such date, the technical agent learns to
"predict" bonus ex-dates, and a long-only backtest books a 33–50% fictitious
loss on the largest weight in the index. **The most damaging defect in the
pipeline.**

**Fix.** Stop deriving actions from `AdjClose/Close`. Build an explicit
corporate-action table and adjust from it. Corporate actions VERIFIED; the
claim about the files INFERRED — settle it with the diagnostic in §Next.

### F04 — The 60% sanity ceiling is unreachable by real trading and sits above the common artifact sizes
NSE's own FAQ: there is no operating range for securities with derivatives
(a dummy 10% filter, flexing 5% at a time after ≥25 trades from 5 participants
on each side at ≥9.90%). Non-F&O index names carry a hard 10%/20% band. A
genuine single-session −60% in a NIFTY100 cash-segment stock cannot occur, so
`SANITY_MOVE_CEILING = 0.60` fires on nothing but corporate-action artifacts —
which means `KNOWN_MARKET_WIDE_DATES` can only ever suppress a real artifact
that happens to coincide with one of its eight dates. It is a pure
false-negative generator.

The artifact magnitudes that matter are all **below** 0.60: Trent −33.87%,
1:1 bonus −50%, Tata Motors −40%, and **Siemens' 1:1 energy demerger, ex-date
2025-04-07, a ~50% mechanical reset**. Only Vedanta's −62.6% clears the
ceiling, which is exactly why the report says "1 stock flagged". The detector
found the one case it was tuned to find.

**Consequence.** SIEMENS is a third confirmed unadjusted demerger the pipeline
never flagged, never excluded, never mentioned — and its ex-date is four
trading days into the Apr-2025 holdout, the window the published alpha comes
from. TRENT is a fourth. Hardcoding two names into
`KNOWN_UNADJUSTED_DEMERGERS` is not a detector; it is a list of the cases
somebody happened to notice.

**Fix.** Drop the flag threshold to ~0.15, delete `KNOWN_MARKET_WIDE_DATES`,
and make correction depend on reconciliation against the action table rather
than a magnitude threshold. VERIFIED (price bands, both ex-dates).

### F05 — Survivorship bias; checkpoint 1.1's own pass criterion is unmet; four stocks exist only inside the holdout
1.1's docstring concedes it uses today's NIFTY 100 list; its stated pass
criterion is "prices for the universe with **HISTORICAL** constituents". That
criterion is not met and nothing downstream addresses it.

Identifying the opaque symbols: **VAML** = Vedanta Aluminium & Metal (83 bars),
a Vedanta-demerger child; **ENRIN** = Siemens Energy India (328), the
Siemens-demerger child; **TATACAP** = Tata Capital (249); **TMCV** = the Tata
Motors CV arm, listed 2025-11-12 (229). The holdout is roughly 378 sessions,
so all four have **zero pre-holdout history**: they cannot appear in any
training fold and cannot complete a 200-session indicator warm-up. HYUNDAI
(491) has ~110 pre-holdout sessions — not enough for warm-up plus a fold.

**Consequence.** Two biases pointing the same way. (a) Classic survivorship:
the 2015–2024 training set contains only names still in the NIFTY100 in Oct
2026 — pre-selected winners, which inflates any momentum/trend edge and makes
the alpha claim indefensible. (b) Reverse selection in the holdout: five
instruments contribute holdout-only predictions from a model that never saw
them, and three exist *because* a demerger completed — information from the
future of the sample.

**Fix.** Reconstruct point-in-time NIFTY100 membership from NSE
index-maintenance circulars back to Jan 2015, store a
`(date, symbol, in_universe)` panel, and have every fold select its universe
as of the fold start. Download the removed/delisted names — they are the point.
Gate each symbol at `listing_date + warmup + horizon`. If that is out of scope
for this pass, the paper must state results are survivorship-biased and not
headline alpha. VERIFIED (criterion unmet, symbol identities, TMCV listing).

---

## HIGH

### F06 — The calendar reindex silently deletes ~11 real trading sessions per stock
Provable from the committed numbers alone. `rows_after_price_reject +
halted_days` should equal `len(calendar)`; instead it varies with history
length: VAML 83+2816 = **2899**; TMCV/TATACAP/ENRIN/HYUNDAI/JIOFIN/ETERNAL/
POWERINDIA = **2902**; MAXHEALTH 2903; ADANIGREEN 2905; HDFCLIFE/SBILIFE/
DMART/VBL 2906; LTM 2907; ADANIENSOL 2908; every full-history stock
2910+0 = **2910**. The only consistent reading is `len(calendar) = 2899`,
with each stock losing `(rows + halted − 2899)` of its own trading dates — 0
for the newest listing, **11 for every full-history stock** — because
`df.reindex(calendar)` drops any row whose date is absent from `NIFTY50.csv`.
Nothing counts or reports this.

~One lost session per year of history points at the Diwali **Muhurat**
sessions (one per Samvat year; 2020-11-14, 2021-11-04, 2022-10-24,
2023-11-12, 2024-11-01, 2025-10-21 confirmed).

**Consequence.** Returns spanning a deleted session become silent two-session
returns; ATR and every rolling window are computed over an unaudited calendar;
the "execution series" is missing sessions on which trades were possible.
Undisclosed data loss in a dataset intended for publication.

**Fix.** Build the calendar as the **union** of all stock trading dates (or
from the official NSE session list). Assert `set(stock_dates) ⊆ set(calendar)`
per stock and hard-fail listing the offenders. Decide explicitly whether
Muhurat sessions are in or out, and if out, mark the adjacent return as
spanning a gap. Add a `dates_dropped_by_calendar_align` column.
Data loss VERIFIED; Muhurat attribution INFERRED.

### F07 — `Halted` is a mislabelled "not yet listed" flag; the 29,623 figure contains zero real halts
The 23 per-stock counts sum to **exactly 29,623**, equal to the reported
total — so the other 77 stocks have exactly 0, and every one of those rows is
pre-listing padding matching a known listing date. 100% padding, 0% suspension.
Reporting "29,623 halted-day rows" mislabels a listing artifact as a market
event, and there is no suspension detection anywhere. Those rows also carry
NaN in `Open/High/Low/Close/Volume/Factor/AdjClose`.

**Consequence.** Mild as a data error (the NaN block is contiguous and
leading). Serious as reporting. And if anything downstream calls `ffill()`
before ATR — the obvious thing to write — the leading block becomes a run of
identical synthetic bars, ATR collapses toward zero, and `±ATR` barriers go
degenerate, labelling Up/Down on microscopic noise for the 23 short-history
names.

**Fix.** Split into `PreListing` / `NoData` / `PostDelisting` and report
separately; only the second is news. Never emit rows before a stock's first
bar — truncate and record `first_bar_date`. Forbid `ffill` on OHLC; require
ATR `min_periods` equal to the full window. VERIFIED (the sum is exact);
the ffill consequence INFERRED.

### F08 — Labels are a total-return series while execution is a price series
Because `Factor` is dividend-only, `AdjClose` is dividend-reinvested. The
docstring has labels/indicators on the adjusted series and fills on raw OHLC.
A `+2×ATR` barrier computed in adjusted units and tested against a raw path is
a unit mismatch; for any stock where a split was folded into `Close`, the two
series differ by up to 10x.

**Consequence.** Labels and P&L measure different quantities. Against a 0.35%
cost budget, a systematic few-tenths-of-a-percent drift is the same order as
the entire edge. A stock going ex-dividend inside the 10-day window gets a
free push toward the Up barrier that the raw P&L never books.

**Fix.** One series for ATR, barrier levels, touch tests and P&L — a
split/bonus/demerger-adjusted series with dividends **excluded** — and credit
dividends as a separate cash line. Unit test: for a stock with no actions in a
window, labels on raw and adjusted must be identical. Mismatch VERIFIED from
the docstring; whether the ATR code mixes series CANNOT VERIFY.

### F09 — "Unexplained events: 0" is a property of the thresholds, not evidence of data quality
`Factor` is a step function rising to 1.0, so `factor_ratio = 1/(1 − D/P) > 1`
on a dividend ex-date and `= r` on an r-for-1 split — the sign convention is
correct, and the split branch would fire if splits were visible (they are not,
per F03). What remains is the dividend branch, and `|ratio − 1| ≤ 0.20` accepts
an implied payout of `1 − 1/1.20 = 16.7% of price in a single ex-date`. Real
NIFTY100 single payouts are 0.1–2%, 4–8% at the extremes. The band is ~8x too
wide, leaving `"unexplained"` reachable only on
`ratio ∈ (1.20, 1.44) ∪ (1.56, 1.92) ∪ …` — a set nothing lands in.

The detector is also under-powered: 924 events / 100 stocks / 11.75 years =
**0.79 detected actions per stock-year** against a norm of 1–2 cash dividends.
The `0.005` step floor drops every payout under ~0.5% yield. So
`CorpActionFlag` is a biased, incomplete **dividend-yield** indicator
(HINDZINC 21, COALINDIA 27, PFC 30, HCLTECH 30 vs KOTAKBANK/BAJAJFINSV/
CHOLAFIN 0), not a corporate-action flag — and must not be fed to the model
as one.

**Fix.** `MAX_DIVIDEND_ADJ` to 0.03, a verify band 0.03–0.10, `>0.10`
unexplained; step floor to ~0.0005; better, replace the inference with the
explicit action table. Stop reporting "unexplained: 0" as a pass — report
action-table **coverage** instead. Threshold arithmetic VERIFIED; typical
yields INFERRED.

### F10 — One boolean conflates three causes, and the docstring contradicts the code
`unexplained` is set by (a) an unexplained factor-step, (b) any >60% move off
the market-wide list, or (c) membership in a hardcoded name list — then
reported as `exclude_from_model_universe` beside `unexplained_events` (which
counts only (a)) and `flagged_big_moves` (only (b)). A stock excluded by (b)
or (c) shows `unexplained_events=0` next to `exclude=True`, which reads as a
bug and makes the exclusion untraceable. The docstring states
`KNOWN_UNADJUSTED_DEMERGERS` is "for documentation/traceability, **not a second
silent exclusion path**", while the code does exactly
`if name in KNOWN_UNADJUSTED_DEMERGERS: unexplained = True`. The prose and the
code disagree, and the prose is what goes in the paper.

**Fix.** Replace with `exclude_reason` (enum) + `exclude_detail` (offending
dates). VERIFIED.

---

## MEDIUM / LOW

### F11 — `full.loc[pd.Timestamp(...), "CorpActionFlag"] = 1` can append a corrupt row
Event dates come from the stock's own rows, and F06 proves up to 11 of those
are absent from `calendar`. `.loc[label] = value` with a missing label performs
**setitem-with-enlargement**: pandas appends a row at the end, NaN everywhere
else, chronologically out of order, with `Halted = NaN` (written after `Halted`
is computed). It lands in the clean CSV, and a later `sort_index()` inserts an
all-NaN bar mid-series. Low probability, silent, and the clean CSVs are the
dataset of record.

**Fix.** `mask = full.index.isin([...]); full.loc[mask, col] = 1`; assert every
event date is in the calendar; compute `Halted` last. Semantics VERIFIED;
whether it triggers CANNOT VERIFY.

### F12 — Volume is never adjusted and never flagged
`Volume` is copied through raw. Under F03's reading Yahoo's volume is
split-adjusted in step with `Close` but not bonus-adjusted, so every bonus
ex-date leaves a permanent step of the bonus ratio. `AdjClose × Volume` as
turnover is wrong wherever the series diverge.

**Consequence.** Breaks OBV, volume z-scores, turnover and Amihud illiquidity
at every bonus date, and corrupts any liquidity filter deciding tradability —
which matters because the 0.10% slippage assumption only holds for liquid
names.

**Fix.** `AdjVolume = Volume × cumulative share-count ratio` from the action
table; keep raw `Volume` for display; turnover from `raw Close × raw Volume`.
Check median volume 20 sessions after each ex-date against 20 before.
CANNOT VERIFY.

### F13 — Back-adjusted prices are non-reproducible and embed a mild look-ahead
`Adj Close` is retro-adjusted: the value at t depends on every dividend
*after* t. Re-download next month and every historical `Factor`/`AdjClose` in
`data/clean/` changes. Nothing records the download timestamp, the yfinance
version, or a hash of the raw CSVs. `get_constituents()` silently falls back
to a cached list with no record of which snapshot was used — and on an NSE HTML
error page returned with HTTP 200, `read_csv` parses garbage before the
`Symbol` check catches it.

**Consequence.** The published numbers cannot be reproduced, including by the
authors after the next `yf.download`. Also a genuine small look-ahead: a
feature at t incorporates knowledge that a dividend occurs after t.

**Fix.** Freeze `data/raw/` as the immutable dataset of record, commit it (or
its hashes) with the download date, pin `yfinance==<version>`, commit the dated
`ind_nifty100list.csv` snapshot with its hash, never re-download inside the
experimental loop, and check `content-type` before `read_csv`. VERIFIED.

### F14 — The index series are never validated and never cleaned
`NIFTY50.csv` becomes the master calendar with zero validation — no row-count
assertion, no start-date check, no duplicate check, no weekend check. One bogus
date injects a spurious padded row into all 100 stocks. `^CNX100` and
`^INDIAVIX` are downloaded then skipped entirely by `02` (`INDEX_NAMES` →
`continue`), so they are never aligned, never audited, never available — yet
the regime/relative-strength families and the risk agent consume them. And
01's late-start check filters `kind=="stock"`, so an index returning only two
years of history would never be reported. `^CNX100` is a legacy pre-2015
symbol from before NSE's CNX→NIFTY rebranding; its 2015–2026 coverage is
unverified.

**Fix.** Assert on the calendar (length bounds, no duplicates, no weekends,
first date ≤ 2015-01-05, last = latest session). Audit the index tickers with
the same first_date/last_date/row-count checks (remove the `kind` filter).
Code gaps VERIFIED; `^CNX100` coverage CANNOT VERIFY.

### F15 — Whole-stock exclusion is itself look-ahead selection, and the pre-event label window is never purged
`exclude_from_model_universe` is all-or-nothing: VEDL's clean 2015–2026-04-29
history is discarded over a single artifact day. And with a 10-day forward
label, an artifact at `t` poisons the labels of `t−10 … t−1`, not just `t` —
nothing purges that window, for any stock, including the ones kept.

**Consequence.** Dropping VEDL and TMPV removes two large caps from the
holdout *because of information that only exists in the future of the sample*
— a reviewer will correctly call that look-ahead. And for every un-caught
artifact (SIEMENS, TRENT, RELIANCE's bonuses) ten labelled samples per event
are silently wrong in the direction of a large fake Down.

**Fix.** Event-window purging: for each artifact ex-date `e`, drop
label-bearing samples with `t ∈ [e − horizon, e]`, and embargo `horizon`
sessions on both sides of every walk-forward fold boundary. VERIFIED.

### F16 — Smaller items
- `rows_in = len(pd.read_csv(path))` parses the whole CSV a second time. Use
  the pre-drop length already in hand. Harmless. VERIFIED.
- VEDL: **ex-date 2026-04-30, record 2026-05-01**, close ₹773.60 → ₹289.50,
  ≈ **−62.6%**. The 1.2b report claims −64.9%, which does not match the
  published prices — reconcile before publishing a number. VERIFIED.
- TMPV: 2025-10-14 is the **record** date and was used as the discontinuity
  date. Always key corporate-action handling to the **ex-date**; they coincide
  for some T+1-era actions and differ for others, and a one-session error
  mislabels a −40% bar. (Subsequently confirmed: for TMPV the ex-date **is**
  2025-10-14.) VERIFIED.
- `pd.to_datetime(df.index).tz_localize(None)` raises `TypeError` on an
  already-naive index. It worked on the installed yfinance version but breaks
  on one returning naive dates. Guard it. INFERRED.
- 1.1's reported result includes "0 OHLC violations", but no committed code
  tests `High ≥ max(Open,Close)`, `Low ≤ min(Open,Close)`, or `High ≥ Low`.
  **Do not report a metric no committed code computes.** Add the three
  inequality checks. VERIFIED.
- T+1 vs T+2 matters to the cleaning pass in exactly one way: the ex-date /
  record-date offset when mapping an action to a bar (T+2 era: ex-date one
  session before record; T+1 from Jan 2023: commonly the same). So key off
  ex-dates. INFERRED.

---

## What the audit cleared

- `any([])` is `False`, so empty `flagged_moves` correctly yields no exclusion.
  The date string format matches. The *threshold* is the problem, not this
  expression.
- `raw_ret = df["Close"].pct_change()` **before** calendar alignment is the
  right choice — it measures consecutive traded sessions rather than spanning
  calendar gaps with NaN.
- Factor direction and sign convention: correct for Yahoo back-adjustment.
- Zero/negative price rejection including `Adj Close`: correct column set.
- `df.loc[idx-1, "Close"]` after `reset_index(drop=True)` with the `idx > 0`
  guard: safe.
- `auto_adjust=False` set explicitly, the `EXPECTED_COLS` presence check,
  MultiIndex flattening, dedupe-keep-last and sort in 01: all correct and
  necessary — the right defensive shape for a yfinance pull.
- Keeping a raw and an adjusted series side by side: correct architecture. The
  contents are wrong (F03) and they must be unified for ATR/barriers (F08),
  but the two-series design itself is right.
- Zero detected actions for KOTAKBANK, BAJAJFINSV, CHOLAFIN, JINDALSTEL,
  ADANIPOWER is **not** in itself evidence of corruption: with `Factor`
  understood as dividend-only with a 0.5% floor, all five are explicable
  (Kotak/Bajaj Finserv/Cholamandalam per-payout yields well under 0.5%,
  Jindal marginal, Adani Power pays no dividend). Cleared as a standalone
  symptom — but BAJAJFINSV's zero is simultaneously the *proof* of F03.
- **HINDZINC 2024-05-21 (+25.6%) is genuine** — Hindustan Zinc hit a record
  high on a zinc/silver rally, up ~13–20% intraday, on news, not a corporate
  action. Per project policy, leave it in. **This open item is closed.**
  VERIFIED.
- **TRENT's ~−33% is the 2026-06-04 ex-bonus**, a 1:2 bonus (−33.33%) plus a
  ₹6 dividend going ex the same session. The 1.2b report's "~2026-01-01" date
  was wrong. **This open item is closed.** VERIFIED.
- **The two Adani dates are genuine news, not corporate actions.**
  2023-12-05: group stocks rallied up to 15% on 2023-12-04 BJP state-election
  results, Dec 5 the continuation. 2024-11-21: US DOJ indictment and SEC fraud
  charges over an alleged $250m bribery scheme, group stocks down up to 20%.
  Per project policy both stay in as signal. **Both open items closed.**
  VERIFIED.
- **CGPOWER 2016-03-15 is a corporate action** — the Crompton Greaves
  consumer-products demerger, **−71.81%** (far worse than assumed). Now in the
  action table. The **2017–2018 CGPOWER drops remain unexplained** and
  uninvestigated. VERIFIED for 2016.
- TMCV showing no matching discontinuity is correct: it listed 2025-11-12, so
  the event predates its series. 229 bars matches. VERIFIED.
- LTM's 2528 rows are not a splice loss: L&T Infotech IPO'd July 2016, merged
  with Mindtree in 2022 to become LTIMindtree; 2528 sessions from mid-2016 to
  Oct 2026 matches a continuous series. Whether `LTM` is the current NSE
  symbol: CANNOT VERIFY — but `ind_nifty100list.csv` is the source of truth
  for the symbol, so it is self-consistent either way.
- ETERNAL carries full Zomato history: 1293 bars from the 2021-07-23 listing
  matches; the rename did not truncate the series. VERIFIED.
- TMPV retained the original Tata Motors listing and history (2910 rows),
  consistent with the PV entity keeping the listing. The problem is the
  unadjusted −40% bar, not a missing history.

---

## Recommendation on VEDL and TMPV: truncate, do not drop

Dropping is wrong for three reasons. (i) It is look-ahead universe selection:
removing 2015–2025 history on the basis of a 2026 action no investor at any
training-time date could know. (ii) It removes two large NIFTY100 caps from
the holdout specifically — changing holdout composition on forward-looking
information is exactly the error a reviewer rejects. (iii) VEDL has ~2,790
clean sessions and TMPV ~2,860 before their events.

**Truncate instead.** VEDL: ex-date 2026-04-30. Keep bars through 2026-04-29;
drop label-bearing samples with `t ≥ 2026-04-30 − 10 sessions` so the last
labelled sample's forward window closes before the artifact; discard all bars
from the ex-date onward (post-demerger Vedanta is a structurally different,
much smaller entity — a feature or label crossing that boundary is meaningless
even if the level is adjusted). TMPV: identical at 2025-10-14.

Three conditions make this correct rather than merely convenient. First, apply
the same treatment to **SIEMENS 2025-04-07**, **TRENT 2026-06-04** and every
entry in the action table — otherwise two cases are special-cased because
somebody found them while the identical defect stays elsewhere, which is worse
than dropping all four. Second, do not carry VAML, ENRIN or TMCV as
independent names in this pass: demerger children with 83/328/229 bars, no
training history, overlapping the truncated parents' exposure, existing only
because the demerger completed. Third, disclose per-stock effective holdout
coverage in the paper — truncating VEDL removes it from roughly the final five
months of a ~378-session holdout and TMPV from most of it, so the holdout is
not a balanced 100-name panel and must not be described as one.

The alternative, if these two names turn out to drive the results:
reconstruct the demerger adjustment factor from the entitlement ratio and the
children's listing-day prices and keep the parent series continuous. Superior
technically and it preserves the holdout, but materially more work, it needs
the children's prices (VEDL's only begin mid-2026), and it introduces an
estimated factor to defend. Do it only if a sensitivity check shows the two
names move the headline numbers.

---

## The one diagnostic that settles F03/F04/F12

Before writing more code, print raw `Close`, `Adj Close` and `Volume` for:

| symbol | window | what it tests |
|---|---|---|
| BAJAJFINSV | 2022-09-09 → 2022-09-16 | split+bonus, R=10 |
| RELIANCE | 2024-10-24 → 2024-10-30 | 1:1 bonus, R=2 |
| TRENT | 2026-06-02 → 2026-06-06 | 1:2 bonus, R=1.5 |
| SIEMENS | 2025-04-03 → 2025-04-09 | demerger, R≈2.01 |

Two further rows are the highest-value cross-checks available, because both
have exact officially discovered pre-open base prices: **RELIANCE 2023-07-20**
(Jio Financial demerger; NSE's special pre-open settled RIL at ₹2,580 and
JFSL at ₹261.85) and **ITC 2025-01-06** (ITC Hotels demerger, ₹482.60 →
₹455.60 discovered). These are the only rows that can prove or disprove the
F03 inference about what Yahoo does with demergers.

`02b_adjust_prices.py` ships a `detect_prefolded_splits()` function that runs
this test automatically across the whole panel and emits a verdict column —
running it over the real series answers the inference directly.
