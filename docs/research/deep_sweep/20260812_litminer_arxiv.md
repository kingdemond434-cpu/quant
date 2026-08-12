# Literature miner — arXiv q-fin FULL-subcategory sweep + divergent grounds
**Run date:** 2026-08-12 · **Agent:** litminer (read-only ground-digger) · **Status: COMPLETE**
(3 mechanism cards · 1 data-loot · 5 graveyard · 3 engine · 6 nulls · footer has DEPTH/NEXT-GROUND)

Mission: full sweep of q-fin.TR/PM/RM/ST/MF/CP/PR/GN (~6mo recent), targeted at desk-thin families
(stat-arb, vol/options, market-making-execution, event/calendar, lead-lag-with-sync-caveat,
attention-if-sharp), plus ≥2 divergent grounds (J-STAGE/CiNii native-JP; Retraction Watch /
failed-replication harvest). Prior ground: `20260805_LIT_arxiv_qfin_sweep.md` (1 week ago) — this
run must NOT re-card its findings; delta-sweep + the subcategories/families it left thin.

Desk priors binding on every card: 420/0 price-only daily grave; −58% McLean-Pontiff haircut on
published effects; no mechanism (who is forced to lose) = hard kill; R0117 lead-lag refuted on
sampling-phase aliasing; DVOL vol-carry EV-rejected 2026-08-12 (0.0003) — do not re-card that exact
construction; ~$5k book so fund-scale-invisible edges are the structural advantage.

---

## Running notes (chronological; blocks tagged for mechanical routing)

_(populated incrementally below — if this file ends without the DEPTH/NEXT-GROUND footer, the run
died mid-flight and the last note is the frontier)_

### 00. Ground state read before any fetch (2026-08-12)
- `20260805_LIT_arxiv_qfin_sweep.md` = header + checklist only, **zero findings appended** — the
  ITEM-2 seat died before executing. This run is the FIRST execution of the full-subcat sweep, not
  a delta. Its coverage map (from `data/strategy_coverage.json` 2026-08-05): STATISTICAL-ARBITRAGE
  n=0 mentioned-never-tested; thin: ATTENTION-SENTIMENT 2, MM-EXECUTION 1, VOL-AND-OPTIONS 2,
  EVENT-AND-CALENDAR 1, LEAD-LAG 2. Hunted (do not re-bring): carry-funding, cross-venue-premium,
  cross-sectional-factor, trend, order-flow-positioning, copy-trader, onchain-flow.
- `LIT_a_failed_replication.md` already harvested: Hou–Xue–Zhang, Chen t-hurdles, JKP, Brigida TVL,
  Fieberg non-standard-errors + crypto-anomalies-constraints, McLean–Pontiff, Chordia–Goyal–Saretto,
  **Lucey/Elsevier retraction cluster (Dec 2025–Jan 2026, incl. 707-citation crypto paper)**,
  Chen–Zimmermann-vs-HXZ, Li–Zhu Lasso. My Retraction-Watch divergent ground = DELTA beyond these.
- Vault graveyard hit relevant to stat-arb: `statarb_kalman_hedge_ratio_refinement` (BTC/ETH Kalman
  hedge-ratio, killed by its own source thread) — Kalman-refinement variants are pre-killed; the
  FAMILY (pairs/cointegration residual reversion) remains untested.
- Network: Bash curl is sandbox-blocked; all fetches via WebFetch. `export.arxiv.org` API answers
  **HTTP 429** (shared egress IP throttled; parallel calls tripped it) — pivoted to `arxiv.org/list`
  monthly listing pages + `arxiv.org/search`, fetched SERIALLY. A future seat should assume the
  Atom API is rate-hostile from this box and go straight to listing pages.

### 01. q-fin.TR month-walk (target: 2026-03..08)
**2026-08 (13 entries, page total)** — URL: https://arxiv.org/list/q-fin.TR/2026-08
Candidates pulled for depth:
- `2608.09188` "When Cross-Venue Agreement Is Not Price Discovery" — crypto perps, cross-venue.
  Directly on the desk's R0117 refutation axis (sampling-phase aliasing). DEPTH-QUEUE.
- `2608.00885` "Optimal Trading of Microstructure Mean Reversion" — stat-arb/execution adjacent.
  DEPTH-QUEUE.
- `2608.04373` "Public Trader Identity: Adverse Selection and Return Predictability" — venue with
  public trader IDs ⇒ adverse-selection signal. Possible map to desk L2/own-fill ground. DEPTH-QUEUE.
- `2608.07690` "Order Imbalance, Skew and Width in OTC Trading" — MM quoting relation; maybe engine.
Rest: AMM/protocol papers (2), FX-ML, HFT-measurement methodology, rough-Hawkes-Heston micro
foundation, price-limit memory — none map better than the four above.

**2026-07 (40 entries)** — URL: https://arxiv.org/list/q-fin.TR/2026-07
Depth-queue adds:
- `2607.09230` "When Does Order Flow Matter? State-Dependent L2 Liquidity-State Transitions in
  Crypto Futures" — the single best title-level match to desk data (own L2 recorder + crypto
  futures + state-dependence). DEPTH-QUEUE (top).
- `2607.09426` "The Quarter-Hour Effect: Periodic Algorithmic Trading and Return Predictability" —
  intraday calendar periodicity in crypto = EVENT-AND-CALENDAR at sub-daily resolution (NOT the
  daily-bar grave). DEPTH-QUEUE.
- `2607.28323` "Optimal Execution with Passive Market Impact" + `2607.04280` "Order Splitting and
  Liquidity Replenishment for Square-Root Law" — execution-gap theory pair. DEPTH-QUEUE (one of).
- `2607.26245` "OpenMarket: A Synchronized Polymarket-Binance Dataset for High-Frequency
  Prediction-Market Research" — [DATA-LOOT] candidate, check licence/access. DEPTH-QUEUE.
- Graveyard-corroboration cluster (cheap kills to confirm, not re-open): `2607.01550` "Is Trend
  Still Your Friend?" (microstructural account of short-term trend demise), `2607.19453`
  "Predictive Extrema, Unprofitable Policies" (candle-based Binance timing audit ⇒ unprofitable),
  `2607.20093` "Retail Trader's Ruin". All three CONFIRM the 420/0 price-only kill from outside.
- Pump.fun pair (`2607.02795` sniper cohorts, `2607.02823` graduation windows) — memecoin-launch
  microstructure; desk has no Solana feed ⇒ no map, skip unless capacity argument emerges.

### 02. Divergent ground 1 — J-STAGE native-JP, query 1
- URL opened: https://www.jstage.jst.go.jp/result/global/-char/en?globalSearchKey=暗号資産%20裁定取引
  (5 hits) — NONE on arbitrage mechanics: blockchain-adoption policy piece, a tax-law translation
  (forking as non-realisation event), COVID multifractal note, DAX ownership network, 1 untitled
  Gendai Finance 2019. **This token pair is dry on J-STAGE.** Next probes: ペアトレード /
  マーケットメイク / 仮想通貨+裁定.
