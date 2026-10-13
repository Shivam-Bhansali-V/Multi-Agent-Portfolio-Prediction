# Ch 12 — Volume, Open Interest, and Breadth (pp. 527–564)

## Nature of volume
- Very noisy: MSFT daily volume σ ≈ 38% of mean (price daily σ ≈ 2.9%). → always smooth/normalise.
- Seasonal & calendar patterns: lower Mondays, pre-holiday, summer; higher on expiry (triple witching). Intraday **U/W shape** (high at open and close) → compare each intraday bar with the same time-of-day average, never with the previous bar.
- Sum volume across a sector to smooth single-stock news bursts. Tick count ≈ volume proxy.
- **Volume predicts volatility**: high volume with small price change = latent volatility/risk.

## Interpretation
| Volume | Price | Meaning |
|---|---|---|
| ↑ | ↑ | confirms rise |
| ↑ | ↓ | confirms drop |
| ↓ | ↑ | weak rally |
| ↓ | ↓ | weak pullback |
- Volume leads price; 1-week returns on declining volume tend to reverse next week.
- **Volume spike** (≥2–4× normal) = crowd all in → usually **end of the move** (AOL, MSFT examples) — exhaustion, size of reversal unknown.
- Declining volume during a rally (AOL late 1999) = lack of support → reversal risk.
- Futures OI table (price, volume, OI → new buying, short covering, liquidation, new shorting).
- Equivolume (Arms): volume replaces time on the x-axis.

## Volume indicators (formulas)
- Average volume (≥50 days; match price MA length). Normalised: NormVol = 100·Vₜ/SMAₙ(V).
- Volume momentum Vₜ − Vₜ₋ₙ; % change.
- **Force Index (Elder)** = (Cₜ − Cₜ₋₁)·Vₜ; EMA₂ (fade extremes, timing) and EMA₁₃ (trend: buy when crosses above 0).
- Volume oscillator: SMA₁₄(V) − SMA₃₄(V) or ΣV₁₄/ΣV₃₄.
- **OBV** = OBVₜ₋₁ + sign(Cₜ − Cₜ₋₁)·Vₜ. Use its trend (MA) and divergence vs price (price ↑ OBV flat = weak). Can substitute OBV for price in an MA trend system (needs testing).
- **Money Flow Index** on TP = (H+L+C)/3: MFI = 100 − 100/(1 + ΣposMF/ΣnegMF) (MF = TP·V).
- Volume Count Indicator: +1 if Vₜ > Vₜ₋₁ else −1, cumulative.
- **Chaikin Volume Accumulator** = VAₜ₋₁ + ((C − L)/(H − L) − 0.5)·2·V (CLV-weighted: avoids OBV's all-or-nothing).
- Accumulation/Distribution = ADₜ₋₁ + (C − O)/(H − L)·V. Intraday Intensity = IIₜ₋₁ + ((C−L) − (H−C))/(H−L)·V.
- **Price-Volume Trend** = PVTₜ₋₁ + (Cₜ/Cₜ₋₁ − 1)·Vₜ.
- **PVI / NVI** (Fosback 1941–75, var. 1 by close direction; standard Fosback uses volume up/down days with % price change): NVI trend up (vs 255-day MA) → 96% chance of bull market; PVI up → 79%.
- Aspray demand oscillator; Blau Tick Volume Indicator TVI = 100·(DEMA(upticks) − DEMA(downticks))/(DEMA(up) + DEMA(down)).
- **VWMACD** = Σ(C·V)/ΣV over 12 − same over 26; signal EMA(0.2).
- **Elastic VWMA (Fries)**: eVWMAₜ = ((OS − Vₜ)·eVWMAₜ₋₁ + Vₜ·Cₜ)/OS, OS = shares outstanding (or ≈ max volume) → reacts faster on heavy volume.
- VWAP (execution benchmark) vs TWAP.

## Breadth (advance/decline)
- A-D line: cumulative (Advances − Declines). Breadth must match what you trade (large-cap breadth doesn't confirm small caps). Appel: equal-weight counts best.
- Sibbett Demand Index = Σ₁₀ up volume / Σ₁₀ down volume (Merrill: n = 5).
- Bolton-Tremblay: (Adv − Dec)/Unchanged accumulated (spiky).
- Schultz: Adv/Total.
- **McClellan Oscillator** = EMA₁₉(Adv − Dec) − EMA₃₉(Adv − Dec) (α = 0.10, 0.05); extremes mark turns.
- Upside/Downside ratio (asymmetric); **TRIN (Arms)** = (Adv/Dec)/(AdvVol/DecVol); Chande Thrust Oscillator = 100·(Adv·AdvVol − Dec·DecVol)/(Adv·AdvVol + Dec·DecVol), ±30 OB/OS. Better to use fractions of totals.
- New highs/lows: HLX cumulative (NH − NL); **HLR = ΣNH/Σ(NH+NL)** over n; Appel buys when 10-day HLR > 0.8–0.9.
- **Breadth as contrarian (Connors)**: AD ratio > 2 → sell index, < 0.5 → buy (5-day hold). NYSE declines > advances 3 days in a row → S&P +0.50% next week; NASDAQ declines > advances 2 days → NDX +0.80%; declines ≥ 2× advances → +0.60% (1996–2003); opposite conditions → ≈0.
- CHADTP = (Σ₅Adv − Σ₅Dec)/5; ±400 extremes + price confirmation (break of prior day's low/high) → 5–7 day reversal trade; best when volume "depressed".

## Systematic use
- Volume filter for trend entries: trade a 20-day trend signal only if V > SMA₁₀(V) (fewer trades, less time in market, similar returns). Waxenberg: trend change confirmed by volume > 1.2× 10-day avg; > 1.4× = extreme. Use Bollinger bands on volume for adaptivity.
- **Volume spike detection with lag**: Vₜ > T × mean(V over t−n−5 … t−5) (exclude the last 5 days so a 2–3 day build-up doesn't hide the spike).
- **Filter low-volume days** out of OBV (V < mean − k·σ ⇒ OBV unchanged) and **tiny price moves** (|Δp| < threshold ⇒ no volume posted).
- Integrated forecast index: 1-day-ahead regression forecasts of price, volume, OI, OBV (n chosen by minimum forecast-error σ) combined with weights w₁Pf + (1−w₁)(w₂Vf + w₃Of + w₄OBVf); weights near 0 reveal useless inputs.
- Opening-bar volume vs its own history predicts the day's volume/volatility.
- **Market Facilitation Index (Bill Williams)** = (H − L)/V: volume↑ & MFI↑ confirm; volume↓ & MFI↓ false move; volume↓ & MFI↑ poor timing; volume↑ & MFI↓ potential new trend / end of old (squat).
- Book's statistical note: removing days below mean − 1σ removes ~16%; below −2σ removes ~2.3% (book says 32% — error).

## Takeaways for NSE project
- We have daily volume (and delivery % on NSE — a uniquely Indian "conviction" volume measure worth adding). Features: normalised volume (V/SMA50), lagged volume-spike flag, OBV slope/divergence, CMF/AD (CLV), Force Index, MFI, VWMACD, PVI/NVI trend.
- Market breadth for NIFTY 100/500 constituents: % above 50/200-DMA, A/D line, McClellan, HLR, TRIN — both as regime filters and **contrarian short-term signals** (Connors) — test on NSE.
- Volume spikes at the end of moves → exit/avoid-entry feature; volume confirmation filter for breakouts.
- Remember intraday U-shape if we ever use intraday bars.
