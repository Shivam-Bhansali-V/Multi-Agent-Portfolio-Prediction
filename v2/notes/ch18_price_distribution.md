# Ch 18 — Price Distribution Systems (pp. 801–832)

## Basics
- σ bands: ±1σ 68%, ±2σ 95%, ±3σ 99.7% — **for normal data only**. Price returns are skewed/fat-tailed → σ misstates tails. Crude oil 20-day annualised vol hit 140% in 2008 (vs long-run 39%).
- Frequency distributions (percentiles from each tail) adapt to skew → often more practical than σ.
- **Bollinger bands** (20-day MA ± 2σ of prices). Compare 21- vs 65-day bands = monthly vs quarterly volatility.
- **Lag problem**: rolling σ widens slowly after a shock and stays wide afterwards (masks a second shock). Fix: compare current vol with a **longer and/or lagged** window (e.g. 6-month vol ending 1 month ago).

## Zones
- Gould: 3-year range in 5 equal zones (avoid buying top zone/selling bottom).
- **Jackson daily zones** (yesterday's H/L/C; same as pivots): Avg = (H+L+C)/3; High1 = 2Avg − L; Low1 = 2Avg − H; High2 = Avg + High1 − Low1; Low2 = Avg + Low1 − High1 → 6 zones from strongly down to strongly up. Fade into the middle zones (noise) with stops in outer zones. Usefulness depends on the actual frequency of prices in each zone (non-random clustering).
- Zones from MAs of H, L, C (e.g. 21-day) embed the trend.
- **Chande–Kroll volatility zones**: A = SMA₁₀|ΔC|; H1/L1 = Cₜ₋₁ ± A, H2/L2 = Cₜ₋₁ ± 2A. Prices jump to a new level then trade with similar volatility → breakout target ≈ prior range width.
- Scorpio zones: prior H + ATR₁₀, H, (H+L)/2, L, L − ATR₁₀ → tabulate open-zone→close-zone transitions.

## Long-term distributions
- Commodities: right-skewed (cluster at low "production cost" prices, long upper tail). Nominal prices distorted by inflation and USD → **deflate** (by PPI/DX) to see the true shape; wheat in USD 170% of 1985 level but below 90% deflated.
- Inflate old prices (current price unchanged) for trading use: Pₜ₋₁(adj) = Pₜ(adj)·(1 − r_DX,t).
- Trend-following trade returns are **strongly right-skewed** (bonds 80-day MA: mean $232, σ $2621 — ±3σ meaningless) → use sorted percentiles (10% tails −$1625 / +$2062).
- Structural changes (euro creation, lean hogs, gold/oil regime) break distributions.
- **Median > mean** as "normal" value; Pearson skew SK = 3(mean − median)/σ.
- Equilibrium: low volatility = accepted price; moving away from equilibrium raises volatility.

## Short-term distributions
- Normal right-skew at low levels → stable; symmetric bell at mid levels → congestion, no direction; **left-skewed (tail toward lower prices) with mode high → top-heavy, unstable, downside risk**.
- Potential moves: broad erratic distributions; right-skew with current price far in upper tail (volatile upside move in progress); left-skew with price entering lower tail (peaked, starting down). Distance from mode → volatility potential.

## Moving skewness (McNicholl)
1. Zero-lag double smoothing (a = 0.1): S = aC + (1−a)S₋₁; D = aS + (1−a)D₋₁; **M = ((2−a)S − D)/(1−a)**.
2. DEV = C − M.
3. SMD = b|DEV| + (1−b)SMD₋₁; DMD = b·SMD + (1−b)DMD₋₁; MD = ((2−b)SMD − DMD)/(1−b), b = 0.05; **STD = 1.25·MD** (σ ≈ 1.2533 × mean absolute deviation for normal data).
4. G = c·(DEV/STD)³ + (1−c)G₋₁, c = 0.333. Spikes mark trend changes.

## Kurtosis–skew strategies
- Excess kurtosis = K − 3. Trend: buy when excess kurtosis crosses **below** 0 with skew > 0 and ATR > minimum; sell with skew < 0. Mean-reversion: when excess kurtosis crosses **above** 0, fade in the direction opposite to skew (book's sell rule has a typo "below"). Stops at 10-bar extreme ± small offset. Few parameters but noisy on short windows.

## Market Profile (Steidlmayer)
- Distribution of **time** at price (TPOs = 30-min letters), not volume. Value area ≈ 70% of activity around the point of control (most TPOs); Jones: value area = ±2σ equivalent (42.5% of non-centre TPOs each side).
- Day types: normal (bell, value centred), trend (narrow value area at one end), non-trend. Auction theory: "price probes high to attract sellers, low to attract buyers"; value = price × time = volume.
- TPO imbalance above/below centre hints breakout direction (only in a normal value area). Moves out of value: price trend (rejected, one period) vs value trend (accepted, builds new value area). Activity above prior value = buyer-initiated, below = seller-initiated.
- Use: trend filter — take trend trades only when price leaves the value area.

## Distribution-based support
- Histogram of closes over ~6 months; central cluster = middle 60% (or ~1.5σ ≈ 86%); break of the cluster's lower edge can signal earlier than a classic n-day low (EuroStoxx 2011 example — one anecdote).

## Takeaways for NSE project
- Use **robust distribution stats**: rolling median, percentile ranks, MAD-based σ (1.2533·MAD), skew/kurtosis of returns (20–60 day) as features; avoid σ-band probability claims.
- Volatility regime: σ₂₀/σ₁₂₀ (lagged) ratio, Bollinger width percentile; vol computed on lagged windows to catch repeat shocks.
- Volume-profile analogue from daily data: rolling price-volume histogram (value area/POC over 20–60 days), distance of close from POC in ATRs, break out of value area flag.
- Strategy returns will be skewed: report percentiles, not just mean ± σ; for evaluation use Sortino/ tail metrics.
