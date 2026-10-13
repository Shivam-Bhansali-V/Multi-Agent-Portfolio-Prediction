# Ch 23 — Risk Control (pp. 1027–1098)
"Embracing risk is more important than measuring risk." You can move profits and losses around but not eliminate them.

## Price shocks & exposure
- Only defences: (1) **be out of the market as much as possible** (in 40% of time → 60% chance to miss a shock); (2) **deleverage** (200%/yr fully leveraged is wiped by one shock; 20% deleveraged is 10× more likely to survive).
- Mistaking luck (windfall shock profits) for skill → over-leverage (LTCM).

## Utility & preferences
Bernoulli diminishing marginal utility → most investors risk-averse. Expected utility P = Σwᵢpᵢ (e.g. 0.6×4 − 0.4×1.5 = 1.8), but perceived preference isn't linear in reward. Efficient frontier: max return per risk; tangency from risk-free rate = max Sharpe point.

## Common-sense rules
Risk small % per trade (never > 5%); know exits in advance; large profits ⇒ large risk (size down); exit quickly when wrong; **don't meet margin calls** (signal to review); liquidate the worst position first; be consistent with your style (trend follower: let profits run); match profile to your risk tolerance; plan for contingencies; don't be undercapitalised.

## Liquidity cost (Ginter–Ritchie)
C = K·Q·V/(L_c·L_o) — cost ∝ order size × volatility / (total and specific volume); K larger when trading with the move. Prefer fewer trades in liquid markets.

## Performance & risk measures
- Prefer: larger profit/trade, upward surges vs downward, short recovery, less time in market. Always compare to a benchmark (60/40).
- **Sharpe** = (E − I)/σ (annualised); **information ratio** omits I (include I when interest income is in returns). Doesn't see order of losses or penalises upside surges. Monthly data looks smoother than daily.
- **Treynor** = (AROR − I)/β.
- **AMR (Schwager)**: average of drawdowns from the max closed-out equity on all non-new-high days.
- **Calmar** = AROR / MaxDD. Max DD will be exceeded in the future.
- **Sortino** = (AROR − MAR)/σ(drawdowns from peak) (downside only).
- **Ulcer Index** = √(ΣDᵢ²/n), Dᵢ = % below running peak (0 at new highs).
- **Drawdown probability DP** = stdev of non-zero drawdowns (16% chance of exceeding DP, 2.5% of 2·DP); **semivariance** vs regression line of equity; ratios AROR/DP, AROR/SV satisfy all three criteria (profits, order of losses, no penalty for upside).
- More risk if: small samples, few historical drawdowns, few sectors.
- Annualised vol = σ(daily r)·√252.
- **VaR (variance–covariance)**: VaR = √(a² + b² + 2ρab) for two positions' risks a, b. Book example: EURUSD 1.25M×0.932% = 11,650; Bund 1.25M×0.998% = 12,475; ρ = −0.27 → **14,590** (book prints 17,068, which is the ρ = 0 value). General: CI·√P·√(wᵀΣw) with annualised σ.
- Lognormal VaR (Kritzman–Rich): P(loss ≥ L at T) = N[(ln(1+L) − μT)/(σ√T)]; VaR = −(e^{μT − Zσ√T} − 1)·W. Within-horizon loss probability is higher than end-of-horizon.
- **Historical VaR**: apply today's positions to last 252 days of returns → R̄ − 2.33·s (99%) (or empirical percentile).
- VaR fails when needed most → **stress tests** (shock periods, all-correlated 2–3σ reversals). Returns kurtosis can be ~25 (normal 3).
- Hindenburg Omen: NYSE new highs and new lows both ≥ 2.8% of issues, NYSE > 50 days ago, McClellan < 0, highs ≤ 2× lows, 3 consecutive days → crash risk within 30 days (~25% hit rate).
- Breakout trade risk at entry = HHₙ − LLₙ (large).
- Risk-adjust before comparing: scale A's returns by σ_B/σ_A (15%/10% vs 25%/16% → 24% vs 25%).
- **Stability**: slope through cumulative returns (24,18,20,15,19 → avg 19.2%, slope 17.9% — declining edge).
- 1% monthly chance of a 50% loss ⇒ ~50% chance within ~50–70 months; small samples → large error in all these stats.
- "It's not the markets, it's the money": in panics correlations → 1.

