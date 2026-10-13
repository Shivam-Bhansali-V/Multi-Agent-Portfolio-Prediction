# Phase 5 report: cleaning v2, ranking model, claim tests, baseline rebuild

Date: 12 Oct 2026. Every number comes from scripts `30` to `36` in `scripts/`, run on the
raw Yahoo files (development window to 31 Mar 2025; the April 2025+ holdout was not used).
Each stage was reviewed by an independent checker; their reports are the four
`checker_report_s*.md` files in this folder. Stock list: today's NIFTY 100 (survivors only).

## Bottom line

- No method tested here predicts NSE large-cap returns well enough to claim an edge.
  Honest accuracy is 50 to 51.5% (chance 50%), and no excess return is statistically
  significant.
- The low-tier baseline paper's recipe, rebuilt under honest rules, has no predictive
  power at all and loses to equal-weight after costs.
- Four separate mistakes each manufacture a fake edge on this data, and each is measured
  below. That is the publishable result.

## 1. Cleaning (`30_clean_v2.py`)

- Yahoo's Close is already adjusted for splits and bonuses: 79 split/bonus dates checked,
  none unadjusted. The dividend factor matches the reference table on 1,404 of 1,404
  matched dates.
- The old universe filter dropped 66 stocks for any one-day move of 15% or more. Those
  moves are almost all real. v2 keeps 234 of them and repairs only 10 corporate-action
  errors (ADANIENT 2015-06-03, 2018-04-05, 2018-09-06; CGPOWER 2016-03-15; ABB
  2019-12-20; MOTHERSON 2022-01-14; ITC 2025-01-06; and TMPV, TRENT, VEDL in the holdout
  period). ITC uses the known holder return; the others use the index return that day,
  which is an estimate.
- 713 stale zero-volume bars removed; total-return prices built; 95 usable stocks, not 32.
- Effect of the repairs alone: fixing the two 2018 ADANIENT dates cut LightGBM's
  walk-forward excess from +7.1% to +4.8% a year.
- Not fixable: Yahoo has no stock data for the real session of 2025-03-18.

## 2. Ranking model (`31_features.py`, `36_pit_universe.py`)

Task: rank stocks by total return over the next 21 trading days; "accuracy" is the
above/below-median hit rate. Walk-forward 2018-01 to 2025-03, yearly refit on past data
only, top 20%, 20-day rebalance averaged over the four possible start days, one-day lag,
0.35% per round trip, benchmark = equal weight of the same stocks with the same costs.
Statistics from daily equity curves.

| Universe | Signal | Accuracy | Excess per year | 90% interval | Sharpe (benchmark) |
|---|---|---|---|---|---|
| All 95 | Momentum 12-1 | 51.5% | +3.9% | -2.2% to +9.8% | 1.23 (1.30) |
| All 95 | Momentum 6-1 | 51.1% | +4.7% | -0.9% to +10.5% | 1.30 (1.30) |
| All 95 | Ridge, no liquidity features | 50.0% | +1.1% | -4.0% to +5.9% | 1.22 (1.30) |
| All 95 | LightGBM, no liquidity features | 50.8% | -1.2% | -6.4% to +3.7% | 1.05 (1.30) |
| Top 50 by traded value, point-in-time | Momentum 12-1 | 51.2% | -0.5% | -7.0% to +6.2% | 0.66 (0.86) |
| Top 50 by traded value, point-in-time | LightGBM, no liquidity features | 50.8% | -1.7% | -8.1% to +4.3% | 0.63 (0.86) |

Max drawdown is about -40% for momentum and -37% for the benchmark.

## 3. Four ways to get a fake edge on this data

1. **Survivor-only stock list.** Equal weight of today's NIFTY 100 names returned 24.6% a
   year over 2018 to 2025; the NIFTY100 price index returned 11.6%. Choosing the 50
   most-traded names on each date instead (83 different stocks pass through) lowers the
   benchmark to 16.1% and turns momentum's +3.9% into -0.5%.
