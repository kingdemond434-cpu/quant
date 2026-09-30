# Practitioner podcasts, forums and free-data hacks: what to add

Cluster: `practitioners_data`. Written 2026-09-27. Machine-readable version: `practitioners_data.json` (30 hypotheses, 15 capability gaps, 21 data sources, 78 source URLs).

**How the quotes were checked.** Every quote and number below was checked against page or PDF text fetched with curl and pypdf. I stopped trusting the WebFetch summaries for numbers after one of them said Krohn et al. report a Sharpe ratio of 2-3. The paper actually reports 0.5-0.7 at better-than-quoted spreads, and a negative Sharpe at full costs.

**Gap in coverage.** The session's WebSearch budget (200 calls) ran out partway through. After that I only fetched URLs I already knew. So Odd Lots, Hidden Forces, Macro Voices, Nuclear Phynance, Wilmott, QuantNet, Glassdoor and WSO are not mined. The forums are behind Cloudflare or a login from this container, and Bloomberg is paywalled.

**Status labels used below.**
- **DOC**: documented in a paper or with published data.
- **REP**: said on the record by a named practitioner, no data behind it.
- **SPEC**: my own mapping, not tested.

## Top 20 additions, ranked

Ranked by: strength of evidence × whether it can be traded on an MT5 CFD × whether it is new to the desk.

