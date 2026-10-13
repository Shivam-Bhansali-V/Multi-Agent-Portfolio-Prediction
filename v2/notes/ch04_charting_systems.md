# Ch 4 — Charting Systems and Techniques (pp. 151–180)

Theme: classic chart ideas that **can be automated**. Occam's razor — what looks unsophisticated may be the key.

## Dunnigan
- Swing definition: downswing when today's high AND low are both below those of the highest day of prior upswing (inside/outside days don't change swing direction).
- Five preliminary buy patterns: (1) test of bottom within x%, (2) closing-price reversal (new swing low then higher close), (3) narrow range (< ½ largest range of the swing), (4) inside day, (5) breakout above top. Signal = 2 of first 4 + a **thrust** next day (thrust = substantial move in fixed time; modern: measure vs σ of daily changes or ATR).
- Repeat signals (re-entries after the trend is established: test of bottom + inside day; closing reversal + inside day) are the most reliable part (smaller profit, higher reliability).
- **One-Way Formula**: thrust = gap day (low > prior high) is only a preliminary; confirmation = double/ascending bottom then another up-thrust → enters on pullbacks within trend.
- Ruggiero's simplified Dunnigan trend: uptrend = two consecutive days of higher highs AND higher lows, confirmed by price above the high of the current downtrend. Simple, performs like complex methods.
- Square-root theory: moves in units of √price (81 → 64 or 100). Esoteric.

## Nofri Congestion-Phase (mean reversion in ranges)
- Range top = a high followed by 2 lower closes; bottom = low followed by 2 higher closes; need both. New high/low cancels.
- Rule: inside the range, after **2 consecutive closes in the same direction, take the opposite position on close of day 2, exit on close of day 3** (third-day reversal). Keep re-entering until a 1-day profit or price leaves the range.
- Filters: after a "large move" (10-day |net change| > 2× its historical average) wait 10 days; after a false breakout (back inside within 2 days) wait 7 days. Near-unchanged days count as one.
- Rare non-trend strategy; worked long but hurt in 2008 volatility.

## Outside day with outside close (Arnold)
Buy close of an outside day closing above prior high (sell: below prior low), stop at other extreme, exit 3 days later. Worked in 1970s–early 80s; **since mid-80s the reverse (fade) works better** → markets became noisier. Lesson: patterns decay/invert; filter out WR days after very narrow days.

## Inside-day 3-bar (Prathap)
Cₜ₋₂ > Cₜ₋₃, then inside day (Hₜ₋₁<Hₜ₋₂, Lₜ₋₁>Lₜ₋₂), then Cₜ > Cₜ₋₁ → continuation up (mirror for down).

## Pivot points (as swings)
High/low with N bars each side; no minimum retracement needed but adds lag N. Best use = **trend following: buy on break above last pivot high, sell below last pivot low**. N=10–20 behaves like a macrotrend system.

## Action & reaction / retracements
- 100% retracement = reason for the move gone (most important level); 50% next; also 1/3, 2/3, 1/4, 3/4 (Tubbs, Schabacker, Angas, Dunnigan), Gann ½,¼,⅛, Fibonacci 0.382/0.618, 1.618.
- Fibonacci ratio Fₙ₊₁/Fₙ → 1.618; inverse 0.618; 1−0.618 = 0.382.
- So many candidate levels → price will stop at *some* level by chance. Large, liquid markets (indices) conform better than single stocks. Use a 10–15% tolerance zone around targets.
- Entering on a retracement only after confirmation (slowing price, falling volatility/volume at the level); exit immediately on new low with rising volume.
- **Tubbs' Law of Proportion**: reactions are ½, ⅔, ¾ of prior move (and of the move before it); confluence with major support = most likely level.
- **Trident**: next wave in trend direction = length of previous same-direction wave, added to end of reaction. Enter after 25% of expected move, exit 25% before target; if midpoint not reached → trend suspect; reversal of 25% of last reaction = trailing stop. Its Martingale sizing → ruin.
- DeMark: measure retracement from the highest point since price last traded at the current low; ratios 0.382, 0.5, 0.618, 1.382, 1.618, 2.236, 2.618.
- **Round numbers**: orders cluster at even numbers (NY Fed study). Place breakout orders slightly ahead (sell at 60.25 not 60).

