# Ch 13 — Spreads and Arbitrage (pp. 565–616)

## Definitions
- Spread/straddle: opposite positions in related instruments. **Pairs trading** = long one stock, short a related one. Arbitrage = relationship definable (location, carry, same bond). **Relative-value arbitrage** = similar products driven apart by market forces. Intramarket (calendar) vs intermarket spreads.
- Purpose: remove directional/market risk → diversification.
- Spread risk: **Var(A − B) = σ_A² + σ_B² − 2·Cov(A,B)**; Cov = (1/N)Σ(Aᵢ − Ā)(Bᵢ − B̄). Higher co-movement → lower spread variance.

## Futures term structure (background)
- Carry = interest + storage + insurance. Contango (normal) vs backwardation (inverted). Precious metals ≈ pure carry (spread widens with price and rates); industrial metals can invert; FX forward set by interest-rate parity; crops: carry within crop year; livestock non-storable (no carry link).
- Convenience yield: F = S + S·r·(T−t)/365 + CY; continuous: F = S·e^{(r − CY)(T−t)}.
- No-arbitrage band with borrow/lend rates and costs; outside the band → arbitrage.
- **Interest-rate parity**: Fwd = Spot × (1 + i_foreign)/(1 + i_domestic) (EURUSD 1.450 × 1.06/1.04 = 1.4779). Don't backtest FX with spot then trade futures.
- Crossrate consistency: a_ij·a_jk = a_ik; a_ij = 1/a_ji → triangular-arbitrage check.

## Equity-related arbitrage
- **Index fair value**: FV = C·(1 + (r − d)·t); program trade when |C − F| − C·r·t − costs > threshold (bands widen with separate borrow/lend rates and costs). Index arbitrage makes constituents move together.
- Track an index with a subset: top-cap names or stepwise regression weights (re-estimate often; tracking risk).
- **Merger arbitrage**: buy target after announced deal below offer price; return small (e.g. $1 on $39 over 4 months ≈ 7.7% annualised) with rare large losses when deals fail (short-option profile) partly offset by bidding wars; needs many deals for diversification.
- Single-stock futures fair value: F = S·e^{rt} − Σ Divᵢ·e^{rᵢtᵢ}.
- Index-ratio spreads: S&P/DJIA ratio range-bound (mean revert); S&P/Russell trends with risk appetite (small caps lead recoveries).

## Pairs trading (Kaufman method)
- Select pairs: same business, **returns correlation ~0.5–0.7** (too high → no profit after costs; too low → risk), or better **cointegration** (Engle-Granger, Johansen, Phillips-Ouliaris).
- **Method 1**: difference of two n-day stochastics (14-day); enter when |Stoch1 − Stoch2| > 50 (sell the high one, buy the low one); exit when difference returns to 0.
- **Method 2 — Stress indicator**: Dₜ = Stoch1ₜ − Stoch2ₜ (raw stochastics); Stressₜ = stochastic of D over n: (Dₜ − min D)/(max D − min D)·100. Stress > 95 → short leg 1/long leg 2; < 5 → reverse; exit near 50.
- **Hold only a few days** (mean reversion fights each leg's trend if held long).
- **Position sizing: equal dollar risk per leg** — shares = fixed investment / (ATR₂₀ × price units) (e.g. $1000/ATR$). Hard to improve on this.
- Stock vs commodity pairs (gold miner vs gold futures) work the same way.

## Product spreads
- Soybean crush GPM = 0.022·meal + 11·oil − soybeans (¢/bu units as quoted); crack spread 3-2-1 (3 crude vs 2 gasoline + 1 heating oil, product months one month later). Reverse crush/crack rare (processors can't easily shut down).
- Intercrop (old vs new crop), butterfly spreads (2 short middle month vs long both wings) capture term-structure distortions (often from fund rolls) — fleeting, floor-trader territory; beware stale last prices.

## Rates
- Eurodollar strip: TV = (1 + L₀·D₀/360)(1 + F₁·D₁/360)…; arbitrage vs actual futures; need ≥25–30 bp edge. Yield-curve steepener/flattener as trend trades, volatility-matched legs. TED spread = credit-risk gauge. Implied yield from pure-carry futures (gold) as safe "deposit".
- **Carry trade (forward bias)**: money flows to highest real yield; monthly long high-yielders / short low-yielders, volatility-sized. Risk: correlated currencies, funding-currency concentration, crash risk.

## Changing relationships
Structural change (new supply regions, consumer tastes, industrial demand) breaks ratios (gold/silver "normal 33:1" ranged 20–100+). Index arbitrage forces stock correlations up and can push stocks in different indices apart.

## Ratio "new markets"
Dividing one market by another (crude/gold, XOM/crude, Werner/crude) creates a new series; trend-trade the ratio with **volatility-matched legs** → signals at different times, diversification (weekly P&L correlation 0.42 vs individual trend trades).

## Trend or mean-reversion for spreads?
- Short-term noise → mean reversion for pairs (short holds). Sustained sentiment shifts (small vs large caps, flight to quality) → trend.
- Bull spread (long nearby/short deferred) as lower-risk trend trade; require trend in nearby + spread confirmation.
- **Volatility regime of the spread matters**: S&P/NASDAQ ratio thresholds that worked pre-2008 → catastrophic in 2008, then never reached after 2009. Use relative-value timing (oscillators on the ratio, e.g. **Fisher transform ±80**) plus a **low-volatility filter** (skip when expected move < costs).
- Historical study of spread: price-volatility relation, seasonality, risk preference, event effects.

## Ranking / market-neutral baskets
- Rank stocks (ratings, fundamentals, returns, information ratio, trend strength). Trade top and bottom 20–35% (or ≥5 each side). If ranking predictive → long best/short worst (trend); if not → reverse (mean reversion).
- Replace a member only when it falls ≥2 positions out of its basket (avoid churning). Exclude illiquid/flat bottom-ranked names. Equal-dollar-ATR sizing; rebalance baskets if volatility differs > 20%.
- Classic market-neutral = mean reversion within an industry with correlations 0.5–0.7; equity noise favours mean reversion and short holding periods.

## Practicalities
Use spread orders (or short leg first); **never leg in/out** (unhedged leg = outright risk); hedging an outright with a spread/option rarely beats simply exiting; avoid extreme price-ratio pairs (cheap stock event risk, liquidity); spread margins → hidden leverage.

## Takeaways for NSE project
- Our scope is cash-delivery, no shorting/F&O → pure pairs/market-neutral not directly tradeable; but **relative-value ideas transfer to long-only ranking**: within each sector, buy the stock whose stress indicator vs its peer/sector index is most oversold, exit near neutral within days.
- Sector-relative features: stock/sector-index ratio, its stochastic/Fisher transform, rolling cointegration residual z-score, correlation of returns with sector.
- Rank-and-rebalance with a 2-position hysteresis buffer; ATR-equal sizing; skip low-volatility setups where expected move < cost.
