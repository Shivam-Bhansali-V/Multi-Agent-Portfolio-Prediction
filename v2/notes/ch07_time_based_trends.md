# Ch 7 — Time-Based Trend Calculations (pp. 279–308)

## Forecasting vs following
- Forecast = predict level (with confidence that decays with horizon). Following = only identify current direction (autoregressive: pₜ₊₁ = a₀ + a₁pₜ + a₂pₜ₋₁ + … + e).
- **Lag is the price of noise filtering**: the lag is the zone of uncertainty that lets the method ignore noise.
- GE rolling 20-day regression, forecast error std: 1-day 1.14, 2-day 1.34, 3-day 1.52, 5-day 1.86, 10-day 2.67 → **use 1-day-ahead forecasts in strategies**.
- A trend system profits if (a) >50% directional accuracy with equal up/down sizes, or (b) <50% accuracy but winners larger than losers. Best method = profitable across **most markets and most periods**. Short periods have no trend (noise) → use longer periods.

## Momentum (first difference)
Mₜ = pₜ − pₜ₋ₙ. Trend up if > 0. For large n ≈ SMA direction. **Always ask: is a new method better than the simple n-day price change?**

## Simple moving average (SMA)
MAₜ = (1/n) Σ_{i=t−n+1..t} pᵢ; recursive MAₜ = MAₜ₋₁ + (pₜ − pₜ₋ₙ)/n.
- MA rises iff new price > price dropped (pₜ > pₜ₋ₙ) → **SMA direction = sign of n-day momentum**.
- **Drop-off effect** = (pₜ − pₜ₋ₙ)/n: abrupt change when a big old value leaves.
- 200-day = stock-market benchmark; 63 days ≈ quarter; 252 ≈ year (removes seasonality). An MA whose length equals a cycle wipes the cycle out; to see a cycle use MA ≤ ½ cycle length; choose MA lengths **out of phase** with known cycles.
- Inputs: close (standard), (H+L+C)/3, (H+L)/2; smoothing highs and lows separately gives a range band.

## Other averages
- **Average-off**: Aₜ = ((n−1)Aₜ₋₁ + pₜ)/n (this is Wilder smoothing = EMA with α = 1/n).
- **Weighted MA**: Wₜ = Σwᵢpᵢ/Σwᵢ. Linear (front-loaded) weights 1..n; geometric weights wᵢ₋₁ = a·wᵢ (≈ exponential); group weights.
- **Triangular**: weights rise to middle then fall (= double SMA); Gaussian: wᵢ = 10^x, x = −(3/2)(1 − 2i/n)² (shape like a bell; sign implied). Used for cycle work (reduce noise at both ends).
- **Pivot-point (end-point) MA**: weights (3i − n − 1), i=1 oldest, sum normalised by n(n+1)/2 → negative weights on oldest data, reduces lag. This equals the **end point of an n-day linear regression** (≈ 3·WMA − 2·SMA). Can go out of phase on short windows.
- Std-dev MA (Lee): MA(15) + 0.05 × (SD(30) − SD(30)[1])/SD(30).
- **Geometric MA**: exp(mean(ln p)) — matters only for wide price ranges (long-term data).
- Accumulative average (since start) and reset accumulative (restart at events/earnings) — limited trend use.

## Exponential smoothing (EMA)
- **Eₜ = Eₜ₋₁ + a(pₜ − Eₜ₋₁)**, 0 ≤ a ≤ 1; init E₁ = p₁ (needs warm-up for small a).
- Weights on past prices: a, a(1−a), a(1−a)², … (geometric decay; never fully forgets).
- **Conversion: a = 2/(n+1)** (Hutson) — equal "average age" to an n-day SMA but leaves ~13–14% residual weight beyond n days. Residual-impact form: a = 1 − RI^(1/n).
- Higher-order: c_p = 1 − (1 − 2/(n+1))^(1/p).
- Fully-calculated equivalence (within 1%): a 0.10 ≈ 20-day SMA, 0.20 ≈ 10, 0.30 ≈ 6, 0.40 ≈ 4, 0.50 ≈ 3. **When optimising, space smoothing constants evenly in log/days**, not linearly in a (linear a-steps waste half the tests on ≤3-day averages).
- Lag comparison (1..15..1 ramp): 5-day SMA reaches constant lag 1 and turns 3 bars after peak; 20% EMA approaches lag 0.95 and turns 4 bars after peak (memory of the past).
- **Lag/error correction**: eₜ = pₜ − Eₜ; ERRₜ = ERRₜ₋₁ + a(eₜ − ERRₜ₋₁); EEₜ = Eₜ + ERRₜ (more responsive; can iterate — like ARIMA).
- **Double smoothing**: DMA of 3-day MAs = (p₁+2p₂+3p₃+2p₄+p₅)/9 (triangular). Double EMA DEₜ = DEₜ₋₁ + a(Eₜ − DEₜ₋₁) → smoother, more lag.
- **Blau double-smoothed momentum**: SMₜ = SMₜ₋₁ + a₁((pₜ − pₜ₋ₙ) − SMₜ₋₁); DSMₜ = DSMₜ₋₁ + a₂(SMₜ − DSMₜ₋₁). Differencing removes one lag, so double smoothing ends with ~one lag; very smooth, early turns. Trade on the line turning up/down. (Basis of TSI.)
- **Exponential regularization (Mills)**: Rₜ = [Rₜ₋₁(1+2w) + α(pₜ − Rₜ₋₁) − wRₜ₋₂]/(1+w).
- **Hull MA**: HMA = WMA(2·WMA(p, n/2) − WMA(p, n), √n) — reduces lag while staying smooth.

## Leads and lags in plotting
Plot MA shifted forward (as an n-day-ahead forecast; price crossing it = signal) or backward by n/2 to centre it on the data (cycle phasing). **Centred averages use future data — only for analysis, never as a live signal.**

## Takeaways for NSE project
- Candidate trend features: n-day log return (momentum), SMA/EMA slope, price vs MA distance (in ATR units), HMA, regression end-point, Blau double-smoothed momentum.
- Parameter grids: geometric spacing of lengths (e.g. 5, 8, 13, 20, 30, 50, 80, 120, 200).
- Benchmark every fancy smoother against plain n-day momentum.
- Warm-up: drop the first ~3–4×n bars of EMA output (initialisation bias).