| # | Family / symbols | Mechanism and construction | Evidence | Source |
|---|---|---|---|---|
| 1 | `forced_flow` (month_end, **conditioned on month-to-date US500 return**): GBPUSD, USDCHF, AUDUSD, NZDUSD | Currency-hedged equity funds reset their hedges at the 16:00 London fix on the last business day. The window is 15:00-16:00 London. If US equities are up for the month, sell USD. | DOC: slope of 2.17bp in GBP/USD per 1pp of S&P, p=0.00022, over 138 month-ends (2015-2026) | [forexdetox](https://forexdetox.substack.com/p/the-4-pm-london-fix-anomaly-at-month); [Melvin-Prins](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_Workshop_MELVIN_PRINS_Equity%20hedging%20and%20exchange%20rates%20Nov%202013.pdf) |
| 2 | `forced_flow` gotobi pre-flow: 7 JPY crosses | Go long the JPY cross 07:00 to 09:55 JST (00:55 UTC; Japan has no daylight saving) on the 5th/10th/15th/20th/25th/30th. Japanese importers buy USD at the bank TTM rate. | DOC: after Covid, all 7 pairs are significant after Holm correction, mean 4.05 pips | [forexdetox](https://forexdetox.substack.com/p/the-tokyo-fix-reversal-anomaly-on); [arXiv 2301.13204](https://arxiv.org/pdf/2301.13204) |
| 3 | `hedging_demand_close` with **a close time per underlying** | The last 30 minutes follow the direction of the rest of the day, in over 60 futures across all asset classes. The desk's family uses one close_hour. Map each underlying's own close instead: US equities 16:00 ET, US Treasuries 15:00 ET, gold 13:30 ET, crude 14:30 ET. | DOC: JFE 2021, 1974-2020 | [Baltussen et al.](https://www3.nd.edu/~zda/intramom.pdf) |
| 4 | `forced_flow` Treasury auction cycle: UST10Y, UST05Y | Short for the 5 days before the auction, long for the 5 days after. Dealers have limited capacity to absorb supply. | DOC: 2-year note, pre-auction minus post-auction return of -8.89bp, t=2.93 | [Lou-Yan-Zhang](https://personal.lse.ac.uk/loud/Shocks.pdf) |
| 5 | `fx_fixing_reversal` at the WMR 16:00 fix, 9 USD pairs | The "W-shape": the dollar rises into the Tokyo, ECB and London fixes and reverses after each. This only works if costs are low. | DOC: at full costs the Sharpe is negative; 0.5-0.7 at tight spreads | [Krohn-Mueller-Whelan](https://sites.insead.edu/facultyresearch/research/file.cfm?fid=66802) |
| 6 | `fx_fixing_reversal` gotobi post-fix: JPY crosses | Short at 09:55 JST, exit between 10:00 and 10:40. | DOC (short sample) | arXiv 2301.13204 |
| 7 | `clock_transition`: EURUSD, GBPUSD, USDCHF | Long EUR against USD from 16:00 London to 17:00 New York. Short from 08:00 to 16:00 London. This comes from time-zone segmentation. | DOC: Sharpe 0.79 after costs, 2007-2014 | [Jiang](https://www.cicfconf.org/sites/default/files/paper_67.pdf) |
| 8 | `clock_transition`: local currency weak during its own trading hours | EUR/USD short in the morning, long in the afternoon. Extend the test to AUD, NZD and JPY in their home sessions. | DOC: EBS data 1997-2007, Sharpe 1.3 / 0.9 after costs | [Breedon-Ranaldo (SNB)](https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf) |
| 9 | `fx_fixing_reversal` at the ECB 14:15 CET fix: EUR crosses | The second leg of the W-shape. | DOC | Krohn et al. |
| 10 | `multi_speed_trend`, fast speeds only on large-tick underlyings (UST, grains, softs) | CFM attributes the decline of short-term trend to tick size relative to volatility. Fast trend still works where the tick is large; use only slow speeds on FX and indices. | REP: CFM paper discussed on Top Traders Unplugged ep.408 | [TTU 408](https://finance.biggo.com/podcast/57764de98bd370e7) |
| 11 | `overnight_drift`, **only after a selloff**: US500, NAS100, US30 | Long 02:00-03:00 ET (European open). The unconditional effect has decayed since 2021, so only the arm that follows a US selloff is worth testing. | DOC, then decayed | [NY Fed 2026](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/) |
| 12 | `opening_range` using a noise-area rule: US500, NAS100 | Intraday momentum beyond the recent noise band, with a trailing stop. | DOC (SSRN): SPY 2007-2024, net Sharpe 1.33 | [Concretum](https://concretumgroup.com/papers/) |
| 13 | `mean_reversion_rsi`, daily: US index CFDs | Retail 0DTE option selling leaves dealers long gamma, and their hedging has pushed one-day index autocorrelation negative. **This contradicts #12, so test the two as a pair.** | REP: CFM research, via Yoav Git | [TTU 409](https://finance.biggo.com/podcast/6fb6a429f599196c) |
| 14 | `relative_value` run as **trend on the spread**: Brent-WTI, NY/London cocoa, arabica/robusta, white/raw sugar, Au/Ag, Pt/Pd | Takahe shut its original fund to stay small enough to trade spreads at equal risk to outright contracts. | REP | [FwM S7E25](https://www.flirtingwithmodels.com/episodes/1iIqmQ7piJd) |
| 15 | `forced_flow` corporate flow at T-2: USD pairs | Corporate USD demand arrives two business days before month-end because spot FX settles T+2. This is separate from the rebalancing flow on the fix day. | REP: blog post by the desk's own broker | [Fusion Markets](https://fusionmarkets.com/posts/forex-month-end-flows) |
| 16 | `opening_range`: HK50, CHINAH | The 15-minute Hang Seng pre-open "still produces something close to the clean momentum" of the 1990s. | REP: Toby Crabel | [Algo Advantage 055](https://www.algoadvantage.io/podcast/055-toby-crabel/) |
| 17 | `calendar_month` across commodities and financials | Van Hemert (Man AHL): long-term trend signals partly capture seasonality. | REP | [FwM S7E6](https://www.flirtingwithmodels.com/episodes/0BxaQSF0wsB) |
| 18 | `event_reaction` pre-FOMC: US500 | Long from the prior close to the announcement, with a VIX filter. | DOC but contested: one study says it vanished after 2015; one replication finds Sharpe 0.5-0.6 over 2014-2024 | [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/); [QuantSeeker](https://www.quantseeker.com/p/trading-the-fed-the-pre-fomc-drift) |
| 19 | `fx_fixing_reversal` at the LBMA gold (10:30, 15:00) and silver (12:00) auctions | Information leaked through the fix before the 2015 reform; nobody has tested the auction since. | DOC before the reform, SPEC after | [UWA](https://researchimpact.uwa.edu.au/research-impact-stories/fixing-a-leaky-fixing/) |
| 20 | `forced_flow` commodity-index roll (early-month roll window) | Front-running the "Goldman roll". The CFD mapping is my speculation, and the effect has probably decayed. | DOC 2000-2010, Sharpe up to 4.39 | [Mou](https://paperswithbacktest.com/strategies/limits-to-arbitrage-and-commodity-index-investment-front-running-the-goldman-roll) |

**Capability gaps with the most value** (full list of 15 in the JSON):

1. **An event clock for the benchmark fixes and gotobi days** that handles daylight saving. It unlocks 8 of the rows above.
2. **A `forced_flow` that takes a cross-asset conditioner.**
3. **Measuring the executable spread in each fix window** from the Fusion tick recorder. This decides whether rows #1-9 can be traded at all.
4. **Walk-forward correlation** across the whole parameter surface, not just the best cell (Tinsley).
5. **A post-publication decay splitter.** This pass found four decays: the overnight drift, pre-FOMC, the opening-range breakout (by Crabel's own account) and the index roll.
6. **A ~50% out-of-sample haircut prior.** A Fed paper found that mined predictors and peer-reviewed predictors both kept about 50% of their power out of sample.
7. **Using fast sub-cost signals as an execution overlay**, not as trades in their own right (Concretum).
8. **Synthetic spread instruments** so trend rules can run on spreads.

**Validation lessons from practitioners:**
- Jane Street (In Young Cho): financial data is "one unit of useful data and 99 units of garbage".
- Jane Street (Eric Mannes): store the time each piece of data arrived. The desk already does this through its point-in-time stamp columns.
- Rob Carver: put costs in from the start, and use position buffering.
- Kevin Davey: write the kill criteria before the drawdown arrives, and incubate a strategy for 6-12 months.
- Jane Street's interview guide centres on adverse selection and on whether a counterparty "care[s] about the price". That is the same test for price-insensitive counterparties that the forced-flow families rest on.

## Top 15 data sources to ingest

| # | Source | Cost / history / frequency | Point-in-time | What it enables | Desk status |
|---|---|---|---|---|---|
| 1 | CFTC TFF + disaggregated, **full contract set** | Free; 2006-; weekly | Stamp by the Friday release | COT families on JPY, NZD, MXN, indices, UST, VIX, crude, natgas, grains, softs | Partial: TFF has 5 FX contracts, disaggregated has gold and silver only |
| 2 | LBMA prices JSON (`prices.lbma.org.uk/json/gold_pm.json`) | Free; 1968-; daily | Safe | Gold/silver auction studies | Not ingested (HTTP 200 verified) |
| 3 | TreasuryDirect auctions API | Free; decades; per auction | Safe | Treasury auction cycle (#4) | Code references only |
| 4 | Fusion MT5 tick recorder around the fixes, plus Dukascopy/TrueFX/HistData history | Free | Safe | Fix-window cost surface; M1 fix replications | Dukascopy fetcher exists; no fix-window dataset |
| 5 | ICE Futures Europe COT | Free; weekly | Stamp at release | COT on XBRUSD, UKCOCOA, COFROB, SUGAR | Not ingested |
| 6 | LME COTR | Free; 2018-; weekly | Stamp at release | COT on Cu, Al, Zn, Ni, Pb | Not ingested (Cloudflare blocks this container; fetch from the box) |
| 7 | SNB sight deposits (cube `snbgwdchfsgw`) | Free; 2009-; weekly | The file carries a PublishingDate | CHF intervention proxy | Not ingested (HTTP 200) |
| 8 | Japan MOF intervention record | Free; 1991-; monthly and quarterly | Disclosure lag must be respected | JPY conditioner | Code reference only |
| 9 | EIA weekly petroleum report and gas storage | Free; 1982-; weekly | Store the release instant | Energy `event_reaction` | Code references; no dataset |
| 10 | ForexFactory JSON forecast → surprise series | Free | Only through desk snapshots | Signed surprise for `event_reaction` | Snapshots already ingested; no surprise series derived |
| 11 | NY Fed primary dealer positions | Free; weekly | Released Thursday | UST dealer-capacity conditioner | Only RRP/SOMA ingested |
| 12 | JPX trading by investor type | Free; weekly | Stamp at release | JPN225 foreign-investor flows | Not ingested |
| 13 | CFETS CNY central parity | Free; daily | Safe | USDCNH fix gap; China risk proxy | Code reference |
| 14 | Dukascopy SWFX sentiment (record forward) | Free | Only if recorded by the desk | Retail positioning contrarian test | Not ingested |
| 15 | Wikipedia pageviews / GDELT tone | Free, rate-limited | Safe if stamped at ingest | Attention/tone conditioners | Pageview code exists with no artifact; GDELT listed as DISCOVERED, never fetched |

Also listed in the JSON: Deribit options open interest (only to inform the BTCUSD/ETHUSD CFDs), USDA NASS crop progress, and ECB 14:15 reference rates (already ingested).
