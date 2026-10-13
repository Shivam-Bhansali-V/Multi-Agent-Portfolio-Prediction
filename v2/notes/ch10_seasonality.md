# Ch 10 — Seasonality and Calendar Patterns (pp. 427–484)

## Concept
- Seasonality = a cycle that repeats each calendar year, driven by **nature (crops, weather) or consumer/institutional behaviour** (travel, holidays, tax, fund flows). It persists even when masked by trends (carry costs, harvest storage pressure always exist).
- Patterns change over time (global supply shifts: wheat low moved May/Jun → Mar/Apr in 2001–10; S&P "sell in May" pattern changed after 2000). Use broad windows, monthly data, not exact days.
- **Only trade seasonal patterns with a clear fundamental reason.** Anecdote: "good South American coffee crop → good European wheat" held 18 years — found by testing hundreds of combos → failed the first year traded. **Computer validates a belief, never creates one.**

## Data cautions
- Back-adjusted futures distort levels (wheat 1965: cash $1.72 vs back-adjusted $12.45; rates can go negative) → no percentages on back-adjusted data; cash vs futures seasonal patterns differ (futures discount expected seasonal moves in advance). Trade the series you can actually trade.
- Stocks: splits change historical levels.

## Methods to compute a seasonal pattern (monthly data)
1. **Monthly average/median** table (years × months); Adj = monthly avg / grand avg − 1. Median preferred (robust to extreme years).
2. **Index/percent changes** (100 → ×pₜ/pₜ₋₁) so high-price years don't dominate. AMZN seasonality: strong Oct–Dec (holiday retail), LUV: Apr–Jul and Nov peaks; Aug/Sep/Jan lows.
3. **Detrend** first: regression residuals or first differences (Bernstein: monthly change table → average change and **% of years up per month**). Detrending rarely changes which months are strongest.
4. **Yearly-average method**: each month / that year's average − 1; APPᵢ = 100·(1/N)Σₙ[12·Pᵢₙ/Σⱼ Pⱼₙ].
5. **Link relatives**: ratio month/prev month → average link relatives → chain relatives (Jan = 1) → correct for compounded trend (rate = (end/start)^(1/N) − 1) → normalise to average = seasonal index.
6. **Moving-average (ratio-to-MA) method**: centred 12-month MA (avg of months 6 and 7 of a 12-MA) = trend; seasonal factor = price − centred MA (or ratio); average by calendar month → seasonal index. Simple and as good as any. (Centred MA uses future data — only for estimation, not live signals.)
7. **X-11 / X-12-ARIMA** (Census/BLS): iterative centred MAs, weighted 5/7-term seasonal MAs, outlier down-weighting (>2.5σ weight 0, 1.5–2.5σ linear), Henderson trend MA; X-12 adds regARIMA and intervention for "ramps". (Modern: statsmodels STL / X-13.)
8. **Winters (Holt-Winters)**: Xₜ = (a + bt)·Sₜ + eₜ, trend and seasonal factors updated by exponential smoothing.

## Robustness checks
- A few extreme years distort averages (cotton 2009–11) → compare averages vs medians, look at max/min monthly move per month, sort monthly changes.
- **Seasonal volatility**: monthly volatility should build up gradually toward a genuine seasonal peak; a one-month spike = shock, not seasonality. Use volatility seasonality to size positions (smaller in high-uncertainty months).
- Separate **bull vs bear years** or seasonal vs non-seasonal years (e.g. classify each year by where price sits in its prior 5-year high-low range at a key date — like a stochastic of month-end price vs 5-yr range).
  - Corn rule: end-April price in lower 50% of 5-yr range → long Apr→Jul; end-July in upper 35% → short Jul→Oct; end-January in upper 35% → short Jan→Oct (non-seasonal year).
- Weather sensitivity: HDD = max(0, 65°F − T), CDD = max(0, T − 65°F), cumulative over critical window.

## Seasonal filters / trades
- Combine **% of up months** with average change per month; average into positions across the month rather than one day.
- On tradeable December corn futures, "sell end-Feb, exit end-Jul" was consistently profitable 1990–2010, while the intuitive post-harvest long was break-even — **cash seasonality ≠ futures seasonality**.
- Three studies of key dates agree only on a few robust patterns (grains harvest pressure Sep–Oct; cattle year-end liquidation/mid-winter rally) → keep only patterns common to independent studies and long histories.

## Stock-market calendar effects
- S&P (futures) 1982–2000 vs 2001–10: summer weakness faded; **Oct–Nov/Dec strength persisted** (money returns after summer; tax selling at year-end). DJIA 1998–2011 peaks end-April, rally in October.
- **Holiday effect (Merrill)**: day before holidays up 67.9% (vs ~54% base rate); day after ~50.8%. Fosback: buy 2 days before major holiday, exit day before → 880% 1928–75, 70% winners, while all other days lost 41%. Kaeppel: buy close 3 days before holiday, sell 2 days later. Still works but weaker (Freeburg); also in bonds.
- **Month-end effect**: buy last (or second-last) trading day of month, exit 4th trading day of new month (fund flows/rebalancing). Confirmed by Merrill, Fosback, Kaeppel, Freeburg; weaker after 1975.
- **Hirsch**: long 1 Nov – 30 Apr, out May–Oct ("sell in May") — historically most gains in those 6 months; recent evidence weaker.
- **January barometer** (Kaeppel table): direction of first 5 days + full January predicts Feb–Dec; worked 1938–89 (but 7:1 up bias), weak 1998–2010. **McGinley**: if each of first five January days up → long S&P for year: 81–82% correct since 1942 (χ² ≈ 15, significant); bullish signal only.
- September consistently weak; October most volatile but most "ricochet rallies" (≥5% within 10 days from monthly low).
- Seasonality in stocks only where business is seasonal (airlines, resorts, retail). No reason for seasonality in currencies/rates. Unexplainable patterns → avoid.

## Takeaways for NSE project
- Calendar features to **test on NSE** (with fundamental rationale): month-end/turn-of-month effect (fund flows, SIP inflows ~ first week), pre-holiday effect (Diwali/Muhurat, Holi), F&O monthly expiry week (last Thursday/now changed dates — use actual expiry calendar), Union Budget day, quarterly results season, March financial-year-end (tax-loss selling), FII flows in Dec holidays.
- Sector seasonality: autos (festive Oct–Nov sales), FMCG (rural/monsoon), cement (pre-monsoon strength, monsoon slowdown), airlines/hotels (holiday seasons), power (summer).
- Use medians, % up months, and compare 2015–19 vs 2020+; require monthly, not daily, precision; use seasonal volatility for position sizing.
