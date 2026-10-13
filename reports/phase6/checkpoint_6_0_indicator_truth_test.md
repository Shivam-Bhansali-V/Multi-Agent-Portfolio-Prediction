# Checkpoint 6.0: indicator truth test (fresh start)

Date: 12 Oct 2026. Script: `scripts/40_indicator_truth_test.py` (copy sent in chat; not yet placed in scripts/).
Data: raw Yahoo daily bars, 100 stocks of today's NIFTY 100 (survivor list), 2015-01-01 to 2025-03-28.
Holdout (April 2025+) cut before any computation. Zero-volume bars dropped. 7 Phase-5 corporate-action
errors repaired (day's return replaced by NIFTY50's, an estimate).
Signal at close t, entry at open t+1, exit close t+h, h = 1/5/10/20/60. Total return.
Independent checker run: no look-ahead, no holdout leak; 3 metric bugs fixed (bear base rate, half-specific
base rates, IC joint ranking) and R:R gap fills made realistic. RSI, one forward return and one label hand-checked.

## Verdict rule
Edge = |t| >= 3 in the signal's direction, both random stock halves right more than their base, mean excess
above 0.35% cost. Weak hint = t >= 2 and halves agree. ~37 signals x 5 horizons tested, so |t| < 3 is treated as luck.

## Result
**0 tradable edges.** Every textbook direction signal is within about +/-3 percentage points of its base rate.

| Group | What the data says |
|---|---|
| Trend structure, SMA, EMA, MACD, OBV (states and crossovers) | Coin flip at every horizon. Best: Close>SMA200 at 10d, +0.12% excess, t 1.4, halves disagree |
| Golden / death cross | Only ~520 events; nothing significant |
| RSI<30, Bollinger lower band (buy dips) | Beat the market 1.5-2.7 pp more often than base, both halves agree, but average excess ~0: small frequent wins, rare big losses |
| RSI>70, Bollinger upper (sell strength) | Lag the market slightly more often, but average excess positive: selling on overbought loses money long-only |
| Breakout above 60d high, new 52-week high | Next 1-5 days 2-4 pp WORSE than base, both halves agree (buying next open after a breakout fades) |
| Volume spike | No reliable signal |
| Low ATR% / low HV20 quintile | +0.05% next-day open-to-close excess, t ~4.2: real but 7x smaller than cost |
| High ATR% / HV20 quintile | +1.5-2.5% at 60d, t ~2, but halves disagree (few stocks drive it) |
| Low correlation to NIFTY quintile | +2.0% excess at 60d, t 2.5, both halves agree: best weak hint |
| 12-1 momentum (reference) | +1.7% at 60d, t 1.9, both halves agree: weak hint, matches Phase 5 |
| 10-day 2xATR/1xATR label | Base Up 27.6% / Down 56.6% / Side 15.7%; no signal moves P(Up) by more than ~3 pp |

## Risk indicators do their real job
Rank correlation with their own future value: Beta250 0.70, correlation 0.66, ATR% 0.58, HV20 0.48;
India VIX vs NIFTY next-20d vol 0.67 (vs next-20d return only 0.12). Use for sizing and stops, not direction.

## Reward-to-risk (1xATR stop, kxATR target, 20 days)
Win rate settles just above break-even for every k; only 1:3 is positive after cost (+0.02%/trade). R:R
changes win rate, not edge.

## Not tested (no data)
All 10 fundamentals (need point-in-time quarterly results with announcement dates), per-stock IV and
put/call (NSE F&O bhavcopy, as a signal only), short interest (no Indian daily disclosure; SLB proxy),
bid-ask (estimable from High/Low), Level 2 (tick feed). Position size is arithmetic, not a predictor.

## Recommendation
Stop using single textbook indicators as direction predictors. Carry forward only: 12-1 momentum and
low-correlation (weak hints, 20-60 day hold), volatility/beta/correlation as risk inputs. Next data to add:
point-in-time fundamentals, since that family is completely untested.
