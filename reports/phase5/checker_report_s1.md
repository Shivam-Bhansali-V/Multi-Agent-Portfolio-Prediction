# Audit of 30_clean_v2.py (checkpoint 5.1)

**Verdict: YES WITH FIXES** for the window up to 2025-03-31. No unadjusted split or bonus was found and the dividend factor is sound, but three demerger ex-dates in the dev window are unhandled, 45 real bars are deleted as "stale", and one whole session (2025-03-18) is lost.

Scripts: /root/check_s1/ (a1, a3–a10). Re-running the cleaner on a copy (/root/check_s1/rc) reproduces all 5 parquets in /root/repo/data/panel_v2 exactly.

## Findings

1. **CONFIRMED-OK — splits and bonuses are adjusted (claim 1).** 79 split/bonus ex-dates since 2015 (same-day actions combined): none shows a raw Close jump matching the ratio on the ex-date or within ±3 sessions. Largest ex-day move: ADANIPOWER 2025-09-22, +20.0% on a 1:5 split (wrong sign and size for an unadjusted split; holdout). Whether it is a real move is NOT VERIFIED.

2. **CONFIRMED-BUG — dev-window demergers are missed (claim 2 is false).** Three ex-dates remain in the panel as "real" returns:
   - **ITC 2025-01-06** (reference: VERIFIED): panel −4.55%. Yahoo back-adjusted by 1.0407 (482.60 / 463.74), not the discovered 1.0593. Holder return from the reference prices is (442.65 + 27.00) / 482.60 − 1 = −2.68%: error about −1.9 pp.
   - **ADANIENT 2018-04-05** (not in reference): Yahoo's back-adjustment factor changes 1.8352 → 1.55855 that day (recovered from tick alignment, 100% fit). Unadjusted close 151.45 → 147.85 (−2.4%); panel +14.95%. ADANIGREEN's first close (31.5, 2018-06-18) × 0.761 implies about +13.5%, so the error is probably small. The 0.761 ratio is from memory, NOT VERIFIED.
   - **ADANIENT 2018-09-06** (not in reference): factor 1.55855 → 1.0. Unadjusted close 210.95 → 163.70 (−22.4%); panel **+20.95%**, right only if the spun-off entity was worth about Rs 91 per share. The child is not in the data: NOT VERIFIED, possibly wrong by 10+ pp.
   - All 8 reference demergers checked. Repaired by the script: ABB (−5.8%), CGPOWER (−18.2%), MOTHERSON (+28.6%), TMPV (−40.2%), VEDL (−64.9%). Already adjusted by Yahoo: RELIANCE 2023-07-20 (−0.1%), SIEMENS 2025-04-07 (−2.8%). Missed: ITC.
   - Fix: add the three events, using the known ratio for ITC.

3. **CONFIRMED-BUG — zero-volume removal deletes real sessions (claim 3 partly false).** 729 zero-volume bars; 681 sit on the 7 "non-session" dates. The other 48 (45 in dev, 18 symbols) are on sessions where 90–99% of stocks traded: 2024-01-15 (10 stocks), 2015-08-12 (8), 2018-11-07, 2021-11-04, 2022-09-12, 2022-10-24 and others.
   - The next bar carries a two-day return: IRFC 2024-01-16 shows +25.1% and is counted as a "real ≥15% move".
   - POLYCAB 2023-05-24 has zero volume but a non-flat bar (+0.8%); it is deleted.
   - Fix: keep the NaN but flag the following bar as multi-day (or drop both from one-day labels); never drop non-flat bars.

4. **CONFIRMED-BUG — 2025-03-18 is a lost real session (dev window).** NIFTY100 traded (+1.65%) and ITC has volume 13.9M, but 95 stocks have flat zero-volume bars, so the date is dropped. Every 2025-03-19 return is a two-day return (panel mean +3.28%; index +2.21% over two days). Fix: re-download that date, or mask 2025-03-19 in one-day targets and features. The other 6 removed dates are post-dev; no stock traded.

5. **CONFIRMED-BUG (minor) — index.parquet has 9 NaN sessions** on which stocks traded: 2019-10-27, 2020-11-14, 2021-01-01, 2022-12-26, 2024-01-01, 2024-02-19, 2025-01-01, 2025-02-01, 2026-01-01. The index return is NaN on each and on the next day (pandas 3.0.5, no padding): 16 dev days of market-relative features. The TRENT 2026-01-01 repair silently used 0% as its target for this reason. Fix: fill from NIFTY50 or a cross-sectional mean.

6. **CONFIRMED-OK — the Adj Close factor is valid (claim 4).** All 100 stocks: the factor never decreases and never exceeds 1. Of 1,430 steps, 1,404 fall on a reference dividend date and all 1,404 match in size (within 10% relative). The 26 unmatched are tiny; 17 are APOLLOHOSP, absent from the reference. Both steps above 12% are genuine special dividends: HINDZINC 2016-04-06 (Rs 24 on 186.75), BPCL 2021-09-16 (Rs 29 on 244.98).
   - Caveat: `close_struct_adj` still contains 56 ex-dividend drops above 4% (HINDZINC −13.2%, VEDL −11.1%, BPCL −10.4%). Build return and momentum features from `close_total_return` only.

7. **CONFIRMED-OK — artifact repair mechanics.** On all 7 dates the price and total-return series give the same ex-day return, equal to the index return (0 for TRENT), and the pre-event Adj/Close factor is preserved. `iloc[:i]` has no off-by-one. Latent bug: an artifact on a stock's first bar gives `i-1 = -1` and would use the last row; no current event triggers it. Add `if i == 0: continue`.

8. **CONFIRMED-OK — output checks.** No zero-volume bar remains, no non-positive price, NaN masks are identical across close, total-return and turnover. `eligible` recomputes exactly from a cumulative bar count, so it is causal given the column set.

9. **CONFIRMED-BUG (design) — claim 5 holds only mechanically.** The 97 columns are today's NIFTY 100, so membership itself uses future information: IRFC, MAZDOCK, ADANIGREEN, ETERNAL, JIOFIN and others enter once they have 273 bars. Size of the bias is NOT VERIFIED.

10. **NOT VERIFIED — the other ≥15% moves.** 232 remain in dev. Beyond the ADANIENT and IRFC cases, the gap-dominated ones fall on dates I recognise as events but could not confirm offline (PSU banks 2017-10-25, Adani group 2023-01 and 2024-11-21, CGPOWER 2019-08). Also unchecked: the true holder return behind the index-return substitution for ABB, CGPOWER, MOTHERSON and ADANIENT 2015-06-03 (that bar's Open is 312 against a Close of 59.8, so Yahoo's OHLC is corrupt there).
