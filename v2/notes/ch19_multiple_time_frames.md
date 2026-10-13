# Ch 19 — Multiple Time Frames (pp. 833–844)

## Principle
Longer time frame → direction (trend, less noise); shorter time frame → **entry timing**. Each component must be **tuned to work together**, not optimised alone.
- If the trend trade lasts ~23 days, the timing oscillator should give an oversold signal within the first 3–5 days (10–20% of the holding period) → oscillator period must be < 5 days. The oscillator alone may lose money; only its contribution to the combined system matters. Use only the **first** pullback signal after a new trend signal.
- Example (EURUSD): 60-day MA up + first 3-day raw stochastic oversold → entry improved a $2075 trade to $6200; a 14-day stochastic delayed or missed entries. Steady trends can give worse entries (waiting costs).
- **Weekly data ≠ 5× longer daily MA**: fewer data points over the same span are smoother; a 10-week average is not a 50-day average.

## Elder Triple Screen (frames differ by ~×5: weekly / daily / hourly)
1. **Screen 1 (tide)**: slope of weekly MACD histogram (≈13-week EMA). Trade only in its direction.
2. **Screen 2 (wave, daily oscillator)**: Force Index = V·(Cₜ − Cₜ₋₁), EMA₂; buy in an uptrend when FI EMA₂ dips below 0 (not below multi-week low); stochastic < 30 alternative. **Elder-Ray**: Bull Power = H − EMA₁₃, Bear Power = L − EMA₁₃; buy when tide up and Bear Power negative but rising (optional: latest Bull Power peak higher; bullish divergence in Bear Power).
3. **Screen 3 (ripple)**: buy stop above prior day's high (intraday trailing).
- Stops: below entry/prior day low → move to break-even → protect 50% of max open profit; take profits at oscillator > 70.

## Krausz (Fibonacci Trader) — laws of multiple time frames
Each frame has its own structure; **higher frame overrules lower**; lower-frame prices respect higher-frame support/resistance ("energy points"); confluence of S/R across frames raises reliability; trade the lower-frame trend only in the higher-frame direction. Tools: HiLo Activator (MA of highs as buy stop / lows as sell stop, stepped), Gann swings on 10-min bars, frames 10-min / 50-min / daily. Sound theory: trend systems' return/trade grows smoothly with period — look for continuity, not isolated optimum.

## Pring KST (multi-period ROC)
- ROC(n) = 100·(Pₜ/Pₜ₋ₙ − 1). Strongest moves when 6-, 12-, 24-period ROCs all turn and move together; if only some peak → minor sell-off.
- **KST** (book's version) = 4·SMA₉(ROC₂₄) + 3·SMA₉(ROC₁₈) + 2·SMA₆(ROC₁₂) + 1·SMA₆(ROC₆). (Pring's standard daily KST: 1·SMA₁₀(ROC₁₀) + 2·SMA₁₀(ROC₁₅) + 3·SMA₁₀(ROC₂₀) + 4·SMA₁₅(ROC₃₀).)
- Signals: trade in direction of a 12-period MA trendline; time with KST crossing its smoothed ROC/signal; divergences & trendlines on KST. Clearer on weekly/monthly data.

## Takeaways for NSE project
- Build features at **daily + weekly (and monthly)** resolution: weekly MACD-hist slope, weekly close vs 10/30-week MA, monthly ROC — merged to daily rows **without look-ahead** (use last *completed* week/month).
- Strategy template: weekly trend filter + first daily pullback (3-day stochastic/RSI(2)/Force Index EMA₂ < 0, Elder Bear Power rising) + entry on break of prior day's high next day. Evaluate the combination, not the oscillator alone.
- KST and multi-horizon ROC alignment (1/3/6/12-month momentum agreement) → classic cross-sectional momentum feature set for NIFTY 100 ranking.
- Exit discipline: break-even then 50% profit protection — test vs ATR trailing.
