# Ch 6 — Regression Analysis (pp. 235–278)

## Time-series components
Price = **trend + seasonal + cycle + random**. Long trends ← macro (rates, inflation, currency); short trends ← behaviour/news; cycles ← slow business response (capex); seasonality ← calendar. Decomposition: remove trend first (subtract regression line, or first differences Pₜ − Pₜ₋₁), then find seasonality/cycles.
- A regression/average over a window equal to a full cycle (e.g. 12 months) neutralises that cycle; windows ≤ 3 months keep seasonal/cyclic moves visible.
- Low-frequency data smooths extremes (looks less volatile).

## Linear regression (least squares)
Y = a + bX; minimise S = Σ(yᵢ − ŷᵢ)².
- **b = (NΣxy − ΣxΣy) / (NΣx² − (Σx)²)**, **a = (Σy − bΣx)/N** (= ȳ − b x̄).
- For a price trendline use X = 1,2,…,N (not dates — weekends break continuity). Wal-Mart 10 days: b = 0.707/day, a = 45.54.
- Regression **explains**, it does not predict; forecasting assumes the same conditions persist and loses accuracy with horizon.
- Projection: Pₜ₊ₙ ≈ Pₜ + n·slope (practice) or a + b(N+n) (line value).
- Two series: index both to 100 to get % relationship (ABX vs gold: slope 1.012 → ~1:1 in % terms). Fair-value spread trading when they diverge (Ch 13).
- Excel: SLOPE, INTERCEPT, LINEST; **CORREL returns r** (book says r² — RSQ gives r²).

## Correlation
- Pearson r = (1/N) Σ [(xᵢ−x̄)/sₓ]·[(yᵢ−ȳ)/s_y], −1…+1. r² = coefficient of determination; **r² < 0.20 → regression has no practical value**.
- **Correlate returns/price changes, not price levels** — common trends inflate correlation (spurious). For arbitrage use **cointegration** (Ch 13), not correlation.

## Confidence bands
s = √(Σeᵢ²/N) of residuals; 95% band = ŷ ± 1.96s (90% = 1.65s). Points outside → either abnormal (expect reversion) or the model is stale (re-estimate). Out-of-sample bands should widen with horizon; more data → slower decay. Slope also has a 95% CI (corn–soy slope 0.336, CI 0.274–0.397).

## Nonlinear fits
- Polynomial y = a₀ + a₁x + a₂x² + … (normal equations; solve by matrix). 2nd order (curvilinear) usually enough; higher orders fit better in-sample but extrapolate badly.
- Linearise: power y = a·xᵇ → ln y = ln a + b ln x; exponential y = a·e^{bx} → ln y = ln a + bx. Fit OLS on transformed data, a = e^{ln a}.
- Lesson: **best in-sample fit (curvilinear/exponential) gave absurd forecasts; the log model (worst fit) gave the most realistic forecast** — common sense > goodness of fit. Prices can't accelerate forever.
- Re-estimate on rolling windows when macro factors change.

## Multivariate regression
y = a₀ + a₁x₁ + … + aₙxₙ; normal equations (XᵀX)a = Xᵀy. Soybeans: price = −1.641 + 3.97·supply + 0.818·demand. Always gives an answer even with nonsense inputs → choose inputs from theory; compare residual variance; **drop tiny coefficients; fewer inputs better**; accurate only within the range of the training data (index/gold at new highs → unreliable).
- Lincoln's 6-month S&P model inputs: BAA/Treasury yield ratio (demeaned), 12-m change USD, 12-m change Fed funds, Fed funds/discount rate, M1, 12-m CPI change, 1-m vs 12-m CPI (inflation/disinflation), 12-m change LEI, S&P 1-month vs 10-month oscillator, real commercial-loan growth. Use yields not bond prices; **volatility-normalise** inputs when price level changes a lot; don't mix monthly macro with daily price targets.
- Sinusoidal least squares: y = a₀ + a₁t + a₂cos(2πt/P) + a₃sin(2πt/P) + a₄t·cos(2πt/P) + a₅t·sin(2πt/P) for known period P.

## ARIMA (Box–Jenkins) ARIMA(p,d,q)
- AR(p): pₜ = a₁pₜ₋₁ + … + a_p pₜ₋ₚ + e. MA(q) models the error with past errors. d = number of differences to make data stationary.
- Steps: stabilise variance (log), difference until correlogram shows no significant autocorrelation, pick smallest p, q; estimate iteratively until coefficients/SSE converge; check residuals.
- ARIMA(0,1,1) = simple exponential smoothing.
- Gold first differences: no significant autocorrelation at lags 1–15 (near random walk on daily data).
- Uses: 1-day-ahead forecast direction as trend; buy dips below forecast in an up-forecast; confidence-band mean reversion (enter at 95% band, exit at centre), only in the direction of the ARIMA trend; intraday breakout of forecast high/low.
- **Kalman filter**: combine a message model (any forecast) with an observation model (new information) via Kalman gain K: p′ₜ₊₁ = c·f(p′ₜ) + Kₜ₊₁·oeₜ.

## Trading with linear regression
- Rolling n-day regression → 1-day-ahead forecast Fₜ₊₁. Buy when close > Fₜ₊₁ + 2Rₜ, sell when close < Fₜ₊₁ − 2Rₜ (Rₜ = σ of residuals). Responds faster to change than a moving average (MA has lag; regression measures against projection).
- **Slope rule**: long when slope > 0, short when < 0 (or slope turning up/down). Longer periods smoother. Competitive with other trend methods (Ch 8).
- **Slope + R (Tesco)**: correlate price with time index; R ∈ [−1,1] measures *consistency* of trend (same slope can be smooth or noisy). Use R (or R trend) as filter.
- **Chande Forecast Oscillator**: %F = 100·(y − ŷ)/y with 5-day regression; signal when %F crosses its 3-day average (residual trending).
- **Relative strength ranking**: index stocks to 100, compute rolling 60-day regression slope on each, rank → buy strongest/short weakest (or reverse for mean reversion). Basis of market-neutral strategy (Ch 13).

## Takeaways for NSE project
- Features: rolling slope (normalised by price or ATR), R/R² of price vs time (trend quality), residual z-score from rolling regression (mean-reversion signal), 1-day-ahead regression forecast vs close.
- Cross-sectional: rank NIFTY-100 stocks by 60-day regression slope of log price within each sector (fits the "judge vs sector" four-quadrant idea).
- Correlate returns (not prices) when grouping stocks; consider cointegration for pairs.
- Keep models simple; check sign/stability of coefficients across 2015–19 vs 2020+.