- Query 2: https://www.jstage.jst.go.jp/result/global/-char/en?globalSearchKey=仮想通貨%20裁定 —
  25 hits, ALL governance/tax/policy/blockchain-adoption (IEICE review 2015, ICO-law, NFT taxation,
  Venezuela report...). ZERO trading-mechanics papers. JP open-access academic finance simply does
  not publish crypto arbitrage mechanics on J-STAGE — consistent with the desk's JP-miner finding
  that the JP alpha ground is practitioner blogs/advent calendars, not journals.

### 03. q-fin.TR month-walk continued
**2026-06 (38 entries)** — URL: https://arxiv.org/list/q-fin.TR/2026-06 (summariser returned
ordinals not IDs; IDs recovered at depth stage for queue items). Depth-queue adds:
- "Dynamic Multi-Pair Trading Strategy in Cryptocurrency Markets" — the ONLY direct crypto
  pairs-trading paper in 3 months of TR. Family n=0 ⇒ DEPTH-QUEUE (top).
- "Signature-Based Optimal Execution for Statistical Arbitrage" — statarb×execution bridge.
- "Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence" — Polymarket-vs-Deribit
  relative pricing; desk HAS the Deribit surface; retail-fragmented venue = capacity moat.
  DEPTH-QUEUE.
- "Correlation emergence and the Epps effect in two coupled limit order books" — the Epps effect
  IS the sampling-synchronisation confound behind R0117's refutation ⇒ potential [ENGINE] for any
  future lead-lag design.
- "Post Selection Estimation of Sharpe Ratios" — [ENGINE] candidate (desk gauntlet uses DSR).
- "Polymarket-v1 Database" + June's "Avellaneda-Stoikov/Cartea-Jaimungal one framework",
  "Empirical Confirmation of the Square-Root Law" — noted, second tier.

**2026-05 (37 entries)** — URL: https://arxiv.org/list/q-fin.TR/2026-05. Depth-queue adds:
- `2605.04004` "Structural Limits of OHLCV-Based Intraday Signals in MNQ Futures: A Systematic
  Falsification Study" — someone else's 420/0, run INTRADAY. The desk's price-only kill was
  daily-resolution ("no SLOW price alpha"); this attacks the intraday flank on index futures.
  DEPTH-QUEUE (graveyard-extension value).
- `2605.23959` "When Alpha Disappears: One-Switch Benchmark for Decision-Time Leakage in
  Backtests" — [ENGINE] candidate.
- MM theory pair `2605.24242` (signal-adaptive execution quotes), `2605.24878` (entropy-regularised
  risk-sensitive MM) — second tier behind the July execution pair.
- Polymarket insider/leakage cluster (5 papers) — no desk Polymarket book; only the June
  options-vs-prediction-market paper keeps a Deribit map. Basis-trading paper `2605.05089` skipped:
  carry-family (hunted).
TR walk state: Aug/Jul/Jun/May DONE (128 titles read), Mar/Apr pending budget.

### 04. q-fin.ST 2026-07 (43 entries) — URL: https://arxiv.org/list/q-fin.ST/2026-07
Depth-queue adds:
- `2607.26188` "Bitcoin Runs on a Clock" — BTC calendar/periodicity. With `2607.09426`
  (quarter-hour effect) forms a two-paper intraday-calendar cluster. DEPTH-QUEUE (top for
  EVENT-AND-CALENDAR).
- `2607.27070` "Where does the criticality live? Early-warning signals" (flagged: crypto
  liquidation cascades) — desk owns a tick-level liquidation stream. DEPTH-QUEUE.
- `2607.06690` "tsbootstrap: Distribution-Free Uncertainty Quantification" — [ENGINE] candidate.
- Options/vol methods trio (`2607.05291` RV-forecast foundation models, `2607.27188` latent RND
  inverse learning, `2607.08500` SDF-from-options) — second tier; PR sweep will judge family.
- `2607.19497` trend-following science-and-practice — HUNTED family, skip. `2607.21826` bubbles —
  LPPL-shaped, no mechanism map, skip.

### 04b. q-fin.PR 2026-07 (15 entries) — URL: https://arxiv.org/list/q-fin.PR/2026-07
**ZERO crypto/Deribit/perp papers this month.** Vol-surface methods only (`2607.05011` local-vol
projection, `2607.27188` RND from irregular quotes — the latter could matter for a THIN Deribit
altcoin surface, second tier). Family verdict deferred to targeted search "variance risk premium
crypto" before declaring PR a null axis.

### 04c. Retraction Watch delta (divergent ground 2, probe 1) — WebSearch
"Retraction Watch cryptocurrency finance paper retracted 2026":
- **NEW since LIT_a:** retraction notice for "Unravelling systemic risk commonality across
  cryptocurrency groups", Finance Research Letters 65 (2024) 105633 — notice at
  https://www.sciencedirect.com/science/article/pii/S1544612326006756 (Aug 2026 wave). FRL is a
  Lucey-edited journal ⇒ verify whether this is inside the 12-paper cluster LIT_a F8 already
  recorded or an extension of the wave. DEPTH-QUEUE (open the notice).
- arXiv `2602.19197` "How Ten Publishers Retract Research" — meta-study, note only.

### 04d. q-fin.RM 2026-07 (34 entries) + q-fin.PM 2026-07 (24 entries)
- RM: https://arxiv.org/list/q-fin.RM/2026-07 — NO liquidation/crypto-cascade work (that lives in
  ST via `2607.27070`). Insurance/portfolio theory dominates. Family-relevant: none first-tier.
  `2607.03669` split-session GARCH overnight/intraday — calendar-adjacent, second tier.
- PM: https://arxiv.org/list/q-fin.PM/2026-07 — zero crypto, zero statarb. `2607.04958`
  "Look-Ahead-Freedom as Temporal Non-Interference" — backtest-leakage verification, [ENGINE]-tier
  note alongside `2605.23959`. `2607.18001` AlphaZeroBeta market-neutral RL (equities) — no map.
- Retraction delta detail (WebSearch): FRL-retracted crypto paper authors = **Rahman, Naeem,
  Yarovaya, Mohapatra** ("Commonality in Systemic Risk Across Cryptocurrencies", SSRN 4366570 is
  the preprint). Naeem/Yarovaya = the hyperprolific crypto-connectedness cluster adjacent to the
  Lucey/FRL editorial network LIT_a F8 recorded. Reason NOT visible (ScienceDirect 403 from this
  box) ⇒ [SUMMARY-ONLY] on the reason; the FACT of retraction is confirmed by the SD notice URL.

