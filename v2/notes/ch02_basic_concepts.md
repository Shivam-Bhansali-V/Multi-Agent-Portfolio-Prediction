# Ch 2 — Basic Concepts and Calculations (pp. 25–78)

Verified numerically in Python where marked ✔.

## Data
- **Law of averages** ≠ "a losing streak must be balanced by a winning streak". It means in a big sample the many normal events swamp the rare ones (gambler's fallacy warning).
- **In-sample / out-of-sample (OOS):** all testing is overfitting to some degree. OOS can be used **once**. If it fails you are done — changing rules after looking at OOS contaminates it. Alternating IS/OOS blocks (e.g. 2-year) handles regime change. Withholding 50% halves the patterns you can learn from → need more data.
- **Sample error** ≈ 1/√N. 4 trades → 50% error; 400 trades → 5%. Slow systems with few trades/yr → pool trades across many markets.
- Data must contain **bull, bear and sideways** periods (e.g. 1990–2000 S&P is only bull).
- **Structural change** (company changes business) — robust systems should survive it; longer data is still better.
- **Economic data:** released late, revised; must use *as-released (point-in-time)* values and the release date, else lookahead.

## Averages
- Arithmetic mean; **time-weighted mean** W = Σ aᵢdᵢ / Σ dᵢ (book example 105.71).
- **Geometric mean** G = (Πaᵢ)^(1/n), ln G = mean(ln aᵢ). For growth/ratios. (10,1000) → 100. ✔ 104.2 for {40,…,200}.
- **Quadratic mean (RMS)** Q = √(Σa²/N) — basis of std dev.
- **Harmonic mean** H = n / Σ(1/aᵢ); H₂ = 2ab/(a+b). For rates over time (20 & 30 mph → 24). ✔ 87.59.
- For a non-symmetric distribution: Arithmetic > Geometric > Harmonic.
- **Median** robust to outliers (preferred except tiny samples); **mode** = most frequent. Right-skewed: Mean > Median > Mode.

## Distributions
- Histogram: bins = (max−min)/(k−1). Commodity prices: long right tail (cost of production floor). Trade P&L with fixed stop: losses truncated, profits open-ended → right skew. "There are no normal distributions in trading."
- **Mean deviation** MD = Σ|pᵢ − P̄| / n.
- **Variance** = Σ(pᵢ−P̄)²/(n−1); **σ** = √(Σ(pᵢ−P̄)²/n) (population form, Excel STDEVP). 1σ≈68%, 2σ≈95.5%, 3σ≈99.7%.
- **Skewness (3rd moment):** S = Σ(pᵢ−P̄)³ / ((n−1)σ³). Pearson approx: (Mean−Mode)/σ ≈ 3(Mean−Median)/σ. Positive = tail to the right.
  - Skew changes with price level: normal mid-range, positive at low levels, negative ("top heavy") at highs.
  - Transforms (log, sqrt, power) can normalise skewed data.
  - Exponential-probability equivalent P_E = X̄·log₁₀(1/(1−P))/log₁₀e — overstates while normal understates; for risk, prefer slightly overstating.
- **Kurtosis (4th):** K = Σ(pᵢ−P̄)⁴ / ((n−1)σ⁴); normal = 3; **excess kurtosis = K − 3**. Bias-corrected form: K = [n(n+1)/((n−1)(n−2)(n−3))]·Σ((pᵢ−P̄)/σ)⁴ − 3(n−1)²/((n−2)(n−3)).
  - Price distribution over a window: **trending → flat (negative kurtosis); range-bound → peaked (positive)**. Usable as a regime feature (Market Profile idea).
  - **Overfit check:** kurtosis of a backtest's daily returns > 7–8 → suspicious (too many same-sized wins).
- When data are skewed, use **empirical percentiles** (sort, take 10% / 90% positions) instead of ±σ. Neither tells you the size of the next extreme — expect bigger than seen.

## Autocorrelation
- Lag-k autocorrelation: correlate series with itself shifted k. Several lags may reveal cycles.
- **Durbin-Watson:** eₜ = rₜ − mean(r); d = Σ(eᵢ−eᵢ₋₁)² / Σeᵢ². d∈[0,4]; 2 = none; <2 positive autocorr (trend persistence); >2 negative (mean reversion). d ≈ 2(1−ρ₁).

## Probability of reaching a target (normal assumption)
- z = (Objective − Mean)/σ. Stock market μ=8%, σ=16% → P(return ≥20%) : z=0.75 → 22.66%. ✔
- Polynomial approximation (Abramowitz & Stegun 26.2.19), for z' = |z|:
  r = 1 + d₁z' + d₂z'² + d₃z'³ + d₄z'⁴ + d₅z'⁵ + d₆z'⁶, d = {0.0498673470, 0.0211410061, 0.0032776263, 0.0000380036, 0.0000488906, 0.0000053830}; **P(tail) = 0.5·r⁻¹⁶**. ✔ (book's printed c₃ = 0.0327… is a typo; correct 0.00327…). In code just use scipy.stats.norm.sf.
- Multi-period target: z = [ln(T/B) − n·ln(1+R_g)] / (s·√n), s = std of ln(1+rᵢ). (Book prints s×n; for i.i.d. log returns the dispersion scales with √n.)
- **Standard error** SE = √(Var/n).
- **t-statistic** t = mean(Δp)/std(Δp) × √n, df = n−1. df=20 needs t>2.086 for 2.5% upper tail; ∞ → 1.96. More parameters ⇒ need more trades.
- **Two-sample (Welch) t-test:** t = (P̄₁−P̄₂)/√(var₁/n₁ + var₂/n₂); Satterthwaite df = (s₁²/n₁+s₂²/n₂)² / [ (s₁²/n₁)²/(n₁−1) + (s₂²/n₂)²/(n₂−1) ] (book misprints the denominators). Use it on *trade returns* of two periods to test if a strategy is behaving consistently.

## Returns, NAV, annualising
- Simple r = p₁/p₀ − 1; log r = ln(pₜ/pₜ₋₁). Simple returns' average > log returns' average. NAVₜ = NAVₜ₋₁(1+rₜ), NAV₀=100.
- AROR simple = (Eₙ/E₀ −1)·252/n (book writes Eₙ/E₀ × 252/n); **compounded AROR = (Eₙ/E₀)^(252/n) − 1** (book's default); log method: Σ ln returns / years.
- 252 trading days (US), 260/262 elsewhere. India ≈ 245–250 — use our actual count.
- **Annualised volatility = σ_daily × √252** (monthly × √12). Monthly data hides intramonth drawdowns → looks ~18% less volatile (S&P 1990–2010: 18.6% daily vs 15.3% monthly).
- **Target volatility:** scale position by target/actual (book standard 12%). Leverage factor = σ_target/σ_actual.
- **Beta** = cov(r_A, r_B)/var(r_B); alpha = regression intercept.
- **Downside risk:** semivariance = Σ(R̄ − rᵢ)²/n over rᵢ < R̄; or std of daily drawdowns from the running equity peak.

## Index construction
- Indexₜ = Indexₜ₋₁ × Pₜ/Pₜ₋₁ (base 100). Lets different-unit markets be compared.
- Leveraged long: XCᵢ = XCᵢ₋₁·((Cᵢ/Cᵢ₋₁ − 1)·L + 1); inverse fund: use (Cᵢ₋₁/Cᵢ − 1). Daily rebalancing ⇒ path dependence/decay.
- Weighted aggregate index; USD index = trade-weighted *geometric* average.

## Performance ratios
- Information ratio = annual return / annual vol. **Sharpe** = (R − r_f)/σ. Treynor = (R − r_f)/β. **Calmar** = R / MaxDD. **Sortino** = (R − r_f)/downside σ.
- **Max drawdown** = largest % drop from a NAV peak to a later trough. One huge DD can hide inside σ — always report it.

## Probability
- Addition law (mutually exclusive), multiplication law (independent). Joint/marginal/conditional: P(A|B) = P(A∩B)/P(B). Example: P(up₂|down₁) = 0.15/0.25 = 0.60. P(A∪B) = P(A)+P(B)−P(A∩B).
- **Markov chain:** transition matrix T; state vector xₜ₊₁ = xₜT; steady state solves x = xT, Σx=1.
  - 2-state: P(up|up)=0.70, P(up|down)=0.55 → steady P(up) = 0.55/(1−0.70+0.55) = 0.647 ✔
  - Weather 3-state ✔ (0.400, 0.425, 0.175).
  - Replace "yesterday's direction" with "n-day trend direction" to get P(up | trend up). **Directly applicable: estimate on NSE data, compare to 50% baseline.**
- **Bayes:** P(Up|E) = P(Up)P(E|Up) / [P(Up)P(E|Up) + P(Down)P(E|Down)] — updating base rates with news/sentiment signal reliability (fits our planned sentiment agent).

## Supply/demand & models
- Elasticity E_D = %Δdemand/%Δprice (negative), E_S positive. Price = equilibrium; equilibrium ↔ low volatility, low volume; imbalance → volatility.
- Cobweb: oscillation away from equilibrium = rising volatility; toward = falling.
- Explanatory vs forecasting models. **Analytic approach** (choose factors in advance, then test) is more credible than mass data-fitting.
- Deflate prices (by PPI/currency) to separate macro drift from the real signal. Wheat's 25-yr rise fully explained by inflation/USD.
- Markets move on **surprise = actual − expected**, not on the report itself. Ruggiero's rules: yield-direction filters using inflation/yield ratio oscillator, M2 momentum, consumer sentiment yoy, jobless claims (all with lagged confirmation of yield trend).

## Takeaways for the NSE project
- Strict OOS discipline: our April-2025+ holdout is single-use.
- Report Sharpe, Sortino, Calmar, MaxDD, and count of trades (sample error 1/√N); require t-test significance of mean trade return.
- Use empirical percentiles, not ±σ, for thresholds (returns are fat-tailed).
- Rolling kurtosis/skew and Durbin-Watson/lag-1 autocorr = cheap regime features.
- Volatility targeting for position sizing.
- For news: model the *surprise* and use Bayes to combine with technical base rate.
