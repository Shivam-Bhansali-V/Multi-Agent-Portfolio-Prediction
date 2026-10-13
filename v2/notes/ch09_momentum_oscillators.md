# Ch 9 — Momentum and Oscillators (pp. 369–426)

## Terms
- Momentum (industry usage) = price change over n days, M(n)ₜ = pₜ − pₜ₋ₙ (really "speed" if divided by n). Rate of change (ROC) in the book = **acceleration** (change of momentum); many software packages use ROC = momentum — check definitions.
- Momentum ≠ volatility (up 50 then down 50 → zero momentum, high volatility).
- Momentum peaks when the *rate* of rise is highest (before price peaks) → **leading indicator**; crosses zero when pₜ = pₜ₋ₙ. Price keeps rising while momentum falls but > 0 (deceleration).
- Percentage momentum: pₜ/pₜ₋ₙ − 1 or ln(pₜ/pₜ₋ₙ) (not on back-adjusted futures — use differences).
- Price minus its MA ("relative strength") behaves like momentum (extremes at the same points).
- Momentum has no lag vs MA but more noise; momentum crossing 0 ≡ MA turning. Use a small band around 0.
- Momentum period: ½ or ¼ of the natural peak-to-peak cycle.
- Volatility does not scale linearly with time (3-day range is not 3/20 of 20-day range).

## Using momentum
- **Entry timing within a trend**: short momentum (e.g. 6 days or 3-day) with a 30–50 day trend → buy dips in uptrends; trend reversal is the stop.
- **Fading extremes**: thresholds set visually, as % of max, or ±kσ of momentum. Entry variants: aggressive (on penetration), minor confirmation (first turn after penetrating), major confirmation (cross back inside band), timing (after n days outside). Exits: opposite signal, partway to zero, **zero line (benchmark: mean is the best forecast)**, or allow extension.
- **Problem: momentum scale changes with volatility** (S&P 2006 ±30 → 2008 ±150) → fixed thresholds fail catastrophically; need volatility-adaptive bands or normalised oscillators. Stops based on % or volatility multiples.
- Test anecdote: a bug that *bought* upper-band penetrations with a tight stop was profitable → high momentum persists briefly; **"declining momentum does not mean falling prices"**; aggressive fading of momentum lost.
- Trend fights mean-reversion: if a move lasts longer than the momentum window, price is higher when momentum returns to zero.
- **High-momentum trading**: trade *with* very high momentum for short periods (minutes–days) after a new high from a quiet base; exit as volume fades.

## MACD (Appel)
MACD = EMA(fast) − EMA(slow) (12/26 standard; 19/39 for NASDAQ); signal = EMA₉(MACD); histogram = MACD − signal. Buy MACD crossing above signal; filter: only take buys after MACD was below −threshold (and sells after above +threshold) — fitted thresholds are unreliable. Main uses: trend and **divergence**.

## Divergence index
DI = (SMA_fast − SMA_slow)/σ(Δp over slow period)² [book prints StDev(...)²; i.e. volatility-normalised spread]. Bands = ±factor·σ(DI, slow). Buy when DI < lower band in an uptrend; sell when DI > upper band in a downtrend; exit at DI = 0. (Buy pullbacks in trend.)

## Oscillators (normalised momentum: 0..100 or ±1)
Normalising by recent range auto-adjusts to volatility/price level (AMZN $2 in 2006 ≈ $8.77 in 2011).

### RSI (Wilder)
RS = AU/AD (avg up changes / avg down changes, n=14, Wilder smoothing AUₜ = AUₜ₋₁ − AUₜ₋₁/n + max(Δp,0)/... i.e. Wilder average with α=1/n); **RSI = 100 − 100/(1+RS) = 100·AU/(AU+AD)**. Thresholds 70/30.
- Aan: 14-day RSI tops/bottoms average ≈ 72 / 32 → 70/30 too close; use ~1.5σ equivalent. Shorter period → widen zones (10-day with 80/20).
- n-day changes inside RSI (non-overlapping 2-day changes ×14) smoother.
- Fast-change countertrend: sell if RSIₜ − RSIₜ₋ₖ > a.
- **CMO (Chande)** = 100(Su − Sd)/(Su + Sd).
- **2-day RSI (Stokes, MarketSci)**: changes pₜ − pₜ₋₂; buy next close when < 10, short when > 90, exit 1 day later. **Was a trend indicator 1970–1998, flipped to mean-reverting after 1998** on S&P; scaling in (RSI<20:25%, <15:50%, <10:75%, <5:100%) worked long and short 2000–08. 1-day trades → cost-sensitive.
- RSI of the MACD spread (5-day RSI of 10/40-week MA spread) gives clearer OB/OS.

### Stochastic (Lane)
%K raw = 100·(C − LL(n))/(HH(n) − LL(n)); %K-slow = SMA₃(%K); %D-slow = SMA₃(%K-slow). Uses H, L, C; closes near the high in uptrends.
- Trade %K-slow/%D-slow crossovers after extremes (80/20), **filtered by a trend** (e.g. 60-day MA: only shorts when %D > 80 and crosses down in a downtrend).
- Lane patterns: left/right crossover (right = slower, more stable turn), hinge (flattening → reversal next day), warning, extremes (0/100 need ~7 closes at highs/lows), bear set-up (price higher highs but %D lower lows), failure (fails to re-cross).
- **Stochastic of any indicator** (e.g. StochRSI = (RSI − min RSI)/(max RSI − min RSI)).
- "Delays in entering = lost opportunity; delays exiting = real losses" — don't use timing rules for exits.

