# Market Prediction Model — Progress Log

**How to use this file:** paste this whole file (or point Claude at it) at the start of a
new chat. It replaces needing the old conversation's context. Claude: read this file +
`CLAUDE.md` (repo root) first, before doing anything else. Update the "Current state"
section in place after real progress (don't just append to it); add one line to the
"Decision log" for anything the user explicitly decided. Keep this file itself short —
detailed numbers live in the checkpoint CSVs under `reports/`.

Repo root (on the user's PC): `C:\Users\BhansaLi\Desktop\Market Prediction Model\`

## Project goal, stated honestly

Build a model that predicts Up / Sideways / Down over the next 10 trading days for NSE
stocks, well enough to actually trade profitably after real costs — that is the user's
explicit goal, not just an academic exercise. At the same time: **no promise that it
will work.** Every number reported here is a backtest result on historical data, not a
guarantee of future profit. The project's own rule (CLAUDE.md) is to report honestly,
label every assumption, and never state anything unverified as fact. Nothing in this
log should be read as financial advice or a claim that the system is ready to trade
real money — Phase 9 (paper trading) is the first point where that question is even
addressed.

## Current state (as of 8 Oct 2026)

**Phase 5 (12 Oct 2026) -- cleaning v2, ranking model, claim tests, baseline rebuild. Read
`reports/phase5/checkpoint_5_report.md` first; it supersedes the 32-clean-symbol universe
and every earlier performance number. Each stage was reviewed by an independent checker
(`reports/phase5/checker_report_s1..s4.md`).**
- Cleaning: the Phase 1.3 filter wrongly excluded 66 stocks for real moves >= 15%.
  `30_clean_v2.py` repairs only 10 true corporate-action errors, removes 713 stale bars,
  builds total-return prices: **95 usable stocks instead of 32**. Audit finding F03
  (bonuses unadjusted) is false on the real data.
- Honest result (`36_pit_universe.py`, walk-forward, past-only training, costs, daily
  curves): accuracy 50-51.5%; best signal is plain 12-1 momentum at +3.9%/yr over
  equal-weight (90% interval -2.2% to +9.8%); **nothing is statistically significant and
  nothing improves Sharpe.**
- Four measured sources of fake edge: survivor-only list (benchmark 24.6%/yr vs 16.1% for
  a point-in-time top-50 vs 11.6% index; momentum +3.9% becomes -0.5%); training on future
  blocks (+10.5% "significant" vs +3.4% causal); two liquidity features on a survivor
  list; drawdown measured every 20 days (-27% vs -37%).
- **Validation rule from now on:** trained models are scored with past-only training.
  Random hold-out is used for stocks; random time blocks only for untrained signals.
  `32_xs_model.py`'s block-CV numbers for ridge/LightGBM are NOT causal -- do not cite.
- Baseline paper (Iskakov et al. 2026) rebuilt without LSTM: next-day accuracy 50.0-50.5%
  (always-up 51.3%); -2.6% to -5.1%/yr vs equal-weight after costs. Our momentum is ahead
  of it by 4-6.5%/yr but about half of that is monthly vs daily trading, and neither
  beats equal-weight.
- Next: `run_33_download_and_model.bat` (NIFTY 500 pool, point-in-time top 100/200). NOT
  yet run against live Yahoo. A constituent history with dropped companies is still missing.

**Phase 0-3: done.** Phases 0-2 (spec, data, labels, backtest engine, walk-forward
splits, baselines) and Phase 3 (4 indicator families, correlation clustering, frozen
feature set) are complete and checkpoint-verified. Phase 4 (technical model) has just
started.

**Pilot symbol set (confirmed, swapped 8 Oct 2026):**
`TCS, RELIANCE, HDFCBANK, ITC, SIEMENS, TATASTEEL, BHARTIARTL, ULTRACEMCO`
(defined in `scripts/04_backtest.py:PILOT_SYMBOLS` — also duplicated in
`scripts/05_splits.py`, must be kept in sync manually, see Known gaps).
Originally `BAJAJFINSV, VEDL, IDEA, ADANIENT` were in the pilot set instead of
`HDFCBANK, TATASTEEL, BHARTIARTL, ULTRACEMCO` — swapped out because they have
unresolved corporate-action adjustment problems (see `reports/phase1/
checkpoint_1_3_universe.csv`, column `exclude_reason`). Only 32 of 103 NIFTY 100
symbols pass that check cleanly; the current 8 pilot symbols are all in that clean 32.

**The bar to beat (after 0.35%/round-trip costs, dev window 2015-01-01 to 2025-03-31,
equal-weight 8-symbol portfolio):** NIFTY100 buy-and-hold Sharpe **1.02**, CAGR 17.17%.
No single indicator-derived rule (11 tested across momentum/trend/volatility/volume)
beats this standalone — closest are `trend_ema_20_50` (Sharpe 0.87) and `vol_vwpm20`
(0.76). This is why the project is building a stacking model rather than trading one
rule.

**Frozen Phase 3 feature set:** 35 features (22 continuous indicator values + 13
Up/Down/Flat vote columns) per symbol/date, in `data/features/<symbol>.csv` (8 pilot
symbols, dev window only — the April-2025 holdout is sealed and must stay that way
until Phase 9). Manifest: `reports/phase3/checkpoint_3_5_feature_manifest.csv`.
Correlation clustering (checkpoint 3.4, threshold 0.6, user-confirmed) found 2 redundant
clusters but **nothing was dropped** — all 35 features carry into Phase 4, drop
decisions deferred to actual model feature-importance.

**Phase 4 — the real plan, from `docs/Stock_MultiAgent_Phase_Plan.pdf`:**
| # | Checkpoint | Pass check | Status |
|---|---|---|---|
| 4.1 | Logistic regression floor | Beats random | **DONE, 4/4 checks pass** |
| 4.2 | Gradient-boosted trees | Beats 4.1 | **DONE, 3/3 checks pass** |
| 4.3 | Probability calibration | Predicted probability matches observed frequency | **DONE, 4/4 checks pass -- but see flag below, mechanical pass hides a real tradeoff** |
| 4.4 | Shuffled-label test | Accuracy drops to chance | **DONE, 2/2 pass -- but the gate itself had to be corrected, see below** |
| 4.5 | Backtest after costs | Compared with 2.4 baselines | **DONE, reported -- model LOSES to buy-and-hold over the same window, see below** |
| 4.6 | Sequence model (approval point) | Kept only if ablation shows a gain | not started |

Training/testing uses the Phase 2.3 purged walk-forward folds (pooled across all 8
symbols, applied directly in `scripts/15_model_logreg_floor.py` rather than re-reading
`checkpoint_2_3_folds.csv`, which is only a summary, not row-level assignments) — never
a plain random train/test split, since that would leak across the label's 10-day
resolution window.

**Checkpoint 4.1 result (`scripts/15_model_logreg_floor.py`, pooled 8-fold
out-of-sample, 13,870 predictions):** multinomial logistic regression on the 35 frozen
features. Macro-F1 0.335 vs. majority-class-baseline 0.237 — **passes** ("beats
random," gated). Separately, and NOT gated at this checkpoint: **log-loss 1.05 is worse
than a naive class-prior baseline (0.97)** — the model's predicted probabilities are
overconfident/miscalibrated even though its hard predictions carry real signal. Tried
fixing directly (class_weight='balanced', C sweep 0.001-1.0): none beat the prior-null
log-loss without destroying the macro-F1 gain. Flagged for checkpoint 4.3 (calibration)
to address properly (Platt scaling / isotonic), not papered over here.

**Checkpoint 4.2 result (`scripts/16_model_gbt.py`, pooled 8-fold out-of-sample,
13,870 predictions, apples-to-apples with 4.1 — same folds, same features):**
honest story, not just the final number — the FIRST attempt (xgboost, default-ish
hyperparameters: 300 trees, depth 4, lr 0.05, no class weighting) **genuinely
failed** the "beats 4.1" gate: macro-F1 0.3191 vs logreg's 0.3350. A diagnostic
sweep (inline, not kept as a separate script) found plain regularization tuning
(shallower/fewer trees, stronger L2) improved log-loss but made macro-F1 *worse* —
a real precision/calibration tradeoff, not a bug. Adding inverse-class-frequency
`sample_weight` (to directly counter the ~55% "Down"-majority class, which
accuracy-driven boosting underweights the minority classes against) combined with
a lighter tree (100 trees, depth 2, lr 0.05, reg_lambda=5) is what actually
passed: **macro-F1 0.3707** (vs logreg 0.3350, vs the majority baseline 0.2367) —
**passes**. Accuracy is lower than logreg's (0.4017 vs 0.4880) because the
weighting trades overall accuracy for balance across the 3 classes, which is the
point of gating on macro-F1 rather than accuracy. Log-loss (1.0765) is NOT gated
here and is still worse than logreg's (1.0544) and the class-prior baseline
(0.9722) — calibration remains genuinely unresolved for both 4.1 and 4.2, carried
to 4.3 as planned, not fixed by swapping the classifier.

**Checkpoint 4.3 result (`scripts/17_model_calibration.py`) — PASSES mechanically,
but flagging a real cost found underneath, not hiding it behind the pass.** Method:
isotonic calibration (sklearn `CalibratedClassifierCV` + `FrozenEstimator`) fit on a
held-out 20% calibration slice carved out of each fold's own train window (never
touching test), applied to 4.2's XGBoost (weighted) model. Gate = calibrated ECE
(Expected Calibration Error, 10-bin) lower than raw ECE, AND calibrated log-loss no
worse than raw log-loss. Result: ECE 0.0806 → 0.0416 (better), log-loss 1.0841 →
1.0162 (better, though still above the class-prior-null 0.9702) — **both checks
pass.**

**The real finding:** getting there cost a lot of hard-prediction quality.
Macro-F1 on the SAME pooled predictions dropped from 0.3733 (raw) to **0.2540**
(calibrated) — barely above the majority-class baseline (0.2367) and well below
4.2's own officially reported 0.3707. Isotonic calibration, fit one-vs-rest per
class then renormalized, does not have to preserve which class had the highest raw
probability — in this case it visibly pushed predictions toward the majority "Down"
class, improving probability calibration while gutting the model's ability to
flag "Up"/"Sideways" at all. (Side note on why the "raw" number above is 0.3733
rather than 4.2's 0.3707: this script retrains the classifier on 80% of each fold's
train window, holding back 20% for calibration, so it is not training on quite the
same rows as 4.2's own checkpoint — a second, slightly data-starved version of the
same model, not the exact 4.2 model.)

This means: as implemented, the calibrated model is probability-accurate but close
to useless for actually picking which direction to trade — which matters a lot given
the user's explicit instruction to keep sight of actual trading profit, not just
pass checkpoints. **Not resolved yet, flagged for the user rather than silently
picking a path:** before Phase 4.5 (backtest), need to decide whether to (a) use the
RAW/uncalibrated model's class choice (argmax) for the trading signal and the
calibrated probabilities only for confidence filtering/position sizing, never for
picking the class; (b) try a less aggressive calibration method (Platt/sigmoid
instead of isotonic, which is more constrained and may distort the decision boundary
less); or (c) accept the calibrated model's own argmax and the macro-F1 hit. Leaning
toward (a) as the honest default (it's what Phase 4.5's design implies anyway --
calibration exists to make position sizing or confidence thresholds trustworthy, not
to replace the classifier's own decision). This is what was actually built into 4.5
below.

**Checkpoint 4.4 result (`scripts/18_shuffled_label_test.py`) — passes, but the gate
itself was wrong on the first attempt and had to be corrected (same pattern as 4.1's
log-loss over-specification).** First attempt compared shuffled-label macro-F1
against the plain majority-class baseline (0.2367) and that comparison "failed" --
shuffled labels scored ~0.311, nowhere near 0.2367. Reason, found by looking at it
rather than just lowering the bar: 4.2's `sample_weight` (inverse class frequency)
pushes ANY model — even one trained on pure noise — to spread predictions across all
3 classes instead of always guessing the majority, which mechanically raises
macro-F1 above 0.2367 with zero real signal (always-guess-majority gets 0 recall,
0 F1, on two of three classes; a noisy-but-balanced guesser doesn't). So 0.2367 was
the wrong "chance" reference once sample_weight is in the pipeline. Corrected gate:
compare the real model's macro-F1 (0.3707) against THIS exact recipe's own noise
floor (the shuffled-label run itself, 0.3111 averaged over 3 seeds) — gap = **0.0596
macro-F1**, real and reproducible across seeds. **Honest sizing, stated plainly: the
model's real edge over actual chance is modest (~0.06 macro-F1), clearly smaller
than the 0.134 gap against the naive majority baseline that 4.1/4.2 had been
quoting — that naive comparison overstated the edge.** No leak found; the signal is
real but small.

**Checkpoint 4.5 result (`scripts/19_model_backtest.py`) — reported as required, and
the honest news is bad: the model LOSES to simple buy-and-hold over the same
out-of-sample window.** Trading rule built for this: direction from the RAW (not
calibrated) 4.2 model's class choice; a trade only happens when that choice is "Up"
AND the 4.3-calibrated P(Up) clears 0.40 (round-number assumption, not tuned on this
backtest); every other day is explicit cash with a recorded reason (`AVOID_DOWN`,
`NO_PATTERN_SIDEWAYS`, `NO_PATTERN_LOW_CONF`) rather than a silent default — this is
the "say no pattern detected" behavior the user asked for. Result over the OOS
window (2018-01-01 to 2025-03-31, equal-weight 8-symbol portfolio, after 0.35%/round
trip costs):

| | CAGR | Sharpe | Max DD |
|---|---|---|---|
| Model (confidence-gated) | 0.84% | 0.68 | -2.0% |
| Equal-weight 8-symbol buy-and-hold | 17.17% | 0.98 | -34.6% |
| NIFTY100 buy-and-hold | 11.45% | 0.72 | -38.1% |

The model is barely ever in the market: only **2.8%** of pooled OOS days triggered a
BUY (386 of 13,870) — `AVOID_DOWN` 42.5%, `NO_PATTERN_SIDEWAYS` 28.3%,
`NO_PATTERN_LOW_CONF` 26.5%. Two symbols (TATASTEEL, ULTRACEMCO) got **zero** trades
across the whole 7-year OOS window at this confidence threshold. The model's own
risk (max drawdown -2%) is far lower than buy-and-hold's (-35% to -38%), which is
the direct consequence of being in cash almost all the time through a period that
was, overall, a strong multi-year bull run for Indian equities — sitting in cash
avoided the drawdowns AND the gains. **Model does not beat either baseline on
Sharpe.** This is consistent with, not contradicted by, 4.4's finding: a real but
modest edge (~0.06 macro-F1 above noise) was not enough, filtered through a strict
confidence gate, to generate enough trades to compete with just holding the market
through a rising period. Full breakdown: `reports/phase4/checkpoint_4_5_decisions.csv`,
`checkpoint_4_5_backtest_per_symbol.csv`, `checkpoint_4_5_backtest_portfolio.csv`.

**What this means, stated honestly and not softened:** the technical-only model, as
currently built, is not a trading edge over this period and this universe. This
matches the standing concern raised earlier: pure price/technical features on 8
stocks showed no standalone edge even in Phase 3's baseline rule-testing, and
Phase 4's model — built only from those same features — inherited that limitation.
The clearest candidate explanations, in rough order of how fixable they are:
1. The 0.40 confidence threshold may simply be too strict for how this model is
   calibrated — worth testing a sweep of thresholds (0.33-0.40) to see if more trades
   at a smaller average edge actually improve Sharpe, before concluding the model
   itself is the problem.
2. The confidence-gating effectively made this a low-exposure strategy during a bull
   market — the comparison may look very different over a sideways or declining
   period; this OOS window happens to most reward simply staying long.
3. Deeper and not yet addressed: the asymmetric label barrier (+2 ATR up / -1 ATR
   down) and the single-signal-source (technical only, no news/sector/fundamental
   data) concerns raised earlier in this session remain unaddressed and are the more
   likely actual ceiling on this model, not a tuning problem.

## Known gaps / risks (not yet resolved, stated so they aren't silently lost)

- `scripts/05_splits.py` has its **own hardcoded copy** of `PILOT_SYMBOLS` (doesn't
  import it from `04_backtest.py`). Already caused one silent bug this session (ran on
  the stale old 8 after the swap without erroring). Any future symbol-list change must
  update both files.
- `scripts/02a_build_corp_actions.py` was missing from the sandbox and has been
  **reconstructed** (8 Oct 2026) from the `CorpActionTypes`/`CorpActionExDate` columns
  already present in `data/clean/*.csv`, not from the original (unseen) source. Verify
  this against the real file on the PC if it still exists there.
- Full NIFTY-100 clean price data exists on the user's PC (`data/clean/`, 103 symbols,
  real Yahoo data through 2026-10-07) but **how/when it was produced is not fully
  traced** — `CLAUDE.md`'s old "Phase 1.1 not yet run against real Yahoo" status line
  was stale and has been corrected, but the exact provenance (which script, which
  session) is still an open question, not chased down since it wasn't blocking.
  Only 32 of 103 symbols pass the Phase 1.3 corporate-action check cleanly; the other
  ~70 have not been investigated (real unhandled corporate actions vs. data errors
  unknown).
- Everything so far is on **8 symbols only**. Scaling to the full universe later means
  re-running Phase 2/3 for whichever new symbols get added (mechanical, but not done
  yet), and resolving the ~70 non-clean symbols' adjustment flags first if they're
  wanted.
- `combined-setup minimum sample count` and `3+ families tested together` (PDF
  checkpoint 3.4, "combined setups across families") were **not done** — only single
  families were gated (checkpoint 3.3), not combined setups. This is a gap against the
  original plan, surfaced here rather than glossed over.
- **NEXT STEP, not yet done:** the new sector/market-relative features
  (`data/features_sector/<symbol>.csv`, checkpoint 3.6) are built and gated but NOT
  yet merged into Phase 4's training pipeline. `attach_features` in
  `15_model_logreg_floor.py` only reads `data/features/` (the frozen 35). Need to:
  (1) extend the merge to also pull in `data/features_sector/`, (2) decide how to
  handle the genuine NaN in `sector_rel_*` for TATASTEEL/BHARTIARTL/ULTRACEMCO — plan
  is to let it pass through as real NaN into XGBoost (handles missing values
  natively) rather than impute, which means logistic regression (4.1) can't use
  these new columns without a separate imputation step not yet written, (3) re-run
  4.2/4.3/4.4/4.5 with the expanded feature set and report honestly whether it
  actually changes anything — no assumption yet that it will.
- News/sentiment features: confirmed blocked from this sandbox (network policy
  rejects Yahoo Finance and GDELT alike, tested directly, see decision log). Needs
  either a file the user fetches on their own machine, or a connector — not pursued
  further until one of those exists.

## Decision log (append-only — user's explicit choices, most recent last)

- 7 Oct 2026: Frozen spec approved (universe NIFTY 100, Jan 2015 start, holdout April
  2025+, 0.35%/round-trip costs, 1% risk per trade).
- 8 Oct 2026: Feature correlation threshold = **0.6** (not the proposed 0.7). Keep ALL
  cluster members for now at checkpoint 3.4 — no drops on correlation alone, deferred
  to Phase 4 feature importance.
- 8 Oct 2026: Pilot symbols swapped — see "Current state" above. User first said "keep
  all 8, flag as risk", then changed to "swap with clean ones" in the same session;
  the swap is what actually happened and is final.
- 8 Oct 2026: Starting Phase 4 with the explicit goal of building a model good enough
  to trade profitably, not just to pass academic checkpoints — keep this framing, but
  never let it override the "report honestly / no promise it works" rule above.
- 8 Oct 2026: Checkpoint 4.2 gate interpreted as macro-F1 only (matches 4.1's "beats
  random" gate shape) — log-loss/calibration stays a reported-not-gated metric,
  explicitly deferred to 4.3, not folded into 4.2's pass check.
- 8 Oct 2026: Checkpoint 4.3 gate operationalized as ECE improves + log-loss doesn't
  worsen (not an absolute numeric threshold) — passed, but surfaced a real macro-F1
  cost from isotonic calibration (see "Current state" above); whether to use the
  calibrated model's own class choice or keep the raw model's argmax + calibrated
  probabilities for confidence-weighting only is an OPEN decision for the user before
  4.5's backtest is built, not yet resolved unilaterally.
- 8 Oct 2026: Checkpoint 4.4's gate corrected mid-run (majority baseline is the wrong
  "chance" reference once sample_weight is used; corrected to compare against the
  shuffled-label noise floor instead) — same self-correction pattern as 4.1.
- 8 Oct 2026: Checkpoint 4.5 backtest built with an explicit confidence threshold of
  0.40 (assumption, not tuned on the backtest) and an explicit "no pattern detected"
  abstention category per the user's request, rather than silently defaulting
  low-confidence days to a bearish read. Result: model loses to buy-and-hold over
  this OOS window — reported honestly, not reframed as a win. Next steps (threshold
  sweep, addressing the asymmetric-barrier and single-signal-source concerns) not
  yet started, awaiting user direction.
- 9 Oct 2026: User asked to inspect the old `Multi_Agent` folder's reported accuracy
  before copying any of its approach. Finding: its candlestick "win rates" (84%,
  78%, 72%, 70%, 50-58%) are hardcoded strings in `candlestick_strategies.py`'s
  `STRATEGY_REGISTRY`, not measured on any backtest in that codebase (sourced from
  Bulkowski's published US-market research, not validated on NSE data). It does have
  one genuine backtest result (+16.48% return / +0.78 Sharpe / 58.33% win rate vs.
  buy-and-hold, in `COMPREHENSIVE_SYSTEM_DOCUMENTATION.md` section 9) from real code
  (`backtester.py`), but on ONE stock (ABCAPITAL.NS), ONE ~1-year test window, with
  ZERO transaction costs modeled anywhere in that backtester — weak evidence by this
  project's own standards, not something to copy. Verdict: do not adopt `Multi_Agent`'s
  approach or its numbers.
- 9 Oct 2026: Tested (not assumed) whether Yahoo Finance / news APIs are reachable
  from this sandbox: `curl` to `query1.finance.yahoo.com` and `api.gdeltproject.org`
  both returned `connect_rejected` (organization policy) — confirmed network-blocked
  regardless of API key. Historical news sentiment is not buildable from inside this
  sandbox by any method right now; would need the user to fetch it outside this
  session (their own machine/API) and hand over a file, or a connector.
- 9 Oct 2026: User chose to pursue sector/cross-sectional features first (lower
  effort, no blocked network calls, addresses the "market beta dominates" concern
  directly) while news stays blocked. Built and gated (`scripts/20_sector_features.py`,
  5/5 checks pass): market-relative return vs. NIFTY100 for all 8 pilot symbols (no
  data-quality issue, always available), plus same-sector peer-average relative
  return — but ONLY using sector peers that pass the Phase 1.3 corporate-action clean
  check. Finding: most NIFTY100 same-industry peers are themselves flagged with
  `unadjusted_big_move` problems (the same issue that got the original 4 symbols
  swapped out of the pilot). Clean-peer coverage ended up thin: ITC has a real 5-peer
  group; TCS/RELIANCE have only 1 clean peer each; SIEMENS has 2; HDFCBANK has 3 of
  22 candidates; TATASTEEL/BHARTIARTL/ULTRACEMCO have ZERO clean peers anywhere in
  the universe — their sector_rel_* columns are left as genuine NaN (not faked/
  zero-filled). Not yet wired into Phase 4's model retraining — that's the next step.
- 9 Oct 2026: User asked (a) whether RSI is actually being used properly, (b)
  to add long-term-horizon factors (noting momentum_252d's baseline Sharpe 0.84 was
  the closest anything got to buy-and-hold), (c) to use Monte Carlo methods to check
  robustness, and (d) for a prompt spec for a future "semantic" (news) agent.
  Addressed (a)-(c) by building and running `scripts/22_model_expanded.py`:
  - **RSI check (direct evidence, not assumption):** fit 4.2's exact model on all
    pooled rows and ranked `feature_importances_`. `mom_rsi14` (continuous RSI)
    ranks 17-27th of 35-45 features depending on run — present, used, moderate
    importance, NOT the model's top signal. `vote_rsi14` (the discretized vote) is
    essentially unused (importance ~0), which matches checkpoint 3.4's own finding
    that it's redundant with `vote_kc_breakout` (same correlation cluster) — the
    tree leans on that instead. RSI is being used as intended; it just isn't this
    dataset's strongest feature. Volatility-regime, ATR, and Bollinger-Band features
    rank highest throughout.
  - **Long-term features added** (`scripts/21_longterm_features.py`, 10/10 checks
    pass): 252-day return, price-vs-200-day-SMA, golden/death-cross regime state —
    the same idea behind the momentum_252d baseline.
  - **Combined result, honestly: no improvement.** macro-F1 with 35 frozen + 6
    sector + 4 long-term features (45 total) = 0.3703, statistically flat vs. the
    35-feature model's 0.3707 (re-run fresh on the same data for a fair comparison,
    not the old cached number). The sector features DID get real usage internally
    (`sector_rel_ret_5d` ranked #4 of 45 in one run), but that didn't translate to a
    better outcome. The resulting backtest was actually WORSE this run (Sharpe 0.18
    vs. the pre-expansion model's 0.68) — still loses to both buy-and-hold baselines.
  - **Monte Carlo robustness check (block bootstrap, 500 resamples, 20-day blocks)
    on the expanded model's portfolio Sharpe:** 90% CI = [-0.45, 0.88], crossing
    zero. This means the single Sharpe number from any one of these backtests
    (pre- or post-expansion) is not statistically distinguishable from noise given
    how few real trades (~370-390) the model generates — a real limitation of
    drawing conclusions from one historical path with this few trades, surfaced
    rather than treated as settled by one favorable-looking number.
  - **What this means:** adding sector and long-term features, done properly, did
    not move the needle. The ceiling looks like it's set by something more
    fundamental than feature choice — most likely the modest real signal size found
    back in 4.4 (~0.06 macro-F1 above noise) and/or the label-barrier-asymmetry
    concern raised earlier, neither of which more technical features can fix.
  - (d) addressed by handing the user a complete news/semantic-agent spec, written
    in this same reply, not filed here (it's a prompt for future work, not a result).
- 9 Oct 2026: User pushed back on fusing everything into one model, worried about
  "wrong correlation" from mixing too many indicators, and asked for each indicator
  class's own accuracy shown separately so the user picks which to trust. Built
  `scripts/23_family_specialist_comparison.py` (2/2 checks pass): one specialist
  XGBoost model per class (momentum, trend, volatility, volume, sector/cross-
  sectional, long-term-trend -- same training recipe as 4.2 throughout, only the
  input columns differ), each with its own pooled macro-F1 AND its own backtest.
  **Real, actionable finding: the volatility-only specialist (ATR/Bollinger/Keltner
  + their votes, 11 features) is the best-performing model built in this entire
  project so far** -- backtest Sharpe 0.53, CAGR 1.5%, trading 12% of days (1670 of
  13,870 pooled days), clearly ahead of the all-45-feature fused model (Sharpe 0.18,
  CAGR 0.26%, trading only 2.7% of days). Momentum, trend, volume, and sector
  specialists all had NEGATIVE backtest Sharpe standalone despite each individually
  "passing" the macro-F1-beats-majority check -- concrete proof that macro-F1
  passing does NOT imply a profitable trading rule, and that fusing weaker classes
  in with a strong one can dilute it. Still: even the best class (volatility alone)
  loses to buy-and-hold (0.53 vs. 0.98 Sharpe) -- a real improvement over every
  other model built so far, not a win. Full table:
  `reports/phase4/checkpoint_4_7_family_comparison.csv`. Natural next step, not yet
  done: try combining ONLY volatility + the one or two next-best classes (rather
  than all 6), to see if a smaller, carefully-chosen fusion beats volatility alone
  without re-introducing the dilution problem.
- 9 Oct 2026: User shared a text export from what appears to be a different AI tool
  describing a GDELT-based historical news-sentiment pipeline (BigQuery-based,
  requires a Google Cloud project). Reviewed honestly: only a prose description was
  shared, not the actual code/ZIP, so it could not be verified, run, or integrated.
  The description itself says the pipeline is untested on real data ("synthetic
  tests passed... live historical data has not been fetched or validated") and
  needs the user's own GCP project + `gcloud auth` on their own machine, which this
  session cannot do from here. If the user wants this reviewed or wired in, the
  actual script files need to be uploaded, not a text summary of them.
- **9 Oct 2026 — BIGGEST FINDING OF THE PROJECT SO FAR. The user was right that RSI
  was being used too narrowly, and a simple RSI rule now beats every ML model built
  here.** Two new checkpoints:
  - **3.8 (`scripts/24_rsi_strategy_study.py`, 4/4 pass):** 11 different documented
    RSI framings tested as standalone long/cash rules, after costs, re-derived from
    scratch (NOT copied from `Multi_Agent`, per CLAUDE.md's archive-only rule).
    Full-dev-window Sharpe: `rsi_above_40_bullrange` **0.83**, `rsi_60_40_range`
    (the user's requested Cardwell/Brown range framing) **0.72**, rsi_30_70 0.57,
    rsi_50_momentum 0.53, rsi_zscore_60 0.49, rsi_bull_divergence 0.40, EMA20-only
    control 0.25, **Phase 3's original rsi_30_50 mean-reversion framing 0.14**
    (worst but one). So the trend/regime framing of RSI is ~5x better than the
    oversold-bounce framing Phase 3 had tested, and RSI clearly adds value over a
    plain EMA20 control (0.83 vs 0.25). Phase 3's conclusion that "momentum is the
    weakest family" was an artifact of testing only ONE narrow RSI usage.
  - **4.8 (`scripts/25_rsi_fusion.py`, 3/3 pass):** combined the two things that
    worked (volatility class from 4.7 + RSI) three ways — RSI-features model,
    volatility+RSI fused model, and volatility model rule-GATED by the RSI 60/40
    rule. OOS-window Sharpe at frozen-spec costs: **RSI 60/40 rule ALONE 0.741**,
    volatility-only model 0.526, volatility-gated-by-RSI 0.521, volatility+RSI
    fused model 0.400, RSI-features model 0.116. **The plain rule with no machine
    learning beats every ML model in this project.** It also beats NIFTY100
    buy-and-hold (0.741 vs 0.723) — the first thing here to beat any baseline —
    but still loses to the harder equal-weight 8-symbol buy-and-hold (0.982). Its
    drawdown is much better though: -20.4% vs buy-and-hold's -34.6% (and the gated
    version: -3.6%).
  - **COST QUESTION SETTLED (user asked to see 0% costs).** Reported at three
    levels — 0.35% (frozen spec), 0.25% (verified Zerodha charges only, no slippage
    assumption), 0.00% (diagnostic, not achievable). Answer: costs are NOT the
    problem for the good strategies. The RSI rule goes 0.741 → 0.772 → 0.848 across
    the three levels (it trades rarely: 176 round trips, 59% time in market), and
    buy-and-hold is almost cost-immune (0.982 → 0.985). Costs devastate only the
    CHURNY strategies — in 3.8, a 1786-round-trip rule bled 1.17 Sharpe to costs
    while a 69-round-trip rule bled 0.03. Even at zero cost the best candidate
    (0.955) still loses to zero-cost buy-and-hold (0.985). **The frozen 0.35% spec
    is unchanged** — zeroing it was run as a diagnostic only, not adopted, because
    0.25% of it is non-optional verified brokerage/STT/exchange charges.
  - **THE DEEPER INSIGHT, and it questions the whole Phase 4 approach:** every RSI
    rule's `up_lift` (precision at predicting the 'Up' triple-barrier label, divided
    by the Up base rate) is ≈1.00 — i.e. **essentially ZERO classification edge on
    the label** — yet the best ones make money. They earn their returns by being
    long during sustained uptrends (exposure management), not by predicting the
    10-day triple-barrier outcome. That strongly suggests the 3-class triple-barrier
    label the entire Phase 4 model stack is trained on **is not measuring the thing
    that actually generates returns in this data.** This is a labeling/target
    specification problem, not a model problem — which would explain why every
    model so far (logreg, XGBoost, calibrated, 45-feature, per-class) has been
    mediocre at trading while "passing" its classification gates. Flagged as the
    most important open question for the project, NOT yet resolved. Changing the
    label is a frozen-spec change and needs the user's explicit approval.
- **9 Oct 2026 (later) — Phase 3.9 (`scripts/26_rsi_exit_and_patterns.py`, 5/5 pass):
  exit-timing study, the M/W patterns, and a Monte Carlo parameter search validated
  out-of-sample. User also asked again to lead with 0% costs; done — 0% leads every
  table, with the frozen-spec 0.35% printed beside it in the same row. The spec is
  unchanged (0.25pp of the 0.35 is non-optional verified charges, so 0% is a
  diagnostic, never an achievable account result).**
  - **A) "At what RSI should I sell?" — answered, and the answer is uncomfortable:
    the best exits are the ones that barely ever fire.** Holding entry at RSI>60 and
    sweeping the exit: breakdown-exit at RSI<20 scored Sharpe 1.0145 @0% / **1.0094
    @0.35%** on just 18 round trips, versus 0.8229/0.7169 for the textbook RSI<40
    exit (241 trips) and 0.4476/0.0390 for an RSI<55 exit (616 trips). Overbought
    exits at 85/90 behaved the same way (~0.99 @0.35%, 8-24 trips). Spread across
    exit choices was 0.64 Sharpe, so the exit decision genuinely matters — but it
    matters in the direction of "sell less". The exit at RSI<20 is effectively
    "almost never sell", and its 1.0094 is statistically indistinguishable from
    equal-weight buy-and-hold's 1.0173. Its one real edge: max drawdown -27.8% vs
    buy-and-hold's -34.6%. Also note exit-at-65 looked best at 0% (1.0830) and
    collapsed to 0.5308 at real cost — 1825 round trips. That is the clearest single
    illustration of why the 0% column cannot be the basis for a decision.
  - **B) M/W patterns — partially vindicated, partially refuted, as measured.** The
    **W** (bullish double-bottom below 40) as an extra entry HELPED at 0% (0.8962 vs
    0.8229 baseline) but HURT at real cost (0.6988 vs 0.7169), because it doubled
    trade count (515 vs 241 trips). The **M** (bearish double-top above 60) as an
    extra exit HURT clearly and at both cost levels (0.6701 @0%, 0.1726 @0.35%, 863
    trips) — it keeps exiting trends that then continued. So the user's W intuition
    has mild merit that costs eat; the M intuition does not survive testing on this data.
    Pattern detection was verified strictly causal (no extremum used on the bar it
    forms; truncation test passes on 2 symbols).
  - **C) Monte Carlo parameter search (60 random parameter sets), search period
    2015-2020, validation 2021-2025 — the anti-data-snooping test.** The
    search-period winner (Sharpe 1.2155 in-sample) delivered 1.0076 @0% in
    validation and **ranked 27th of 60** out of sample. Degradation 0.2079 Sharpe.
    Conclusion stated plainly: **"best parameters" from single-period RSI tuning are
    substantially luck, and tuning RSI levels harder is not a path to a real edge.**
    Also decisive: buy-and-hold over that same validation window scored **1.2831**
    @0% / 1.2774 @0.35% — higher than every one of the 60 tuned strategies.
  - **Label decision taken (user said "I do not understand label or do as per you"):
    the triple-barrier 3-class label is RETAINED only for the ML comparison in the
    paper, and is NO LONGER the optimisation target for the trading system.** Reason:
    measured up_lift stays ≈0.96-1.00 across every RSI variant tested here and in
    3.8, i.e. zero classification edge on that label even for rules that make money.
    This needs no frozen-spec change — the spec still defines the label, we simply
    stop treating it as the trading objective. The trading side is now rule-based,
    with ML kept as the academic comparison. User explicitly approved dropping ML
    from the trading path ("I am okay if you want to remove the ML").
  - **Where this leaves the project, honestly.** Across many independent tests now
    — 11 indicator rules (Phase 3), 6 per-class models (4.7), 11 RSI framings (3.8),
    3 fusion designs (4.8), 19 exit variants and 60 Monte Carlo parameter sets (3.9)
    — nothing has beaten equal-weight buy-and-hold after real costs, and the best
    results consistently come from trading LESS. The evidence is now consistent
    enough that "technical signals on 8 large-cap NSE names, 2015-2025, do not beat
    holding them" is the honest headline finding, not a failure to tune. That is a
    publishable negative result with real rigour behind it (purged walk-forward,
    cost modelling, shuffled-label test, bootstrap CIs, out-of-sample parameter
    validation) — and it is a much stronger paper than an overfitted positive one.
- **9 Oct 2026 — Phase 3.10 (`scripts/27_rsi_ema_grid.py`, 3/3 pass): the RSI-period /
  EMA-period grid, scored on the user's OWN success metric, with the overfitting gap
  measured in the units the user asked about.**
  - **New metric, at the user's request and better than what I had been using:** for
    every (stock, calendar year) pair, did the strategy beat THAT stock's own return
    that year? 88 stock-years across 8 symbols. Reported alongside mean annual EXCESS
    return, because win_rate alone misleads — in a down year, cash wins automatically.
    Context: **76.1% of the 88 stock-years were positive for the stock itself**, so a
    permanently-in-cash rule would "win" ~24% while earning nothing. A combination is
    only genuinely good if win_rate > 50% AND mean annual excess >= 0.
  - **Grid: 108 combinations** (RSI period 7/14/20 x EMA period 14/20 x entry 55/60/65
    x exit floor 20/30/40 x EMA-confirmation off/on), each scored at 0% and at the
    frozen-spec 0.35%.
  - **ANSWER — does the RSI period matter? YES, and longer is better, monotonically:**
    mean win_rate across all combos sharing that period — RSI 7: 0.279 (excess -7.15%,
    Sharpe 0.795, CAGR 8.92%); RSI 14: 0.343 (-4.90%, 0.900, 11.36%); **RSI 20: 0.354
    (-4.55%, 0.899, 11.77%)**. RSI 7 is clearly the worst — short/noisy RSI is actively
    harmful here. The monotonic 7 < 14 < 20 ordering is consistent with every other
    finding in this project: smoother, slower, trade-less wins.
  - **ANSWER — EMA 14 vs EMA 20? Makes essentially no difference.** win_rate 0.3228 vs
    0.3274, Sharpe 0.8664 vs 0.8628. Not a meaningful lever either way.
  - **ANSWER — does EMA confirmation on entry help? No.** Marginally better win_rate
    (0.3279 vs 0.3224), marginally worse Sharpe (0.8594 vs 0.8698) and CAGR. A wash.
  - **The exit floor is again the dominant lever** (re-confirming 3.9 independently):
    exit<20 win_rate 0.381 / excess -1.98% / Sharpe 1.0018 / CAGR 14.71%;
    exit<30 0.319 / -5.12% / 0.907 / 10.97%; exit<40 0.276 / -9.51% / 0.685 / 6.37%.
    Monotonic: the less it sells, the better it does.
  - **BEST COMBINATIONS: RSI 20 + EMA (either) + entry >55 + exit <20** — win_rate
    0.466, mean annual excess **-0.69pp**, CAGR 16.33%, Sharpe 1.0175. That -0.69pp is
    **the best mean annual excess of any of the 108 combinations**, and it is still
    NEGATIVE. The highest-win_rate combo (RSI14 EMA20 in>65 out<20 EMAconf, win_rate
    0.5227) also has negative mean excess (-1.98pp) — it wins slightly more than half
    its stock-years but loses more when it loses.
  - **VERDICT ON THE USER'S BAR: 0 of 108 combinations clear BOTH bars** (win_rate >
    50% AND mean annual excess >= 0) at real cost. One combination clears the win_rate
    half on its own, but with negative average excess. So the stated goal — "beat that
    stock's own yearly return most of the time, profitably" — is NOT met by any
    RSI/EMA combination tested.
  - **OVERFITTING, QUANTIFIED (the user explicitly asked to see how much an overfitted
    model flatters itself):** best-of-108 chosen AND scored on the whole window gives
    win_rate **0.5227**. The SAME combination, chosen on 2015-2020 only and then scored
    on 2021-2025 which never informed the choice, gives win_rate **0.3000** — inflated
    by **+22.3 percentage points**. For reference the median win_rate across all 108
    combos with no selection at all is 0.3068, i.e. the "winner" is barely different
    from a random pick once you stop scoring it on its own selection data. (The honest
    walk-forward run did post CAGR 18.48% / Sharpe 1.2057 / max DD -18.54% on
    2021-2025 — but buy-and-hold over that same window scored Sharpe 1.2774, so it is
    still behind the benchmark, as measured in 3.9.)
  - Reports: `checkpoint_3_10_rsi_ema_grid_full.csv` (all 108 rows),
    `checkpoint_3_10_selection_period_scores.csv`,
    `checkpoint_3_10_overfit_vs_honest.csv`.
- **9 Oct 2026 — Phase 4.9 (`scripts/28_sharpe_levers.py`, 3/3 pass): the user set a
  hard target of Sharpe > 1 (ideally 2-3) and asked what to change if RSI/EMA tuning
  is not working. Answer, measured: change the UNIVERSE, not the indicator — and
  Sharpe > 1 is now met.**
  - Signal held fixed at 3.10's best (RSI20, enter >55, exit <20). Only portfolio
    construction varied. Universe expanded from the 8 pilots to **all 30 tradeable
    symbols that pass the same Phase 1.3 corp-action check** (10 extra clean CSVs
    staged from the PC; no data-quality compromise made to get the extra names).
  - A fractional-weight portfolio backtester was written (the verified
    04_backtest.backtest_signal takes 0/1 signals only, so position sizing needed a
    new engine) and **validated against the verified engine before any of its numbers
    were reported** — agreement within the expected open-vs-close execution gap on 2
    symbols. Cost convention: cost_pct/2 per unit turnover, so a full round trip costs
    exactly the spec's 0.35%.
  - **RESULT — the user's minimum bar is MET: RSI signal on 30 clean symbols, equal
    weight: Sharpe 1.2217 @0.35% (1.2240 @0%), CAGR 15.95%, vol 13.06%, max DD
    -26.55%.** Up from Sharpe 1.0225 on the 8 pilots.
  - **Lever-by-lever contribution (8-symbol universe, real cost), so the credit goes
    where it is due:**
    - **L3 universe 8 -> 30 symbols: +0.1992 Sharpe. The only lever that worked.**
      Exactly what diversification theory predicts — more independent bets, lower
      portfolio vol for the same return.
    - L1 volatility targeting (15% target): **-0.0766** — it HURT. It cut vol as
      designed (16.5% -> 14.0%) but generated 20x the turnover (30.1 vs 1.5) and the
      cost drag more than ate the benefit. Slightly positive at 0% cost on the
      30-symbol universe (1.2372 vs 1.2240), so the idea is not wrong — the trading
      cost of implementing it is.
    - L2 inverse-volatility weighting: **-0.0622** — also HURT, same mechanism, far
      worse: 108 units of turnover because weights move every day.
    - L4 NIFTY100 200-day regime filter: **-0.6841** — a disaster (Sharpe 0.338). It
      cut average exposure to 41% and sat out most of a decade-long bull market.
  - **MY PRE-STATED EXPECTATION WAS WRONG AND IS RECORDED AS SUCH.** The script's
    docstring committed, before running, to "L1 and L3 should raise Sharpe
    meaningfully; L2 modestly; L4 is a coin flip". L3 was right. L1 and L2 both went
    the wrong way once real costs were applied, and L4 was far worse than a coin flip.
    Noting this rather than quietly rewriting the expectation.
  - **Sharpe 2-3: NOT REACHED, and not reachable this way. Best was 1.2217.** The
    structural reason, stated plainly: Sharpe is return/vol, and on this universe the
    MARKET itself delivers ~1.24 (30-symbol equal-weight buy-and-hold: Sharpe 1.2401,
    CAGR 17.10%; vol-targeted buy-and-hold: **1.2596**). Both still beat the strategy.
    To reach 2-3 you need either materially lower vol at the same return (requires
    genuinely uncorrelated assets, not 30 correlated Indian large caps) or materially
    higher return at the same vol (requires real alpha, which this project has now
    measured as approximately zero across ~200 tested variants). Leverage does NOT
    help: it scales return and vol together, leaving Sharpe roughly unchanged — and it
    would be a frozen-spec change ("long or cash only") needing explicit approval.
  - **Standing recommendation given to the user:** run the RSI20 signal on the
    30-clean-symbol universe, equal weight. It clears their Sharpe > 1 bar at 1.22
    with a -26.6% max drawdown. But be honest in the paper that plain buy-and-hold on
    the same 30 names gives Sharpe 1.24 / CAGR 17.1%, so the strategy's only real
    contribution is a modestly smaller drawdown (-26.6% vs -29.1%), not higher
    risk-adjusted return.
- 12 Oct 2026: User gave full permission to change cleaning, universe and validation,
  asked that validation not use only the last rows/stocks, and asked for an independent
  checker after every stage and for internet claims to be tested on the data. Done as
  Phase 5. Outcome after the checkers' corrections: no significant edge; random time
  blocks dropped for trained models because training on later blocks leaked ~5-7%/yr;
  holdout (April 2025+) still sealed. See "Current state".
