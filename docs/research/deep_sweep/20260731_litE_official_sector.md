# Deep-sweep: LIT-E — Official-sector practitioner research (BIS / IMF / Fed / NY Fed)
_Date: 2026-07-31. Miner: literature deep-mining sub-agent, first-ever visit to this family._
_Charter: mechanisms not summaries; every mechanism mapped to desk data; §27 data-loot; published ≠ true
(McLean–Pontiff −58% post-publication haircut standing prior); NK-005 routing (no SSRN/ScienceDirect/Wiley,
no bot-gate defeat — blocks logged and routed around)._

**Desk data inventory referenced throughout:** multi-venue perp funding (incl. BitMEX 2016–2026 full
funding archive), open interest, liquidation stream, perp basis, 4-venue spot tape
(Coinbase/Kraken/Bitstamp/Bitfinex), Binance/OKX/Upbit historical archives, FRED macro, stablecoin
mint/burn on-chain reconstruction path (USDT/USDC treasury Transfer events).

**Graveyard cross-check baseline (read first, per discipline):** regional-premium timing class DEAD
(kimchi refuted 2026-07-30); DeFi TVL/activity aggregates DEAD (daily + weekly xsec); MVRV/exchange-flow
daily DEAD; positioning-contamination law (price-derived positioning proxies) STANDING; FRED-macro
conditioning overlays on the carry book DEAD (btc_correlation_regime_carry_conditioning EV-gated,
vol-target overlay HURTS); stablecoin_mint_burn_supply_signal EV-gated 2026-07-19 (`narrow_breadth` —
reopening requires a MATERIALLY NEW mechanism, e.g. run/depeg asymmetry, not a supply-level signal);
funding_momentum + cross-exchange funding dispersion DEAD.

---

## STATUS: COMPLETE (all 6 leads resolved; see SWEEP STATUS at end for verification grades)

## Lead 1 — Schmeling–Schrimpf–Todorov "Crypto Carry" (BIS WP 1087) — PRIMARY TEXT READ IN FULL
_Status: RESOLVED at primary-text level. Full PDF (Oct 1 2025 revision, the Management Science version)
downloaded from bis.org and text-extracted (97.5k chars); main text + references read end to end._

**URLs opened:** https://www.bis.org/publ/work1087.htm (abstract page) and
https://www.bis.org/publ/work1087.pdf (full text). Both fetched 2026-07-31, no blocks.

**What carry IS here (construction).** NOT perp funding: annualized 1m/3m constant-maturity
FIXED-DATE futures basis, daily, BTC+ETH, Mar 2019–Jul 2024, from Skew + Coinmetrics, across
Binance/OKEx/FTX/Huobi/BitMEX/Deribit/CME (CME from Aug 2020, Bloomberg from Jan 2018). Organizing
equation: carry = f−s = (r−r*) + u − ψ + ε, where r* = spot yield (Aave lend / staking), ψ = net
convenience yield. Empirically r, r*, u explain almost nothing → carry ≈ −(net convenience yield):
a large, volatile INCONVENIENCE of holding spot vs futures, same family as the Treasury
cash-futures inconvenience (Schrimpf–Shin–Sushko 2020, Duffie 2020).

**Stylized facts (exact numbers).** 1m BTC carry avg ≈8% p.a. OKEx / 6.4% CME; maxima ≈55% / 45%;
avg across exchanges Apr 2019–Jul 2024 ≈7% p.a. (~10× S&P 500 carry, ~12× UST carry; correlation of
crypto carry with other asset classes' carry ≈ 0). Right-skewed, AR(1) just under 1 (very
persistent daily). Panel variance decomposition: time FE R² = 88% (BTC) / 93% (ETH); exchange FE
< 0.5% — carry is ONE market-wide factor, not venue idiosyncrasy. CME carry least correlated with
crypto-native venues (segmentation). BTC & ETH carry highly correlated; cross-venue corr > 0.90
among crypto-native. Total BTC futures OI Jul 2024: $20.8bn in-sample ($25.5bn with
ByBit/Bitfinex/CoinFlex); 78% of OI and 93% of volume on crypto-native venues.

