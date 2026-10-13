# Review of checkpoint 5.3 (scripts 31/32)

## Verdict: NOT TRUSTWORTHY as absolute returns; trustworthy only as "no demonstrated edge over equal weight"

The mechanics (features, target, purging, costs, arithmetic) are clean and I reproduced the momentum and benchmark numbers to 4 decimals with independent daily-return code. But the universe is today's index membership, so every CAGR level is survivorship-inflated, and nothing beats the benchmark with statistical or risk-adjusted significance. I did not re-run `32_xs_model.py`; ridge/LightGBM predictions are NOT VERIFIED beyond metric recomputation from the periods CSV.

Scripts: `/root/check_s2/c1.py` (look-ahead, target), `c2.py` (purge, costs, metrics), `c3.py` (replication).

## Findings, by impact

**1. CONFIRMED-BUG: survivorship / look-ahead universe.** The universe is `data/reference/ind_nifty100list.csv` (current constituents; `31_features.py:27`), and all 97 symbols have a price on 2026-10-07 (c3). No delisted or demoted stock exists. The equal-weight benchmark earns 24.6% versus 11.6% for the NIFTY100 price index over the same window; dividends and equal weighting cannot explain 13 points. Stocks promoted into the index after 2018 are by construction past winners, so this plausibly favours momentum specifically. The membership list also post-dates the holdout, so the holdout is already contaminated by universe choice. Size of the bias NOT VERIFIED (no historical constituents offline).
*Fix:* rebuild the universe from point-in-time NIFTY100/500 membership including dead stocks; until then report excess returns only, with this caveat.

**2. CONFIRMED-BUG (interpretation): no significant outperformance.** From the periods CSV: excess t-stats are momentum 0.63, ridge 0.52, LightGBM 1.47; all bootstrap 5% bounds are negative (reproduced: -0.040/-0.042/-0.021). On daily data, momentum Sharpe is 1.15 versus 1.29 for equal weight. Momentum excess moves from 1.8 to 5.1 points depending only on which day the 20-day cycle starts (offsets 0/5/10/15). Rank IC 0.032 has a naive t of 2.76, about 1.3 after allowing for 4x label overlap.
*Fix:* headline excess return with CI, averaged over the four rebalance offsets; do not claim LightGBM > momentum.

**3. CONFIRMED-BUG: max drawdown understated.** `stats()` (`32_xs_model.py:100`) uses 20-day period endpoints. Daily replication: momentum -40.7% (reported -28.6%), equal weight -37.1% (reported -26.7%).
*Fix:* compute drawdown and volatility from a daily equity curve.

**4. CONFIRMED-BUG (small): annualisation factor.** `PER_YEAR = 252/20` (`:27`), but the window has 1,780 trading days in 7.21 calendar years (246.8/yr, 12.34 periods/yr). Calendar-true CAGR: momentum 26.1% (not 26.7), LightGBM 28.7% (not 29.4), benchmark 24.0% (not 24.6). Sharpe drops about 0.01. Excess is barely affected.
*Fix:* annualise by elapsed calendar time.

**5. CONFIRMED-OK: no look-ahead in features.** For 4 dates (2017-06-23, 2020-03-23, 2022-08-22, 2025-02-14) I recomputed 17 features, including rolling max, rolling std, ewm/MACD/RSI, beta, idio vol and the sector-mean feature, from inputs truncated at that date: zero mismatches, and my ranked values equal `xs_panel.parquet` exactly. Separate from-scratch values for RELIANCE (momentum, 52-week high, vol_20, beta) match. `eligible` is `cumsum(bars) >= 273 & close.notna()` (`30_clean_v2.py:94`), which is causal. Forward-fill: leading NaNs stay NaN; only 44 interior gaps in the dev window; 9 of 39,144 labels touch a stale price. Negligible.

**6. CONFIRMED-OK: target and execution timing.** `fwd_ret == TR[t+22]/TR[t+1]-1` on 2,000 random rows. Sample dates are exactly 5 days apart (446/446). Walk-forward: 89 periods, all entries exactly 20 days apart, contiguous with no gap or overlap; first entry 2018-01-02, last exit 2025-03-20; the end clamp (`:64`) never binds (2521 < 2527). No panel row after 2025-03-31; latest price used is 2025-03-28. Minor: label is 21 days, holding is 20.

**7. CONFIRMED-OK: purging.** Over all 45 CPCV splits and all 8 walk-forward years, the minimum gap between any train label window and test label window is 14 trading days; the last backtest holding day in a test block ends 15 days before the next train label starts. Training rows after a test block do have feature lookbacks overlapping the test label period (239 days in my example). Judgement: irrelevant for momentum (untrained) and for the walk-forward (trains on past only); for CPCV ridge/LightGBM it is a weak, indirect channel since features are cross-sectional ranks and labels are disjoint. CPCV results for learned models are in any case weaker than momentum (accuracy 50.2/50.4%), so there is no inflation to worry about.

**8. CONFIRMED-OK: costs.** A 4-stock hand example matches `backtest()` exactly for first rebalance (traded = 1.0), drifted weights, a stock leaving the universe (its sale is counted), exit cost on the last period, and the benchmark. Treatment is reasonable to mildly conservative. Note: `max(...,3)` at `:66` forces a 3-name minimum. Whether 0.175% per side is adequate is NOT VERIFIED.

**9. CONFIRMED-OK: metrics and replication.** Summary CAGR/Sharpe/drawdown recompute exactly from the periods CSV. Calling the script's own `score_fold` for momentum reproduces the CSV to 1e-16. Independent accuracy 0.5154 and rank IC 0.0324 match. Independent daily-return replication: momentum 26.73%, equal weight 24.60% (252-day basis) versus reported 26.73% / 24.60%; gap 0.00 points. Gross: 28.1% and 24.8%. One-way turnover 24% per rebalance matches. Block bootstrap (circular, block 6) is correctly coded; period excess autocorrelation is about 0, so it is adequate.

**10. NOT VERIFIED:** "hyper-parameters fixed before any result was seen" (`:13`); CPCV CSVs being current; ridge/LightGBM walk-forward predictions; data quality of the upstream price adjustment.

**11. Other referee points.** Execution-lag sensitivity is healthy (momentum CAGR 28.0/26.7/25.4% at lag 0/1/2). Accuracy near 50-51.5% is economically tiny; the shuffled control at 50.2% equals real LightGBM in CPCV (50.2%), i.e. LightGBM shows no detectable skill there. Single 7-year bull-heavy window on about 90 names.
