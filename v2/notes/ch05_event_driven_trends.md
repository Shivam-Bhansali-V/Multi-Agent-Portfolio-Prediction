# Ch 5 — Event-Driven Trends (pp. 181–234)

Event-driven = **ignore time, react only to price level** (new highs/lows, swings). Key property: **no action while prices move sideways inside the old range** (no "agenda" like a moving average that requires prices to keep moving). Robust, immediate response to news/shocks, but **higher risk per trade** (stop is the opposite swing/extreme, can be far).

## Swing charts
- Swing = move ≥ swing filter (points or % of price). Filter sets sensitivity.
- Classic 2-day construction: in an upswing, first test new high (extend, ignore low); else if swingHigh − todayLow ≥ filter → new downswing column. Mirror for downswing. Outside day → continue current direction (be consistent). Inside day → ignore.
- **Use % filter** (MSVₜ = p × price) for robustness across price levels/splits; use **yesterday's MSV** (no lookahead).
- Trading rules: conservative = buy when current upswing exceeds previous upswing high (sell below previous downswing low). Active = buy as soon as an upswing is recognised (reversal ≥ filter).
- Risk = distance from entry to the reverse signal level.

## Livermore
Two filters: swing filter and penetration filter (≈ ½ swing). Trade only with major trend (higher highs & higher lows). Add on each new penetration in trend direction; stop at penetration beyond prior pivot. Failed reversal: first penetration exits; second needed to confirm new trend; re-enter old trend if confirmation fails. "Easier to re-enter an old trend than establish a new one."

## Keltner Minor Trend Rule
Minor trend up when price trades above the most recent (daily) high; down when below most recent low; always reverse. Basis of N-day breakouts.

## Pivot points
High/low with k bars each side; 5-day pivot → 3-day lag.

## Wilder Swing Index
SIₜ = 50 × [ (Cₜ − Cₜ₋₁) + 0.5(Cₜ − Oₜ) + 0.25(Cₜ₋₁ − Oₜ₋₁) ] / R × K / M
- K = max(|Hₜ−Cₜ₋₁|, |Lₜ−Cₜ₋₁|); M = limit move (now: any constant larger than normal daily move, e.g. 100 — only scales).
- R depends on which is largest: (a) |H−C₋₁| → R = |H−C₋₁| − 0.5|L−C₋₁| + 0.25|C₋₁−O₋₁|; (b) |L−C₋₁| → R = |L−C₋₁| − 0.5|H−C₋₁| + 0.25|C₋₁−O₋₁|; (c) H−L → R = (H−L) + 0.25|C₋₁−O₋₁|. (Wilder's original uses + 0.5 for the second term; check implementation.)
- ASI = cumulative SI used as a price substitute; HSP/LSP = ASI local max/min (needs next day). Buy when ASI crosses above HSP; SAR at latest LSP; trailing SAR 60 ASI points.
- Five bullish components: close>prior close, close>open, high>prior close, low>prior close, prior close>prior open.

## Point-and-figure (P&F)
- Columns of X (up) and O (down); box size + reversal (traditional 3 boxes). **Net reversal = box × boxes** is what matters; smaller box with more boxes captures more continuation (preferred).
- Daily rule: test continuation first (high in X column), then reversal.
- Signals: buy when X column exceeds previous X column by 1 box; sell when O column below previous O. 45° trendlines as filter (only trade with trend). Davis study: best buy = ascending triple top, best sell = triple-bottom breakdown.
- Studies: 1960–69 53% winners, avg 50 days; 1973–74 40% winners, 12.4 days (more volatile markets → shorter).
- **Fixed box sizes fail across markets/time**; test 2000–2010: trending markets (rates, EUR) profit at all sizes, **equity indices consistently lose** with fixed % boxes.
- **Variable boxes: box = k × ATR(50)** gave far more uniform results across EUR, S&P, gold (clustered profits, similar trade counts) than % of price. Best: model the true price–volatility relationship (nonlinear; e.g. crude vol ≈7% at $20, ≈50% at $140).
- Limited-risk entries: buy pullback after signal to acceptable risk level (stop stays at logical P&F reversal point); enter on second upswing (trailing buy 4 boxes above low) — avoids whipsaw but may miss runaway moves; require increasing momentum (higher highs/lows by extra boxes). **Don't put an arbitrary tight stop right after a breakout — it has no logical basis.**
- Plotting reversal first on outside days → earlier exits, usually better (unless reversal small and wide days frequent).
- Trade selection: take only trades with reward/risk ≥ 2 (objective from counts, risk = reversal).
- **Horizontal count:** HU = lowest box of base + W × R (W = columns in base excluding breakout, R = reversal value). HD = top − W × R.
- **Vertical count:** V_up = lowest box + (boxes in first reversal × reversal boxes); V_down mirror. Often understates.
- Taking windfall profits: trailing 3-box reversal stop after ≥10-box move; generally doesn't raise profit but may improve reward/risk; a system should not depend on one huge trade.
- Splits/stock dividends: divide boxes by multiplication factor (2:1 → 2.0, 3:2 → 1.5, 10% div → 1.1).

## N-day breakout (Donchian channel)
- Buy when high > highest high of past N days; sell when low < lowest low (always in). Conservative: use close.
- N < 5 → not really event-driven (needs continuous new highs). Larger N → bigger risk per trade.
- **Donchian 4-week rule** (20-day) — long-lived; volatile markets dominate results unless positions are **risk-normalised**.
- Adaptive N: Nₜ = N_I × V_normal / V_current (higher vol → shorter N).
- Optimisation crude oil 10–100 days: profitable almost everywhere, but **best N 75 (1991–2000), 15 (2001–10), 100 (combined)** → best parameter unstable; prefer robust region. Table: best N jumps 10↔95 across futures and stocks; % profitable tests varies (gold 21%, EUR 100%).
- Weekly price channel (Friday closes vs N-week high/low closes): smoother, fewer false signals, higher risk. Use true weekly bars (holidays shift last day).
- Stridsman Dynamic Breakout: stops placed a day ahead at k × σ; trades separate into quick stop-outs vs long holds.
- Costs: compute returns per share/contract to check costs are covered.
- **Donchian 40/20**: enter on 40-day breakout, exit on 20-day opposite breakout.

## Turtles
- S1: enter 20-day breakout, exit 10-day opposite; skip if previous S1 signal was a winner (unless prior loss ≥ 2L). S2: 55-day entry / 20-day exit, no filter.
- L (N) = Wilder-smoothed 20-day ATR: Lₜ = (19·Lₜ₋₁ + TRₜ)/20 × point value.
- Stop 2L from entry; unit size = 1% equity / (L × point value) (volatility parity).
- Pyramiding: add a unit every +½L–1L, max 4–5 units, stops raised to 2L from latest entry; limits: 4 units per market, 6 closely correlated, 10 loosely, 12 net directional.
- Portfolio: each 10% DD from peak → cut size 20%.
- Copper 1980–2010: slow S2 (55/20) steady profits; fast S1 profitable only early 1980s → fast breakouts decayed.

## Takeaways for NSE project
- Test N-day breakout (close-based) on NIFTY 100 with N ∈ {10…100}; look for a **broad profitable plateau**, not the single best N; compare 2015–19 vs 2020+.
- Size by ATR (Turtle unit) — equalises risk across stocks of different volatility.
- Swing filters and P&F boxes should be ATR-based, not fixed.
- Expect equity indices/large caps to be noisy → breakout on daily data may underperform; validate on our data.
