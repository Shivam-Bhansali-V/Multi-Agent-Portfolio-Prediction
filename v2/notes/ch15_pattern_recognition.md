# Ch 15 — Pattern Recognition (pp. 685–736)

## Idea
Patterns = recurring sequences of price behaviour (time of day, gaps, weekdays, month days, reversal bars). Many are market lore; the computer can test them, but **the number of cases collapses as patterns get longer** → small-sample, data-mined results. Every pattern must be explainable by participant behaviour (fund flows, liquidation before weekends, order flow at the open).

## Projecting daily highs/lows
- **Pivot point**: P = (H+L+C)/3; R1 = 2P − L; S1 = 2P − H; R2 = P − S1 + R1 (= P + (H − L)); S2 = P − (R1 − S1) (= P − (H − L)).
  Example H/L/C 12.50/11.50/11.75 → P 11.917, R1 12.333, S1 11.333, R2 12.917, S2 10.917.
- Symmetric: prior close ± ½·avg(H−L, 14).
- **DeMark**: X = H + L + 2C if C = O; 2H + L + C if C > O; H + 2L + C if C < O. Proj. high = X/2 − L; proj. low = X/2 − H. (Book's "today's open vs previous close" text is inconsistent with the formulas, which use today's close vs today's open.)

## Time of day (intraday)
- Volume U-shape (open highest, close next, midday lowest). Floor traders fade the opening move → early reversal; if it is absorbed, the open direction continues.
- S&P 2000–2011 (30-min bars): most of the daily move happens overnight + first bar; small continuation of (prev close → end of first bar) direction through the day, but behaviour **depends on regime** (bear 2001–02 continuation; bull 2003–07 drift up; 2008 strong continuation; 2009–11 reversal of the opening move). Regimes known only after the fact.
- Gap filter: requiring ≥50 bp gap at end of first bar → rest of day continues modestly in gap direction.
- **Highs/lows timing**: the open is the most likely time of the day's high or low (~2.5× the close, ~8× midday). With ±2% gap, low (for up gaps) overwhelmingly at the open and high more likely at the close. Trade: once an early extreme holds, trade toward the unseen extreme; stop beyond the early extreme. 1995–96 strong bull flattened the U pattern.

## Opening gaps (daily data)
- Gap table: per gap bucket (25 bp), % closing beyond open (continue), between open and prior close, reversing; % crossing prior close; % pulling back from open; % only continuing; % continuing next open.
- Stocks (ABX, XOM, AMZN, LUV): small gaps often cross back through the prior close yet close in the gap direction; **little next-day continuation** (equities are noisy). Futures indices with near-24h trading have few gaps.
- Rate markets (bonds) & EURUSD: small gaps very rarely close against the open → buy an up-gap that dips back below prior close (rates trend). Large down-gaps in bonds/euro tend to reverse the next open (few cases).
- **Reverre gap fade** (GE, Dow stocks): limit buy if open < prev close − 1%, sell if > +1%; exit at the close. Small but consistent profit (~2–3¢/share → costs matter). Gaps ~1% = noise (correct); >2% gaps more structural (bigger P&L variance). Optimised gap size drifts with volatility → use volatility-scaled thresholds.
- **Close-to-close extreme move fade (Reverre)**: largest 20% of daily moves (≈1.28σ) → fade; 70% of corrections by next close, best hold 2 days. 2000–2011: 2–4% moves still profitable; >4% moves lost money (shocks continue).

## Weekday patterns
- Code the week as X/O relative to Friday→Monday direction (X same, O opposite); binary tree of 16 Friday outcomes, ~500 weeks → ~31 cases each by Friday → weak statistics.
- emini S&P: Tuesday reverses Monday 54% ("up Monday, down Tuesday"); other markets differ (BAC, INTC, bonds, gold, wheat each idiosyncratic).
- Adding a **trend filter** (20/50/200-day MA; record only weeks where Mon move agrees with trend) raises probabilities; prefer combinations that improve under all trend lengths (robust) over single high-% cells.
- Trading idea: find cases where a losing day still has >50% chance of recovering by holding (e.g. bonds XO → XOO 55%, XOX → XOXO 57%).

## Weekend patterns
- Friday liquidation, Monday re-entry, new positions after weekend digestion.
- S&P: after an up week, only 37% chance Monday opens higher but 47% chance it closes in the week's direction → buying a lower Monday open profitable. 16 weekday patterns × markets → beware chance results.

## Day of month
- S&P 1982–2011: buying concentrated on **first trading day(s)** of the month (and last days); middle of month weaker. Commodities 2001–11 shifted to buying in last ~4 days (index funds). Strategy: buy ~4 days before month-end, exit end of day 1 of next month. Averages hide large adverse months.

## Reversal patterns (next day)
- Trend continued (H > H₋₁ and C > C₋₁): little bias; downward trend days more consistently continue.
- Reversal day (higher high, lower close): S&P next open 52% lower but close only 43% lower → rally open-to-close; upward reversal day similar → S&P noise + upward bias.
- Outside reversal (H > H₋₁, C < L₋₁): rare; S&P little follow-through, rally by close.
- Conclusion: popular "key reversal" follow-through is **not** reliable in equity indices.

## Computer-based pattern recognition
- Define the *trade profile* you want (e.g. move ≥3% within 20 days with no adverse move > 0.5%); label the 5 days before each such move as buy/sell days; search indicator values (MA direction, RSI, volume change, momentum) that separate labelled days → a classification problem (like regression / ML labelling). Must still check net return and risk.
- Repeated up/down sequences: number of patterns = 2ⁿ (book misprints 3-day = 9, 10-day = 100; correct 8 and 1024) → cases per pattern vanish quickly. Better: **count of ups in a window** (e.g. 15 of 20 up) — far more samples, a "bullishness" quality.
- Stock market: P(up after up) historically ~55%; most markets ~50%.
- AI/heuristics: knowledge base + inference engine; unlimited pattern search = **overfitting at a sophisticated level**.

## Takeaways for NSE project
- **Labelling approach** (trade-profile labels → classifier) is exactly our ML setup; define labels by a realistic trade (target %, horizon, max adverse excursion) rather than raw next-day direction. Use triple-barrier-style labels consistent with our cost model.
- Features: pivot distance (C vs P, R1, S1), DeMark projected range, gap size (open/prev close − 1, vol-scaled), close location in range, gap-filled flag, reversal/outside-day flags, count of up days in last 10/20, day-of-week, trading-day-of-month (first/last 4), pre-expiry.
- Strategy candidates: gap fade 1–2σ on NIFTY 100 stocks (needs open-price execution; long-only → buy down-gaps), extreme 1-day drop fade (2–4% / ~1.3–2σ, hold 1–2 days, skip >4σ shocks), turn-of-month long.
- Statistical discipline: report n per cell; Bonferroni-style caution when scanning 16+ patterns; check patterns hold in both 2015–19 and 2020–24 and under different trend filters.
