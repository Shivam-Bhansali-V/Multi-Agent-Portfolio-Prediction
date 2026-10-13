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
- Feature correlation limit: **0.6** (confirmed by user 8 Oct 2026, via AskUserQuestion -- supersedes the earlier proposed 0.7). At checkpoint 3.4 the user also chose to keep all cluster members for now rather than drop redundant features on correlation alone; the drop decision is deferred to Phase 4 feature importance.
- Proposed, not yet confirmed by user: combined-setup minimum 100 cases across 30+ stocks.

## Base paper
Kotekar, Mohan, Kolukuluri, "Can News Sentiment Improve Deep Learning Models for Nifty 50 Index Forecasting?", IEEE Access vol. 14, 2026, DOI 10.1109/ACCESS.2025.3644013.
- Only page 1 has been read. Full PDF still needed in `docs/papers/`.
- Their task: next-day Nifty 50 return sign. Ours is different, so two comparisons are planned: our system on their task, and their models rebuilt in our backtest.

## Status
- Phase 0: research done; 0.1 and 0.3 approved by user. Open item: full base paper not yet read.
- Phase 1.1: `scripts/01_download_prices.py` written, logic tested with fake data only. **Not yet run against real Yahoo.** Launcher: `run_01_download.bat` (untested on Windows).
- **Pilot symbols swapped 8 Oct 2026** (user decision): `BAJAJFINSV, VEDL, IDEA, ADANIENT` -> `HDFCBANK, TATASTEEL, BHARTIARTL, ULTRACEMCO`. The 4 removed symbols were flagged in the Phase 1.3 universe check with unresolved corporate-action adjustment problems (BAJAJFINSV 1 unexplained move; VEDL `APPROX_RATIO` on 96% of rows; IDEA 33 unexplained moves; ADANIENT 17). The 4 replacements are confirmed clean (no `exclude_reason`, `AdjQuality`=OK). Current pilot set: `TCS, RELIANCE, HDFCBANK, ITC, SIEMENS, TATASTEEL, BHARTIARTL, ULTRACEMCO` (see `scripts/04_backtest.py:PILOT_SYMBOLS`). All Phase 2/3 checkpoints below are the re-run, corrected numbers on this set -- any earlier report mentioning the old 8 is stale.
- Full NIFTY-100 clean price data (`data/clean/*.csv`, real Yahoo data through 2026-10-07) already exists on the user's PC for all 103 symbols -- it just wasn't synced into this sandbox until the swap needed it. **CLAUDE.md's earlier "Phase 1.1 not yet run against real Yahoo" status line was stale/wrong** and is corrected here: the full-universe download clearly already ran in some prior session (evidenced by `reports/phase1/checkpoint_1_3_universe.csv` covering all 103 symbols with real recent dates). What has NOT been verified: whether `scripts/01_download_prices.py`/`02a_build_corp_actions.py` (missing from this sandbox, PC-only) are the actual scripts that produced this, or something else was used. Not chased further since it wasn't blocking the 8-symbol work.
- Phase 2 (backtest engine, purged walk-forward splits, baselines): done and verified on the corrected 8. 51/51 + 256/256 + 22/22 checks passing. **NIFTY100 buy-and-hold (dev window, after costs) Sharpe 1.02 is the bar to beat** (changed from the old pilot set's 0.90 -- the flagged-adjustment symbols were apparently understating it).
- Phase 3.1-3.3 (indicator families -- momentum, trend, volatility, volume): done on the corrected 8. TA-Lib installed cleanly (pip wheel). 232/232 checks passing. **Nothing beats the new Sharpe-1.02 bar standalone** (closest: `vol_vwpm20` 0.76, `trend_ema_20_50` 0.87 -- both below buy-and-hold now, unlike on the old flagged pilot set where `trend_ema_20_50` had appeared to beat 0.90 at 1.04). Momentum (mean-reversion) family remains weak across the board.
- Phase 3.4 (correlation clustering): done, confirmed. Threshold 0.6; same 2 redundant clusters as before the swap (`vote_rsi14`/`vote_kc_breakout`; `vote_cci20`/`vote_stoch`/`vote_willr14`); nothing dropped, per user's "keep all" choice, deferred to Phase 4.
- **Phase 3.5 (add-on test + freeze): DONE, 44/44 checks passing.** Frozen feature set = 35 features (22 continuous + 13 vote columns) across the 4 families, written to `data/features/<symbol>.csv` for the corrected 8 pilot symbols (dev window only, holdout still sealed). Manifest at `reports/phase3/checkpoint_3_5_feature_manifest.csv`. **Phase 3 is closed.**
- Next: Phase 4 (the stacking model) can start on the frozen 8-symbol feature tables. Scaling to the full NIFTY 100 later means re-deriving Phase 2/3 for whichever symbols get added, and resolving the ~70 non-clean symbols' adjustment flags first.

## Known open risks
- Historical NIFTY 100 constituents not found yet (survivorship bias until solved).
- Yahoo codes `^CNX100` and `^INDIAVIX` unverified.
- News history depth unknown.
- Yahoo has no delivery percentage; NSE daily files needed (jugaad-data, not yet run).
- Only 32 of 103 NIFTY 100 symbols pass the Phase 1.3 corporate-action check cleanly (`reports/phase1/checkpoint_1_3_universe.csv`); the other ~70 (including the 4 swapped out of the pilot set below) have unresolved adjustment issues and have NOT been investigated for whether the flagged moves are real unhandled corporate actions or data errors. This matters whenever the pilot set or the eventual full-universe run draws from outside the clean-32.
