# Ch 17 — Adaptive Techniques (pp. 779–799)

## Idea
Change an indicator's speed automatically with market conditions (noise, volatility, cycle) instead of one fixed period. Premise: noisy/sideways → slow trend; clean directional move → fast trend. Helps, but "the rules to vary the period have not been perfected." Every adaptive rule adds parameters → judge only by whole-period robustness.

## KAMA (Kaufman Adaptive Moving Average)
- **ER (efficiency ratio / fractal efficiency)** = |pₜ − pₜ₋ₙ| / Σᵢ₌ₜ₋ₙ₊₁..ₜ |pᵢ − pᵢ₋₁| ∈ [0,1].
- fast = 2/(2+1) = 0.6667, slow = 2/(30+1) = 0.0645.
- **sc = [ER·(fast − slow) + slow]²**; KAMAₜ = KAMAₜ₋₁ + sc·(pₜ − KAMAₜ₋₁). Code: sc = (ER·0.6022 + 0.0645)².
- Squaring makes the slow end extremely slow (sc_min = 0.00416 ≈ 480-day EMA equivalent via n = 2/sc − 1; book loosely calls it "30² = 900") and fast end sc_max = 0.444 ≈ 3.5-day EMA.
- ER period n: 8–10 (≤14); longer n only shrinks ER. Keep slow bound 30; raise fast bound to desensitise.
- Practical: KAMA always turns when price crosses it → add a filter (e.g. only accept direction change > 0.1·σ of KAMA changes); guard against ER = 1 on tiny moves.
- Noise ≠ volatility: same range achieved steadily vs back-and-forth gives very different ER.

## Other adaptive trends
- **FRAMA (Ehlers)**: fractal dimension D = log(N₂/N₁)/log(s₁/s₂) (box counting; a line has D = 1); α derived from D.
- **VIDYA (Chande)**: VIDYAₜ = k·s·Cₜ + (1 − k·s)·VIDYAₜ₋₁, s = 0.2, k = σ(n=9)/σ(m=30) (better on returns). Higher relative vol → larger k → **faster** (book's text says "slower" — formula makes it faster). Opposite philosophy to KAMA.
- **r²-adaptive (Chande)**: use r² of a linear regression of price vs time as the smoothing constant.
- **MAMA/FAMA (Ehlers)**: sc = fastlimit / phase-rate-of-change (Hilbert), clipped to [0.05, 0.5]; FAMA = same on MAMA with ½ sc; MAMA/FAMA cross = signal.
- Futures 1990–2011 comparison (no costs): avg profit factor KAMA 1.53 (fewest trades, ~159), MAMA 1.36, r² 1.22, VIDYA 1.17 (most trades). Success inversely related to trade count. All profitable on average → trend-following works across futures.
- **Adaptive momentum as sc**: any oscillator mapped to 0..1 (|M|, M/100, |M/100|) can be the smoothing constant (adaptive RSI; square it to slow down).
- **Adaptive stochastic**: lookback per = int(slow − ER·(slow − fast)).
- **McGinley Dynamic**: MDₜ = MDₜ₋₁ + (pₜ − MDₜ₋₁) / (k·n·(pₜ/MDₜ₋₁)⁴), k = 0.6 — speeds up in falls, slows in rises.
- **Parabolic SAR (Wilder)**: SARₜ = SARₜ₋₁ + AF·(EP − SARₜ₋₁), EP = extreme price of the trade; AF starts 0.02, +0.02 per new extreme, max 0.20; SAR never inside the last 2 bars' range; always in the market (stop-and-reverse). "Time is the enemy."
  - Knapp ER variant: initial stop 6·ATR(10); ER < 0.3 hold; 0.3–0.6 tighten 0.1·ATR; > 0.6 tighten 0.2·ATR (asymmetric for shorts); ratchet only.
- **Mart Master Trading Formula**: rank ATR(15) and net change(15) into 21 zones → CVF → sc ∈ [0.084, 0.33] (5–23 day); trend on (H+L+C)/3; band inversely related to volatility; breakout band trading.

## Adaptive oscillators
- **Trend-Adjusted Oscillator**: O = mean over n of (C−L)/(H−L) (×100); MAO = SMAₙ(O); **TAO = 50 − (MAO − O)** → removes persistent OB/OS clustering in trends (but loses some extremes).
- **Dynamic Momentum Index (Chande)**: period = int(14 / V), V = σ₅(C)/avg₁₀(σ₅) → higher volatility → shorter RSI period (book text inverts this in one sentence). Better: use price changes (or Σ|ΔC|) and m ≫ n.

## Adaptive intraday breakout (Meyers)
HR = Hₜ − Lₜ₋ₙ, LR = Lₜ − Hₜ₋ₙ (single bars n back), normalise by nᵃ and ATR(n) (range ∝ √n so a ≈ 0.5–0.75), take n-bar maxima, buy when HRmax > thrH and LRmax < thrL. 4 optimised parameters → overfit risk.

## Adaptive process
Re-optimise periodically on recent data (walk-forward) — trade-off between responsiveness and sample size (Ch 21).
- Arrington variable MA: period from |Δp|/σ between 0.25σ and 1.75σ mapped linearly to 5–30 days. Note: the printed formula gives a **longer** period for bigger moves, opposite of the stated intent — use nₜ = max − (max − min)·(z − 0.25)/1.5 for "faster when volatile".

## Takeaways for NSE project
- **ER(10)** is one of the most useful single regime features (noise vs trend): use as a feature and as a gating variable (trend models when ER high, mean-reversion when ER low).
- KAMA slope/distance, VIDYA, TAO, parabolic SAR distance (in ATRs) as features. Adaptive ≠ better automatically: compare against simple fixed MAs on the same walk-forward folds.
- Volatility-scaled thresholds everywhere (ATR multiples, σ-scaled breakouts) — this is the robust part of "adaptive".
