# Ch 11 — Cycle Analysis (pp. 485–526)

## Basics
- Price = trend + seasonal + cycle + noise. To isolate cycle: remove trend (first differences or regression residuals) and seasonality (subtract 1-year MA / 252-day difference).
- Cycles: production (cattle 9–12 months), inventory, business (≈8.6 yrs, Princeton Economic Institute), Kondratieff (~54 yrs; too imprecise to trade — 10% period error = 5 years), political (presidential cycle), behavioural (short cycles).
- Harmonics: sub-cycles at ½, ¼ … of the main cycle; when synchronised, peaks/troughs coincide.
- **Need a fundamental reason and ≥8 repetitions** before believing a cycle. Financial cycles drift in period (Swiss franc 24–35 weeks, later 30–52) → hard to systematise.
- Simple ways: average peak-to-peak distance on a weekly chart (Ehrlich cycle finder); detrend with the cycle-length MA (p − MA₂₀) or n-day differences; oscillators with period ≤ ½ cycle; **two-EMA MACD with long EMA = ½ cycle, short = ¼ cycle**; triangular MACD (difference of triangular MAs of P and P/2; weights rise to 2.0 at centre, step 2/(P/2)).
- Presidential cycle (DJIA 1912–92): pre-election year +11.0%, election +7.0%, post-election +4.7%, mid-term +2.3%. S&P futures 1983–2010: election year strongest, 1st year worst. Election-year sub-periods (first 10 days, pre-convention, post-election) positive.

## Terminology
Amplitude a, period T, frequency ω = 1/T (or 360°/T per bar), phase (offset), phase angle; left/right translation (peak earlier/later than centre of cycle).
y = a·sin(ωφ + b). Compound waves = sums. Extrema at y′ = 0; y″ > 0 minimum, y″ < 0 maximum.

## Trigonometric regression
- Detrend (OLS), then single frequency yₜ = a cos ωt + b sin ωt:
  α from least squares αΣc² = Σcd with c = yₙ, d = yₙ₋₁ + yₙ₊₁; **cos ω = α/2**; then solve the 2×2 normal equations for a, b. Copper (quarterly 1963–79): α = 1.464 → ω = 42.9° → period 8.4 quarters.
- Two frequencies: 2x² − α₁x − (1 + α₂/2) = 0 with x = cos ω (α₁, α₂ from least squares with c = yₙ + yₙ₊₂, d = yₙ₊₁, p = yₙ₋₁ + yₙ₊₃); then 4×4 normal equations. Copper → 10.6 and 2.6 quarters.

## Fourier / spectral analysis
- yᵢ ≈ Σ_k [u_k cos(2πki/N) + v_k sin(2πki/N)], u_k = (2/N)Σ yᵢ cos(…), v_k = (2/N)Σ yᵢ sin(…).
- **Requires stationary data** (detrend, ideally use returns not differences when price level changes a lot). Periodogram / spectral density (power ∝ amplitude²). Noise of similar amplitude obscures cycles.
- Autocovariance-based spectrum with lag windows: Tukey λ_k = ½(1 + cos(πk/M)); Parzen λ_k = 1 − 6(k/M)² + 6(k/M)³ for k ≤ M/2, 2(1 − k/M)³ for k > M/2.
- FFT practicalities: detrend, taper ends with a bell window, pre-filter with MA (an n-bar MA removes cycles ≤ 2n bars); Excel FFT needs 2^k points; take IMABS of complex output.
- FFT needs ≥256 points and ~16 cycles → not usable for short-term cycles.

## Ehlers (MESA, Hilbert, Fisher)
- **MESA** (maximum entropy) finds cycles from little data. Key "lateral shift": Ehlers uses the presence of a short-term cycle to decide **market mode** — if a cycle exists, the market is not trending; trade the trend otherwise. Useful cycles exist only ~20% of the time. Phase-angle sawtooth regular = cycle mode; erratic = cycle breaking down.
- Trend mode test: trend exists if smoothed price hasn't crossed the instantaneous trendline within the last half dominant cycle.
- **Hilbert transform** (truncated): Quadrature Q = 0.0962pₜ + 0.5769pₜ₋₂ − 0.5769pₜ₋₄ − 0.0962pₜ₋₆; InPhase I = pₜ₋₃; phase θ = arctan(Q/I). Needs as little as 4 bars; sharp peaks/valleys suitable for mean reversion.
- **Fisher transform**: price position in n-bar channel normalised to x ∈ (−1,1) (Ehlers: x = 0.33·2·((P − min)/(max − min) − 0.5) + 0.67·xₜ₋₁, clipped ±0.999), y = 0.5·ln((1+x)/(1−x)) (+0.5·yₜ₋₁ smoothing). Converts the bimodal (sine-like, clustered at extremes) distribution of bounded oscillators into near-Gaussian → sharp turning points; trade crosses of its 1-bar-lagged trigger after extremes. Book prints both coefficients as 0.5.
- **Inverse Fisher** x = (e^{2y} − 1)/(e^{2y} + 1) (= tanh y) applied to a centred, scaled RSI (0.1·(RSI − 50), WMA-smoothed) → bipolar oscillator clustering at ±1.
- A sine wave spends most time near its extremes — same as price within a channel.

## Other
- **Cycle/Commodity Channel Index**: use SMA (not EMA) with N < ¼ cycle; CCI > +100 = cyclic turn up, < −100 down.
- **Short Cycle Indicator (Lorca-Susino)**: based on squared EMA(8)/EMA(20) convergence relative to lowest-high/highest-low of slow period; sell setups when indicator rises but is below its value 12–16 bars ago with expanding range at a 12–16 bar high, etc. (intraday, multi-timeframe).
- **Hurst phasing**: full-span MA (≈ cycle length) and half-span MA, each shifted back by half its length; trend = regression through their crossings; when half-span turns down, target = projected crossing − D (D = max excursion above trend). Trade: long when half-span turns up, short when it turns down, exit at target (10% early).
- Centred/shifted averages and FFT on full samples use future data — **only valid for analysis, not live signals**.

## Takeaways for NSE project
- Most useful idea: **regime/market-mode detection** (cycle present ⇒ mean-revert; absent ⇒ trend). Candidate features: Hilbert phase stability, dominant-cycle period estimate, Fisher transform of price in N-day channel, CCI.
- Check earnings-cycle (quarterly ≈ 63 trading days) effects per stock.
- Any spectral work must be on returns (stationary) and computed with rolling, causal windows.
