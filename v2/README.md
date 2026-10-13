# v2 — Kaufman, *Trading Systems and Methods* (5th ed.) — study notes for the NSE prediction project

These are concept notes from reading the whole book once. They are not a copy of the book's rules. Each chapter file lists the ideas and formulas, fixes the book's misprints (checked numerically), and ends with **"Takeaways for NSE project"**: NIFTY 100, daily data from 2015, holdout from Apr 2025, cash equity only.

## Files (notes/)
| # | File | Core idea |
|---|---|---|
| 1 | ch01_introduction | Noise vs trend, efficiency ratio, market maturity → more noise |
| 2 | ch02_basic_concepts | Returns, σ, skew/kurtosis, t-tests, Sharpe, regression basics |
| 3–4 | ch03/ch04 charting | Patterns, programmable versions, most chart lore weak on stocks |
| 5 | ch05_event_driven_trends | Swings, N-day breakouts, Turtles, P&F |
| 6 | ch06_regression | OLS, correlation, ARIMA, Kalman, cointegration basics |
| 7–8 | ch07/ch08 trends | MA/EMA/HMA etc.; trend systems; slow periods best; equity indices noisy |
| 9 | ch09_momentum_oscillators | RSI, stochastic, MACD, TSI, divergence; oscillators best as timing inside a trend |
| 10 | ch10_seasonality | Seasonal methods; turn-of-month, holiday effects |
| 11 | ch11_cycles | Fourier/MESA/Hilbert/Fisher; regime (cycle vs trend) detection |
| 12 | ch12_volume_breadth | OBV, MFI, A/D, breadth, contrarian breadth, volume spikes |
| 13 | ch13_spreads_arbitrage | Pairs/stress indicator, ranking baskets, ATR sizing |
| 14 | ch14_behavioral | Event/shock trading, COT index, sentiment, EWO |
| 15 | ch15_pattern_recognition | Gaps, weekday/month-day patterns, trade-profile labelling |
| 16 | ch16_day_trading | Costs, ORB, NR4/inside day, gap fades |
| 17 | ch17_adaptive | KAMA/ER, VIDYA, MAMA, parabolic, TAO |
| 18 | ch18_price_distribution | Robust distribution stats, zones, moving skew/kurtosis, Market Profile |
| 19 | ch19_multiple_time_frames | Weekly trend + daily timing, Triple Screen, KST |
| 20 | ch20_advanced_techniques | Volatility estimators, vol filters, entropy, NN, GA |
| 21 | ch21_system_testing | **Testing protocol: IS/OOS, walk-forward, robustness, shocks** |
| 22 | ch22_practical_considerations | Data cleaning, crisis rules, runs/Martingales, trade-offs |
| 23 | ch23_risk_control | Risk metrics, VaR, sizing, stops, ruin, Kelly, live monitoring |
| 24 | ch24_portfolio_allocation | Equal-risk weights, MVO pitfalls, GA allocation, vol targeting |
| 25 | ch25_appendices | Gaussian elimination, Markov chain steady state |

## What the book teaches overall
1. **Noise vs trend decides the method.** Equity indices and most large stocks are the noisiest markets. Short-term trend following loses there. Long trends, or short-term mean reversion, are what work. Measure noise with the efficiency ratio (ER) and choose the approach to match.
2. **The market matters more than the method.** All trend methods make or lose money on the same moves, so a different formula rarely matters. The useful choices are the speed of the trend and the regime.
3. **Normalise everything by volatility.** Use ATR or σ for thresholds, stops and position sizes. Fixed thresholds break when volatility changes.
4. **Combine time frames.** Take direction from the slow trend and entry timing from a short oscillator or a pullback. Exits must never be delayed.
5. **Testing is for validating an idea, not discovering one.** Write down expectations before testing. Space parameters geometrically. Pick values from broad stable areas, not the single best result. Expect the average across all reasonable tests. Run walk-forward tests and keep an untouched holdout. Count every test you run.
6. **Price shocks dominate risk.** Backtests usually profit from shocks by luck. Be out of the market when you can, keep leverage low, and stress-test. Diversification disappears in a crisis.
7. **Costs and liquidity decide whether short-term edges are real.** Never assume a fill at the high or low. Model trades you could not have filled.
8. **Risk control.** Size every position to equal risk, target a portfolio volatility, and judge results by drawdown-based measures. Check live results against the backtest profile with binomial and χ² tests.

## NSE research backlog (from the chapter takeaways)
- **Features:** ER(10), KAMA slope, RSI(2/14), stochastic, TSI, MACD histogram, ATR%, Parkinson and Garman-Klass vol, relative vol (lagged), Bollinger-width percentile, OBV and money-flow slopes, normalised volume and delivery %, gap and close-location, NR7/inside day, weekly trend state, multi-horizon ROC (1/3/6/12 m), breadth (% of NIFTY 100 above 50/200-DMA, McClellan), India VIX, FII/DII flow index, calendar (turn of month, expiry week, pre-holiday, results season).
- **Strategy candidates (long-only, cash):** cross-sectional momentum ranking with hysteresis; RSI(2)/N-down-days dip-buy within a long-term uptrend; low-relative-vol entry filter on trend signals; gap-down / extreme-drop fade (1.3–2σ, 1–2 day hold, skip shocks); turn-of-month; sector-relative mean reversion.
- **Protocol:** pre-register each idea; walk-forward inside 2015 to Mar 2025; leave Apr 2025 onward untouched; use a realistic Indian cost model (about 0.25–0.35% round trip); neutralise shock-day P&L and compare; robustness across stocks and sectors; ATR-equal sizing; portfolio vol target of about 10–12%; paper-trade before using real money.

## Book misprints corrected in the notes (selection)
Pivot S1 = 2P − H. KAMA slow end ≈ 480-day equivalent. VIDYA gets faster as volatility rises. Parkinson constant 0.601 applies to ln(H/L). Garman-Klass uses ln(C/O) with constant 0.386. Lognormal example ln 40 = 3.689. Risk of ruin (2/3)^c, not (1/3)^c. VaR example 14,590 (17,068 is the ρ = 0 value). Number of n-day up/down patterns is 2ⁿ. Diversification lowers σ by 1/√n. Wilder −DM = Lₜ₋₁ − Lₜ. Arrington's variable-MA formula is inverted. Lower conditional entropy (not higher) means more predictive.