## Leverage, margin, target volatility
- Leverage magnifies; brokers require more than exchange margin; real leverage = exposure / total account.
- **Investment size for a target vol**: Investment = σ_annual($ P&L) / target vol (σ_daily$ × √252 / 0.15). Typical target 15% (aggressive); practical 6–12%. Max-loss limit 50% (or 10% → target vol ≈ 3%).
- Expect losses of 2–2.5σ over time.

## Position sizing
- Equal dollars ≠ equal risk. Three methods: $/price; $/(price·annual vol); **$/(ATR·√252 or ATR × shares)** → pool capital and rescale to fit the budget. ATR sizing on BAC 200-day MA: 27% lower volatility than fixed shares.
- **Equal risk per trade** is the most conservative default; vol-adjusted sizing keeps portfolio vol stable (otherwise 6% ↔ 25% swings).

## Stops
- Random-walk fact: (frequency stop is hit) × (distance) ≈ constant → a stop must beat randomness to be useful.
- Types: parabolic-style advance, swing high/low, n-day extreme, KAMA, k×ATR, % of price, % of profits (after a trigger), **Kase Dev-stop**: TR over 2 days, ATR & σ of it (20 days daily), DDEV = ATR + f·σ (f = 1, 2.06–2.25, 3.2–3.5) from trade extreme. ISAM: 12×ATR(252).
- Trend systems already cut losses; mean-reversion needs room → stops often hurt MR. Test: bonds MA 10–100 with σ-stop factor 2–10 → almost every stop variant beat no-stop on average (one market).
- Stop on intraday trigger but exit on close (noise); profit targets exit at the intraday spike.
- Gaps make stops slip; proximity risk (clustered stops). Alternative: **reduce size as volatility rises** instead of stops.
- Overlays: % of margin, % of portfolio (1–2.5%), beyond **maximum adverse excursion (MAE)**.

## Profit targets
E ± f·V; essential for short-term/noisy trading, harmful for long-term trends (miss fat tail; must allow re-entry). EUR 60-min: 80-bar trend best without targets; 5-bar trend turned profitable with targets (5.5–9 ATR). Scale out in thirds (floor-trader style).

## Market selection / ranking
- Trend measures over 5/10/20/40 days: r² (> 0.25), net moves, regression slope, ADX (> 20), avg |Δp|.
- **Wilder DMI/ADX**: +DM = Hₜ − Hₜ₋₁, −DM = Lₜ₋₁ − Lₜ (book prints Lₜ − Lₜ₋₁), keep the larger (if positive), else 0; Wilder-smooth DM and TR over 14 (X₁₄ = X₁₄,ₜ₋₁ − X₁₄,ₜ₋₁/14 + Xₜ); +DI = +DM₁₄/TR₁₄, −DI = −DM₁₄/TR₁₄; **DX = 100·|+DI − −DI|/(+DI + −DI)**; ADX = Wilder average of DX; ADXR = (ADX + ADXₜ₋₁₄)/2. Ruggiero: ADX > 25 trending, < 20 consolidating, falling below 45 = consolidation.
- **CSI** = ADXR × ATR₁₄ × [100·V/√M · 1/(150 + C)] — rank markets by expected move per margin $.
- DMI crossover systems: inconsistent across markets/periods (not robust). Colby 2-day DMI on DJIA profitable 1928–2000.
- **Chande trend strength** Sₜ = ln(pₜ/pₜ₋ₙ)/(σ(1-day log returns)·√n) (= t-stat-like normalised return).
- **Kaufman strategy selection by ER**: 65-day average ER vs profit factor of 65-day MA across markets → clear positive relation (low noise markets → trend systems; high noise (equity indices, most stocks, grains) → mean reversion).

