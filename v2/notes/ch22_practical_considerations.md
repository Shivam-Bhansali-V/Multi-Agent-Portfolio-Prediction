# Ch 22 — Practical Considerations (pp. 983–1026)

## Computers & data
- Computers compute; they don't think. "Automating a mess speeds up the mess."
- **Data checks** (daily): outliers (> ~4% moves → inspect), missing dates (> 4-day gaps), Open/Close outside High–Low (impossible → fix/remove); intraday: tick frequency gaps, spikes that reverse in seconds. Different vendors' H/L differ; decimal shifts; units when merging sources.
- Dirty-data paradox: a system developed on cleaned data traded on dirty live data gets extra false signals → develop on the same quality data you trade.
- Prefer standard tools first; use the platform to avoid look-ahead; export optimisation results and analyse averages/variance.
- **Paper trade** with documented expectations (frequency, holding period, % winners, avg win/loss); assume worst price of the 5 minutes after a signal / worst of closing range; then start small.

## When it doesn't work
- Outcomes: works / not profitable / can't be implemented / too slow or expensive. Build vertically: each piece must add value before the next.
- **Vertical vs integrated**: integrated (interdependent parameters tested jointly) is legitimate only if the % of profitable combinations rises vs the base component alone; otherwise it's overfit.
- Transparent > complex (complex systems can be wrong without anyone noticing; hard to debug).
- Common errors: rules interpreted wrongly ("volume confirmation" ≠ V > Vₜ₋₁; use V > 10-day average); medium trends have highly variable move lengths → combine long trend (direction) + medium (timing); results should be similar within a sector (two auto makers), not necessarily across sectors.
- Hidden assumptions: selected data; **ignoring a few large losses (LTCM)** — history understates risk; volatility growth (NASDAQ 600 → 4000 = 6× volatility per contract → size by volatility); market evolution adds noise → trend signals later, performance decays.

## Extreme events / price shocks
- Most likely cause of catastrophic loss; diversification fails (correlations → 1, "money moves the markets", liquidation of unrelated assets).
- You can't be on the right side of more than ~50% of shocks; backtests silently pick parameters that profited from them → OOS worse than backtest.
- Examples: Gorbachev abduction 1991 (double shock), UK election 1992, Gulf War 1990–91 (oil −$10 in a day), 9/11 (−5.4% gap, low 5 days later, then recovery).
- Patterns: shocks don't always hurt trend followers; **prices usually reverse after the shock is absorbed**; volatility always rises.
- **Crisis management rules**: windfall profit → exit (or reduce); large loss → hold a few days expecting partial reversal (most risk already taken); with reserves, add later when volatility declines. Re-initialise trend indicators after the crisis (1987: 50/100/200-day MAs stayed out of phase for months).
- Identify shocks as TR > ~5× ATR and measure their P&L contribution.

## Theory of runs / Martingales
- Run of exactly n (bounded by opposites) probability = (½)ⁿ⁺²; in 256 trials expect one run > 6 (average length 8); longest run grows by 1 each doubling of trials.
- Martingale (double after losses): capital must survive the longest run (stake/2⁸ for run of 8); wins small, rare catastrophic loss. Anti-martingale (double after wins): small chance of big win.
- Markets vs coin flips (15 futures 2000–11): DAX has excess 1-day reversals (noise) → after a trend signal wait for a reversal to enter; Eurodollars fewer reversals → enter immediately. Generally fewer runs of 4–5 days than random.
- Martingale within a 60-day trend (cap 8 units): improved IR on trending Eurodollars, worse on noisy S&P. Anti-martingale capped (2–8) beat plain MA on Eurodollars; uncapped lost (largest position at the loss). Fractional (×1.5) variants.
- **Gustafson**: S&P long after 4 consecutive lower closes; exit after 5 consecutive up closes or 8 days → 76–78% winners (in a bull market).

## Discipline and trade-offs
- Don't override systems based on intuition (tends to hold losers); don't add black boxes you don't understand.
- Can't filter out all losers; profit size, frequency and opportunity trade off:
  - **Trend following**: many small losses, few large profits; low risk per trade; 30–35% winners (40–45% max); longer periods → more fat-tail capture but more lag risk; conservation of capital.
  - **Mean reversion**: many small profits, few large losses; higher risk per trade; farther entry thresholds → fewer trades, lower risk per trade; stop placement trade-off (tight stop ≈ half stopped out; wide stop = rare big losses).
- Commodex: scoring of long/short MA states + OI/volume momentum into a trend index; partial profit taking at +50%/+100%.
- Combine trend with S/R ranges: don't enter shorts at support / longs at resistance; exit shorts in buy zone above support or on breakout above resistance.

## Limits & disconnects
- Limit moves (futures; also stock circuit breakers/halts): locked-limit days (O=H=L=C) can't be traded — tests must not fill there; cash market can't hedge after a limit (already moved).

## "Too good to be true"
1974 silver "always buy, meet all margin calls" system; NASDAQ late 1990s: any long method works in a bull market. True test = profits across different market types.

## Similarity of systems
- Lukac/Brorsen/Irwin: 12 systems' monthly returns significantly positively correlated; same-day signals rare but more than random; large AUM trend followers crowd entries/exits.
- Bond MA 10–60-day P&L correlations always positive; decline with **percentage** difference in periods (10 vs 20 ≫ 50 vs 60) → geometric parameter spacing for diversification.
- ISAM: trend systems' returns converge over long horizons. **Correlation is highest at the best and worst times** (all aligned → shocks hit all).

## Takeaways for NSE project
- Data-cleaning script for NSE OHLCV: O/C within [L,H], outlier returns > ~4–5σ flagged and cross-checked against corporate actions (splits/bonuses/dividends — NSE has many bonus issues), missing sessions vs NSE holiday calendar, circuit-limit days (stock hits upper/lower circuit → no fill possible; treat as untradeable in backtest).
- Model "unables": if next-day open gaps through limit/circuit, skip.
- Paper-trade the final model on live NSE data (forward test after Apr 2025 holdout) before any capital.
- Crisis rules for COVID-like crashes (Mar 2020): define shock days by TR/ATR and test exit-on-windfall/hold-on-loss variants.
- Run statistics on NIFTY stocks (count of consecutive up/down days vs random expectation) to decide "wait for pullback" vs "enter immediately" per stock/sector.
- Gustafson-style "N down closes in uptrend" dip-buy is a concrete long-only test candidate (cost-aware).
