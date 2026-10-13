# Stage 4 review: baseline rebuild (35) and paired test (35b)

## Verdict
No look-ahead leakage found; the CSV numbers reproduce. But the headline "ours beats the baseline by 4.9-7.2%/yr" is **not supportable as a statement about signal quality**. For three of five models it is mostly a trading-frequency/cost effect (finding 1). Ours does not beat equal weight either (+1.4%/yr, CI -3.7 to +6.5). Three small bugs. Scripts: `/root/check_s4/c1.py`-`c4.py`. Figures are protocol B.

## Findings (by impact)

**1. CONFIRMED-BUG (interpretation) - comparison confounds signal with rebalance frequency.**
Ours minus baseline, lag 1, calendar-fixed (see 3):

| model | as designed, with cost | both zero cost | baseline top-third 20-day, same engine, with cost (10d / 20d smoothing) |
|---|---|---|---|
| ridge | +5.1% p=.92 | +2.4% p=.74 | +1.2% p=.62 / +0.2% p=.53 |
| lasso | +5.1% p=.92 | +2.5% p=.74 | +0.7% p=.57 / +0.4% p=.54 |
| MLP | +4.1% p=.87 | +2.1% p=.73 | +3.7% p=.82 / +1.5% p=.65 |
| GBM | +6.0% p=.95 | +3.3% p=.81 | +6.9% p=.93 / +6.8% p=.91 |
| RF | +6.5% p=.96 | +5.3% p=.92 | +8.9% p=.96 / +9.1% p=.96 |

Baseline cost drag is 1.6-3.0%/yr (one-way turnover 2.4-4.1%/day vs ours 0.9%). Without costs only RF differs from equal weight (-3.5%, CI -5.7 to -1.3); lasso, GBM, MLP are -0.4 to -1.5% with CIs spanning zero. Our momentum in *their* shape (daily rank-weighted) is -0.9%/yr vs equal weight.
Fix: report the matched-frequency row beside the as-published row.

**2. CONFIRMED-BUG - 35b paired bootstrap is misaligned by one day.**
`portfolio()` labels a return by its start date (t -> t+1 stored at t); `daily_backtest` labels by end date. The inner join pairs different days: correlation of the two series is -0.04 as written, +0.85 when aligned. Estimates barely move (ridge +5.82% -> +5.57%); probabilities rise: ridge .912 -> .938, RF .949 -> .971, GBM .940 -> .961, MLP .877 -> .905. As written it is conservative but not a paired test.
Fix: relabel `net` to the next calendar date before the join.

**3. CONFIRMED-BUG - calendar mismatch makes the baseline 100% ITC for the last 9 days.**
Raw ITC has a 2025-03-18 row with volume; TCS has volume 0 and the cleaned panel lacks that date. The pivot gains a row where 19 stocks are NaN, so `rolling(10)` blanks them for 9 rows (S has 9 rows with 1 non-NaN name, in both A and B). BRITANNIA (4 missing days) and BAJAJ-AUTO (1) likewise drop out for 10 days each (50 rows with 19 names); their entry/exit trades are not costed. Effect is small: baseline vs equal weight lasso -3.96% -> -3.70%, RF -5.32% -> -5.10%; ours minus baseline falls about 0.7 pt (ridge 5.8 -> 5.1).
Fix: reindex the pivot to the panel calendar and forward-fill short gaps before smoothing.

**4. CONFIRMED-BUG (minor) - accuracy denominators.** 20 NaN labels (last day) count as wrong and in the up-rate denominator. Clean: ridge 50.46% (CSV 50.43), always-up 51.32% (CSV 51.15). 

**5. CONFIRMED-OK - leakage and alignment.** `y` at t equals log(Close[t+1]/Close[t]) (3 stocks checked to 1e-15). Window's last row is date t, first is 59 rows earlier. Scaler min/max from train rows only. The last-train-row drop works (2020-12-31 removed) and is sufficient; that label is in any case known by the first test close. Walk-forward trains strictly before each test year. Ridge refit (HDFCBANK, fold 2021) matches saved predictions exactly.

**6. CONFIRMED-OK - `portfolio()`.** Hand example: lag 0 applies the weight of close t to t -> t+1; lag 1 to t+1 -> t+2. Drift, turnover, cost and `traded.iloc[0]=1.0` (initial buy, one side) are right; all-ones score gives 1/20 each. Rolling mean is trailing. Independent recomputation (no cost / cost / lag 1 + cost): ridge -1.31 / -4.39 / -3.95%, RF -4.18 / -5.81 / -5.36% (CSV -1.31 / -4.36 / -3.92; -4.18 / -5.77 / -5.32; the 0.03-0.04 gap is the uncosted entries in 3).

**7. CONFIRMED-OK with caveat - raw vs total return.** corr(y, total-return next day) = 0.997; signs differ on 0.2% of rows, so accuracy moves by at most about 0.2 pt. 18 rows differ by more than 3% (BPCL 2021-09-15: -11.0% raw vs +1.6% total). Fix: build the target from the total-return panel.

**8. CONFIRMED-OK - `ours()`.** Momentum uses prices from t-21 and t-252 only; trade one day after the signal. Averaging the four offsets is a legitimate four-sleeve portfolio (first 15 days have fewer sleeves; negligible). The two equal-weight benchmarks (20-day vs daily) differ by 0.17%/yr. The CI in `ours()` is a mean of four CIs, not a CI of the mean.

**9. Fairness of the rebuild.** Smoothing and rank weighting *help* the baseline: with no smoothing it loses 11-18%/yr after costs (turnover 9-19%/day); daily top-third loses 6.6-9.1%. So the as-built shape is not a handicap. NOT VERIFIED: fidelity to the paper's hyper-parameters (paper not available here). LSTM was never run; one seed only. Train-only min-max puts test OBV/SMA outside [0,1] (HDFCBANK 2021: up to 1.27). Rank IC of raw forecasts is -0.012 to +0.009.

**10. Robustness.** Ours minus baseline is positive in 2018 and 2020-24, about zero in 2019, negative in 2025 Q1. Protocol A portfolio numbers NOT VERIFIED (alignment only).

## What can be claimed
- Can: rebuilt under train-only scaling and walk-forward, the recipe has no next-day predictive power (accuracy 50.0-50.5% vs 51.3% always-up; rank IC about 0), and its daily signal-weighted portfolio trails equal weight by about 3-5%/yr after 0.175% costs (CIs exclude zero), 0.4-3.5% before costs (only RF significant).
- Cannot: "our method beats the baseline" as a signal claim. Only RF and GBM survive frequency matching, none at 95% two-sided. Cannot claim ours beats equal weight, nor a replication of the paper's LSTM or exact numbers.
