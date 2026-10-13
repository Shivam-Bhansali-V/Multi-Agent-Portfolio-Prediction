# Ch 21 — System Testing (pp. 905–986)
"Numbers are like people; torture them enough and they will tell you anything." Most important chapter for our project methodology.

## Philosophy
- Testing is for **validation of an idea, not discovery**. Write expectations (number of trades, % winners, rough profit, risk) **before** testing; if results differ, something is wrong (including when results are surprisingly good).
- The best optimised result "never lives up to expectations"; everyone overfits sometimes.
- Objective: risk-adjusted (Sharpe = (R − R_f)/σ annualised; information ratio without R_f), plus drawdown, profit/trade (to see cost sensitivity).

## Parameters
- Types: continuous, discrete, **coded** (rule switches/regimes — no continuity across values, don't average or smooth them).
- **Ranges set in advance** and consistent with the idea (short-term MA 3–15 → RSI 3–10, not 3–50). Fewer combinations = more honest.
- **Non-uniform spacing**: geometric steps (×1.5: 1, 1.5, 2.2, 3.3, 5, 7.6, 11.4, 17.1, 25.6, 38.4, 57.7). Equal steps over-weight the long end (49 vs 50 is 2%, 2 vs 3 is 50%).
- **Order**: test the primary component first (trend period), then timing, then risk control. A stop-loss should refine risk, **not turn a losing system into a winner**.
- Count tests before running (250×30×30 = 225,000).

## Data
- Stocks: split-adjust (divide pre-split by ratio). Futures: back-adjusted continuous (roll on volume/OI or fixed date) — no percentages on back-adjusted series (can go negative); keep a second unadjusted series for true historical levels. Indexed (return-based) series good for comparisons. Constant-maturity/perpetual series are smoother than anything tradable.
- **Split-adjusted prices understate past volatility relative to price level**; past absolute price levels are distorted (relevant for any price-level feature).
- Don't test cash FX and trade futures. **Trade the same data you tested.**
- Synthetic data: block-reshuffled Monte Carlo breaks bull→crash sequences; random series lack fat tails/long runs; kernel-regression synthetic (Wolberg) with checks (fraction same sign). A clever learner can exploit the generator.

## In-sample / out-of-sample
- Split ~50/50: first half, last half, alternating equal blocks, or **alternating random blocks fixed in advance** (different random blocks per strategy). Show daily returns, not cumulative P&L across gaps (cheating).
- OOS typically delivers ~50% of IS performance (IR 2.0 → 1.0 is good). **Once OOS is used, you cannot fix anything** — any change after seeing OOS is feedback → overfitting.
- **Walk-forward (step-forward)**: optimise on a window (e.g. 2 yrs), trade next 6 months, roll. Pitfalls: short windows bias toward fast models and erratic parameter jumps (10 → 50 → 15) → lengthen windows (≈5 yrs); repeated walk-forward runs are themselves feedback → keep a final untouched holdout.

## Search
- Full grid; sequential one-parameter-at-a-time (n₁+n₂+n₃ tests) can miss the joint optimum; **seeded** sequential searches from random starts; steepest ascent for continuous surfaces; GA (Ch 20; 5 reseeds; check whether the top 20 strings cluster); **Monte Carlo sampling** of the parameter space (random combinations analysed as a representative subset, gives the full distribution, not just the max).

## Visualising / choosing
- Plot 1-D curves and 2-D heatmaps/surfaces: want **broad plateaus**, not spikes; erratic maps = no edge. Two profit areas: fast (more trades, costs) vs slow (fewer, bigger, more reliable) — prefer the broad one, usually slower.
- Smooth result maps: PL̄ᵢ = (PLᵢ₋₁ + PLᵢ + PLᵢ₊₁)/3; 2-D: average of 9 neighbours (6 on edges, 4 at corners); pick the best **smoothed** value.
- Standardise: annualise; risk-adjust; subtract standard error (results with 2 trades vs 50 trades are not comparable).
- **Rule changes**: a good change raises the average of *all* tests (or lowers their σ); a change that helps one case and hurts others raises kurtosis of results → overfit.
- **Expect the average of all reasonable tests, not the best.** Adjusted expectation = mean(all tests) − 1σ(all tests) (≈84% chance). Robustness score = % of tests profitable (≥70% good).
- **Sensitivity in n-space**: distance rᵢ² = Σ(paramᵢ − param₀)² from the chosen point; bin tests into concentric shells; performance should decay gracefully outward. A peak surrounded by losses = overfit.
- Review outliers: remove windfall shock profits; study the largest wins and losses; **many large profits and no large losses ⇒ overfit**.
- Multiple-testing: one success among 1000 parameter sets (or among many strategies tried) is not significant — count all tests ever run.
- A system for the S&P should also work on NASDAQ/Dow (natural OOS); single-market advertised systems = curve fit.

## Performance criteria
Information ratio (primary), net profit, number of trades, % profitable (trend 30–40% normal; >60% = frequent small wins), **average profit per trade vs realistic slippage**, max drawdown (erratic; tiny DD = overfit; use average DD over neighbouring tests; capitalise ≈3× max DD), annualised return, **time to recovery**, **time in market** (less is better — only defence vs shocks), **slope of periodic returns** (should be flat; declining = edge decaying).
- Benchmarks; beware survivorship and asymmetric returns (−50% then +50% = −25%).
- Probability of drawdown ≥ D (normal returns, Wolberg): P(DD ≥ D) = (1 − D)^(2μ/σ²) → D at confidence c: 1 − (1 − c)^(σ²/2μ). Example 30%/yr, σ/μ = 9 daily: μ = 1.3^(1/250) − 1 = 0.00105, σ = 0.00945, 2μ/σ² = 23.5 → 5% chance of a ≥12% drawdown.
- Scale to tolerance: 50% return / 20% σ → 2.5% chance of −40% year; halve leverage for 2.5% chance of −20%.

## Costs
Include realistic costs: profitable parameter range narrows sharply as costs rise (NASDAQ MA: profitable 15+ days at zero cost → only 45–75 days at $150). Too-high costs kill everything; measure slippage from actual fills.

## Use the worst results
Persistent losses at short MA periods in noisy equity indices → **fade the fast trend inside the slow trend**: buy when slow MA up and fast MA turns down; exit when slow turns down (better PF, no reversals).

## Retesting / is the model broken?
- Retest after 5–10% new data; parameters should shift only slightly (big jumps → too-short sample or unstable model). Don't invent rules after one bad shock.
- Broken model check: drawdown size/duration vs tested profile; a new system that loses steadily from day 1 to its max DD is suspect.

## Cross-market evidence (1990–2011, 17 futures, 2–80 days, $40 costs)
- SMA, EMA, LWMA, regression slope, N-day breakout: **all profitable on average → trend following works; the market matters more than the method**. Best periods cluster at the long end (often up to the max tested). Breakout & slope fewer trades but high risk. Two-MA crossover worse robustness and lower profit/trade than single trend.
- Non-trending: S&P (2/40 MA tests profitable), CAD, gold (1990s). Robustness ≥70% for 11 of 17 markets.
- Lukac-Brorsen-Irwin: 12 systems × 12 markets, walk-forward 3-yr optimisation: channel breakout, parabolic, MII, dual MA consistent; trade a system only if profitable in ≥50% of markets.
- Old studies (Davis-Thiel 1970, Maxwell, Hochheimer): periods have lengthened over decades as noise increased.

## Price shocks
- Tests can't distinguish skill from windfall shock profits. Removing days with range > 5× ATR₁₀ consistently improved S&P MA results → shocks hurt on average. If a backtest profits from >50% of shocks, **profits and risk are both wrong** → reverse the 1-day shock P&L. Shocks list: range ≥ 3.5× average range.
- Crude 1990–91 (Kuwait): optimisation each time chose the parameter that profited from the last shock and then held the wrong side for the next. Best optimised result = one tuned to one move.

## Final checklist (condensed)
1. Sound premise; fully programmable; write expected results; be critical of good results.
2. Proper tools (no look-ahead), lots of varied data, IS/OOS split, sensible ranges, ordered parameters, geometric spacing, success criteria defined, visualise.
3. Verify calculations by hand; enough trades; most parameter sets profitable; rule changes improve averages.
4. Final values from a broad stable area (not the peak); profits spread evenly over time; check shock dependence; scale risk; prefer less time in market; validate OOS (or on similar market).
5. Trade exactly the tested rules and data; monitor slippage and live vs expected profile.
"Begin simply, increase complexity slowly, and stop as soon as possible."

## Takeaways for NSE project (protocol)
- Freeze a **final holdout (Apr 2025+)** never used for any decision; walk-forward (expanding or ≥3–5-year windows) inside 2015–Mar 2025 for model/parameter selection.
- Pre-register each strategy: premise, parameter ranges (geometric), expected trades/win rate, costs.
- Report: distribution over all parameter sets (mean, σ, % profitable), smoothed-surface choice, n-space sensitivity, per-year returns & slope, time in market, profit/trade vs ~0.3% Indian round-trip cost, drawdown/recovery.
- Check shock dependence: list NIFTY/stock days with range > 3.5–5× ATR (e.g. Mar 2020, election-result days, Budget days, demonetisation Nov 2016) and recompute results with shock-day P&L neutralised/reversed.
- Cross-sectional robustness: the same rule must work across most NIFTY 100 stocks/sectors, not a few names; use other indices (NIFTY Midcap) as natural OOS.
- Track total number of strategies/feature sets tried (multiple testing — deflate Sharpe accordingly).
