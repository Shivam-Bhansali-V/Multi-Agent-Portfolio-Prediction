# Ch 1 — Introduction (book pp. 1–24)

## Core ideas
- **Technical analysis (TA)** = systematic evaluation of price, volume, breadth, open interest to forecast price. Must have *clear, complete rules*. Includes regression, mean reversion, pattern recognition, ML.
- **Random walk** argument: no serial correlation → TA fails. Kaufman's counter-arguments:
  1. Long, documented track records of systematic strategies (20–30 yrs).
  2. Prices move on **anticipation** (expectations of further moves) — e.g. after 2 rate cuts, traders front-run the 3rd.
  3. Returns are **not normal and not symmetric**: fat tails, long "runs" (consecutive same-direction days) longer than normal theory predicts. Fat tail ⇒ some other part of the distribution must be thinner (mass has to come from somewhere). Those deviations are *why* methods work.
  4. People act for non-random reasons (fund flows at month-end, redemptions).
- **Data frequency changes apparent randomness.** Lower frequency (weekly/monthly) → smoother, more trend visible, higher correlation between successive prices. Higher frequency (intraday) → more noise.
  - Long-term trend follower → low-frequency data + long trends.
  - Short-term trader → high-frequency data + mean reversion.

## Measuring noise (noise ≠ volatility)
Noise = erratic movement around the underlying direction. Must be measured independent of volatility.

**Efficiency Ratio (ER, a.k.a. fractal efficiency)** — Kaufman's preferred:

    ER_t = |P_t − P_{t−n}| / Σ_{i=t−n+1..t} |P_i − P_{i−1}|

- Range 0..1. ≈1 → clean trend (straight line). ≈0 → pure noise.
- Book example: two 8-day paths with similar total path length (595 vs 554) but net change 35 vs 310 → ER 0.06 (noisy) vs 0.56 (trendy). *Bigger swings ≠ more noise if net move is bigger.*

**Price density** (how much of the n-day high–low box is filled):

    PD = Σ_{i=t−n+1..t} (High_i − Low_i) / (max(High over n) − min(Low over n))

High density → choppy/overlapping bars (noisy); low → bars stack directionally.

**Fractal dimension (FD) estimate** over n days:
1. Max = highest high over n, Min = lowest low, Range = Max − Min
2. dx² = (1/n)²
3. L = Σ_{i=t−n+1..t} sqrt( dx² + ((p_i − p_{i−1})/Range)² )   ← book prints the 2nd term without the square; the standard form (and dimensionally consistent arc length on a unit box) squares it.
4. FD = 1 + (ln L + ln 2) / ln(2n)
- FD ≈ 1 → straight line (trend); FD ≈ 2 → fills the plane (noise). Inverse relation to ER.

**Empirical result (2000–2012, futures + world equity indices):** 20-day avg ER vs a 40-day MA trend system's profit factor → positive relationship. Low noise (high ER) markets = better trend following. Short rates (central-bank driven) trendiest; **equity indices noisiest, worst for trend following**. High noise favours mean reversion.

**Market maturity:** noise rises as participation/liquidity rises (US index noise up over 20 yrs). Asia 2005–10 ranking: India Nifty/Sensex mid-table — more mature (noisier) than Shanghai (~0.37 ER) but less than Japan/HK; North America ≈ 0.25.
> Note on the book's axis: in Fig 1.7 "noise" is plotted as the ER value itself, so higher number = *less* noise. Keep the direction straight: high ER = trend.

## Research guidelines (8)
1. Start from a sound premise (an observed behaviour), not by brute-force testing everything.
2. State it in its simplest form (Occam's razor).
3. Assume nothing; prove everything.
4. Test the simplest/most important rule first; add rules one at a time and prove each one's contribution ("transparent solution").
5. Look for errors of omission (costs, risks you didn't model).
6. Question *good* results as hard as bad ones — surprisingly good is often a bug/lookahead.
7. No shortcuts; verify others' work and formulas by hand.
8. Start at the end — define goal, work backwards to needed inputs.

## Profile of a trading system (checklist)
- Markets change (technology, participation, globalisation, costs) → want **longevity/robustness**, not peak fit.
- Data choice (sector peers, yield curve, macro).
- Diversification (across markets, or multiple strategies on one market).
- Trade selection/filters — too many filters ⇒ overfitting or no trades.
- **Testing is for validating an idea and showing robustness, not for discovering one.** A system that works across all stocks in a sector looks worse than one optimised to a single stock but is far more realistic.
- Risk control at every level: trade → sector → system → portfolio of systems; volatility-based sizing.
- Transaction costs: fast systems most sensitive; trend (directional) entries suffer more slippage than mean reversion. Overstating costs is as harmful as understating.
- Monitor live vs expected performance.

## Takeaways for our NSE project (v2)
- Compute ER (and/or FD) per stock as a **regime feature**: high ER → trend rules, low ER → mean-reversion rules. Test this on our own data rather than assuming.
- Equity indices are the noisiest asset class in Kaufman's study → plain trend-following on NIFTY stocks with daily bars should be expected to be weak; mean-reversion or longer bars may fit better. Must be verified.
- Robustness over the whole NIFTY 100 (same rules for all stocks) beats per-stock optimisation.
