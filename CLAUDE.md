# Market Prediction Model: project state and rules

Read `docs/Phase0_Report.md` and `docs/Stock_MultiAgent_Phase_Plan.pdf` before doing anything.

## Rules set by the user
- **Never state anything unverified as fact.** If something could not be checked, say what the problem is. Label assumptions as assumptions.
- **Ask before deciding** on any approval point listed in the plan PDF (base paper, families/setups kept, news sources, risk limits, any spec change).
- **Gate rule:** no checkpoint moves forward until its pass check passes. Each checkpoint saves a short report under `reports/`.
- User prefers short, action-first answers with one clear recommendation.
- Never copy code or indicator settings from the old `Multi_Agent` folder as-is; it is an archive only.

## Goal
Predict Up / Sideways / Down over the next 10 trading days for NSE stocks, with technical, sector, news and risk agents fused by a stacking model. For a final-year project and a journal paper. Target: beat the base paper on accuracy and/or alpha after costs. No promise that it will; report honestly.

## Frozen spec (approved 7 Oct 2026)
- Universe: NIFTY 100. History: Jan 2015 to date.
- Final holdout: April 2025 onward, opened once in Phase 9. Development: Jan 2015 to Mar 2025, walk-forward.
- Daily bars. Labels: target 2x ATR = Up, stop 1x ATR = Down, 10-day time-out = Sideways.
- Entry at next day's open; no fill on price-band-locked days. Long or cash only.
- Cost: 0.35% per round trip (0.25% charges verified from Zerodha's page + 0.10% slippage, which is an assumption).
- Risk: 1% of capital per trade.
- Proposed, not yet confirmed by user: combined-setup minimum 100 cases across 30+ stocks; feature correlation limit 0.7.

## Base paper
Kotekar, Mohan, Kolukuluri, "Can News Sentiment Improve Deep Learning Models for Nifty 50 Index Forecasting?", IEEE Access vol. 14, 2026, DOI 10.1109/ACCESS.2025.3644013.
- Only page 1 has been read. Full PDF still needed in `docs/papers/`.
- Their task: next-day Nifty 50 return sign. Ours is different, so two comparisons are planned: our system on their task, and their models rebuilt in our backtest.

## Status
- Phase 0: research done; 0.1 and 0.3 approved by user. Open item: full base paper not yet read.
- Phase 1.1: `scripts/01_download_prices.py` written, logic tested with fake data only. **Not yet run against real Yahoo.** Launcher: `run_01_download.bat` (untested on Windows).
- Next: run 1.1, check `reports/phase1/01_download_log.csv`, then 1.2 (split/bonus adjustment), 1.3 (sector map; the NSE list has an Industry column), 1.4.

## Known open risks
- Historical NIFTY 100 constituents not found yet (survivorship bias until solved).
- Yahoo codes `^CNX100` and `^INDIAVIX` unverified.
- News history depth unknown.
- Yahoo has no delivery percentage; NSE daily files needed (jugaad-data, not yet run).