### Williams
- A/D oscillator: BP = H − O, SP = C − L; DRF = (BP + SP)/(2(H−L)) ∈ [0,1]; smooth (e.g. EMA 0.3); OB/OS 80/20 (raw), 70/30 (smoothed). Fix gaps by replacing H/L with prior close when outside range (true range logic).
- Oₜ = (Hₜ − Cₜ₋₁)/(Hₜ − Lₜ) links today to yesterday.
- **%R** = (HH₁₀ − C)/(HH₁₀ − LL₁₀) (inverted stochastic); use for adding in trend direction.
- **Ultimate Oscillator**: BP = C − min(L, C₋₁); TR; UO = [4·(ΣBP₇/ΣTR₇) + 2·(ΣBP₁₄/ΣTR₁₄) + (ΣBP₂₈/ΣTR₂₈)]/7 ×100. Divergence-style entries (failure on right shoulder), exits at 30/70, stops at 65/35.
- **Relative Vigor Index (Ehlers)**: N = (C−O) with 1-2-2-1 weights/6, D = (H−L) same weights; RVI = ΣN/ΣD over n=10; signal = 1-2-2-1 weighted RVI; trade crosses after extremes.

## Double-smoothed momentum (Blau)
- **TSI** = 100 × EMA_s(EMA_r(Δp)) / EMA_s(EMA_r(|Δp|)). Smooth with little lag. Variant: use n-day Δp (e.g. 10-20-20) for smoother. Anticipate turns when slope ≈ 0.
- Double-smoothed stochastic DS(q,r,s) = 100·EMA_s(EMA_r(C − LL_q)) / EMA_s(EMA_r(HH_q − LL_q)).
- TRIX: triple EMA then difference (differencing last → smoother than TSI).
- Returns divided by today's price (instead of yesterday's) said to stabilise.
- **Strength oscillator** (trend vs sideways) = SMAₙ(Cₜ − Cₜ₋₁)/SMAₙ(Hₜ − Lₜ): large → trend; near 0 → sideways.

## Volume in momentum
- MV = (pₜ − pₜ₋ₙ) × avg volume(n); %MV; TRMV = Δp/ATR(p) × avg vol.
- **Money Flow Index** = volume-weighted RSI on typical price (H+L+C)/3: MFI = 100 − 100/(1 + Σpos MF/Σneg MF), 14 days.
- Herrick Payoff Index (futures, with OI).
- Volume is erratic: use long-smoothed volume; use only exceptionally high-volume days; low volume = cluster or decay. Volume is a good proxy/forecaster of volatility.

## Velocity and acceleration
- Velocity = 1st difference (slope), acceleration = 2nd difference. Derivatives table: line (v=b, a=0), quadratic (v=b+2cx, a=2c), ln x (1/x, −1/x²), e^{ax} (ae^{ax}, a²e^{ax}); MAs/EMA have constant velocity (need second-order smoothing to get acceleration).
- Sign table: v+,a+ up accelerating; v+,a− up decelerating (leading reversal warning); v≈0 and a≈0 → sideways (v≈0 alone isn't enough).

## Hybrids
- Wilder Directional Parabolic: trade Parabolic SAR only in ADX/DMI direction; ADX above both DIs and turning down → exit.
- **Kestner**: osc = SMA10 − SMA50; enter in direction of osc change only when ADX(14) < 30 (no-trend regime) — mean reversion of oscillator direction in quiet markets.
- **Trend + oscillator timing**: 40-day MA up and 5-day stochastic < 20 → buy (mirror short); exit immediately on trend change; force entry after n days so trades aren't missed.
- Cambridge Hook: outside reversal + RSI > 60 + rising volume/OI in uptrend → reversal; stop above hook high.

## Divergence
- Bearish: price higher high while momentum lower high; bullish mirror. Must be **opposite directions**; bigger divergence → sooner reversal; longer time span → bigger reversal; best when momentum starts from an extreme and signal occurs while momentum still far from neutral.
- Rules: enter on MACD/signal cross after divergence; stop if momentum exceeds prior momentum peak; target momentum neutral (0/50) or price objective; may convert to trend trade.
- Anticipate: once price breaks prior high with lower momentum, scale in thirds (new high with lower MACD; MACD within 15–20% of previous peak; MACD crosses signal).
- Double/triple divergences more reliable. Programming: swing-based peaks (2–5% swing), stochastic momentum, strength ≥5%. **Slope divergence**: regression slope of price vs slope of momentum since last momentum peak (catches rounded tops with no swings); double-smoothed momentum (20-20-20) for slope.

## Final comments
Fast oscillators are unstable; countertrend use = high risk. Best as **timing inside a trend strategy**: tune oscillator period so it gives 1–2 oversold signals within the acceptable entry delay window.

## Takeaways for NSE project
- Features: RSI(2), RSI(14), stochastic %K/%D, CMO, TSI, MACD histogram, Ultimate Oscillator, MFI, strength oscillator, velocity/acceleration of log price, divergence flags (slope-based).
- Strategy candidates to test (cash equity, long only fits our scope): RSI(2) < 10 dip-buy in long-term uptrend (book shows regime flip ~1998 in US — verify sign on NSE 2015–19 vs 2020+); trend + stochastic pullback entries; Kestner ADX<30 mean reversion.
- Normalise everything by volatility; fixed momentum thresholds break when volatility changes.
- Exits: don't delay on exits; mean-reversion target = neutral oscillator.
