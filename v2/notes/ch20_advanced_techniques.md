# Ch 20 — Advanced Techniques (pp. 845–904)
Volatility (measurement & use), noise, expert systems, fuzzy logic, chaos/fractals, entropy, neural networks, genetic algorithms, replication.

## Price–volatility relationship
- Volatility grows with price level (roughly lognormal): use returns/log prices. Lognormal rule of thumb: |Δpₜ|/ln pₜ ≈ |Δpₛ|/ln pₛ → vol $1.00 at 20 ⇒ $1.23 at 40 (ln 40 = 3.689; book misprints 3.99).
- Commodities: **base price** (below production cost vol → 0): adjust p′ = ln(p/p₀) or ln(p − p₀); find p₀ from the lowest residual below a price regression, or by regressing volatility on price (range-based vol shows a cleaner relationship than returns because it uses more data).
- Exceptions: rates (use yields), FX (vol rises away from equilibrium either side), cartel-controlled energy.
- Vol rises with measurement horizon but at a decreasing rate (≈√t), up to the largest move.

## Volatility measures (n days)
1. Net change |Cₜ − Cₜ₋ₙ| (2 points only; understates).
2. Max range HHₙ − LLₙ (good for stop/target over a known holding period).
3. **ATR(n)** (most popular; smooth; handles gaps).
4. Σ|ΔC| (path length; ignores gaps' connection; returns for stocks).
5. **Annualised σ** = stdev(rᵢ)·√P (P = 252 daily, 12 monthly). Don't use % returns on back-adjusted futures.
- ATR is smoother than σ and jumps less on gaps; can diverge.
- **Range estimators** (Bookstaber/standard forms):
  - Close-to-close: V² = (1/(n−1))Σ(ln Rᵢ − Ā)², Rᵢ = Cᵢ/Cᵢ₋₁.
  - **Parkinson (high-low)**: V = 0.601·√[(1/n)Σ ln(Hᵢ/Lᵢ)²] (0.601 = √(1/(4 ln 2)); book misprints ln(C/C₋₁)).
  - **Garman–Klass**: S² = 0.5·ln(H/L)² − 0.39·ln(C/O)² (0.386 = 2 ln 2 − 1; book uses C/C₋₁); V² = mean S².
  - Range estimators are ~5–8× more statistically efficient than close-to-close.
- **Relative volatility** = V(n)/V(m), m ≥ 5–10·n, preferably **lagged**: long window t−m−n+1…t−n so it doesn't contain the short window (catches repeated shocks and the "back side" of volatile periods).
- **VIX**: 30-day implied vol of S&P options. 1σ 30-day range = Index × IV × √(21/252): 1600 × 25% × 0.2887 = 115.47. VIX inversely related to S&P (peak 89.53 on 24 Oct 2008); mean-reverting.

## Using volatility
- Intraday volatility follows volume U-shape (R ≈ 0.6 NDX).
- Brower: higher 3-day ATR → higher next-day range; RSI < 40 → higher volatility; inside day → expansion.
- Bierovic On-Balance True Range (OBV logic with TR) + EMA₉ crossovers.
- **Connors CVR9**: VIX high > 10-day high, VIX closes below open, yesterday VIX closed above open, VIX range > previous 3 → buy S&P on close, exit in 3 days. **VIX RSI**: S&P > 200-DMA, RSI₂(VIX) > 90, VIX open > prior close → buy, exit when RSI₂(S&P) > 65.
- MarketSci: VIX EMA₁₀ vs SMA₁₀ cross as mean-reversion trigger (symmetric long/short, on untradeable cash VIX).
- Appel: high VIX = buy; no reliable VIX sells; market rises while vol stable/declining.
- **Volatility breakout** (Bookstaber): buy if Cₜ₊₁ > Cₜ + k·ATR(n), sell if < Cₜ − k·ATR, k ≈ 3.
- Targets/stops = entry ± k·ATR. Targets suit short-term (noise) trading; long-term trend systems must not cap the fat tail (re-enter if stopped/targeted while trend intact). Stops: trigger on H/L but exit at close in noisy markets.

## Trade selection by volatility
- Very high vol entries: big wins and losses, worse return/risk; very low vol: directionless small losses. Eliminate (short-term) vs **delay** (long-term trend, don't miss the big trade).
- Test (40-day MA trend, 1990–2011, $15 costs, 20-day σ of returns): **entering only on low relative volatility improved all markets** (threshold < 0.35σ; Eurodollar IR 1.143 vs 0.867 for high-vol entries). High-vol thresholds inconsistent across markets.
- **High-vol exit** (bonds): exit when |return| > 10× 20-day σ; re-enter in same direction when vol falls to ¼ of the exit-day move → considerably better.
- Appel fund ranking: only average/below-average volatility funds; rank 3-month + 12-month performance; buy top 10%.
- "You can't remove the risk, only delay it or move it around." Filtering removes good trades too.

## Liquidity
Backtest fills at the day's extremes are fictitious (volume ≈ 0 at H/L). Countertrend systems overstate profits most; trend systems entering at extremes usually lose on day 1.

## Noise
Noise ~ random: ~50% of moves reverse next day, 25% continue 2 days, 12.5% 3 days…; shock sizes geometric too. Low-noise markets (short rates) suit trend systems; high-noise (equity indices) delay entries/exits until trend profits vanish → longer periods (more reliable, fewer shocks flip them) or **mean reversion with short holds**. Noise rises as markets mature. Low-rate environments: long bond futures still earn roll/carry.

## Expert systems & fuzzy logic
- Knowledge base (facts) + inference engine (if-then rules, forward chaining). Example rules: ADX(18) > 18 and rising → 95% trending; ADX < 30 and falling → 90% non-trending; assign indicator reliabilities per regime (MACD 0.8 trend / 0.55 non-trend).
- Probabilities should come from measured reliabilities (% profitable), not opinion.
- Fuzzy logic: membership (acceptable/desirable/unacceptable), fuzzy rules, defuzzify. Weight short- vs long-window statistics by their standard errors (σ/√n: 250 days 6.3% vs 20 days 22.3% → ≈3.5:1). Ruggiero fuzzy candlesticks: body size relative to average body with zero/one triggers → still thresholds.

## Chaos / fractals
Fractal dimension (coastline length depends on ruler). **Fractal efficiency = efficiency ratio**: compare markets by ER and volatility; low noise → enter fast with trend; high noise → wait for better price / mean revert. Prices as decaying "raindrop" news shocks.

## Entropy
- H(X) = −Σ pᵢ log₂ pᵢ; 0 = certain, max log₂ n (equal probabilities). Normalise by log₂ n.
- Conditional entropy H(Y|X) = −Σᵢ p(xᵢ) Σⱼ p(yⱼ|xᵢ) log₂ p(yⱼ|xᵢ), p(yⱼ|xᵢ) = nᵢⱼ/nᵢ. **Lower H(Y|X) (relative to H(Y)) = more predictive** (book says "higher"; the useful quantity is mutual information I = H(Y) − H(Y|X)). Watch cells with tiny n.

## Neural networks
- Layers of weighted connections (synapses = weights), hidden layers combine inputs non-linearly. Train by feedback on history with known answers.
- **Preprocessing is critical** (trends, indicators, ratios, correlations, system positions −1/0/1 as inputs). Too many inputs → slow and overfit; too few → no information.
- Ruggiero: networks predict **smoothed forward indicators** better than raw returns (target e.g. 5-day average of a 5-period stochastic shifted 5 days forward).
- Split 70% train / 20% test / 10% out-of-sample. Success: correlation, t/F stats, RMSE = √(Σe²/n), MAPE = (1/n)Σ|eᵢ/Aᵢ|.
- Fewer layers/neurons/inputs → more general and robust. ANNs solve closed systems; markets may have no stable solution → must validate out of sample.

## Genetic algorithms
- Chromosome = rule set (genes: trend type, period, operator, price, lag, and/or, indicator, period, operator, threshold, action) → 4.8×10¹⁰ combos searched in < 1000 generations.
- Fitness example: **Rank = PPT·(1 − 1/√NT)·(GP/GL)** (or replace GP/GL by information ratio). $500 × 10 trades × 0.5 → ~171; $250 × 100 × 1.4 → 315 (prefers many trades and smoothness).
- Propagation ∝ fitness/average fitness; mate (swap whole individuals) ~10–15%; mutate ~10% (too little → premature convergence, too much → lose best). Stop when average/best fitness stalls.
- Local optima → **multiple random seeds**; 70–80% in-sample then out-of-sample/walk-forward.

## Replication
Regress fund returns on asset returns (constrained weights) to replicate; rebalance on tracking-error threshold.

## Takeaways for NSE project
- Volatility features: ATR(14)/price, Parkinson & Garman-Klass vol (we have OHLC), lagged relative vol σ₁₀/σ₆₀(lag 10), India VIX level/percentile/RSI(2), vol-of-vol.
- Test the **low-relative-volatility entry filter** and the high-vol-exit-with-reentry rule on our trend/momentum strategies.
- Sizing and stops in ATR units; profit targets only for short-horizon mean-reversion models.
- Never assume fills at H/L; use next-open or close with slippage.
- ML discipline from this chapter: small, preprocessed feature sets; smoothed targets can be easier to learn (but must map to tradeable P&L); train/validation/test chronological split; multiple seeds; mutual information as a quick feature-relevance check.