### 04e. q-fin.MF 2026-07 (50 entries) — https://arxiv.org/list/q-fin.MF/2026-07
Null for target families: 3 MM-theory papers (`2607.11328` OTC MM w/ reputation, `2607.08291`
robust sequential MM, `2607.17991` prediction-market MM), zero perp/funding/statarb/VRP. Noted:
`2607.27019` dark-pool multi-asset liquidation w/ adverse selection (execution theory, 2nd tier).

### 04f. Targeted search — stat-arb literature spine (WebSearch, 2025-2026)
- **"Copula-based trading of cointegrated cryptocurrency Pairs" — Financial Innovation 11 (2025),
  OPEN ACCESS** (https://link.springer.com/article/10.1186/s40854-024-00702-7; RePEc
  https://ideas.repec.org/a/spr/fininn/v11y2025i1d10.1186_s40854-024-00702-7.html). Claims: linear
  + nonlinear cointegration screens, copula signal beats plain cointegration/copula baselines on
  profitability + risk-adjusted. DEPTH-QUEUE (open full text — primary stat-arb candidate).
- "Pair trading strategies in the cryptoassets market: cointegration + GA-optimised thresholds" —
  **Quantitative Finance 26(5) 2026, PAYWALLED ⇒ [SUMMARY-ONLY]**
  (https://www.tandfonline.com/doi/full/10.1080/14697688.2026.2653663): 229 cointegrated pairs;
  snippet claims BTC-ETH at 0.10%/trade cost still 14.89% ann / Sharpe 2.23; ETH-LTC dies as costs
  rise; OOS = last 30% split; costs varied 0.05-0.30%.
- Frontiers Appl. Math. Stat. 2026 deep-learning pairs forecasting (open) — ML-wrapper tier, note
  only (https://www.frontiersin.org/journals/applied-mathematics-and-statistics/articles/10.3389/fams.2026.1749337/full).
- IJSRA pdf — junk-journal tier, discarded.

---

# FINDINGS — routed blocks

## [MECHANISM-CARD] 1/3 — Copula-state BTC-hedged altcoin spread reversion at 5-min (stat-arb, the n=0 family)

**Primary source (opened, PRIMARY-grade):** Tadi & Witzany, "Copula-based trading of cointegrated
cryptocurrency Pairs", *Financial Innovation* 11 (2025), open access. PDF read from
https://link.springer.com/content/pdf/10.1186/s40854-024-00702-7.pdf (via idp cookie-bounce);
HTML https://link.springer.com/article/10.1186/s40854-024-00702-7; free arXiv mirror
https://arxiv.org/abs/2305.06961; RePEc https://ideas.repec.org/a/spr/fininn/v11y2025i1d10.1186_s40854-024-00702-7.html

**Construction (exact):** 20 Binance USDT-M perps, 2021-01-01..2023-01-19. Rolling cycles:
3-week formation / 1-week trading, 104 overlapping cycles. Spread S_i = BTCUSDT − β_i·ALT_i with
β from Engle–Granger; keep EG-cointegrated alts, rank by Kendall's τ vs BTC, trade top 2. Fit
marginals (AIC) + copula family (AIC) on formation spreads; signal = conditional copula
probabilities h(1|2), h(2|1); enter when h(1|2)>0.5+α₁ AND h(2|1)<0.5−α₁ (α₁=0.20 best), exit on
reversal or week-end. Taker fee 0.04% both legs, market orders.

**Claimed results (CLAIM-grade, in-paper):** 5-min bars: net total 205.9% over ~2yr (≈75.2% ann),
Sharpe 3.77, maxDD −19.9%. Hourly: net 35–52%, Sharpe 1.0–1.8. **Honest in-paper negatives that
make the claim credible in shape:** plain cointegration-threshold at 5-min nets **−18.7% to
−88.3%** (fees eat it); return-based copula nets −40% to **−1138.9%**; KSS nonlinear variant DD
−160%. I.e. the family's base rate is NEGATIVE and only this one construction clears fees —
exactly the shape McLean–Pontiff selection produces. Treat 3.77 as the winning-tail draw.

**Mechanism (who loses, why they persist):** at 5-min horizon the alt leg is pushed off its
BTC-cointegrated level by unhedged directional retail flow on alt perps (momentum chasers,
liquidation cascades) that arrives coin-idiosyncratically and is not instantly arbitraged because
the professionals who would close it face per-pair capacity too small to pay their fixed costs —
the desk's own RU-practitioner measurement puts statarb capacity at **$3–11k/pair**, which is
invisible to funds but is EXACTLY a $5k book. The loser is the impatient taker on the alt leg; the
persistence is capacity-rationed competition, not ignorance. (This mechanism is MINE, not the
paper's — the paper offers none, which is its weakest point and the first falsifier below.)

**Replication status:** none exists (published 2025-01; 11 citers, all extensions/wrappers —
checked via https://api.semanticscholar.org/graph/v1/paper/DOI:10.1186/s40854-024-00702-7 and
WebSearch; no critique/comment found). Independent same-family evidence: QF 26(5) 2026 GA-threshold
pairs paper [SUMMARY-ONLY, paywalled, https://www.tandfonline.com/doi/full/10.1080/14697688.2026.2653663]
claims BTC-ETH survives 0.10%/trade at 14.89% ann, Sharpe 2.23, and that ETH-LTC dies as costs
rise. **Near-replication READ (landing page https://www.aimspress.com/article/doi/10.3934/QFE.2026016,
PDF https://www.aimspress.com/aimspress-data/qfe/2026/2/PDF/QFE-10-02-016.pdf): "Adaptive
copula-based pairs trading with market overlay" (QFE 10(2) 2026) — 10 Binance USDT perps, HOURLY,
2021-01..2023-12, 0.08% round-trip: market-neutral copula strategies "generated NEGATIVE net
returns after accounting for trading costs" (their Alpha-Overlay variant merely tracked
buy-and-hold). An independent group, same venue, same era, hourly ⇒ NET-NEGATIVE.** So the
family's positive evidence now rests ENTIRELY on the 5-min construction; the hourly rung is
independently dead. This narrows the desk test to 5-min-or-faster and raises the prior that the
5-min result is the selection tail.
Reference-level base rate: Krauss 2017 review + Fil–Kristoufek 2020 "Pairs Trading in
Cryptocurrency Markets" — family is fee-fragile; only high-frequency variants survive on paper.

**Desk-data mapping:** desk HAS multi-venue perp OHLCV (5-min feasible), funding panel, and own
L2/fills for slippage calibration. Reconstruction: EG β on 3-week formation windows over the
desk's perp universe, copula-h signal exactly as specified, THEN add what the paper omitted —
**funding accrual on both legs** (paper holds perp positions up to a week with funding unmodelled;
desk knows funding dominates carry P&L) and slippage at the desk's measured 66bps execution-gap
prior. Horizon: intraweek, 5-min bars. NOT price-only-daily (grave doesn't bind); BTC-hedged by
construction so the 1.54-effective-bets directional kill doesn't bind either.

**Falsifier / kill criteria (pre-registerable):** (1) adding funding accrual at desk's historical
funding panel flips net Sharpe ≤ 0 in the paper's own window ⇒ dead as published; (2) OOS
2023-02..2026-08 (fully post-sample, post-publication) net Sharpe < 1 after the −58% haircut
expectation ⇒ decayed, graveyard with decay coefficient; (3) slippage at own-fill calibration
(not 4bps taker fiction) kills it ⇒ record as execution-bound, feeds the MM-execution family
instead; (4) if edge survives only in the 2021-2022 alt-mania regime segment ⇒ regime artifact.

**Capacity note:** authors sized at 20k USDT (<1% of 5-min volume); RU-measured $3–11k/pair;
weekly top-2 pairs ⇒ book-compatible. This is a fund-invisible edge class — the desk's declared
structural lane.

**Graveyard-check verdict:** family n=0 (strategy_coverage 2026-08-05: mentioned-never-tested);
nearest graveyard row is `statarb_kalman_hedge_ratio_refinement` (Kalman hedge-β variant, killed) —
this construction uses static EG β per cycle, not Kalman, so no conflict; 420/0 price-only kill is
daily-resolution and directional — does not bind a 5-min hedged spread. CLEAR to queue.

## [MECHANISM-CARD] 2/3 — Quarter-hour clock: scheduled-algo participation leaks 4–12h order-imbalance predictability (event-and-calendar × order-flow)

**Primary source (ABSTRACT-grade, v2 ack. read):** Kim & Hansen, "The Quarter-Hour Effect:
Periodic Algorithmic Trading and Return Predictability in Cryptocurrency Futures",
arXiv:2607.09426 (q-fin.TR, July 2026). URLs opened: https://arxiv.org/abs/2607.09426 and
https://arxiv.org/html/2607.09426v2 (ack. section). Antecedent (published, replicated layer):
Hansen–Kim–Kimbrough "Periodicity in Cryptocurrency Volatility and Liquidity", arXiv:2109.12142,
J. Financial Econometrics — vol/volume periodicity across Binance/Coinbase/Uniswap "linked to
algorithmic trading and futures market funding times".

**Claim (verbatim abstract core):** bursts in volatility/volume at 1-min/5-min/15-min marks; trade-size
roundness DROPS inside bursts (algo signature); "Opening returns are predictable out of sample,
while opening order imbalance predicts returns over four to twelve hours, with much weaker effects
at finer clock-time frequencies." Six Binance perp contracts, trade-level data. No cost accounting
in the abstract — treat net-tradability as UNMEASURED, not claimed.

**Mechanism (who loses, why persist):** interval-scheduled execution (TWAP/rebalance/funding-anchored
bots) fires on round clock marks; the schedule is information leakage — the imbalance printed at
the mark reveals persistent parent flow that will keep arriving for hours. The loser is the
principal behind the clock-scheduled executor paying impact along a predictable schedule; they
persist because calendar-scheduled execution is operationally standard (cron-shaped, funding-window
anchored) and its leakage cost is invisible in the executor's own benchmarks. Crowding caveat:
QuantPedia already covers the 2021 periodicity layer (https://quantpedia.com/periodicity-in-cryptocurrencies-recurrent-patterns-in-volatility-and-volume/)
⇒ the VOLATILITY layer is public knowledge; the return-predictability layer is 2026-new.

**Replication status:** phenomenon layer replicated + published (JFEC, three venues, "intensified
over time"); the 2026 return-predictability layer carries an in-paper independent data validation
+ replication by Wade Kimbrough (acknowledged in v2 — semi-independent, same group's orbit). No
external replication yet (paper is 1 month old). Related but distinct: Wen–Bouri–Xu–Zhao NAJEF
2022 intraday momentum/reversal (SSRN 4080253).

**Desk-data mapping:** desk's own L2/microstructure recorder with OWN-CLOCK provenance (exactly
what a clock-phase study needs — the desk can resolve venue-clock vs own-clock, which R0117 taught
it to distrust), tick liquidation stream, funding panel for the funding-timestamp anchor, perp
OHLCV multi-venue. Construction: clock-phase-resolved imbalance at :00/:15/:30/:45 opens on desk
venues → forward returns 4–12h; condition on funding windows (00/08/16 UTC) separately — the
desk's funding expertise is the differentiator the paper lacks. Validation via
`libs/validation/event_study.py` treating each quarter-hour open as an event — BUT NOTE event_study
is ONE-SIDED POSITIVE (desk memory): a negative-direction effect needs the sign handled explicitly.

**Falsifier / kill criteria:** (1) desk replication of the Autocorrelation-Map dependence on own
data at matched marks fails ⇒ dead (sampling artifact); (2) imbalance→4-12h predictability exists
but net of taker fees + measured slippage < 0 at desk size ⇒ file as execution-timing overlay
(avoid trading INTO marks; still valuable for the 66bps gap program) rather than alpha; (3) effect
present only on Binance (not desk's other venues) ⇒ venue-idiosyncratic, capacity fine but single
point of failure; (4) the 4–12h horizon return sign flips across funding windows ⇒ construction
confounded with funding carry (hunted family), demote.

**Capacity note:** signal is per-mark, hours-horizon, on the most liquid perps — capacity is NOT
the binding constraint; crowding is (QuantPedia visibility). For a $5k book irrelevant; the dual
use (don't execute ON marks) has negative capacity requirement — it is pure execution hygiene.

**Graveyard-check verdict:** EVENT-AND-CALENDAR n=1 (thin, aimed); intraday flow-conditioned ≠ the
420/0 daily price-only grave; not carry/trend/premium-shaped. No graveyard collision found
(vault: no quarter-hour/intraday-periodicity rows). CLEAR to queue; cheapest first step is the
execution-hygiene use, which needs NO alpha claim at all.

## [GRAVEYARD] Liquidation-cascade early-warning alarms from critical-slowing-down — killed by its own seven-event census

**Source (ABSTRACT-grade, verbatim):** Garcia Seuma, "Where does the criticality live?
Early-warning signals are event-heterogeneous across seven crypto-perpetual liquidation cascades",
arXiv:2607.27070 (July 2026), https://arxiv.org/abs/2607.27070. Seven BTC cascades 2022–2025 incl.
the 2025-10-10 $19B event; minute price + 5-min leverage/order-flow; rolling variance + lag-1
autocorrelation (critical-slowing-down) with Kendall-τ trend tests, 39 configs/variable/event.
**Mechanism of death:** "No variable is event-invariant." CSD fires in 5/7 events and is silent in
exactly the 2 exogenous-news (tariff) crashes; the celebrated Oct-2025 leverage-lives-here reading
is "the outlier, not the rule"; "Single-event critical-slowing-down claims in crypto derivatives
are therefore fragile by construction" — cascades behave as discontinuous shock-driven
transitions, not critical ones. **Desk consequence:** any future "liquidation-cascade early
warning" proposal keyed on price/leverage variance-autocorrelation ramps inherits this kill unless
it distinguishes endogenous-buildup vs exogenous-shock event types ex ante (which is the
unobservable). **Residual live lead (one line, not a card):** the ONE population-level survivor is
taker order-flow variance COMPRESSION pre-cascade (300-onset placebo, Fisher p≈5e-6) — a
population-level prior usable for sizing rails, never a per-event alarm; desk has the taker-flow +
liquidation feeds to check the compression stat, and the desk's ruin rails (not alpha) are the
only legitimate consumer.

## [MECHANISM-CARD] 3/3 — Polymarket-vs-option-implied binary wedge on BTC threshold contracts (vol-and-options; NOT the EV-rejected DVOL carry)

**Primary source (ABSTRACT-grade, full abstract read):** Portnaya, "Do Prediction Markets Match
Option Prices? Bitcoin Threshold Evidence from Binance and Polymarket", arXiv:2606.19517 (June
2026), https://arxiv.org/abs/2606.19517 (html: https://arxiv.org/html/2606.19517v1; RePEc:
https://ideas.repec.org/p/arx/papers/2606.19517.html). 22pp, no code/data statement.

**Claim (verbatim core):** hourly-matched Polymarket Yes vs discounted risk-neutral binary from
listed Binance calls, same underlying/strike/maturity. Main Sep-2023 BTC contract: mean gap
**5.6pp** (214 hourly obs, t=6.46); pooled 3 contracts **6.3pp** (287 obs, HAC + block-bootstrap
robust); **Deribit extension: pooled 11pp**; ETH mixed. Gap persistent, **AR(1) half-life ≈ 4h**,
mean-reverting — "slow information transmission between segmented venues rather than mechanical
noise". Wedge largest at LOW option-implied probability and LONG maturity — "speculative demand
for prediction-market contracts". "A delta-hedged arbitrage proxy remains profitable after
conservative transaction costs, though with marginal statistical precision."

**Mechanism (who loses, why persist):** favourite-longshot demand — prediction-market bettors
overpay for low-probability Yes (lottery consumption), and the professionals who would sell it
rich cannot: Polymarket is US-locked/KYC-segmented from the option-MM population, has no
cross-margin against Deribit/Binance, runs on Polygon USDC rails, and carries UMA oracle
resolution risk — so option MMs also demand a gamma-warehousing premium rather than close the gap.
The loser is the longshot bettor; persistence is REGULATORY segmentation (not ignorance), which
does not decay via publication. 2026 practitioner corroboration: Q1–Q2 2026 gaps vs
Deribit-call-spread binaries "stuck around for hours"
(https://cryptodaily.co.uk/2026/07/prediction-markets-vs-options-pricing-gaps).

**Replication status:** no formal replication (single-author, 2 months old). CRITICAL boundary
evidence from an independent failure: OpenMarket (arXiv:2607.26245, see [DATA-LOOT] + [GRAVEYARD]
below) tried to trade Polymarket **15-minute** BTC binaries against Binance order flow and LOST
(−0.116 payoff units/trade net) — the FAST end of this seam is bot-patrolled and efficient; the
wedge evidence lives at long-maturity/low-prob threshold contracts. Wedge ≠ uniform.

**Desk-data mapping:** desk HAS the Deribit public options surface (the 11pp leg!); Polymarket
side is free (public API + the CC-BY OpenMarket corpus for backfill/calibration). Construction:
hourly Polymarket Yes vs Deribit-implied discounted binary on matched strike/maturity; measure the
wedge time series; trade = short rich Yes / delta-hedged Deribit replication, or the zero-execution
version: wedge as a positioning-sentiment INPUT to the options book. Horizon: hours-to-days
(4h half-life). Start MEASUREMENT-ONLY (both feeds free, no capital).

**Falsifier / kill criteria:** (1) desk-rebuilt wedge on 2026 Deribit data has |mean| < combined
fees+spread of both legs ⇒ untradable, file as measurement; (2) wedge exists but only at
maturities/probs where Polymarket book depth < $1k ⇒ capacity below even this desk, kill; (3) UMA
resolution-risk premium explains ≥ half the wedge (test: wedge vs time-to-resolution profile) ⇒
it is compensation, not mispricing; (4) execution on Polygon rails adds ops surface the
legitimacy/ops review refuses ⇒ demote to signal-only permanently. NOTE for router: Polymarket
access is jurisdiction-gated — route the TRADING leg through needs-legitimacy-review (same lane as
the KR licence reads); the MEASUREMENT leg needs no account.

**Capacity note:** threshold books thin (single-market depth often $10²–10⁴) — structurally
fund-invisible, desk-sized. Deribit hedge leg is deep. Segmentation moat means slow decay.

**Graveyard-check verdict:** VOL-AND-OPTIONS n=2 (thin, aimed). NOT the DVOL vol-carry the desk
EV-rejected 2026-08-12 (that was variance-premium harvesting; this is cross-venue relative value
on binaries). No graveyard row on prediction markets (vault search: none). CLEAR — measurement
first, trading gated on legitimacy review.

## [DATA-LOOT] OpenMarket — millisecond-paired Polymarket-BTC / Binance-BTCUSDT corpus, CC BY 4.0

**Source:** arXiv:2607.26245 (Gregory Young), https://arxiv.org/abs/2607.26245. Dataset:
https://huggingface.co/datasets/gregyoung14/openmarket-btc-polymarket · code:
https://github.com/gregyoung14/openmarket (tag v0.5.2, Rust pipeline, Parquet).
**Contents:** 727,098,247 deduplicated rows, 202 snapshots, 54 Polymarket days / 57 Binance days
(2026-02-12..2026-05-15), **2,936,031 explicit lead-lag pairs** with pairing metadata, ms-level.
**License:** CC BY 4.0 (stated on dataset page icon — verify LICENSE file at ingest).
**Desk uses:** (a) free calibration/backfill corpus for MECHANISM-CARD 3's wedge measurement;
(b) the lead-lag pairs are EXACTLY the sampling-synchronised cross-venue data R0117's
sampling-phase-aliasing critique demands — a testbed for any future lead-lag design without
desk collection cost; (c) reference implementation of ms-pairing infrastructure (Rust) for the
desk's own two-venue clock alignment. Routed as candidate for `data_axis_watchlist.md` (parent
routes; this file is my only write).

## [GRAVEYARD] Polymarket 15-min BTC binaries vs Binance order flow — author's own honest negative

**Same source (verbatim abstract):** OpenMarket arXiv:2607.26245 — "The attempt did not produce a
tradable edge: out-of-sample, a walk-forward logistic model over 43 microstructure features does
not beat, and slightly underperforms, the probability already implied by Polymarket's own order
book, and simulated trading nets **-0.116 normalized payoff units per attempted trade** under
stated fee and slippage assumptions." **Mechanism of death:** at 15-min resolution the
prediction-market book already impounds Binance microstructure — resolution-adjacent bot flow
(corroborated by the cryptodaily desk-note) makes the fast end efficient; 43-feature ML adds
nothing over the venue's own mid. **Desk consequence:** do NOT propose fast Polymarket-vs-spot
constructions; the seam's only live region is the long-maturity/low-probability wedge (card 3).
Also a base-rate datum: one more ML-microstructure-features-vs-liquid-mid failure for the
graveyard's ML-wrapper shelf.

## [GRAVEYARD] Retraction-wave extension (divergent ground 2 delta): "Datestamping the Bitcoin and Ethereum Bubbles" is RETRACTED, and the wave now reaches the Naeem cluster

Delta beyond LIT_a F8 (which recorded the Dec-2025/Jan-2026 Lucey/Elsevier cluster incl. the
707-citation FINANA paper):
1. **Corbet–Lucey–Yarovaya, "Datestamping the Bitcoin and Ethereum Bubbles", FRL 26 (2018) —
   RETRACTED**, notice https://www.sciencedirect.com/science/article/pii/S1544612326000140.
   This is the GSADF/PSY bubble-datestamping citation classic for crypto. Mechanism of death:
   compromised editorial process (receiving-editor-on-own-paper per the FINANA notice pattern:
   "review was overseen by Receiving Editor Brian Lucey despite his role as a co-author") — NOT
   adjudicated data fraud, but the empirics are now unciteable as evidence. Desk consequence: any
   bubble-dating (GSADF-on-crypto) prior sourced to this paper is orphaned; treat
   crypto-bubble-datestamping as UNVERIFIED literature, and treat the desk's own skip of
   LPPL/bubble papers this run (`2607.21826`) as further justified.
2. **Rahman–Naeem–Yarovaya–Mohapatra, "Unravelling systemic risk commonality across cryptocurrency
   groups", FRL 65 (2024) 105633 — RETRACTED** (notice
   https://www.sciencedirect.com/science/article/pii/S1544612326006756, 2026; reason text
   [SUMMARY-ONLY] — ScienceDirect 403s this box; preprint: SSRN 4366570). Extends the wave from
   Lucey-authored papers into the hyperprolific Naeem/Yarovaya crypto-connectedness cluster.
   Desk consequence: the entire FRL-connectedness genre (spillover/commonality indices on crypto)
   now carries a provenance discount on top of its already-zero desk mapping.

## [GRAVEYARD] Intraday OHLCV signal families — 14/14 fail realistic friction on MNQ (someone else's 420/0, run at 5-min)

**Source (ABSTRACT-grade, verbatim):** Mesfin, "Structural Limits of OHLCV-Based Intraday Signals
in MNQ Futures: A Systematic Falsification Study", arXiv:2605.04004,
https://arxiv.org/abs/2605.04004. 14 signal families, 947 trading days of 5-min MNQ 2021–2025,
walk-forward OOS, t≥2, n≥30, net-positive after 2-point round-trip friction, cross-year
consistency. **"None of the tested strategies satisfied all of these requirements"** — max GROSS
0.07–1.50 pts/trade vs 2-pt friction. Includes real positive controls (RTH Confluence t=5.83
n=538; London Session B t=5.15 n=289) proving the harness detects genuine edges. **Mechanism of
death: gross-per-trade an order of magnitude below friction — structural, not statistical.**
Desk consequence: extends the desk's daily-resolution price-only kill (420/0) DOWN to 5-min OHLCV
on an index future, closing the "maybe intraday price-only survives" flank cheaply (blind-
rediscovery memory flagged that flank OPEN: "price-only alpha is dead really = no SLOW price alpha
at daily resolution"). Instrument differs (MNQ ≠ crypto) — record as strong cross-instrument
prior, not a crypto measurement. Also a worked example of the desk's own L1-grade
negative-result discipline (treatment-positive controls) published externally.

## [GRAVEYARD]+watchlist — "Bitcoin Runs on a Clock": every cycle price-indicator dies on a documented ladder; a pre-registered falsification window lands Oct–Nov 2026

**Source (ABSTRACT-grade, verbatim):** Molnar, "Bitcoin Runs on a Clock: Why Every Price Indicator
Dies and the Halving Clock Doesn't", arXiv:2607.26188, https://arxiv.org/abs/2607.26188 (32pp,
code+data on GitHub). Documents that Pi Cycle / MVRV / Mayer / Puell all degraded in ONE sequence
— "precise, then early, then silent" — per-cycle oscillator maxima decline monotonically, so any
threshold calibrated on past cycles MUST stop firing; several short-horizon indicators invert
sign. **This is independent, mechanised corroboration of the desk's price-only kill and of the
MVRV/NVT/Mayer z-score graveyard rows, with the decay MECHANISM (monotone amplitude compression)
named.** The paper's positive claim (halving-clock: tops 525/546/534d post-halving, power-law
exponent ≈5.6) is n=4 cycles, retrospective-rule, self-graded "suggestive not decisive" — NOT
card-able (no mechanism, directional, ~4 effective observations). **Free natural experiment:
pre-registered windows — "a 2026 bottom (Oct 5–Nov 16)" — resolve within ~3 months of this sweep;
the desk can grade the clock hypothesis at zero cost by watching.** [ENGINE] nugget inside: their
rotation null shows HAC inference over-rejects at cycle scale (size 0.33 at nominal 0.05) —
relevant to any desk test with 4-ish independent regime observations.

## [ENGINE] Lead-lag on venue MARKS is unidentified by construction — a second, independent ground for the R0117 lane

**Source (ABSTRACT-grade, verbatim):** Seo–Cha–Son–Lee–Lee–Sung, "When Cross-Venue Agreement Is
Not Price Discovery", arXiv:2608.09188, https://arxiv.org/abs/2608.09188. On closed-window
crypto-listed equity perpetuals: marks are fixed points of an oracle operator (external anchor +
self/peer reference); "every reduced form admits infinitely many topology decompositions... so
**lead-lag and information-share estimators have power equal to size**"; only DISCLOSURE of the
mark construction or a cash-reopen anchor breaks the equivalence class. Desk consequence: R0117
died on sampling-phase aliasing; this paper supplies a SECOND, deeper kill for the same family —
even perfectly-sampled cross-venue lead-lag on marks/indices is unidentifiable when venues
reference each other's prices (crypto index/mark prices DO — mark = f(index of peer venues)).
Standing rule candidate for the lead-lag family: any future proposal must run on RAW TRADES with
own-clock provenance (desk recorder) — never on mark/index series — AND address sampling
synchronisation, or it is pre-killed twice over. This hardens the mission's lead-lag caution into
an identification argument.

## [ENGINE] Execution-program findings (grouped)

1. **Liquidity-state-first for the 66bps gap program:** Jeon, "When Does Order Flow Matter?
   State-Dependent L2 Liquidity-State Transitions in Crypto Futures", arXiv:2607.09230,
   https://arxiv.org/abs/2607.09230 — Binance BTC/ETH futures 2023–2026, top-20 L2: "the
   first-order predictive signal is the pre-event L2 liquidity state" — a coarse pre-event state
   baseline predicts post-event liquidity REGIMES; order flow only adds on top; ETH consistent,
   BTC sparse. Not alpha — an execution-timing prior: the desk's own L2 recorder can classify
   liquidity state BEFORE placing child orders; predicts fill conditions, not returns. Cheap to
   replicate on own data; 8pp single-author so treat as design-hint, not evidence.
2. **Epps effect on coupled LOBs** ("Correlation emergence and the Epps effect in two coupled
   limit order books", q-fin.TR 2026-06 listing): the Epps correlation-collapse at high frequency
   is the formal name for R0117's sampling-phase confound — any cross-venue correlation at fine
   timescale must be Epps-corrected. Reference for the lead-lag rule above.
3. **Backtest-leakage detectors:** `2605.23959` "When Alpha Disappears: A One-Switch Benchmark for
   Decision-Time Leakage" + `2607.04958` "Look-Ahead-Freedom as Temporal Non-Interference" — two
   independent 2026 formalisations of decision-time leakage checks; candidate additions to the
   desk gauntlet (the desk's own leakage defence is currently design-review, not a mechanised
   gate).
4. **Stats shelf (titles logged for the methods backlog):** `2607.06690` tsbootstrap
   (distribution-free UQ for time series); "Post Selection Estimation of Sharpe Ratios"
   (q-fin.TR 2026-06) — post-selection-corrected SR, directly relevant to a desk that selects
   before it reports; `2607.27544` "Lucky or Good? Outcome Noise, Effective Sample Size, and the
   Attribution of Skill" — same denominator discourse as the desk's effective-bets doctrine.

### 05. Divergent ground 1, query 3 — J-STAGE ペアトレード: **HIT**
URL: https://www.jstage.jst.go.jp/result/global/-char/en?globalSearchKey=ペアトレード (6 hits)
- **"Cointegration Pairs Trading between Cryptocurrency Markets" — Ohwada & Suzuki, Proc. JSAI
  Annual Conf. 2020, OPEN ACCESS.** Exactly the divergent-target: native-JP academic crypto
  pairs/cointegration. DEPTH-QUEUE (must open PDF; JSAI proceedings are open on J-STAGE).
- Also: Sato 2017 pairs-trading-on-JP-equities (Behavioral Econ & Finance, open); Higashide et al.
  2020 first-passage-time pair-portfolio formulation (JSIAM Trans., open) — theory, may inform
  exit-rule design; bond-market arbitrage-detection JSAI 2016. Others off-family.

## [GRAVEYARD]-adjacent corroboration (divergent ground 1 primary yield) — JSAI 2020: cointegration between crypto pairs is UNSUSTAINABLE

**Source (landing page read; PDF open on J-STAGE, 409K, Japanese):** Ohwada & Suzuki (Ibaraki U.),
"Cointegration Pairs Trading between Cryptocurrency Markets", Proc. JSAI Annual Conf. 2020, DOI
10.11517/pjsai.JSAI2020.0_2L4GS1305,
https://www.jstage.jst.go.jp/article/pjsai/JSAI2020/0/JSAI2020_2L4GS1305/_article/-char/en
2-page conference note; no performance numbers on the landing page. Its ONE substantive claim:
"because of the possibility that the cointegration is unsustainable, the diversified investment is
important to stabilize profits." **Value to the desk:** an independent JP-academic 2020 prior that
crypto cointegration RELATIONS BREAK — which is precisely why MECHANISM-CARD 1's construction
re-selects pairs every cycle and why any desk test must penalise β-staleness. Not evidence FOR the
family; evidence about its failure mode. [ABSTRACT]-grade.

## [NULL] blocks — searched seams that yielded nothing (each with per-axis evidence)

1. **J-STAGE crypto-arbitrage mechanics:** 暗号資産+裁定取引 → 5 hits, all policy/tax (URL in §02);
   仮想通貨+裁定 → 25 hits, all governance/tax/adoption (§02); 仮想通貨+マーケットメイク → 1 hit
   and it is TSE equity tick-size research (Uno–Shibata–Tobe, Gendai Finance 47 (2025), DOI
   10.24487/gendaifinance.470001 — open PDF; incidental MM datum: MM-HFT liquidity provision drops
   when relative tick >10bps — one-line input to venue/symbol selection for any future quoting
   sleeve). VERDICT: JP open-access ACADEMIC finance does not carry crypto trading mechanics; the
   JP ground's yield stays where the JP-miner found it (practitioner blogs/advent calendars).
   ペアトレード was the exception and it produced the JSAI note above.
2. **q-fin.PR as a crypto-vol source:** 2026-07 = 15 papers, ZERO crypto/Deribit (§04b). Targeted
   search resolves the family instead to: Almeida–Grith–Miftachov "Risk Premia in the Bitcoin
   Market" (https://arxiv.org/abs/2410.15195; BVRP time-varying, high in LOW-vol regimes) and
   Atanasova et al. "What Do Crypto Options Tell Us?" (SSRN 6771170, May-2026; VRP positive,
   persistent, option-implied factors predict BTC excess returns). BOTH are VRP-harvesting /
   premium-shaped — the construction family the desk EV-rejected 2026-08-12 (DVOL vol-carry,
   EV 0.0003). NOT re-carded per mission; logged as the breadth-evidence source if the DVOL
   watchlist trigger ever fires. Vol-options family is instead served by MECHANISM-CARD 3
   (relative value, different mechanism).
3. **ATTENTION-SENTIMENT:** across all 8 subcats + searches, nothing with a sharp mechanism —
   only generic NLP wrappers (`2607.28127` FinSMART, `2607.13968` transformer news sentiment,
   `2607.09121` LLM-RAG fundamentals). Desk prior (weak family, graveyarded attention rows)
   stands; NO card manufactured. Per-axis evidence: TR/ST/GN listings above, each flagged
   sentiment entries, none crypto-mechanism-bearing.
4. **q-fin.RM/PM/MF/CP as family sources this window:** each swept 2026-07 in full (§04d/§04e,
   §07 CP/GN); zero first-tier family papers beyond cross-listings already handled in TR/ST.
   CP yielded second-tier options-methods only (`2607.29220` arb-aware IV-surface refinement,
   `2607.25353` crash bounds from bid-ask quotes — parked for a Deribit-surface methods pass).
5. **Stablecoin axis (desk has USDT/USDC series):** GN-07 has two policy-grade papers
   (`2607.08524` Austrian CASP transaction-level stress evidence, `2607.09514` MiCA gateways) —
   official-sector-adjacent priors, no trading construction. Noted for the stablecoin data axis,
   no card.

### 06. Subcategory checklist (close-out state)
| Subcat | Months walked | Verdict |
|---|---|---|
| q-fin.TR | 2026-05/06/07/08 (128 titles) | RICH — cards 1-3 all sourced here or via its cross-lists |
| q-fin.ST | 2026-07 (43) | 2 depth items (clock→graveyard+watchlist; criticality→graveyard) |
| q-fin.PM | 2026-07 (24) | null + 1 engine title |
| q-fin.RM | 2026-07 (34) | null |
| q-fin.MF | 2026-07 (50) | null (3 MM-theory noted) |
| q-fin.CP | 2026-07 (42) | second-tier methods only |
| q-fin.PR | 2026-07 (15) | zero-crypto null; family resolved via targeted search |
| q-fin.GN | 2026-07 (21) | stablecoin-policy priors; 1 engine title |
Coverage honesty: TR walked 4 months; the other 7 subcats walked 1 full month each + covered
2026-02..2026-08 via targeted searches (stat-arb, VRP, quarter-hour, prediction-vs-options,
retraction sweeps). arXiv API 429 forced listing-page mode; a 6-month exhaustive walk of all 8
cats was traded for depth on the queue — the trade is recorded, not hidden.

---

## DEPTH (per lead: surface / citations-2-level / replication-scanned / exhausted — and what depth surfaced that the surface didn't)

- **Tadi–Witzany copula pairs (card 1): citations-2-level + replication-scanned + PRIMARY full-PDF.**
  Depth surfaced what the surface never would: an independent 2026 near-replication (QFE
  market-overlay paper) finding the HOURLY version net-NEGATIVE at 0.08% RT costs — the family's
  live region collapsed to 5-min-or-faster; plus the paper's own buried negatives (plain
  cointegration −18.7%..−88.3% net) that reframe the headline Sharpe 3.77 as a selection tail.
- **Quarter-hour effect (card 2): replication-scanned + lineage-traced.** Depth surfaced the
  in-paper independent validation (Kimbrough, v2 ack.), the published JFEC antecedent tying
  periodicity to FUNDING TIMES (the desk's home turf), and QuantPedia's coverage of the 2021
  layer (crowding warning). Full-text estimator extraction still owed.
- **Portnaya wedge (card 3): replication-scanned + boundary-mapped.** Depth surfaced the seam's
  FAILURE region: OpenMarket's own 15-min-binary attempt lost money (−0.116/trade) ⇒ the wedge
  lives only at long-maturity/low-prob; plus 2026 practitioner corroboration vs Deribit.
- **OpenMarket corpus (loot+graveyard): surface+license-checked** (CC BY 4.0, HF+GitHub, verify
  LICENSE at ingest).
- **Cross-venue-marks unidentifiability (engine): surface** — but the abstract IS the theorem
  statement; consumed as an identification rule for the lead-lag lane.
- **Liquidation-cascade CSD (graveyard): surface** — the paper is itself the depth (39 configs ×
  7 events × placebo).
- **Retraction wave (graveyard): citations-2-level vs LIT_a** — delta isolated (Datestamping +
  Naeem-cluster FRL); retraction REASONS remain [SUMMARY-ONLY] (ScienceDirect 403).
- **OHLCV-intraday falsification, Bitcoin-clock decay ladder (graveyards): surface, verbatim
  abstracts** — both are self-contained negative results with controls/nulls.
- **JSAI 2020 cointegration note (divergent): landing-page only** — 2pp Japanese PDF unopened;
  its instability caveat consumed. NOT exhausted.
- **Overall: no lead advanced on an unread summary without being marked [SUMMARY-ONLY]; ~45
  fetches spent; every claim above carries the exact URL opened.**

## NEXT-GROUND (for the next litminer rotation)

1. **Portnaya full text** (arXiv HTML is open) → extract the delta-hedged proxy construction and
   the maturity/probability wedge profile → draft the MEASUREMENT-ONLY pre-registration for the
   Deribit-vs-Polymarket wedge (both feeds free; no capital; legitimacy review only gates the
   trading leg).
2. **Hansen–Kim full text** → extract the Autocorrelation Map estimator into the event-study
   methods backlog; then the desk-data replication at own-clock marks.
3. **QFE adaptive-copula PDF** (saved locally this run at
   `~/.claude/projects/-home-quant-quant-platform/*/tool-results/webfetch-1786499378799-0ko1jt.pdf`
   but NO pdf tooling on the box — poppler/pypdf absent; landing-page numbers used instead).
   Box-capability gap worth an ops note: PDFs are fetchable but not locally readable.
4. **arXiv walk completion:** TR 2026-03/04; ST/PR 2026-02..06 — the enumeration debt left by
   trading breadth for depth this run.
5. **Carried strandings from the 20260805 header, now FIVE runs old:** S1 SEC-interventions FRL
   numbers; S2 IMF WP 2023/163 mirror; S3 negative-carry computation inside arXiv 2510.14435.
6. **CiNii proper** (cir.nii.ac.jp full-record sweep) — J-STAGE is done this run; CiNii itself
   untouched, and the JP thesis layer (bachelor/master theses on crypto statarb) is where JP
   honest negatives live per the theses-layer seat.
7. **Retraction Watch database mechanically:** the RW dataset is public via Crossref — pull the
   full crypto/finance slice as CSV instead of search-snippet archaeology; grade reasons
   (editorial-process vs data-fraud) — the desk's provenance discount should differ by class.

**Run status: COMPLETE. 3 mechanism cards (stat-arb 5-min copula pairs; quarter-hour clock;
Polymarket-Deribit wedge), 1 data-loot (OpenMarket CC-BY ms-corpus), 5 graveyard entries
(hourly-copula-pairs near-replication kill; 15-min-binary ML failure; liquidation-CSD alarm kill;
OHLCV-intraday 14/14; retraction-wave extension incl. Datestamping), 3 engine blocks (lead-lag
mark-unidentifiability rule; execution liquidity-state-first + leakage detectors + stats shelf;
HAC-over-rejection nugget), 6 documented nulls. Zero candidates manufactured; every carded claim
cites the exact URL opened.**