## Probability of ruin
- Equal win/loss: R = ((1 − A)/(1 + A))^c, A = P − (1 − P), c = capital units. P = 0.6: (0.8/1.2)^c = **(2/3)^c → 67% (c=1), 44% (c=2)** (book misprints as (1/3)^c → 33%, 11%). With goal G: R = ([(1+A)/(1−A)]^G − 1)/([(1+A)/(1−A)]^{c+G} − 1).
- Unequal (Vince/Griffin, spreadsheet form): Z = pW·W% − pL·L%; A = √((pW·W%)² + (pL·L%)²); P = 0.5(1 + Z/A); **Risk of ruin = ((1 − P)/P)^(MaxRisk/A)**. Check: W 4%, L 2%, pW 0.4 → Z 0.004, A 0.02, P 0.6, MaxRisk 25% → (2/3)^12.5 = 0.6%. Halving capital or slightly smaller avg win raises ruin risk fast.

## Entry and position building (80-day MA tests: bonds, S&P, gold)
- **Averaging in** (5 units spaced 1–5 days): improved all three (noisy S&P most; bonds best at 2-day spacing). Spread entry over a period proportional to the trend's holding period.
- **Wait for a better price** (pullback threshold, max 5-day window then enter anyway): cut trades ~40% (false signals filtered), improved all; window is essential to avoid missing the big trade.
- Timing with RSI(8) < 30 within 5 days after a long signal: similar improvement.
- **Adding on new high profits** (unit every n days, max 5): improved profit factor (futures: profits too); **averaging down** worse except Apple.
- Compounding into the top: largest size at the worst time; +100%/−50% cycles with full reinvestment = zero return; keep size constant in profit phase, rebalance margin/reserves after drawdown stabilises.
- Trading the equity curve (10/60-day MA on system equity): inconsistent; check autocorrelation of returns first; hypothetical equity is too smooth.

## Optimal f / Kelly
- Kelly growth G(f) = P·ln(1 + B·f) + (1 − P)·ln(1 − f); **f* = P − (1 − P)/B** (= [P(B+1) − 1]/B). P = 0.5, B = 2 → 25%.
- Vince optimal f: maximise Π(1 + f·(−Rᵢ)/LargestLoss) over f.
- Over-betting f → eventual ruin; under-betting reduces risk linearly but returns geometrically. f changes with every trade; trade-level f ignores intra-trade drawdowns. Markowitz: E[log r] ≈ μ − σ²/2 → optimal leverage M* = μ/σ². Use these only to **reduce**, not increase, leverage (fractional Kelly).
- Elder's lessons: never average down, never meet margin calls, liquidate worst first. Recovery: required gain = 1/(1 − loss) − 1 (50% loss → 100%).

## Is the system broken? (expected vs actual)
- **Binomial**: P(l losses in n) = C(n,l)·pˡ(1 − p)ⁿ⁻ˡ. p_loss = 2/3, n = 5: P(4 losses) = 5 × 0.1975 × 0.333 = 0.33. Mean n·p, sd √(np(1−p)). 15 trades: 8% chance of ≥ 13 losses → more than that = suspect.
- **χ² test** of observed vs expected win rate: (20−35)²/35 + (80−65)²/65 = 9.89 > 6.64 → significant at 1% (needs adequate sample; sample error 1/√N). Critical values (1 df): 3.84 (5%), 6.64 (1%), 10.83 (0.1%). Runs vs random (8 classes): χ² = 5.47 → not significant. **Yates correction** for small counts: Σ(|O − E| − 0.5)²/E.

## Takeaways for NSE project
- Position sizing: equal-risk (ATR or σ) per stock with a portfolio **target volatility (8–12%)**; cap single-stock weight; pool capital and rescale.
- Report Sharpe, Sortino, Calmar, Ulcer, MaxDD & recovery time, time in market, slope of yearly returns, VaR/CVaR (historical) and stress periods (2015–16 China/devaluation, Nov 2016 demonetisation, 2018 IL&FS, Mar 2020 COVID, 2022).
- Exits: test ATR/Kase-style trailing stops vs time stops vs no stop separately for trend and mean-reversion models; profit targets only for short-horizon MR.
- Entry improvement tests: averaging in over 2–5 days, wait-for-pullback with max window, RSI(8)<30 timing inside a trend.
- Use ER(n) and Chande trend strength to choose trend vs MR per stock/regime.
- Live monitoring: binomial/χ² test of live win rate & drawdown vs backtest profile; stop trading if outside ~95–99% bounds.
- Use fractional Kelly (≤ ¼–½) only as an upper bound on leverage; cash-only (no leverage) fits our scope anyway.