2. **Training on the future.** With all 24 features, ridge and LightGBM scored by block
   cross-validation show +10.5% and +8.9% a year with intervals that exclude zero. Trained
   on the past only, the same models show +3.4% and +5.4% with intervals that include
   zero. The checker isolated the cause: training on blocks after the test block.
3. **Liquidity features on a survivor list.** That edge comes from two features
   (`amihud_60`, `turnover_trend`). Removed, the models fall to between -1.5% and +3.9%.
   The illiquidity signal works when a stock is compared with its own full-sample
   liquidity (IC 0.088) and not when compared with its own past (IC 0.003). It cannot be
   separated from survivorship without the dropped companies.
4. **Measuring drawdown and cost loosely.** Sampling the equity curve every 20 days
   understated max drawdown by about 10 points (-27% vs -37% for the benchmark).

## 4. Published claims tested (`34_claim_tests.py`)

Time blocks were split at random into a design half and a confirm half.

| Claim | Result |
|---|---|
| Momentum predicts winners | IC +0.030 and +0.035 in the two halves; accuracy 51.5% at 21 days, 52.4% at 63 days; not significant |
| NSE momentum-index formula is better | No: IC 0.034 / 0.017, same as plain momentum |
| Low volatility wins | Unstable: sign flips between halves (regime effect) |
| RSI, MACD, Bollinger, EMA rank stocks | No: accuracy 49.5 to 50.1% |
| ML beats simple signals | Only through items 2 and 3 above |
| Trade only confident calls | Top and bottom 20% of calls: 51.3 to 51.8% |
| Choose the best signal on half the data | The choice (beta) reversed on the other half |

29 signals were tested with no multiple-testing correction, so isolated t-values near 2
mean little.

## 5. Baseline paper rebuilt (`35_baseline_replication.py`, `35b_paired_test.py`)

Iskakov et al. (2026), ETASR 16(4): 20 large caps, 8 indicator inputs, 60-day window,
next-day forecast per stock, 10-forecast smoothing, rank-weighted daily portfolio. Rebuilt
with ridge, lasso, random forest, gradient boosting and an MLP; scaler fitted on training
rows only. **LSTM was not run** (PyTorch could not be installed), so this is not a
replication of their best model or of their exact numbers.

Walk-forward 2018-01 to 2025-03 (1,789 test days):

- Next-day direction accuracy 50.0 to 50.5%. Always predicting "up" scores 51.3%.
- Their own rules (no cost, no delay): -0.5% to -3.6% a year against equal weight.
- With 0.35% round-trip cost and one-day delay: -2.6% to -5.1% a year; every interval
  excludes zero. Sharpe 0.67 to 0.82 against 1.00 for equal weight.
- Our 12-1 momentum on the same 20 stocks: +1.4% a year (interval -4.0% to +6.8%),
  Sharpe 0.96.
- Paired, ours minus theirs: +4.1% to +6.5% a year as each is designed (87 to 96%
  bootstrap probability). About half of that is simply trading monthly instead of daily:
  at zero cost the gap is +2.1% to +5.3%, and with their forecast pushed through our
  monthly engine it is +1.1% to +9.2% (only random forest and gradient boosting above 90%).
- On their short 80/20 split (261 test days) our momentum lost 9.9% to equal weight and
  did worse than their models.

## 6. What can and cannot be claimed

Can: the baseline recipe has no next-day predictive power on this data and loses to
equal weight after costs; survivorship, non-causal validation and liquidity features each
create a large spurious edge; plain momentum is the only signal with a consistent sign.

Cannot: that any model here beats equal weight, that ours beats the baseline as a signal,
or that these results hold out of sample (the holdout is unopened and is itself
survivor-biased).

## 7. Next

`run_33_download_and_model.bat` downloads today's NIFTY 500 and reruns cleaning, features
and the point-in-time test with the top 100 and 200 by traded value. It has not been run
against live Yahoo. A list with dropped companies is still missing.
