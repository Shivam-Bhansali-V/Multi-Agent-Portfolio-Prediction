# Ch 24 — Diversification and Portfolio Allocation (pp. 1099–1146)

## Terms
Alpha (excess over benchmark), beta (relative volatility/sensitivity), returns Eₜ/Eₜ₋₁ − 1, NAV (index from 100), information ratio (AROR/annual σ; or semideviation-based for derivatives), objective function, passive (buy-and-hold) benchmark, "string" = one candidate allocation.

## Diversification
- Reduces **systematic/specific** risk, not market (shock) risk. "There is no diversification during a crisis" — money moves markets; correlations → 1 (or flip, e.g. S&P vs gold/euro −0.6 in 2008).
- Equity sectors diversify only partly (all react to the same economy). Financial markets (rates, FX, equities, commodities via USD) are linked by predictable reactions to economic news.
- Risk falls fast up to ~4 assets then flattens; realistic max reduction ~50%. (Book's "2 assets → 50%, 3 → 33%" is variance; for independent equal-weight assets **σ falls as 1/√n**: 2 → 71%, 4 → 50%.)
- **Strategy diversification**: trend, mean-reversion, spreads/relative value, fundamental/value, carry — functionally different methods hold conflicting positions; different trend methods (MA, ARIMA, P&F) are still one strategy.
- Diversification gives the *average* return; a zero-return asset negatively correlated with a winner can still raise the return/risk ratio (then lever if possible).

## Balancing risk
- Equal dollars (old standard), **equal σ** (closes only), **equal ATR** (best if OHLC). Inverse-vol weights: wᵢ ∝ 1/σᵢ, normalised (A 4%, B 1% → 20%/80%). BAC (cheap, volatile) gets most risk under equal dollars.
- Narang's construction approaches: equal-dollar, equal-risk, alpha-driven (rank by expected alpha, larger weights to top ranks, not proportional), decision-tree (strategy × risk bucket); plus mean–variance optimisation.

## Mean–variance (MPT)
- E(R) = Σwᵢ E(Rᵢ), Σwᵢ = 1; σ²_R = Σwᵢ²σᵢ² + ΣΣ_{i≠j} wᵢwⱼ covᵢⱼ, covᵢⱼ = ρᵢⱼσᵢσⱼ. Two assets: σ² = w₁²σ₁² + w₂²σ₂² + 2w₁w₂cov₁₂.
- Also check max portfolio loss and VaR exceedances — one extreme correlated event is hidden in long-run averages; largest historical loss will be exceeded.
- Example: S&P 21.9%/11.6% and bonds 9.15%/… (ρ 0.55) 1994–97 → 60/40 ratio 1.73 < S&P alone (period-dependent).
- **Excel Solver**: maximise IR by changing weights, Σw = 1, w ≥ 0 (or −1 ≤ w ≤ 1 for shorts). 4-asset example IR 1.37 → 1.97 in-sample (heavy gold + Apple, zero MSFT) — but that is hindsight; re-estimating on rolling windows (3–5 yrs, monthly/quarterly) has no proven best choice.

## Why classic MVO fails for trading-system returns (Kaufman)
- Use **strategy P&L returns**, not underlying prices (two rising stocks may be long and short in the system → opposite correlation).
- Intermittent exposure: a system in the market 25% of the time shows half the σ of one in 50% → MVO over-allocates to the less active system although per-active-day risk is equal. Covariances dominated by days when only one system is active understate joint risk.
- Selective, high-payoff low-activity strategies get eliminated by MVO despite diversification value.

## Objective functions / risk measures
- Annualised σ (√252 scaling assumption); residual σ around a linear equity fit (penalises upside surges too); **semivariance of drawdowns** σ_D = σ(E_high − Eᵢ) over non-new-high days (no annualising, no penalty for gains). GASP objective **OF = AROR/σ_D**.
- Target risk as probability of a specified loss over a horizon (e.g. 0.1% chance of −10% in 10 years); set both max and min risk bounds (otherwise the optimiser goes to tiny, low-return allocations).
- Optimal portfolio = tangency point (highest ratio) on the efficient frontier; moves right as the risk-free rate rises.

## Constraints
- Liquidity: ≤ 1% (max ~3%) of average daily volume per asset; absolute caps per asset and per group (e.g. energy complex).
- Long-only constraint if shorts unwanted.
- Hierarchical optimisation: optimise within sectors, then across sector sub-portfolios — faster and lets judgement about stress correlations enter. Include stress periods in the data.

## GASP (genetic algorithm solution to portfolios)
1. Prepare return series (equal notional per asset to avoid hidden weighting).
2. Initialise pool (≈5000 strings): random weights normalised to 1; reject strings breaking constraints; rescale groups; rescale to target volatility ±5%, reject if liquidity breached.
3. Evaluate OF for each string (portfolio returns Rᵢ = Σwₙrₙᵢ).
4. Completion: convergence over several cycles or fixed number of cycles (better: **3–5 independent passes of 50–100 cycles** than one long run).
5. Propagation: sample uniform R in [OF_min, OF_max], copy the string whose OF is nearest — gaps between top OFs give the best strings more copies; cull ~10% worst per cycle.
6. Mating (switch left parts at random split, renormalise, re-check group constraints), mutation (~5–15%: replace one weight, renormalise).
- **Optimal subsets** (e.g. best 12 of 19): keep exactly s non-zero weights through init/mate/mutate. Full solution only marginally better.
- Many near-optimal allocations exist (differences in 2nd–3rd decimal irrelevant); similar OF with different weights → flat optimum. Example: 19 NASDAQ strategies, subset 12, target risk → best OF found by cycle ~59; 80% of improvement in first 15 cycles; three passes OF 17.3–17.9, AROR ~49–51%.
- Test interval: longer is better (include bull, bear, full seasonal cycle); short rolling windows unproven and mis-weight seasonal assets.

## Volatility stabilisation & caps
- Portfolio with long-run 8.5% vol ranged 1.5%–25.5% → investors want stability.
- **Volatility factor** VF = target vol / rolling (lagged) realised vol; scale positions by VF (10-day vol example: IR 1.27 → 1.38, realised 13.7% vs 12% target because vol trended up and factor lags).
- Switching costs: longer vol window, change threshold before resizing.
- VaR still needed (vol targeting is backward-looking). **Cap leverage/exposure** (UCITS: exposure ≤ 2.5× equity, commodities ≤ 20%): if exposure > cap, scale all positions by C/Eₜ (keep balance); apply last; usually small effect on IR.

## Takeaways for NSE project
- Portfolio of NIFTY 100 signals: **inverse-volatility (ATR/σ) weights** with per-stock cap (e.g. 5–10%) and sector caps (banks/financials dominate NIFTY — cap sector weight), long-only, Σw ≤ 1 (cash allowed).
- Optimise (if at all) on **strategy P&L returns**, using drawdown-based objective (AROR/σ_D, Sortino) with walk-forward re-estimation; compare against simple equal-risk weights (often as good out of sample).
- Liquidity constraint: position ≤ 1% of 20-day median traded value per stock.
- Volatility targeting at portfolio level (e.g. 10–12%) with lagged 20–60 day realised vol and a resize threshold to limit STT/brokerage churn; never above 100% invested (cash scope).
- Combine functionally different strategies (trend/momentum ranking, short-term mean reversion, calendar effects) — measure their P&L correlation especially in stress windows (Mar 2020).
- Report diversification ratio and stress-period correlations, not just full-sample correlations.
