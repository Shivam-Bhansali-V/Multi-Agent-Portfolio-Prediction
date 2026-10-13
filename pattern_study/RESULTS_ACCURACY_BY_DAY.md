# Accuracy by holding day and "best day" check (12 Oct 2026)

Scripts: `accuracy_deep_dive.py` (8 accuracy definitions, delay, confirmation, filters) and
`horizon_test.py` (every pattern at 1-20, 25, 30, 40, 60 days; best-day pick on 2015-19 checked on 2020-25;
follow-ups). Run each with no arguments from this folder (~30 s each). Full write-up with tables and
charts: the "Pattern accuracy and project review" doc on claude.ai.

## Findings
1. "Eventually right" is real but not an edge: patterns touch 2% their way within 20 days 76-84% of the
   time; any random day does 78-82%.
2. No holding day rescues the patterns. Beats-the-market accuracy stays within a few points of base at
   every day from 1 to 60.
3. Picking each pattern's best day on 2015-19: +4.0 points on average. Same day on 2020-25: -2.6 points;
   7 of 25 stay above zero. A per-pattern "best N days" rule is overfitting.
4. Waiting 1/3/5 days or for a confirmation candle does not help (bullish chart patterns: -0.49%, -0.53%,
   -0.35%, -0.14% vs market at delay 0/1/3/5; never positive).
5. Kept for the holdout (hypotheses, not results):
   - Descending Triangle breakdown: first 1xATR move is down 55.8% vs 47.4% (both time halves, both stock
     halves). As an exit it saves about the 0.35% cost, so use it only as a free "don't buy today" flag.
   - Head and Shoulders / Double Top on a stock below its 200-day average: lags the market ~61% vs 54%
     over 10 days, same in 2015-19 and 2020-25 (186 cases). Don't-buy / exit rule.
   - Hammer at 2 days held in both periods but adds only ~0.14% over the market: below cost.

## Not possible from this sandbox (needs your PC or new data)
- Point-in-time NIFTY 100 / 500 members with delisted companies (NSE archives).
- Quarterly results with announcement dates for post-earnings drift (BSE/NSE filings or a screener export).
