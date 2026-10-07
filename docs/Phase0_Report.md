# Phase 0 Report: Spec research

Date: 7 October 2026. Status: **awaiting your sign-off** (0.1 and 0.3 are approval points).

Confidence labels used below:
- **Verified** = I read the figure on the linked page today.
- **Partly verified** = seen in search results or a secondary source, not read in full.
- **Not verified** = could not confirm; treated as an open item.

---

## 0.2 NSE costs and trading rules

### Charges, equity delivery (NSE)

| Charge | Rate | Status |
|---|---|---|
| STT | 0.1% on buy and on sell | Verified (Zerodha charges page) |
| Exchange transaction charge | 0.00307% per side | Verified (same page) |
| SEBI fee | Rs 10 per crore (0.0001%) per side | Verified |
| Stamp duty | 0.015% on buy side | Verified |
| GST | 18% on brokerage + SEBI + transaction charges | Verified |
| Brokerage | Zero at Zerodha for delivery; differs by broker | Verified for Zerodha only |
| DP charge | Rs 15.34 per scrip on sell (Zerodha) | Verified for Zerodha only |

Round trip, worked out from the rates above: 0.2% STT + 0.015% stamp + about 0.006% exchange + about 0.001% SEBI and GST = **about 0.22%**, plus the flat DP charge (about 0.03% on a Rs 50,000 trade).

**Change to the plan:** backtest cost goes from 0.30% to **0.35% per round trip** (0.25% charges + 0.10% slippage). The 0.10% slippage is my assumption for large-cap stocks, not a sourced figure. Phase 9 paper trading is where it gets measured.

