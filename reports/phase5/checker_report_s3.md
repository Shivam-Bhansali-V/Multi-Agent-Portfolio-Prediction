# Review of checkpoints 5.4 / 5.4b

## Verdict

No arithmetic bug found in the backtest, targets, alignment or purge, and all four CSVs reproduce exactly. Conclusions (a) and (b) stand as descriptions, with weak statistics. Conclusion (c) is half right: the edge is the liquidity features, but **the survivorship attribution is asserted, not demonstrated**, and the block-CV "significant" edge is inflated by training on future blocks. "No honest edge can be shown on this universe" is the defensible statement; "the illiquidity edge is survivorship" is not proven and cannot be with this data.

Scripts: `/root/check_s3/c1.py` to `c5.py`; reruns on a private copy.

## Findings, by impact

**1. CONFIRMED-BUG (method): block CV trains on the future, and that is where its edge comes from.**
Same test rows (blocks 2-9), same unseen-stock folds, all 24 features, top-20% excess per year:

| model | published block CV | trained on past blocks only | trained on future blocks only (blocks 2-8) |
|---|---|---|---|
| ridge | +12.2% (IC 0.032) | +5.4% (IC 0.027) | +8.6% |
| lgbm | +9.3% (IC 0.032) | +2.6% (IC 0.022) | +5.1% |

- Not a label leak: the gap between train label end and test start is 13 trading days on both sides of every block checked (0, 4, 9); no stock overlap.
- Not a period mismatch: block CV on 2018+ dates only still gives +12.3% / +9.2%.
- So the ablation table's CV vs walk-forward gap (10.5% vs 3.4%) is non-causal training, which the author's explanation does not cover.
- Fix: report walk-forward (or past-only block) numbers as the headline; drop the block-CV CI as evidence of significance.

**2. NOT VERIFIED (interpretation): "liquidity edge = survivorship".** Evidence for amihud_60 (IC 0.055, excess +15.3%/yr overall):

| subset | n | IC (t) | top-20% excess/yr |
|---|---|---|---|
| turnover-rank risers | 47 | 0.063 (3.7) | +24.5% |
| non-risers | 48 | 0.036 (2.1) | +8.0% |
| top-half liquid at first date | 38 | 0.024 (1.3) | +7.2% |
| all present at first date | 76 | 0.042 (2.9) | +7.6% |
| late entrants only | 19 | 0.132 (3.3) | n/a |
| excluding the 15 named stocks | 80 | 0.058 (3.9) | +12.4% |

- Consistent with survivorship: the effect halves among stocks present in 2016 and is strongest in late listings and ex-post risers.
- Right-tail driven: top-quintile forward return mean 3.70% vs median 2.28% (bottom quintile 1.31% / 1.22%). Spread: 2.4% mean, 1.6% winsorised, 1.1% median. ADANIENSOL and ADANIGREEN supply 31% of the top quintile's summed excess.
- Strongest single piece: illiquidity relative to the stock's full-sample mean has IC 0.088 (t 5.6), but relative to its own trailing mean IC 0.003 (t 0.2). The signal is "illiquid compared with its own future", a look-ahead signature.
- Against the author's story: removing his 15 names barely dents it; the top-half-liquid subset keeps +7.2%; his own table shows turnover rank falling or flat for most of the 15 (only TRENT, BSE, ABB rise); correlation of mean amihud with turnover-rank change is 0.13.
- It is not a vol/beta/momentum proxy: residual IC 0.041 (t 3.6). Size or price-level effect: NOT VERIFIED, no market cap in the data.
- No analysis here separates a real premium from survivorship: every subset is still conditioned on 2026 membership. Needs point-in-time constituents including deleted names.
- Fix: reword (c) to "indistinguishable from survivorship on this universe" and include the tables above.

**3. CONFIRMED-BUG (minor): `ic_table` t-stat uses one arbitrary offset.** It disagrees in sign with the mean IC in the CSV (mom_6_1_vs_sector confirm: IC +0.0086, t -0.06; rev_1w confirm: IC -0.004, t +1.03). Fix: average over the four offsets or use Newey-West on all dates.

**4. CONFIRMED-BUG (minor): `day_is_design` mislabels boundary days.** 2.5% of days (offset 0) carry returns of a position formed in the other half; 3.9% are in the wrong block. Fix: label each day by the block of the rebalance date that formed the position.

**5. CONFIRMED-OK: `daily_backtest`.** Matches a hand-rolled 4-stock synthetic to 1e-16 (costs, drift, first-day cost, segment joins) and my independent implementation on real data to 1e-15.

**6. CONFIRMED-OK: `at()`, fwd_5 / fwd_63, fwd_ret, signs.** Four (date, symbol) pairs hand-checked. fwd_ret equals close t+1 to t+22 exactly. amihud_60 high means illiquid (correlation with turnover rank -0.95). `SIGN` is applied once.

**7. CONFIRMED-OK: independent recompute matches the CSV.**

| signal | IC design | IC confirm | accuracy | excess/yr, offset 0 (CSV 4-offset mean) |
|---|---|---|---|---|
| mom_12_1 | 0.0297 | 0.0353 | 0.5154 | +6.0% (+5.1%) |
| rsi_14 | -0.0157 | -0.0111 | 0.4946 | +0.1% (0.0%) |
| amihud_60 | 0.0317 | 0.0776 | 0.5134 | +16.3% (+15.3%) |

**8. (a) holds, but it is underpowered rather than "no effect".** About 112 non-overlapping periods; momentum IC rises to 0.055 at 63 days. macd_hist accuracy is 50.07%, just outside the stated 49.5-50% range.

**9. (b) holds numerically, but "flip" is a regime effect.** Per-block IC of raw vol_252 swings from -0.11 to +0.15 and beta from -0.15 to +0.12. The design/confirm contrast mostly reflects which blocks landed in which half.

## Other referee objections

- 29 signals tested, with no multiple-testing correction.
- The date-level IC t-stat ignores that amihud is 83% between-stock variance, so the effective sample is about 95 stocks. Stock-clustered bootstrap of the IC still gives a 90% interval of 0.038 to 0.071.
- Prices run to 2026-10-07, about 18 months past `DEV_END`. I did not touch that holdout; it is still survivor-biased.
