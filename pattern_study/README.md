# Pattern study: do classical chart and candlestick patterns work on NSE large caps?

Date: 12 Oct 2026. Folder: `pattern_study/` (self-contained; reads `../data/raw/yahoo`).
Run: `python run_patterns.py` (about 1 minute). Writes everything below into `results/`:
`pattern_scores.csv`, `measured_move_test.csv`, `chart_pattern_events.csv` (every detected event with
trigger, stop, target), `examples_chart_patterns.png`, `examples_candles.png`, `meta.json`.
Only `measured_move_test.csv` is pre-copied here; run the script for the rest.

## Setup
- 100 stocks of today's NIFTY 100 (survivor list), 2015-01-01 to 2025-03-28. April 2025+ holdout untouched.
- Same cleaning as `scripts/40_indicator_truth_test.py` (zero-volume bars dropped, 7 Phase-5 repairs).
- Each pattern is dated on its **completion day** (breakout close, or last candle) using only data up to
  that day; trade at next day's open. Swing pivots need 5 bars each side, so they are only used 5 bars
  after the turn (no hindsight).
- Detector rules are in `patterns.py` (tolerances: same level = within 3%; flat triangle line = 1.5%;
  pattern depth at least 2xATR; flags need a pole of 3xATR in 10 days; candles need prior 5-day trend
  and close vs 20-day average). These are one reasonable textbook reading; other thresholds were not tried
  (on purpose, to avoid fitting).

## Three tests per pattern
1. **Direction**: hit rate and beats-market rate vs base rate at 1/5/10/20/60 days; random stock halves A/B.
2. **10-day label**: P(Up) for your 2xATR/1xATR label (base 27.6% Up).
3. **The pattern's own promise** (chart patterns): did price reach the measured-move target (pattern
   height projected from the breakout) before the textbook stop, within 60 days? Compared with a
   **placebo**: same stock, same direction, same % stop and % target, random dates. Bear patterns are
   scored as hypothetical shorts; you are long-only, so for you they only mean "exit / avoid".

Checked: 30 random detections plotted (shapes match the textbook pictures); 5 events hand-checked
against raw prices by an independent checker, which also fixed 2 bugs (t-stat spacing, event dedup order).

## Results

| Pattern | Cases | Beats market vs base, 10d | Excess vs market, 20d | Target before stop (needed) | Edge vs placebo | Verdict |
|---|---|---|---|---|---|---|
| Head and Shoulders | 172 | +6.5 pp | -0.65% (right way, t -1.9) | 29% (39%) | +1.3%, t 1.3 | Weak hint, not significant |
| Inverse Head and Shoulders | 105 | -5.7 pp | -1.2% (wrong way) | 35% (45%) | -1.2%, t -1.1 | Wrong way |
| Double Top | 398 | +1.9 pp | -0.64% (right way) | 40% (56%) | -0.7%, t -1.3 | Noise |
| Double Bottom | 390 | -1.2 pp | -0.70% (wrong way) | 56% (58%) | -0.8%, t -1.4 | Wrong way (weak) |
| Triple Top | 105 | +6.6 pp | -1.5% (right way) | 39% (54%) | +0.8%, t 0.7 | Noise, few cases |
| Triple Bottom | 85 | -0.7 pp | -0.39% | 58% (58%) | +0.2%, t 0.1 | Noise |
| Bullish Flag | 909 | -2.1 pp (-5.2 at 1d) | -0.24% | 31% (28%) | -0.4%, t -1.6 | Wrong way short term (breakout fades) |
| Bearish Flag | 660 | -2.5 pp | +0.32% (wrong way) | 16% (21%) | -0.2%, t -1.0 | Noise |
| Bullish Pennant | 228 | -3.2 pp (-11 at 1d) | -0.58% | 30% (29%) | -0.4%, t -0.6 | Wrong way short term |
| Bearish Pennant | 194 | -4.9 pp | +1.1% (wrong way) | 19% (23%) | -0.5%, t -0.8 | Wrong way |
| Ascending Triangle | 642 | -5.3 pp | -0.78% (wrong way) | 43% (45%) | -0.5%, t -1.1 | Wrong way |
| Descending Triangle | 463 | -0.3 pp | -0.33% (right way) | 30% (41%) | +1.0%, t 1.7 | Noise / weak hint |
| Symmetrical Triangle, up break | 332 | -1.1 pp | -0.49% | 26% (27%) | +0.5%, t 0.7 | Noise |
| Symmetrical Triangle, down break | 264 | -3.8 pp | +0.55% (wrong way) | 16% (22%) | +0.7%, t 1.2 | Noise |
| Cup and Handle | 245 | -5.4 pp | -0.37% | 29% (36%) | +0.3%, t 0.4 | Noise; lags market |
| Doji after uptrend (bear) | 9,235 | +0.1 pp | +0.19% | - | - | Noise |
| Doji after downtrend (bull) | 7,250 | +2.0 pp | +0.11% | - | - | Noise |
| Hammer | 1,143 | +1.9 pp | -0.06% | - | - | Noise |
| Hanging Man | 1,429 | -0.6 pp | +0.12% | - | - | Noise |
| Shooting Star | 1,472 | +2.2 pp | +0.07% | - | - | Noise |
| Inverted Hammer | 1,086 | -0.2 pp | +0.15% | - | - | Noise |
| Bullish Engulfing | 2,494 | +0.5 pp | +0.17% | - | - | Noise |
| Bearish Engulfing | 5,714 | -0.6 pp | +0.17% (wrong way) | - | - | Noise |
| Morning Star | 119 | +0.5 pp | -0.94% (wrong way) | - | - | Noise, few cases |
| Evening Star | 266 | -0.4 pp | +0.92% (wrong way) | - | - | Noise |

10-day label: P(Up) ranges 20-35% across all patterns vs 27.6% base; no bullish pattern beats base by
more than ~3 pp except Triple Bottom (35%, only 85 cases).

## What it means
- **No pattern has an edge.** Every measured-move result is within about 1.3% of the placebo
  (|t| < 1.7). The impressive-looking raw numbers (e.g. Double Bottom reaching target 56% of the time)
  come from the market's upward drift: random trades with the same stop/target do as well or better.
- **Bullish breakouts consistently lag the market.** Pooled across all 8 bullish chart patterns
  (2,749 breakouts): beat the market 2.5-4 pp less often than base at every horizon, in both stock halves;
  -0.3 to -0.5% excess. Non-overlapping t only -0.6 to -1.4, so not proven, but it matches the
  indicator test (60-day high breakouts also fade next 1-5 days). Buying the open after a breakout is
  the worst entry.
- Bearish tops (Head and Shoulders, Double/Triple Top, Descending Triangle) lean the right way at 10-20
  days but none passes t >= 2 after the placebo.
- Candlesticks: all within +/-0.2% excess at 10 days. Nothing to use.

## Recommendation
Do not add pattern detectors as features or agent signals. If anything is kept, use "fresh bullish
breakout" as a **don't-buy-today** filter and test it inside the full model, not standalone.

## Not done
- One parameter set only (no threshold search). Results could differ for other tolerances, but searching
  would overfit; Bulkowski-style statistics also come from hand-picked charts, which this avoids.
- Survivor-only stock list (see Phase 5 report).
- Weekly-chart versions of the chart patterns were not tested.