**Mechanism (who pays, who collects, why it persists).**
- PAYERS: smaller, trend-chasing, attention-driven investors buying leveraged upside via futures.
  Evidence: ΔGoogle-searches ("bitcoin futures" etc.) → carry with R²=12% on OKEx but only 1%/insig
  on CME; past-week and past-month BTC returns strongly positive predictors of carry; signed
  futures volume and OI (price-pressure proxies) positive, OI stays significant in full spec. CFTC
  COT: NONREPORTABLES (small accounts) are net LONG on average and their position increases track
  carry UP; leveraged funds + dealers net SHORT (leveraged funds' longs negatively correlated with
  carry). Causal wedge: CME micro-BTC futures introduction (3 May 2021) DiD → CME carry +11%
  relative to unaffected venues. Payers persist because leveraged long exposure is the PRODUCT they
  want (max leverage up to 100–125× crypto-native vs 2× CME) and spot is inconvenient
  (custody/regulatory/leverage constraints) — demand recurs with each attention boom.
- COLLECTORS (and why they under-deploy): cash-and-carry arbitrageurs face (i) NO cross-margining —
  CME won't hold spot, so capital is pledged twice and futures-leg losses aren't offset by the spot
  leg; (ii) opaque crypto-native margin rules (pre-collapse FTX capped max loss at $30k → $1m short
  liquidated on a 3% BTC rise); (iii) funding risk à la Brunnermeier–Pedersen. Futures leg: excess
  return 2–3%/MONTH but vol ~17%/month; AT 10× LEVERAGE THE FUTURES LEG WOULD HAVE BEEN LIQUIDATED
  IN OVER HALF THE MONTHS IN SAMPLE. The "risk-free" carry is priced compensation for
  forced-liquidation risk plus segmentation rent.

