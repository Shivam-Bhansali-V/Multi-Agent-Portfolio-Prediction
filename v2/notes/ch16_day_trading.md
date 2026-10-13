# Ch 16 — Day Trading (pp. 737–778)

## Core realities
- Intraday moves = mostly **noise**; fundamentals irrelevant over hours. Two consequences: (1) for directional entries **wait for a pullback**; (2) **mean reversion** is the natural intraday style.
- **Costs dominate**: commissions + slippage. Example: S&P daily range $931 − $10 fees − $100 slippage. Trend trading with 1/3 winners and 2:1 win/loss = break-even before costs → loses after costs.
- S&P open→close span ≈ ½ of the day's range; after a trend is identified you can rarely capture >25% of the range.
- Choose markets with **high volatility (cost becomes smaller %) and high volume (low slippage)**. Thin markets: displayed prices unreachable.
- Mean-reversion orders add liquidity → roughly **½ the slippage** of trend orders (exits on stops still pay full slippage).
- **"Unables"** (missed fills after jumps) come only from winners: 10% unables on a system with avg win $250/loss $150/50% win → profit $5000 → $4750 per 100 trades, PF 1.66 → 1.50. Backtests silently assume them away.
- Slippage model: slip = a₀ + a₁·volatility + a₂·volume + a₃·time-of-day + a₄·order size (fit by regression on own fills). Without data: scale slippage with volatility but **floor it** (never assume less than a minimum). Trade-on-settle orders to get the close.

## Bars and timing
- Standard vs custom bar lengths; uneven last bar breaks comparisons. **Tick (equal-activity) bars** de-emphasise quiet midday; patterns look different in time vs tick bars.
- MAs intraday: more noise → need bigger moves; trend trades should span several days.
- P&F with min box/3-box reversal = classic floor tool; no lag at breakout.
- Overnight gaps as % of daily range have shrunk in 24-h futures; **in stocks (news after hours) gaps remain meaningful signals**.

## Key levels / support–resistance
- Floor traders' levels: today's open/high/low, yesterday's H/L/C, last week's H/L, memorable older extremes; confluence strengthens a level.
- **Midday support/resistance strategy** (S&P, 15/30-min): morning range up to 12:00; afternoon: close in lower 25% of morning range → go long; upper 25% → go short; break below morning low → exit long (and vice versa); can hold overnight. +$268/trade, 8404 trades 2000–2011 (no costs, unoptimised).
- Bressert chart: entry levels evolve with the clock (prev day H/L early; today's H/L midday; open/high late).

## Taylor 3-day cycle (book method)
Buying day → selling day → short-sale day, repeating; in uptrend buy on a test of prior day's low **only if the low occurs first**, sell at test of prior highs. A short-term **mean-reversion** method that fades penetration of nearby support/resistance. Cycle start = lowest low of first 10 days, then every 3rd day.

## Opening range breakout (ORB)
- Buy when price rises a fixed amount above the open; reverse when it falls same amount below; exit on close. Pivot can be prior close.
- **Crabel**: an **inside day / narrow-range day beforehand** greatly improves % profitable; crude oil 2009–11 tests: all breakout sizes profitable (no costs), overnight holding adds profit per trade, inside-day filter → only ~10% of days but much higher profit/trade and PF.
- **Volatility breakout**: threshold = open ± k·ATR(n) (n = bars per day) — adapts to volatility; fixed thresholds decay.
- Low-vol filter: trade only if HV(6) < HV(100) (Crabel-style volatility contraction; halves trades). (Book prints HV = ln(Pᵢ/Pᵢ₋ₙ); proper HV = annualised stdev of daily log returns over n.)
- **Raschke NR4**: day 4 range < previous 3; next day buy stop 1 tick above NR4 high, sell stop below low; stop-and-reverse same day; exit after 2 days if not profitable; trailing stop.
- First-hour breakout (McNutt): first-hour H/L; targets = first-hour low + avg daily range / first-hour high − avg range.
- **Momentum Pinball** (Raschke/Connors): LBR/RSI = 3-day RSI of 1-day ROC; if yesterday < 30 → buy stop above first-hour high, stop at first-hour low; carry overnight if profitable; exit next open if it gaps in favour. Sell mirror at > 70. S&P 2000–11 +$703/contract, 1734 trades (no costs).
- **Mark Fisher ACD**: opening range OR (20 min stocks); A = ORH + x·(ORH−ORL), C = ORL − y·(…); buy if price holds above A for ½·OR time; exit below ORL; reverse below C; time stop 1×OR. **Pivot range**: DPP = (H+L+C)/3 (yesterday), AHL = (H+L)/2, DPD = DPP − AHL, pivot high/low = DPP ± DPD; close above pivot range = bullish bias.
- **Larry Williams filters**: %R(10) < 20% and close < close 7 days ago, today's close > previous close(s), not an inside day → buy breakout of open + 20% of yesterday's range.
- Afternoon breakouts (after midday) imply continuation → hold overnight.

## Stock set-ups (Rudd, 5-min)
Dip-and-rally to early highs then buy breakout; consolidation near highs then breakout; delayed consolidation; early breakout after narrow 15-min range; reverse on failed breakout. After a **wide-range bar closing near high**: buy breakout if next day opens above and tests that high; sell a big gap open that fades in the first minutes. 3-day reversal set-up.

## Fading the open / gaps
- Open & close most likely times of extremes → with gap ≥ 0.5% (S&P), fade the gap at a designated bar; stop-and-reverse at the day's extreme; exit at close. 1600 trades, $32/trade (no costs) → needs volatility filter.
- Gap definitions: true gap (open beyond prior H/L) vs **lapse** (beyond prior close). Williams: short an up-gap when it pulls back to prior high. Best tested variant: sell when price pulls back to **prior close**, exit **next open**.

## Volume & shocks intraday
- Compare each bar's volume to the **same bar's average** (U-shape). Volume ≥2× same-bar average marks events.
- Intraday shock fade: bar TR ≥ 3× average (open bar) or 2× same-bar average (later) with close in top/bottom 20% → fade on next bar open; no stop for 2 bars, then stop beyond the 3-bar extreme; exit at close. Profitable gold (20-min), bonds (factor 2.5). Exit when volume falls back to normal (floor-trader "noise" rule).

## Takeaways for NSE project
- Our horizon is daily/swing in cash equities; intraday ideas transfer as **daily features**: NR4/NR7 & inside-day flags, HV(6)/HV(100) contraction ratio, gap vs prior close/high, wide-range-bar flag + close location, Fisher pivot-range position, Williams %R(10) with 7-day close comparison, LBR/RSI (3-day RSI of 1-day ROC).
- **Cost realism**: Indian delivery trades pay STT (0.1% each side), stamp duty, exchange/SEBI fees, GST, DP charges + slippage → round trip ~0.25–0.35% for liquid NIFTY 100. Any strategy with avg profit/trade below ~0.5% is fragile. Model unables (skip fills after gap-through-entry) and volatility-scaled slippage with a floor.
- Narrow-range → breakout expansion is a well-documented, testable effect: test NR7/inside-day + breakout on NIFTY 100 daily bars with next-open entries.
