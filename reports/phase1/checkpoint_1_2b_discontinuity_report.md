# Checkpoint 1.2b: discontinuity scan and exclusion fix

Scope: scan all 100 cleaned stocks for single-day raw-Close moves >15%,
explain the cause of each where possible, and apply a suitable fix. This is
an amendment to checkpoint 1.2, not a replacement of it.

## 1. Bug found and fixed in `02_clean_adjust.py`

The script computed a >60% raw-Close "sanity ceiling" flag (`flagged_moves`)
but never wired it into `exclude_from_model_universe` — only an
"unexplained" **factor-step** could exclude a stock. A demerger that Yahoo
never adjusts for (Factor stays ~1.0) produces zero factor-step signal, so
this check alone could never catch VEDL or TMPV. Fixed: a big move not on a
confirmed market-wide date now also triggers exclusion. TMPV's actual drop
(-40.2%) is below the 60% ceiling, so it's additionally forced by name via
`KNOWN_UNADJUSTED_DEMERGERS`, which is honest about being a manual override,
not an emergent detection.

Re-running the full pipeline with the fix: **924 corporate-action step
events, 0 unexplained steps, 1 stock over the 60% sanity ceiling (VEDL),
2 stocks now excluded from the modeling universe: TMPV and VEDL.**

## 2. VEDL and TMPV — confirmed unadjusted demergers

| Stock | Date | Raw Close move | Yahoo Adj Close adjustment applied? | Source confirms |
|---|---|---|---|---|
| VEDL | 2026-04-30 | -64.9% | No (Factor ≈ 1.0 across the date) | Vedanta's 5-way demerger, ex-date ~May 2026; multiple sources describe a 60%+ share-price drop on ex-demerger adjustment |
| TMPV | 2025-10-14 | -40.2% | No (Factor ≈ 1.0 across the date) | Tata Motors Commercial/Passenger Vehicles demerger, record date 2025-10-14 |

**VEDL: excluded, per your explicit instruction ("exclude VEDL for now").**
**TMPV: I have excluded it by the same rule, but this is MY inference from
the pattern matching VEDL, not something you confirmed — please tell me if
you'd rather keep TMPV in with a flag instead of excluding it.**

TMCV (the other half of the Tata Motors demerger) was checked and shows no
matching discontinuity in this dataset — most likely because it only began
trading after the split, so its own price series never contains the event.

## 3. Market-wide dates — confirmed by web search, left UNEXCLUDED (real signal)

11 dates account for 80 of the 242 flagged single-stock events. Per your
instruction to treat COVID-era moves as expected market-wide noise, and by
the same logic for the other confirmed macro events, none of these are
excluded or treated as data defects — they are genuine market history and
are deliberately kept in the training data as-is.

| Date(s) | Event | Status |
|---|---|---|
| 2020-03-12, 2020-03-20, 2020-03-23, 2020-04-07 | COVID-19 crash and early recovery | Confirmed (your instruction + widely documented) |
| 2023-01-25 / 2023-01-27 | Hindenburg Research report on Adani group | Confirmed (web search) |
| 2017-10-25 | Rs 2.11 lakh crore PSU bank recapitalisation announcement | Confirmed (web search) |
| 2024-06-04 | 2024 general-election result day (narrower BJP majority than exit polls) | Confirmed (web search) |

Other stock-specific events confirmed this pass (not market-wide, but
genuine news, so also left unexcluded):
- **POLYCAB**, Jan 2024: Income Tax Department raid, ~Rs 1,000cr alleged
  unaccounted sales — confirmed.
- **CGPOWER**, 2019: accounting fraud / SFIO probe — confirmed for the 2019
  event specifically; CGPOWER's earlier 2016–2018 drops are NOT yet
  investigated (see open items below).
- **IDEA**, 2019–2020 (26 flagged events): AGR dues crisis — confirmed as a
  recurring, genuine cause across this period.

## 4. Open items — NOT yet resolved (stated plainly, not glossed over)

- **2023-12-05 and 2024-11-21** Adani-group dates: not yet individually
  searched. Working guess (unverified) is further Hindenburg-saga fallout
  and/or the Nov 2024 US DOJ bribery indictment of Gautam Adani, but I have
  not confirmed either.
- **CGPOWER 2016–2018** drops: cause not yet investigated.
- **TRENT, ~2026-01-01** (-33%): found news about growth concerns around
  Jan 6 2026, but the dates don't line up exactly with the flagged
  2026-01-01 event. Not reconciled — could be a non-trading-day data
  artifact or a different, earlier cause.
- **HINDZINC, 2024-05-21** (+25.6%, a rally, not a drop): found two
  competing explanations (special-dividend anticipation vs a China-demand
  rally in base metals). A +25.6% move is inconsistent with an ordinary
  ex-dividend mechanical adjustment (which would show as a drop), so this
  looks organic/news-driven rather than a corporate-action artifact, but
  this is not conclusively resolved.
- **~100+ remaining singleton stock-day events** (IRFC, POWERINDIA,
  MAZDOCK, HAL, GODREJCP, MUTHOOTFIN, SHRIRAMFIN, CHOLAFIN, BPCL,
  BANKBARODA, JINDALSTEL, TITAN, ZYDUSLIFE, TORNTPHARM, SUNPHARMA, WIPRO,
  TATAPOWER, UNIONBANK, LTM, M&M, MAXHEALTH, INFY, IOC, INDIGO, DLF, the
  Adani group's early-listing-era dates, BSE, MOTHERSON, DIVISLAB, GAIL,
  and others) have NOT been individually investigated. None of them hit the
  60% sanity ceiling or TMPV/VEDL-style unadjusted-demerger pattern, so the
  pipeline does not exclude them — but I have not confirmed each one is
  genuine news rather than a data artifact. I'm telling you this directly
  rather than claiming full coverage: if you want these individually
  checked too, say so and I'll continue through them.
- The adversarial "debate agent" review has only had one round, and that
  round's prompt had a bug (the script text wasn't actually embedded, so
  its critique was based on the stated method/results only, not the real
  code). No second round has run yet.

## 5. What changed mechanically in this pass

- `scripts/02_clean_adjust.py`: fixed (see §1).
- `data/clean/VEDL.csv`, `data/clean/TMPV.csv`: unchanged in content, but
  both now carry `exclude_from_model_universe = True` in the regenerated
  `checkpoint_1_2_summary.csv`.
- `reports/phase1/checkpoint_1_2_summary.csv`, `checkpoint_1_2_corp_action_events.csv`,
  `checkpoint_1_2_report.md`: regenerated with the fix applied.
- This file: new.
