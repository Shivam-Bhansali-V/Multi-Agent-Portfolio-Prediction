# Ch 8 — Trend Systems (pp. 309–368)

## Why trend systems work
1. Long trends driven by slow, persistent **government/central-bank policy** (rates → FX, carry, equities).
2. **Fat tails in runs**: real markets have fewer short runs and more long runs than coin flips (random: in 100 tosses ~25 runs of 2, ~6 of 4, ~3 of 5, 1–2 of 6). Mass for the long tail comes from fewer short runs.
3. **Money flows** sustain trends as the public joins.
- Trend trading only works when markets trend; most trend methods give **similar returns but different risk profiles and trade frequencies**.
- Trade P&L distribution of a 40-day MA system (S&P, bonds, euro, crude, gold): very long right tail, short left tail — one $18,750 winner pays for >30 losses. **A pure trend strategy needs this tail; profit-taking/tight stops cut it off.**
- Longer periods + lower-frequency data + markets tied to fundamentals → better. Individual stocks are erratic (earnings jumps, index arbitrage drag); new/illiquid markets trend more, then noise rises with participation.

## Basic signals
- Price crosses trendline (close-based reduces whipsaws) vs **trendline direction** (MAₜ > MAₜ₋₁). Trendline direction: 26–37% fewer trades and generally better for slower trends (AMZN: 20–80 day PF 1.34–1.46 vs 0.98–1.31); price-cross may be better for very fast trends.
- **SMA turns up iff pₜ > pₜ₋ₙ** → you can place a stop order in advance at the dropped-off price; MA-direction system ≡ n-day momentum system.
- Execution timing: trendy markets (Eurodollar) best on signal-day close; noisy markets (S&P) often better delayed to next open/close. Practical: compute just before close and trade at close. Next-open entries got better prices 75% of the time but **lower total profit** (missed runaway breakouts).
- **Trend profile** (NASDAQ 40-day MA, 10 yrs): 150 trades, 34.7% winners, win/loss 2.22 (book figure), winners held 31.7 bars vs losers 6.6, max 10 consecutive losses. → low % winners, big win/loss ratio, long winners, long losing streaks ("conservation of capital").

## Bands and channels (reduce false signals)
- MA of highs and MA of lows: enter when high > MA(H) / low < MA(L). Worse for trendy Eurodollar, better for noisy S&P (40-day turned loss into profit). **Bands help noisy markets, hurt trendy ones.**
- Keltner: MA(10) of (H+L+C)/3 ± 10-day avg range (use ATR today).
- Percentage band: MA(1±c). Not valid on back-adjusted futures (can be negative). Absolute-point buffer for small noise.
- General: Bₜ = MAₜ ± s × {c·MA, c·p, ATR, σ}. Same multiplier gives very different widths per method; std-dev bands most reactive.
- **Bollinger**: MA(20) ± 2σ(20) of price. Because prices aren't normal, 2σ contains ~87% not 95%. Bands bulge after volatility spikes and are slow to contract.
- **McNicholl modified Bollinger** (faster to normalise): Mₜ = αCₜ + (1−α)Mₜ₋₁; Uₜ = αMₜ + (1−α)Uₜ₋₁; Dₜ = ((2−α)Mₜ − Uₜ)/(1−α) [zero-lag EMA]; apply same to |Cₜ − Dₜ| to get dₜ; bands Dₜ ± f·dₜ, α=0.15, f=2.5.
- Rules: reversal (close above upper = long, below lower = short), or **enter on band, exit on centre line** (neutral zone, half order size, can re-enter same direction). Separate slow entry / fast exit bands. Timing variants (close, next open, delay, 50% retracement, within-risk). "A missed contingent order is guaranteed to be a profit" → combine e.g. "buy on 0.5×ATR pullback or next close".
- Wider bands = fewer, more reliable signals but later entry, smaller average profit, bigger risk.
- Bollinger himself uses bands **mean-reverting with confirmation** (volume, breadth not confirming the move). Volatility is cyclic: very low bandwidth forecasts expansion; after extreme rally bandwidth expansion, sell when bandwidth starts narrowing (upside only).
- **Squeeze (Williams)**: Bollinger(20,2) inside Keltner(20) while Chaikin oscillator(21) < 0, then Chaikin crosses above 0 → long (mirror for short).

## Single-trend systems
- **Calculation period is the most important decision** (more than the method). Classic periods: 3, 5, 20–23, 63, 252; 200-day for stocks.
- Simple momentum (pₜ − pₜ₋ₙ sign) ≈ SMA for large n.
- MPTDI step-weighted MA: period, weights, entry penetration, stop all keyed to volatility bands — precursor to adaptive methods.
- **Volatility system (Bookstaber)**: buy if close rises > k·ATR(n)ₜ₋₁ from prior close; sell if falls > k·ATR; k ≈ 3.
- Keltner 10-day MA rule (typical price, ± avg range band, always reverse). Fast periods no longer work well (markets noisier since 1980) but **volatility bands held up**.
- **TRIX**: triple EMA (s = 2/(n+1), n≈6–9, orig. on ln p), TRIX = % change of E3; signal = 3-day MA of TRIX; trade the crossover. Smooth with little lag.
- **Raschke First Cross**: osc = fastMA − slowMA; trend = MA(osc). Buy when osc crosses below trend (pullback) **and** today's low > yesterday's low; sell mirror. Exit when close turns down after an up close. Trades the first pullback after a new trend impulse.