**The two desk-usable empirical hooks.**
1. CARRY → SHORT-LIQUIDATION PREDICTOR (Table 7): "a rise in standardized carry by 10% predicts a
   22% increase in total sell liquidations (relative to total open interest) over the next month."
   Sell (short-position) liquidations ONLY — buy-side not predicted. Robust in the subsample where
   closing early is unprofitable (i.e., it's forced liquidation, not profit-taking). High carry
   also comes with RISING 1m implied vol (crash-insurance cost). Abstract-level companion claim:
   "high crypto carry predicts future price crashes."
2. ACCESS-PRODUCT STRUCTURAL BREAKS COMPRESS CARRY (Table 5 DiD): spot BTC ETF launch (Jan 2024)
   cut carry ~3pp on ALL exchanges and an ADDITIONAL ~5pp on CME = −36% and −97% of the ~7.5% mean.
   The carry premium is regulation-segmentation rent and each access product (ETF, in-kind
   redemption, future cross-margining) structurally shrinks it.

**Data mapping to desk.** Desk HAS: perp funding multi-venue (incl. BitMEX 2016–2026), perp basis,
OI, LIQUIDATION STREAM, 4-venue spot tape. Hook 1 is directly testable on desk data at better
granularity than the paper (they used monthly liquidation aggregates from Skew/Coinmetrics; desk
has the tick liquidation stream): basis/funding level (standardized) → forward short-liquidation
intensity → and the desk-only extension the paper never runs: whether the liquidation flush marks
the LOCAL TOP of carry (entry-timing for the funding book — collect after the flush, stand down
into rising-carry blowoffs). Hook 2 is a capacity/decay model input for the LIVE funding book:
post-Jan-2024 the fixed-basis premium is structurally thinner; desk should expect funding-carry
expected returns below pre-2024 backtest levels and watch further access events. NOT a new sleeve;
a conditioning fact for sizing/expectations.

**Graveyard cross-check.** Desk's `funding_momentum` kill (momentum OF funding) is untouched — this
is carry LEVEL → liquidation flow, not funding momentum. `cross-exchange funding dispersion` kill
untouched (paper says dispersion is tiny: exchange FE <0.5% — consistent with the desk's kill).
The trend-chasing→carry regression direction (returns→carry) is the OPPOSITE direction to any
carry→return timing signal, so no collision with positioning-contamination law, but any desk test
of hook 1 must de-contaminate carry vs same-period returns per standing rule.

**Replication status / decay risk.** Published (Management Science acceptance-grade); BIS + CEPR
authors; DiD designs are the credibility core. Decay: the paper ITSELF documents the decay channel
— ETF launch already removed 36–97% of the premium in its own sample. McLean–Pontiff −58% haircut
applies ON TOP for any timing use. The liquidation-prediction hook is a FLOW relationship (not a
return anomaly), which typically decays slower than return predictability. No failed replication
found (searched); concurrent independent corroboration exists (He et al. 2022; Christin et al.
2022 — perp versions, chased below).

**Depth line:** Level 0 = WP1087 primary text in full. Level 1 (backward): Christin et al. "The
crypto carry trade", He–Manela–Ross–von Wachter "Fundamentals of Perpetual Futures", Angeris et al.
"A primer on perpetuals", Koijen et al. "Carry" (JFE 2018, known). Level 2 (forward): 2026 arXiv
"Implied ETF Carry Rates and the Limits of Arbitrage in Segmented Bitcoin Markets" (2605.29309).
Chase status below.

### Lead 1 citation-chase results (depth levels 1–2)

**He–Manela–Ross–von Wachter, "Fundamentals of Perpetual Futures"** —
https://arxiv.org/abs/2212.06888 + https://arxiv.org/html/2212.06888 (both opened; abstract page +
HTML full text mined via targeted extraction). The PERP version of the mechanism. Data: Glassnode
funding rates + CoinGecko volumes, Jan 2020–Dec 2022, wash-trading venues excluded (median daily
perp volume $17.8bn 2020 → $132bn 2021 → $101.9bn 2022). Findings: mean ABSOLUTE perp-spot
deviations ≈60–90% p.a. across coins (mean deviation ~0/insignificant — it's two-sided clustering,
not a one-way premium); funding ≈ avg perp-spot spread over preceding 8h + clamp; random-maturity
arbitrage (open when spread exceeds cost-tier bounds, close on normalization) Sharpe 1.8 at retail
costs → 3.5 at maker-zero fees, alphas survive 3- and 5-factor models. TWO DESK-CRITICAL FACTS:
(a) deviations COMOVE strongly across coins (a shared funding/liquidity factor — matches WP1087's
88–93% time-FE); (b) deviations DECLINE ~11%/yr — a measured structural decay rate for
funding-basis alpha as arb capital arrives. Replication status: widely cited, no failed replication
found; presented Utah Winter Finance 2024.

**Christin–Routledge–Soska–Zetlin-Jones, "The crypto carry trade"** (CMU WP 2022) — located via
search only; primary text NOT yet read (no open copy found this session; NOT SSRN-routable).
Search-level claims (SUMMARY-ONLY, do not graveyard): long-spot/short-perp carry profits driven by
funding rate; attributed to differences of opinion + leverage constraints. Cited in WP1087 as
finding "high Sharpe ratios" for short-perp carry.

**Forward level 2 — "Cryptocurrency as an Investable Asset Class: Coming of Age"** (survey, arXiv
2510.14435v2, opened https://arxiv.org/html/2510.14435v2): computes the short-perp/long-spot BTC
carry Aug 2020–May 2025: funding-return mean ≈8% p.a. at 0.8% vol, full-sample Sharpe 6.45 —
falling to 4.06 in 2024 and **NEGATIVE in 2025**. [SUMMARY-grade numbers from a survey, but the
direction matches WP1087's causal ETF result.] ⇒ THE LIVE QUESTION FOR THE DESK'S FUNDING BOOK:
verify on the desk's own multi-venue funding archive whether post-2024 realized carry confirms
this compression. Also flagged forward: Ackerer–Hugonnier–Jermann "Perpetual Futures Pricing"
(arXiv 2310.11771, theory) and AEA-2026 "Perpetual Futures and Basis Risk" (not yet open-access).

**Depth reached (Lead 1): 3 levels** (WP1087 primary → backward He et al. primary / Christin et al.
summary-only → forward 2025 survey + 2026 papers identified).

## Lead 2 — Auer–Claessens regulatory-news event studies — QR PRIMARY READ; persistence chased
_Status: QR feature read at primary level via bis.org; expanded WP is DALLAS FED GI WP 381 (not BIS
WP 811 — that number is Auer's "Embedded supervision", correction logged); post-2018 persistence
followed into 2024–2025 literature._

**URL opened:** https://www.bis.org/publ/qtrpdf/r_qt1809f.htm (Auer & Claessens, "Regulating
cryptocurrencies: assessing market reactions", BIS Quarterly Review Sep 2018). Also attempted
https://www.bis.org/publ/work811.htm — WRONG PAPER (embedded supervision), logged.

**Event taxonomy (the desk-wireable part).** 151 regulatory news events, Jan 2015–Jun 2018, Reuters
newswire, jurisdictions: CN/IN/JP/UK/US + EU/international bodies. Categories: (1) LEGAL STATUS —
bans, securities treatment, currency recognition; (2) AML/CFT & infrastructure; (3)
INTEROPERABILITY with regulated finance (fiat ramps, ETF/derivative listings, banking access); (4)
general warnings [NULL — no significant effect]; (5) CBDC statements [NULL — no significant
effect].

**Effect sizes + windows (exact).** Favourable events: +0.33% in the 120-minute window, +1.52% over
24h. Unfavourable: −0.32% (120min), −3.12% (24h). AML/CFT: ~−4pp MEDIAN over a 10-DAY window (−24pp
on multi-event days). Interoperability restrictions: −6.4pp over 10 days. Legal-status is the
strongest category (bans and securities classification most negative; NEW TAILORED FRAMEWORKS
POSITIVE). The 120min→24h→10d gradient is the KEY microstructure fact: the full response takes DAYS
— i.e., a documented UNDERREACTION/drift, not an instantaneous jump. Segmentation: responses are
jurisdiction-specific (they cite the kimchi premium >50% at peaks — NOTE: desk's regional-premium
class is DEAD; the premium is NOT the tradeable object here, the drift is).

**Post-2018 persistence (level-1 forward chase).** Search located: "Uncertain Regulations, Definite
Impacts: The Impact of the U.S. SEC's Regulatory Interventions on Crypto Assets" (FRL 2024; author
copy hosted ON SEC.GOV: https://www.sec.gov/files/ctf-input-arte-2025-02-19.pdf — fetch pending
below): search-level numbers −5.2% within 3 days of SEC intervention announcements, deepening to
−17.2% over 30 days — the drift SURVIVED and got BIGGER in 2021–2024 samples. Also flagged:
Feinstein–Werbach (J. Fin. Regulation 2021) critique claiming little effect on trading VOLUMES
(chase pending). 2023 saw a positive-CAR regime around ETF-approval news (regulatory GOOD-news era)
per 2026 J. Asset Mgmt paper (Springer, summary-level).

**Data mapping to desk.** Desk has an event-study gate and 4-venue spot tape + Binance/OKX/Upbit
archives back a decade. The event TIMELINE is reconstructable free from regulator sites (SEC
press releases + litigation releases, CFTC, ESMA, PBoC/CSRC circulars, FSA JP, Korea FSC) — the
taxonomy above is the labeling scheme (5 classes, 2 of which are pre-registered NULLS: warnings,
CBDC). Mechanism card: multi-day post-event drift AFTER classifiable regulatory events, long
favourable / short unfavourable, 24h–10d horizon. Who loses: slow-moving holders who process legal
news over days (retail; segmented-jurisdiction holders); why persistent: legal analysis is genuinely
slow, arbitrage across jurisdictions is capital-controlled, and the event class recurs.

**Replication status.** QR feature (not peer-reviewed) BUT independently confirmed direction+drift
by a 2024 FRL paper on a different event set (SEC interventions 2021+) with LARGER magnitudes.
Effects are event-conditional (rare-ish events, ~150 over 3.5yr ⇒ ~4/month globally) — capacity
tiny, but the desk's event gate is built for exactly this. McLean–Pontiff haircut applies; drift
magnitude −58% still leaves multi-pp moves on the unfavourable tail.

**Depth reached (Lead 2): 2 levels** (QR primary → SEC-intervention FRL paper + Feinstein–Werbach
critique identified; SEC.gov copy fetch in progress).

## Lead 3 — NY Fed / Fed Board stablecoin runs & flows — RESOLVED (primary via Boston Fed mirror)
_Status: Liberty Street post read; sr1073 page 403'd from this box (LOGGED, no bot-gate defeat
attempted) → routed around via Boston Fed full-text PDF per NK-005._

**URL opened:** https://libertystreeteconomics.newyorkfed.org/2023/07/runs-on-stablecoins/ (fetched
OK). May 2022 Terra episode numbers: UST $0.9964→$0.7934 May 7–8; LUNA supply 365m (May 9) → >6tn
(May 13); sector-wide May 1–16: total circulation −15.58bn units / mcap −$25.63bn; FLIGHT-TO-SAFETY
DECOMPOSITION: algorithmic stables −8.70bn units, crypto-collateralized −2.25bn, **US-based
(USDC/BUSD) +3.88bn** — runs are ROTATIONS between stablecoin classes, not exits from crypto.
Attempted https://www.newyorkfed.org/research/staff_reports/sr1073 → HTTP 403 (LOGGED). ROUTED
AROUND successfully: Boston Fed hosts the full paper —
https://www.bostonfed.org/-/media/Documents/Workingpapers/PDF/2023/sra2302.pdf (SRA 23-02, "this
version June 2025") — downloaded and text-extracted (1.02M chars incl. appendices); core sections
read via targeted extraction.

**sr1073/SRA23-02 primary-text extraction (the run mechanism, exact).**
- STRUCTURE: asset-backed stablecoins = 96% of industry mcap (Dec 2022). Trading is ETF-like
  (secondary market dominant; only restricted primary-market participants can mint/redeem at $1
  fixed price with the issuer). Ma–Zeng–Zhang (2023) theory result they build on: THE FIXED-PRICE
  PRIMARY WINDOW CREATES A FIRST-MOVER ADVANTAGE when backing < circulation — unlike ETFs (floating
  NAV), stablecoins inherit MMF-style run incentives, transmitted from primary to secondary market.
- FLIGHT-TO-SAFETY IS DIRECTIONAL-BY-RISK-SOURCE (the key novel fact): design = 12 stablecoins,
  Jan 2021–Mar 15 2023, stress days = 5th percentile of BTC daily returns, local projections of
  cumulative %-flows by type (US-based / offshore asset-backed / crypto-collateralized /
  algorithmic; categories mutually exclusive+exhaustive). CRYPTO-NATIVE stress (Terra May 2022):
  outflows from offshore+algo+crypto-backed → INFLOWS to US-based (govt-MMF analog); Frax lost 45%
  of May-1 mcap by May 16; UST mcap −95%. TRADFI stress (SVB Mar 2023): DIRECTION INVERTS — run OUT
  of USDC (held $3.3bn of its $42.1bn reserves at SVB; ~77% was T-bills at BNY/Customers) INTO
  offshore USDT/TUSD; **Tether traded UP to $1.03**; USDC traded down to ~$0.88 on secondary while
  the authors are "not aware that any USDC tokens were redeemed for less than $1 in the primary
  market". DAI+Frax dragged down mechanically (USDC collateral). Cross-type flow matching: 2022 run
  regression of US-based inflows on offshore outflows R²≈0.60; 2023 (inverted) R²≈0.70 on large
  chains — near-1:1 rotations, NOT exits.
- BLOCKCHAIN-LEVEL: 90% of stablecoins trade on Ethereum/BSC/Tron; during runs, flows rotate
  WITHIN large chains but EXIT small chains entirely (small chains perceived risky as a class).
- ABSTRACT-LEVEL (search-verified): they estimate a "break-the-buck" threshold at $1 below which
  redemptions ACCELERATE — the discrete nonlinearity; MMF parallel.

**Mechanism card (desk mapping).** The desk's USDT/USDC treasury-Transfer mint/burn reconstruction
is EXACTLY the primary-market flow variable this paper studies. Tradeable structure is EPISODIC,
not daily: (1) secondary depeg > primary par ⇒ arbitrageurs buy discount + redeem at par ⇒ BURN
SPIKES are the real-time run signature (observable on-chain hours before aggregators reprice
risk); (2) the burn/mint ROTATION PAIR (USDC burn + USDT mint vs the reverse) CLASSIFIES the risk
source (TradFi-reserve vs crypto-native) — which the sr1073 evidence says determines flow
direction and which stablecoin trades at premium; (3) during runs the depeg premium of the SAFE
coin ($1.03 USDT 2023; USDC premium in 2022) is a flight-intensity gauge on the desk's own 4-venue
USD/USDT tape. Who loses: holders who redeem late (redemption queue/banking-hours friction) and
secondary-market sellers at the discount trough; why persistent: run equilibria are inherent to
fixed-NAV + fractional-liquidity structures (the MMF literature's 3 episodes say this NEVER fully
prices in), and the primary window stays restricted.
**Graveyard note:** `stablecoin_mint_burn_supply_signal` (EV-gated, narrow_breadth) is a DAILY
SUPPLY-LEVEL signal kill — the run/rotation mechanism here is materially different (episodic,
directional-by-risk-source, nonlinear at $1) and is a CONDITIONING/interpretive layer for the
already-running stablecoin_flows family, not a new daily sleeve. No collision.

**Replication status.** Staff report revised June 2025 (multi-Fed author team), event studies +
local projections; the two episodes are the population of large runs (n=2) — mechanism credible,
statistical power inherently episodic. Independent corroboration: Oefele–Baur–Smales (Econ Letters
2024) same March-2023 flight-to-quality result; Liu–Makarov–Schoar (NBER 31160) Terra anatomy
(who ran first — level-2 chase target); Lyons–Viswanath-Natraj (JIMF 2023) mint/burn↔peg arbitrage
(level-2 chase, NBER w27136 route).
**Data loot:** DefiLlama per-chain stablecoin circulation (their chain-level flow source (cited as
"DeFiLlama"), free API); CoinGecko stablecoin mcap series (their Fig 10 source, free).

**Depth (Lead 3): 2 levels done** (LSE post + sr1073 primary → corroborations identified;
Lyons–Viswanath-Natraj chase pending below).

## Lead 4 — BIS DeFi/CeFi leverage & liquidations (Aramonte–Huang–Schrimpf line) — RESOLVED at QR level
**URL opened:** https://www.bis.org/publ/qtrpdf/r_qt2112b.htm ("DeFi risks and the decentralisation
illusion", BIS QR Dec 2021, fetched OK). Mechanism: DeFi lending is overcollateralized BECAUSE
collateral is volatile; positions auto-liquidate at threshold collateral ratios; liquidators sell
collateral into falling prices → further liquidations (cascade); Sep 2021 crash as worked example
("forced liquidations of derivatives positions and loans on DeFi platforms accompanied sharp price
falls and spikes in volatility"); DeFi loans ~$20bn late 2021; stablecoins are the leverage bridge
(~$120bn circulation late 2021). QR is mechanism-rich but NUMBERS-THIN on liquidation→price
elasticities. Level-1 successors located via search: **Heimbach–Huang "DeFi leverage"** (BIS,
wallet-level: aggregate leverage 1.4–1.9×, largest wallets higher; leverage driven by LTV caps +
borrow cost; near-liquidation borrowers TILT TOWARD VOLATILE COLLATERAL — gamblers-for-
-resurrection fact); OECD 2023 "DeFi liquidations: volatility and liquidity" (liquidation↔vol
elasticities); BIS Bulletin 57 (DeFi lending, intermediation without information). SNB-hosted
slides: https://www.snb.ch/dam/jcr:88f29f5c-2da2-427a-836a-558dc4d1c314/sem_2024_05_24_huang.n.pdf.
**Desk mapping:** desk's liquidation stream is CEX-perp, not DeFi — the BEST liquidation mechanism
for desk data is already Lead 1's carry→short-liquidation regression (WP1087 Table 7). The DeFi
line's transferable content: liquidation cascades are COLLATERAL-side (sell pressure is mechanical,
price-insensitive, and clusters at known LTV thresholds) — on-chain liquidation-threshold maps
(Aave/Compound public state) would give the desk forward-looking cascade-level maps, but that is a
NEW DATA BUILD (desk lacks on-chain protocol state); named as the missing dataset. No graveyard
collision (desk's DeFi kills are TVL/activity aggregates, not liquidation mechanics).
**Depth (Lead 4): 1.5 levels** (QR primary + successors located, not primary-read — budget routed
to higher-yield leads).

## Lead 4 — BIS DeFi/CeFi liquidations & leverage (Aramonte–Huang–Schrimpf line)
_Status: pending._

## Lead 5 — BIS retail-adoption / app-download database (Auer–Cornelli–Doerr–Frost–Gambacorta, WP 1049)
_Status: RESOLVED at abstract+page level (dataset located and confirmed downloadable)._

**URL opened:** https://www.bis.org/publ/work1049.htm (fetched OK). "Crypto trading and Bitcoin
prices: evidence from a new database of retail adoption." THE DATASET: daily crypto-exchange APP
USAGE by country — 95 countries, 2015–2022 — **published as downloadable files on the paper page
(xlsx / csv / Stata .dta)**. Findings: rising BTC prices pull in new users (~40% men under 35);
**73–81% of users (majority in nearly all economies) LOST money on their bitcoin app investments**;
entry is feedback-trading, not fundamentals; causal identification via China mining-crackdown
(mid-2021) and Kazakhstan unrest (early 2022) shocks. Companion BIS Bulletin 69 "Crypto shocks and
retail losses" (https://www.bis.org/publ/bisbull69.htm, fetched OK, page-level): around Terra/Luna
AND FTX collapses, "crypto trading activity increased markedly, with large and sophisticated
investors selling and smaller retail investors buying" — the wealth-redistribution mechanism
(whales exit INTO retail dip-buying during collapses).
**Desk mapping:** the WHO-LOSES ledger for the entire asset class: retail leveraged trend-chasers
(Lead 1's carry payers) are the same population documented here losing at 73–81% rates. The app
panel itself is a candidate ATTENTION/adoption regressor at country granularity — but desk's
multilingual-attention daily kill and kimchi retraction mean any use must be (a) non-daily, (b)
non-regional-premium. Honest read: loot the DATASET (free, unusual granularity, ends 2022), do NOT
spend a screen slot on it now (stale end-date; attention-class priors negative). [DATA-LOOT
primary; mechanism GRAVEYARD-ADJACENT, discarded as a signal.]
**Depth: 1 level + companion bulletin.**

## Lead 6 — IMF crypto-cycle work + NY Fed macro-disconnect (read together — they constrain each other)
_Status: RESOLVED at abstract/summary level (IMF) + PRIMARY level (NY Fed sr1052)._

**IMF Che–Copestake–Furceri–Terracciano, "The Crypto Cycle and US Monetary Policy" (WP 2023/163).**
Located: https://www.imf.org/en/Publications/WP/Issues/2023/08/04/The-Crypto-Cycle-and-US-Monetary-Policy-534834
(+ open PDF mirror https://www.aof.org.hk/docs/default-source/hkimr/conference-workshop/S5_2_Alexander-Copestake_paper.pdf;
IDEAS record ideas.repec.org/p/imf/imfwpa/2023-163.html). Summary-level (not primary-read this
session): a single "crypto factor" (1st PC) explains ~80% of variation across major crypto prices;
its correlation with GLOBAL EQUITIES rose as institutional participation grew (2020+); Fed
TIGHTENING lowers the crypto factor via the risk-taking channel — crypto is NOT a hedge; it rides
the same global financial-conditions cycle as equities. Follow-on: "The Crypto Cycle and
Institutional Investors" (Copestake et al.) extends the institutional-transmission evidence.

**NY Fed Benigno–Rosa, "The Bitcoin–Macro Disconnect" (Staff Report 1052, Feb 2023) — PRIMARY READ.**
newyorkfed.org/research/staff_reports/sr1052.html is 403-blocked from this box BUT the PDF at
https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1052.pdf downloads fine
(852KB; extracted 264k chars; abstract + design + results sections read). NK-005 ROUTE NOTE:
**medialibrary PDF paths bypass the newyorkfed.org staff_reports HTML 403.** Design: intraday
(5-min) event study, BTC sample 2017–2022 (traditional assets Jan 2000–2022); monetary surprises
decomposed Swanson-style into Target / Path / LSAP (LSAP from 2-by-8 forward Treasury rate residual,
post-2008); macro news standardized by surprise/σ vs Bloomberg median forecast, |surprise|>5σ COVID
outliers filtered; announcement set: nonfarm payrolls, jobless claims, Conference Board confidence,
ISM, PPI-core, CPI-core. RESULT (verbatim): "Bitcoin is orthogonal to all macro news that we
consider EXCEPT CPI." Gold, silver, S&P 500, and all FX respond normally in the same design;
bitcoin does not respond to Target, Path, or LSAP monetary surprises at all.

**Joint reading + desk mapping.** High-frequency: macro/monetary surprises do NOT move BTC
(2017–2022) — EXCEPT CPI-core releases. Low-frequency: the crypto factor comoves with global risk
conditions and responds to the STANCE of policy (IMF). For the desk this is 90% DOCTRINE, not
signal: it independently corroborates the desk's own kills of FRED-macro daily overlays
(btc_correlation_regime_carry_conditioning EV-gated; era FRED-overlay kills) with official-sector
evidence on a cleaner design. The one residual live edge: **CPI-release-window BTC responsiveness**
is the single macro event with a documented BTC response — an event-gate candidate (desk has FRED
+ event gate + minute bars), narrow, pre-registrable, and NOT a conditioning overlay. Caveat: 2017–22
sample; IMF line implies responsiveness may have GROWN with institutionalization post-2022 (the two
papers' tension resolves in the direction of macro mattering MORE over time).
**Graveyard cross-check:** correlation-regime carry conditioning stays DEAD — nothing here reopens
it (the IMF finding is the fact that made the overlay tempting; the overlay itself already failed
EV). No collision for a CPI event study (different clock, different class).
**Depth: 2 levels (sr1052 primary + IMF WP summary/mirror located + institutional-investors
follow-on identified).**

## CHASE CLOSURES / LOOSE ENDS
- Christin–Routledge–Soska–Zetlin-Jones "The crypto carry trade": NO open primary copy found this
  session (not on arXiv; SSRN blocked by NK-005). Remains [SUMMARY-ONLY]; carded facts here rely on
  WP1087 + the 2025 survey citing it. Candidate future route: CMU author pages / andrew.cmu.edu.
- "Uncertain Regulations, Definite Impacts" (SEC-interventions FRL 2024): sec.gov-hosted PDF
  (https://www.sec.gov/files/ctf-input-arte-2025-02-19.pdf) returned an HTML stub via curl and HTTP
  403 via fetcher; ScienceDirect blocked (NK-005). Numbers (−5.2%/3d, −17.2%/30d post SEC
  interventions) are [SUMMARY-ONLY] from search snippets — must be primary-verified before any
  graveyard/doctrine entry. BLOCK LOGGED; no bot-gate defeat attempted.
- BIS WP 1087 crash-prediction regressions ("high carry predicts price crashes") are stated in
  abstract + footnote 15 of the paper; the full crash-regression table appears to sit in the online
  appendix (not extracted). Direction verified in text; exact crash coefficients NOT captured.
- Heimbach–Huang "DeFi leverage" + OECD DeFi-liquidations: located, summary-level only (see Lead 4).
- Ma–Zeng–Zhang "Stablecoin runs and the centralization of arbitrage" — SSRN-only (blocked); its
  role here is via sr1073's primary-text restatement of the theory (first-mover advantage).

## DATA-LOOT (§27)
1. **BIS retail crypto-adoption app-usage panel** — 95 countries, daily, 2015–2022; xlsx/csv/dta
   download links on https://www.bis.org/publ/work1049.htm. License: BIS website terms (free).
2. **CFTC Commitments of Traders, BTC futures** (used by WP1087 for the who-pays decomposition) —
   free weekly, cftc.gov; desk lacks this feed; smallest-trader ("nonreportable") net-long is the
   carry-payer positioning proxy. NOT price-derived → passes positioning-contamination law on its
   face (report-based, weekly lag).
3. **Auer–Claessens 151-event regulatory-news taxonomy** (Jan 2015–Jun 2018) — event list not
   published as a machine file, but the taxonomy (5 classes + stance sign) is fully specified in
   the Dallas Fed WP 381 PDF (https://www.dallasfed.org/~/media/documents/institute/wpapers/2020/0381.pdf,
   downloaded + extracted this session) — desk can rebuild and EXTEND from free regulator sites
   (SEC/CFTC/ESMA/FSA/FSC press+litigation pages). CRNI index construction documented.
4. **DefiLlama per-chain stablecoin circulation** (sr1073's chain-flow source) — free API; the
   cross-chain rotation variable.
5. **CoinGecko stablecoin market-cap series** (sr1073 Fig 10 source) — free tier.
6. **Glassnode funding rates** (He et al. source) — desk already HAS multi-venue funding incl.
   BitMEX 2016–2026, strictly better; noted only for replication parity.
7. **NY Fed medialibrary PDF route** (meta-loot): staff_reports HTML 403s; medialibrary PDF path
   serves — reusable for ALL NY Fed staff reports (add to NK-005 substitute routes).
8. Skew/Coinmetrics fixed-maturity basis + liquidation aggregates (WP1087 core data): Skew is a
   defunct/acquired vendor (Coinbase) — NOT freely reconstructable; desk's own basis + liquidation
   stream substitutively covers BTC/ETH from its archives. Named as the gap: desk lacks
   FIXED-MATURITY constant-maturity basis series pre-2019 outside BitMEX/CME.

## HONEST NULLS / BLOCKS
- **Macro-news timing on BTC is a verified official-sector NULL** (sr1052 primary): no response to
  NFP, claims, confidence, ISM, PPI, or ANY monetary surprise dimension, 2017–2022 — sole exception
  CPI-core. Corroborates desk's standing FRED-overlay kills. (This null is the sweep's most
  load-bearing negative result.)
- Auer–Claessens auxiliary categories: **general warnings and CBDC statements have NO price
  effect** — pre-register these as null classes in any regulatory-event build (saves labeling
  budget).
- BLOCKS this session (all logged, all routed around where a route existed): newyorkfed.org
  /research/staff_reports/* HTML (403; routed via Boston Fed + medialibrary PDFs), sec.gov files
  PDF (403 + HTML stub; NOT routed — paper stays summary-only), SSRN (standing NK-005, not
  attempted), ScienceDirect (standing NK-005, not attempted).
- NOT manufactured: no stablecoin mint/burn → next-day-return timing mechanism was found in the
  official-sector corpus (the literature links flows to PEG deviations and funding conditions,
  not to directional crypto returns at daily horizon). The desk's EV-gate kill of the supply-level
  signal stands unchallenged by anything read today.

## SWEEP STATUS: COMPLETE 2026-07-31. Web ops ~24 (7 searches, 13 page fetches, 4 PDF downloads).
Primary-text level reached on: WP1087 (full), Dallas Fed WP381 (full), sr1073/SRA23-02 (core
sections), sr1052 (abstract+design+results), He et al. 2212.06888 (HTML targeted), BIS QR 2018
regulatory feature (page), BIS QR Dec 2021 DeFi (page), WP1049 (page), Bulletin 69 (page), LSE
runs-on-stablecoins (page). Summary-only: Christin et al., SEC-interventions FRL, IMF WP 2023/163,
Heimbach–Huang, survey 2510.14435 carry numbers.