Budget 2026 raised STT on futures and options from 1 April 2026; search results say delivery STT was not changed (Partly verified: headlines only, consistent with the 0.1% on Zerodha's live page).

### Rules

| Rule | Finding | Status |
|---|---|---|
| Short selling | Cannot sell short and carry overnight in the cash segment. Only intraday, futures/options, or SLB. Confirms **long or cash only**. | Verified (IIFL article) |
| Settlement | T+1 for all stocks since 27 January 2023. The IIFL article still says T+2, which is outdated. | Partly verified (several broker pages in search results) |
| Price bands | 2%, 5%, 10% or 20% per stock. Stocks with derivatives have **no price band**, only a 10% operating range for orders. | Verified (NSE price bands page) |
| Market-wide circuit breaker | 10% / 15% / 20% index moves | Partly verified (search headline, page not read) |

Backtest consequence: on a day a stock is locked at its band, the engine must not assume a fill. This becomes a rule in checkpoint 2.2.

---

## 0.1 Base paper candidates

I read abstracts and tool-generated page summaries, **not the full papers**. Read the chosen paper yourself before committing to it.

| Paper | Market and test | Why it fits | Weakness we can beat |
|---|---|---|---|
| **TradingAgents** (Xiao et al., arXiv 2412.20138, Dec 2024) | US stocks (AAPL, GOOGL, AMZN and others), Jan to Mar 2024 | Same agent roles: technical, sentiment, fundamental, risk. Code is public. | Only 3 months. No transaction costs mentioned. Authors admit the Sharpe (5.6 to 8.2) is inflated. Not Indian market. |
| **Kotekar, Mohan, Kolukuluri**, "Can News Sentiment Improve Deep Learning Models for Nifty 50 Index Forecasting?", IEEE Access 2025 | Nifty 50 index, next-day return direction | Indian, peer-reviewed, news + price | Index only, not stocks. Reports a 5.2% accuracy gain; no trading backtest seen in the abstract. |
| **Mishra et al.**, DRL framework for NIFTY 50 index trading, MDPI AI 2025 | Nifty 50 index, 15-minute bars, test May 2024 to Apr 2025 | Indian, includes brokerage | 15 trades in the test year; slippage excluded; index only |
| **Adhikari et al.**, NeSy-MAT V2, IJCISIM 2026 | BANKNIFTY weekly options, 2019 to 2024 | Indian, multi-agent with veto rules, honest statistics (bootstrap intervals) | Options, not stocks; results "mixed", Sharpe not distinguishable from LSTM |
| "Sentiment-Driven Improved Stock Prediction: An Evidence from India", Computational Economics (Springer) 2026 | Unknown | Title is close to our news agent | **Could not read: the page refused the request (rate limit).** Open it yourself. |

**Recommendation:** TradingAgents as the base paper (architecture comparison), Kotekar et al. as the Indian peer-reviewed comparator.

Open items on this:
- I do not know whether TradingAgents was accepted at a peer-reviewed venue. If your guide requires a journal base paper, Kotekar et al. becomes the base paper instead.
- Running TradingAgents as a baseline needs paid LLM API calls. A multi-year, 100-stock rerun would be expensive; a reduced rerun (fewer stocks, shorter period) is the realistic option.
- I found no paper applying target/stop/time labels with multi-agent fusion to NSE stocks. That is not proof none exists; the search was four queries.

**Novelty claim this supports:** calibrated, correlation-aware fusion of technical, sector-rotation and exchange-filing event agents with a risk gate, on NSE stocks, tested over multiple years with real costs.

---

## 0.3 Data sources

**Limit on my side:** I cannot download market data myself. My workspace is blocked from Yahoo Finance, NSE archives and niftyindices.com (tested today, all three refused), and I have no way to run commands on your PC in this session, only read and write files. So I write the download scripts, you run them, and I check the output files.

| Data | Source | Status |
|---|---|---|
| Daily prices, volume, delivery % | NSE bhavcopy through the `jugaad-data` Python library (v0.35.10, released 6 Oct 2026) | Library verified as maintained; **not yet run** |
| Split/bonus adjustment | Bhavcopy prices are unadjusted. Use NSE corporate-action data, cross-checked against Yahoo adjusted prices | Not verified |
| Sector and Nifty index history | `jugaad-data` index data | Listed on its page; not yet run |
| Historical index constituents | niftyindices.com (a forum post says it covers the major indices) | **Not verified. Biggest data risk.** Fallback: rebuild from NSE reconstitution announcements |
| Corporate announcements | NSE/BSE via `nsefin`, `NseKit`, `nse-bse-api` | Libraries exist; **history depth unknown** |
| News headlines | Publisher RSS, GDELT, a figshare NSEI news-sentiment dataset | Not inspected. History depth decides how long the news agent can be backtested |
| India VIX, FII/DII flows, F&O open interest | NSE | Not yet checked |

---

## Proposed spec for sign-off

| Item | Proposal |
|---|---|
| Universe | NIFTY 100, with historical constituents if obtainable |
| History | January 2015 to date |
| Final holdout | April 2025 to latest date, opened once in Phase 9 |
| Development data | January 2015 to March 2025, walk-forward |
| Bars and horizon | Daily, 10 trading days |
| Labels | Target 2x ATR = Up, stop 1x ATR = Down, time-out = Sideways |
| Execution | Signal at close, entry at next day's open, no fill on band-locked days |
| Direction | Long or cash only |
| Cost | 0.35% per round trip |
| Risk per trade | 1% of capital |
| Metrics | Return after costs, Sharpe, max drawdown, hit rate, profit factor, turnover, macro-F1 |
| Combined-setup minimum | 100 past cases across at least 30 stocks (my proposal) |
| Correlation limit | Absolute correlation below 0.7 between kept features (my proposal) |

The last two thresholds are my starting proposals, not sourced standards.

---

## Sources

- https://zerodha.com/charges/
- https://www.nseindia.com/static/products-services/equity-market-price-bands
- https://www.indiainfoline.com/knowledge-center/online-share-trading/can-I-short-sell-in-delivery-trading
- https://www.motilaloswal.com/learning-centre/2023/1/t-plus-1-settlement-for-stocks-kicks-in-from-27-january-2023
- https://www.moneylife.in/article/stt-hike-applies-only-to-options-and-futures-it-dept-clarifies/79539.html
- https://www.businesstoday.in/markets/stocks/sensex-nifty-crash-circuit-breaker-rules/story/398162.html
- https://arxiv.org/abs/2412.20138
- https://github.com/TauricResearch/TradingAgents
- https://idr.nitk.ac.in/items/98e64904-2b11-49b3-9287-8d13c7e84a7f/full
- https://www.mdpi.com/2673-2688/6/8/183
- https://cspub-ijcisim.org/index.php/ijcisim/article/download/4738/3894
- https://link.springer.com/article/10.1007/s10614-026-11376-x (not readable)
- https://pypi.org/project/jugaad-data
- https://tradingqna.com/t/historical-constituents-of-various-nse-indices/176515
- https://pypi.org/project/nsefin/
- https://figshare.com/articles/dataset/Dataset_and_News_Sentiments_for_NSEI_Stock_Market_Prediction/30150130
