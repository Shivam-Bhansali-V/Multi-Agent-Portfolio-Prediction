# Ch 14 — Behavioral Techniques (pp. 617–684)

## News and expectations
- Markets price **expectations**; the reaction is to the *surprise*, not the news. Klein–Prestbo style model:
  **ΔPrice = a·(Actual − Expected) + b·(Revision − Previous)** — both the surprise and the revision of the prior figure matter.
- Impact of news decays fast; book's rule of thumb: effect ∝ 1/T² (T = time since release) → most of the move is in the first minutes/hours/day.
- "Buy the rumour, sell the fact": anticipated good news is already in price; release often marks the end of the move.
- Media coverage as a **contrary indicator**: magazine covers / front-page headlines appear near the end of a move (crowd fully committed).

## Event (price-shock) trading
- Identify a shock with a **volatility ratio**: VR = TrueRangeₜ / ATR(60) measured with a lag (e.g. ATR ending 30 days earlier so the shock doesn't inflate its own baseline). VR > 2–3 ⇒ shock.
- **Warwick rules**: on a scheduled-report day, if close is in the top 20% of the day's range and history shows continuation after such days → buy at close, hold a fixed number of days, protective stop. Mirror for bottom 20%.
- Larson (corn reports): 81% of the report-day move direction held on the day; only ~8% reversal within 4 days → follow-through dominates.
- Unemployment-report surprise → S&P +4.5% over the following 27 days (one study; directional drift after macro surprise).
- **Ruggiero report-day trade**: on report day if a 1-day stochastic (close position in day's range) < 0.5 → buy next open, hold 3 days. (Weak close on report day = temporary overreaction.)
- **Raschke**: fade the initial spike of a report if it fails to extend in the first bars.
- Shock studies on S&P: large upward shocks (> 30 pts at the time) were followed by declines on average; but outcome depends on **where the close sits** in the day's range: close in top/bottom 20% → continuation more likely; close mid-range → reversal more likely.
- Lesson: shocks are where the largest profits and losses occur; a system must either exit before scheduled events or have a tested rule for them. Event risk is unforecastable in size → size positions with it in mind.

## Commitments of Traders (COT)
- Three groups: commercials (hedgers) — usually **right at extremes**; large speculators (funds) — trend followers, right in trends, wrong at turns; small speculators — usually wrong.
- **COT Index** = stochastic of net long position: 100·(Netₜ − min Net)/(max Net − min Net) over 1.5–4 years (Briese 3 yrs). > 80–90 = commercials extremely long (bullish), < 10–20 bearish.
- Ruggiero rules: buy when commercial index (lag 1 week, report is delayed) > 30 and small-spec index < 50; another: commercials > 80 **and** price lower than 4 weeks ago (buying weakness while hedgers accumulate) → buy; exit when index < 40.
- Data delay (Tuesday positions, Friday release) must be modelled.

## Contrary opinion / sentiment
- Bullish Consensus (Hadady): % of advisors bullish; neutral ~55%; extremes ~90% (sell) and ~20% (buy). Needs price confirmation — extreme sentiment can persist in strong trends.
- Put/call ratio: smooth (e.g. 10–20 day MA); high P/C = fear = bullish contrarian.
- **Dogs of the Dow**: buy the 10 highest-yield Dow stocks yearly (value + mean reversion).
- Insider activity: big-block insider selling more informative than routine; clusters matter.
- Contrary only works at **extremes** and with confirmation; the crowd is right during the trend.

## Fibonacci and ratios
- Fₙ = Fₙ₋₁ + Fₙ₋₂; ratio → φ = 1.618 (and 0.618, 0.382, 0.236, 2.618). Lucas numbers 2,1,3,4,7,11… same limit.
- Retracement levels 38.2/50/61.8% used as targets/entries. Self-fulfilling at best; with enough ratios, some level always "works" → **untestable unless pre-specified**.

## Elliott Wave
- 5-wave impulse (1–5) + 3-wave correction (A–B–C); wave 3 usually longest, never shortest; wave 4 doesn't overlap wave 1; nested degrees.
- Subjective counting → **Ruggiero programmable version, Elliott Wave Oscillator**: EWO = SMA₅(mid) − SMA₃₅(mid), mid = (H+L)/2.
  - New n-period high in price with EWO at new high ⇒ wave 3 in progress.
  - Wave 4 when EWO pulls back toward 0 (trigger ≈ 0.35 retracement of EWO peak); wave 5 when price makes a new high on lower EWO (divergence).
  - Trade: buy wave 3 and wave 5 entries; exit when EWO < 0. Best trend period for EURUSD ≈ 40.
- **Fischer (Golden Section Compass)**: time goals Tᵢ₊₁ = Lᵢ + 1.618·(Lᵢ − Lᵢ₋₁) (L = dates of swing points); price targets wave 3 = 1.618 × wave 1, wave 5 = 0.618 × wave 1 (from wave-4 low). Entry: after time goal, on close > 5-day high.

## Gann, astrology, lunar
- Gann angles (1×1 = one price unit per time unit; 1×2, 2×1…), squares of price/time. Depends on chart scaling → arbitrary.
- Moon-phase dates (Meeus): JDE = 2451550.09765 + 29.530588853·k + small corrections (k = lunation number). Some studies report weaker returns around full moon — **no mechanism, weak evidence; low priority**.

## Book's message
Behavioral methods capture real crowd effects (overreaction, herding, extremes), but most need **programmable, objective rules** to be testable. Prefer those with measurable inputs (surprise, sentiment index, positioning) and clear timing; treat the rest as narrative.

## Takeaways for NSE project
- **Shock/event features**: VR = TR/ATR(60, lagged), close position in day's range on shock days, gap size; test follow-through vs reversal at 1–20 day horizons on NIFTY 100 (separate up/down shocks).
- **Results-day effect** (quarterly earnings): reaction day close-location, gap, volume spike → post-earnings drift test. Need an earnings-date calendar (NSE corporate announcements).
- **COT analogue**: NSE publishes FII/DII cash flows daily and participant-wise OI (F&O) — usable as *features* even though we trade cash only; build a "flow index" = stochastic of cumulative FII net flow over 1–3 years.
- Sentiment proxies: India VIX level/changes, NIFTY put-call ratio (smoothed) as contrarian extremes.
- EWO (SMA5 − SMA35 of mid) is a cheap trend/momentum feature; Fibonacci/Gann/astro — skip (unfalsifiable or no mechanism).
- Exit/avoid rules around scheduled events (RBI policy, Budget, results) — test whether holding through them helps or hurts.