## Comparison of six trend systems (20 yrs; ED, euro, S&P, crude; IBM, BAC, Ford; periods 5–160)
Rules: Momentum (C > Cₜ₋ₙ), SMA direction, EMA direction, N-day breakout (high > highest(n) & C > C₋₁), Swing breakout (% swing), Linear-regression slope sign. Always in market, costs $20/contract, $0.01/share.
- Eurodollar (trendy): **all methods profit, almost identical profit factors**, improving with longer periods → "Does the method matter? The market controls the result."
- Euro, crude, S&P: similar PF up to ~85 days, diverge after; N-day breakout best but erratic at long periods.
- **Stocks (IBM, BAC, F): MA systems lose for nearly all periods**; S&P mostly losses, worst at short periods. IBM worse than S&P (index smooths stock noise).
- Euro detail: breakout has < ½ the trades, ~50% winners (MA/momentum ~34%, slope/EMA ~43%), and far larger avg profit — but larger risk per trade (n-day range).
- More than ~200 trades in 20 years (≈10/yr) → markedly worse profit factors (costs, noise).
- **No best system, only trade-offs**: MA = many small losses, few big wins, conservation of capital; breakout = higher reliability and profit/trade with large risk; slope in between.
- Robust testing standards: same 20-yr window; all tests start the same date (longest warm-up); speeds from ~2–3 to ≤100 trades/yr; realistic costs; judge by profit factor / information ratio.
- % swing filters on rate futures fail (price vs yield) — compute on yields.

## Two-trend systems
1. Fast MA crosses slow MA (always in).
2. Price above both MAs = long; exit when below either (neutral zone).
3. Fast trend turns up while slow is up = long; exit when trends disagree.
- Small bands around lines reduce whipsaw.
- Eurodollar 60 vs 20 vs combined (trade 20-day only in direction of 60-day): profit/trade 149 / 62 / 92, days held 31/16/16 — **slightly lower total profit but half the holding time and only ~50% time in market (less shock risk)**.
- **Donchian 5/20 MA** with 1×ATR penetration bands: buy if C > MA5₋₁ + ATR and C > MA20₋₁ + ATR; exit long if C < MA5₋₁ − ATR or C < MA20₋₁ − ATR. Size = Investment/(ATR × point value). Corn 1960–2010 profitable throughout (slowing).
- **Donchian 20/40 breakout**: enter on 40-day breakout, exit on 20-day opposite (Turtle basis).
- **Golden Cross** (SMA50 > SMA200 long, else T-bills): 1999–2010 +66.7% on SPX vs −7.8% buy-and-hold; avoided 2008.
- Volatility-adjusted NAV procedure: daily returns → rolling 20-day annualised vol → factor to 12% target → apply **previous** day's factor → NAV.
- **Woodshedder ROC method (SPY)**: buy when 5-day ROC < 252-day ROC for 2 consecutive days; exit when 5-day ROC > 252-day ROC for 2 days; cash earns ½ T-bill. Beat Golden Cross 1994–2011 (vol 14.1% vs 10.5%). (Buy short-term weakness within long-term strength.)
- **Front-run the crowd**: 8/18 instead of 10/20; 4-9-18 instead of 5-10-20 (each ≈ double the previous).

## Three trends
- Third, fastest MA slope as entry confirmation (don't enter long unless fast MA rising). Fewer trades, bigger profit per trade.
- Eurobund 1990–2011: 40-MA PF 1.11 (310 trades), 80-MA 1.88, 40/80 cross 1.45, **20/40/80 PF 2.80 (42 trades, $1457/contract)**.
- Appel: sum of three ROCs on SPX; buy above +4%, exit below.
- Beware combinations that only work in combination (likely curve-fit). Each trend must have a purpose (macro direction, holding period, timing).

## Choosing speed
- For trader: best performance profile; for commercials: frequency fits their buying schedule.
- Faster = more cost/slippage sensitivity. **A cycle/season of length L needs a trend period ≤ L/4**; "best" period ≥ cycle length = failure to capture it.
- Manual method: mark the swings you want; average swing span (IBM ≈ 3 months ~ earnings cycle) ÷ 4 → 16-day MA → IBM 2000–02: 36 trades, 20 winners, +$114/share.
- Don't size the MA to avoid the worst retracement (42-day IBM lost) — accept the natural small losses.

## Signal progression / sequences
- Check neighbouring periods (19, 20, 21…): an orderly up/down progression from short to long periods is reliable; an isolated flip in one period (drop-off artefact) is not. Automate: average the signals of a range of periods (e.g. 20–32 for a 30-day target) or require a consensus → removes dependence on one parameter.

## Early exits
Macro trends end when **policy changes** (e.g. central bank reverses); exiting on that fundamental change beats waiting for a 200-day MA (which lags ~100 days). Decide carefully — clear only in hindsight.

## Projected crossovers
- Price that makes an n-day SMA cross price = (sum of last n−1 prices)/(n−1) = the (n−1)-day average.
- Price P that makes SMA_m and SMA_n (m<n) cross tomorrow: (S_m + P)/m = (S_n + P)/n → **P = (m·S_n − n·S_m)/(n − m)** where S_m, S_n = sums of the most recent m−1 and n−1 prices (derived; book's print is garbled).
- Lambert MDI = 100 × (crossover price yesterday − crossover price today)/avg of last 2 prices; buy on cross above 0.
- **Trendline-direction signal = n-day momentum**: MA turns up iff today's price > price n days ago. In most cases better than MA price penetration.

## Takeaways for NSE project
- Expect weak plain trend-following on individual NIFTY stocks (book: stocks lose with MA systems). Better candidates: long periods, index-level trend filters (Golden Cross on NIFTY), ROC-method (buy short-term dip within long uptrend), multi-trend confirmation, or rank-based relative momentum.
- Use trendline direction / momentum, not price crossing MA.
- Signal consensus across a range of lookbacks instead of one tuned period.
- Report trade count; keep < ~10 trades/stock/year unless costs justify.
- Vol-target position sizing using lagged volatility.