## Channel breakout (automated)
1. Swing/pivot points; trendline through last 2 (or regression through last 3–5) swing lows; parallel line through highest high.
2. **Regression channel**: fit Y = aX + b on closes since last swing (X = bar index). B_U = max distance above, B_L = max distance below. Upper = aX+b+B_U, lower = aX+b−B_L. Project one bar ahead (add a). Uptrend (a>0) & close < projected lower → trend down; downtrend & close > projected upper → trend up.
   - Counter-trend scale-in: in a downtrend sell when price comes within 15% (of channel width) of the upper band.
   - Minor channel (smaller swing) inside a major one for entry timing.
- **Moving channel**: M = SMA(n) of (H+L+C)/3, R = SMA(n) of (H−L). U_{t+1} = Mₜ + (Mₜ − Mₜ₋₁) + f·Rₜ/2; L_{t+1} = Mₜ + (Mₜ − Mₜ₋₁) − f·Rₜ/2. Long if p > U, short if p < L. Objective = one band width beyond.

## Commodity Channel Index (Lambert)
TP = (H+L+C)/3; SMA_TP = mean over n; MeanDev = mean |TP − SMA_TP|.
**CCI = (TPₜ − SMA_TPₜ₋₁) / (0.015 × MeanDevₜ₋₁)** (book uses yesterday's average; standard uses today's). 0.015 scales ~70–80% of values to ±100. Mean-reversion use; overbought can persist for weeks → many small wins, rare huge loss.

## Wyckoff
Bar chart + volume (direction & intensity; uses group/sector indices to pick stocks), point-and-figure (extent/targets, event not time), waves (timing). Prefers horizontal congestion areas over triangles/flags.

## DeMark Sequential (counter-trend exhaustion)
- **Setup (buy):** ≥9 consecutive closes < close 4 days earlier.
- **Intersection:** high on/after day 8 > low of any day ≥3 days earlier (orderly, not plunging).
- **Countdown:** count (not necessarily consecutive) days with close < close 2 days ago; at 13 → buy. Cancel if close > highest high of setup, or an opposite setup appears; new buy setup → recycle.
- Entry: on countdown close; or when close > close 4 days ago; or close > high 2 days earlier. Stops: lowest day's low − its true range.
- Typically 24–39 days to form. Single fixed counts (9, 13) → robustness only testable across many unrelated markets.

## Robustness of patterns
Parameterised systems can be tested for neighbourhood stability (longer period → fewer, bigger trades). Fixed one-off patterns cannot → must test across many markets.

## Academic evidence — Lo, Mamaysky & Wang (2000)
- Kernel-regression smoothing, then extrema E1..E5 in a 38-day window define H&S (E3 > E1,E5; shoulders within 1.5%; troughs within 1.5%), broadening, triangle, rectangle (tops/bottoms within 0.75%), double top (separated > 22 days).
- US stocks 1962–96: patterns occurred ~3× more often than in random series (behaviour, not chance). All but triangular top had positive 3-day returns; 5 statistically significant (H&S top, broadening bottom, rectangle top/bottom, double top). Rising volume generally improved results.

## Bulkowski rankings
Best bullish: upward breakout of rectangle top, falling wedge, ascending triangle, double bottom, symmetric triangle after downtrend (breaks up reliably!). Best bearish: descending scallops, down-break of symmetric triangle in downtrend, broadening top, right-angled descending broadening, broadening bottom. Symmetric triangle most dependable either direction.

## Takeaways for NSE project
- Programmable candidates to test: pivot-point breakout (N = 3, 5, 10, 20), Nofri third-day reversal inside defined ranges, outside-day fade, 3-bar inside continuation, CCI mean reversion, DeMark setup/countdown, Lo-Mamaysky-Wang extrema patterns via kernel smoothing (scikit/statsmodels).
- Patterns can invert over decades → check 2015–19 vs 2020+ separately (consistent with our "latest trend decides" rule).
