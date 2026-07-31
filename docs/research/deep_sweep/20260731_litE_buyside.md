# LIT-E: Buy-side practitioner research deep-mine — 2026-07-31

**Ground:** AQR Insights, Man Institute (Man AHL/Man Group), Two Sigma public research; Robeco/DE Shaw
secondary. First desk visit to this family.
**Mission:** mechanisms + implementation priors for a small crypto perp/spot desk (~$5k book;
Binance/BitMEX/OKX/Upbit; multi-venue funding incl. BitMEX 2016-2026, OI, liquidations, basis,
4-venue spot, FRED). Published REAL cost data from live managers is the highest-value target class
(backtest cost assumptions = #1 phantom-edge source).

## Discipline cross-check (read before mining — docs/graveyard.md + negative_knowledge.md)

Standing kills that constrain this run:
- **vol-target overlay: DESK KILL** (`regime_artifact`): overlay on carry book took Sharpe 1.40→1.07.
  "Carry edge is vol-correlated; de-levering high vol cuts the good periods." Any practitioner
  vol-scaling claim must be read AGAINST this: the question is *which return streams* vol-targeting
  helps, not whether it works in general.
- **Price-only daily anomaly mining: WEAKENED prior, not law** (420/0 partially instrument-artifact).
  Practitioner *trend* evidence in crypto is admissible but must beat the −58% McLean–Pontiff
  post-publication haircut and the desk's own trend-book redundancy (tftrailbreakout/tfatrexit died
  at corr 0.91 vs existing trend book — new trend variants need orthogonality, not existence proofs).
- **Trading-frictions anomaly family: DEAD** (HXZ RFS 2020, 96.2% category fail). Liquidity-premium
  *signals* stay dead; liquidity/cost *models for execution* are NOT the same thing and are in-scope.
- **Retail TA canon: DEAD** (era natural experiment). Practitioner "trend" ≠ retail TA — Donchian-class
  breakout already died on-desk for redundancy; time-series momentum sign(r) class is the live question.
- **Positioning-proxies-that-are-price-in-disguise: standing hazard** — de-contamination gate mandatory.
- **NK-005**: SSRN/ScienceDirect/Wiley 403 from this box → aqr.com, man.com, twosigma.com, arXiv,
  RePEc/IDEAS, NBER, author pages, institutional OA repos. No bot-gate defeat; log blocks.
- Provenance grades: [PRIMARY] = full text read; [ABSTRACT] = verbatim abstract only;
  [SUMMARY-ONLY] = search-index summary, BARRED from graveyard/priors until upgraded.

Depth line per lead: surface / interior / citations≥2 / exhausted.

---

## Leads

### LEAD 1 — AQR "Trading Costs" (Frazzini–Israel–Moskowitz): the real-cost anchor  [COST-PRIOR] [PRIMARY]

**Source:** author copy PDF (Moskowitz Yale faculty page, publisher-sanctioned self-archive):
https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2021/08/Trading-Cost.pdf
(AQR page: https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs ; SSRN 4124576-adjacent id 3229719 — 403 from this box, routed around per NK-005.)
Draft Aug 2018; $1.7T of LIVE trade executions, 21 developed equity markets, Aug 1998–Jun 2016.
Full text extracted locally (stdlib flate extractor); numbers below quoted from body text, not summaries.

**Mechanism (what the live data says):**
- **Mean market impact 9.97 bps; mean implementation shortfall 11.02 bps** (difference 1.05 bps =
  model-price vs first-fill gap). **Medians 6.18 / 8.63 bps** (right-skewed: expensive trades are rare
  but big). **Value-weighted means 15.14 / 16.06 bps** (biggest trades cost most).
- Large-cap trades 8.90 bps vs small-cap 18.95 bps. Long-only trades ~13.7 bps vs long-short 8.4 bps
  (equal-weighted; converges value-weighted).
- **~85% of impact is PERMANENT**: only 1.26 bps on average reverses in the next 24h. Impact is
  information/flow-priced, not a temporary liquidity dent that patience refunds.
- **Functional form: square-root in trade size.** Log-log regression of impact on trade size gives
  power **0.35, R² 95%**; they adopt sqrt(%DTV) (F-test rejects linear vs sqrt). Same family as
  Almgren et al. (2005), Kyle-consistent, Grinold–Kahn/Barra practice.
- Impact **rises with market volatility (VIX) and idiosyncratic vol**, falls with stock size, falls
  secularly over time; trade-size fraction of daily volume is THE dominant cost variable. Exchange
  microstructure rules (taxes, uptick) ≈ no effect; venue competition lowers costs.
- Headline claim: real institutional costs are **an order of magnitude smaller** than prior academic
  estimates (Lesmond/Korajczyk–Sadka class), because academics measure hypothetical aggressive
  trades while a patient manager schedules child orders and supplies liquidity.

**Who loses money and why they persist:** anyone using academic cost estimates over-prices capacity
and under-trades real edges; anyone using naive zero/flat cost under-prices impact on size. Both
persist because neither ever observes a counterfactual fill tape.

**Desk mapping (execution-physics law):**
- The desk's cost model for anything sized should be **cost_bps = spread/2 + c·σ·sqrt(Q/ADV)** shape,
  NOT linear. At $5k book on Binance majors, %DTV≈0 → spread/fees dominate, impact≈0; the sqrt term
  is the GROWTH constraint, and it says capacity degrades gracefully (concave), not cliff-like.
- The 85%-permanent finding is a warning for signal evaluation: impact does not mean-revert away, so
  "enter slow, exit slow" does not refund impact — it only avoids paying the sqrt premium twice.
- Caveat on transfer: developed-equity institutional flows ≠ crypto perps. Crypto has maker rebates /
  taker fees dominating at small size, and funding transfer costs. Use the FORM and the
  order-of-magnitude discipline, not the equity coefficients.

**Replication status:** the sqrt-impact form is independently found by Almgren et al. 2005 (broker
data) and is standard in practitioner TCA; the LEVEL (≈10bps mean) is manager-specific (patient,
limit-order-heavy). Not crypto-replicated in this paper.
**Depth:** interior (body text read; regression tables partially extracted). Citation chain: Almgren
2005, Kyle 1985, Keim–Madhavan, Korajczyk–Sadka — standard, not chased further (diminishing).

---

### LEAD 2 — Man AHL / Harvey et al. "An Investor's Guide to Crypto" (JPM Nov 2022): crypto TSMOM + vol-scaling with LIVE cost disclosure  [MECHANISM] [ENGINE] [COST-PRIOR] [PRIMARY]

**Source:** author copy (Cam Harvey Duke page, published JPM version):
https://people.duke.edu/~charvey/Research/Published_Papers/P164_An_investors_guide.pdf
Man page: https://www.man.com/insights/investor-guide-to-crypto . Authors: Harvey, Abou Zeid,
Draaisma, Luk, Neville, Rzym, Van Hemert (Man AHL). Full text extracted; exhibit legends recovered.

**A. Crypto time-series momentum (Exhibit 11, GROSS of costs, excess of funding, scaled to 10% ex-post vol):**
- BTC (2016-05-10 → 2022-06-30): **mom22d Sharpe 1.46; mom65d 1.48; mom261d 1.63; momAvg(22d,261d)
  1.65; buy-and-hold 1.18.**
- ETH (2017-03-10 → 2022-06-30): mom22d 1.45; mom65d 1.23; mom261d 1.38; momAvg 1.47; B&H 1.20.
- Construction: Harvey et al. (2019) methodology, 1m=22d / 3m=65d / 12m=261d trend, mostly-long book
  because sample trends up. Their own caveat: trend "needs to see" the B&H tailwind; short history.
- Citation chain: Rozario et al. (2020), Liu & Tsyvinski (2021), Liu–Tsyvinski–Wu (2022) as the
  academic momentum record.

**B. Vol-targeting in crypto (Exhibit 10, the honest table — this is Man publishing AGAINST its own
  franchise, highest-credibility class):** 7 sizing variants (unscaled; HF-intraday vs daily vol
  estimate × 5d / 180d / avg(5d,180d)), all ex-post rescaled to 10% for comparison:
- BTC Sharpe: unscaled 1.08 → vol-scaled 1.04–1.20 (best: 180d). **Modest gain at best.**
- ETH Sharpe: unscaled 0.91 → 0.76–0.94. **Vol-scaling adds ~nothing on ETH; fast (5d) scaling HURTS
  (0.80 HF / 0.76 daily) and RAISES max DD (20.3%→23.9%).**
- S&P500 same table: 0.73 → 0.88 (5d HF). Vol-targeting helps equities more than crypto.
- The REAL benefit in crypto is **vol-of-vol: BTC 2.6%→1.4%, ETH 2.0%→1.1%** (avg estimator) — i.e.
  risk STABILITY, not Sharpe. Max DD BTC 19.0%→16.1% (180d).
- Mechanism why it works at all: vol persistence (5d vol quintiles predict next-5d vol) while **vol
  does NOT predict returns** — so scaling cuts risk without cutting conditional mean.
- **Mean notional exposure for a 10% vol target: BTC ≈ 13.5–14.9%, ETH ≈ 9.6–10.6%** of NAV (SPX
  needs 54–83%). Crypto's high vol means tiny notional → tiny absolute costs.
- Annualized turnover of the vol-scaled sleeve: ~3x (avg estimator) to ~10x (5d daily) — slow 180d
  scaling turns only ~0.3x/yr.

**C. LIVE COST DISCLOSURE (footnote 25) — the number this run came for:** "From our live trading
experience, transactions costs are very modest, **around one basis point for a position with 10%
annualized volatility that turns over once a year**" — i.e. ~1bp per unit-notional-turnover-year at
crypto's ~14% notional-per-10%-vol; costs quoted per VOL-EXPOSURE unit, and small precisely because
vol-targeted notional is small. (Man AHL, live, 2022, BTC/ETH-class liquid coins.)

**Desk mapping:**
- The desk holds funding-excess perp returns on 4 venues — the exact return object Man uses (returns
  in excess of funding). The momAvg(22,261) construction is directly replicable on desk data, and its
  **post-publication window 2022-07→2026-07 is a free out-of-sample decay measurement** (McLean–
  Pontiff −58% prior says expect Sharpe ≈0.7 from 1.65). CAUTION: desk trend book already exists;
  tftrailbreakout/tfatrexit died at corr 0.91 — any test here is a DECAY MEASUREMENT, not a new sleeve.
- Vol-scaling: Man's evidence says in crypto use SLOW (180d) or avg(5d,180d) vol, expect stability
  not alpha, and never fast-only scaling. Consistent with the desk's own vol-target overlay kill
  (carry Sharpe 1.40→1.07): vol-scaling is return-stream-specific, and Man only claims it for
  LONG/directional crypto exposure, NOT for carry books.
- 10%-vol-target notional math (≈14% of NAV in BTC) is a sizing sanity anchor for the engine.

**Replication status:** published Nov 2022; Man's own Dec 2024 follow-up ("In Crypto We Trend")
extends the trend claim on fresher data (Lead 3). Liu–Tsyvinski–Wu is the academic corroboration.
Post-publication decay NOT yet measured by anyone found this run — desk can do it.
**Depth:** interior (full text + exhibit numbers). Citations chased: Harvey et al. 2018 vol-targeting
(Lead 4), Rozario 2020 (Man decade-of-trend), LTW 2022.

---

### LEAD 3 — Man AHL "In Crypto We Trend" (Dec 2024): costed crypto trend capacity curve  [MECHANISM] [COST-PRIOR] [PRIMARY-HTML / figures unrecovered]

**Source:** https://www.man.com/insights/in-crypto-we-trend (HTML full text read; PDF download URL
serves a JS confirmation page — figure VALUES are chart images, NOT recovered; logged, not defeated).
Man Group, as of 1/11 December 2024, Coinbase data from 2016, coins added at launch.

**Mechanism + the costed capacity curve (verbatim-anchored):**
- Portfolio built "start[ing] with a 100% Bitcoin portfolio and progressively add[ing] coins, sharing
  risk equally across coins... considering **transaction costs, shorting costs, liquidity constraints
  and shorting availability**" — i.e. the curve is NET, which is what makes it citable.
- **"Peak risk-adjusted returns in a trend-following crypto portfolio occur with around 10-15 coins.
  Beyond this point, transaction costs and liquidity constraints outweigh diversification benefits."**
- **Breakout-family models peak EARLIER, ~10 coins**, because a breakout "generates a sharp binary
  signal which enters a full long or short position straightaway, thus requiring greater liquidity."
  (Faster signal ⇒ lower breadth capacity in thin coins — a general speed-vs-breadth law.)
- Average high-frequency pairwise correlation between coins over the last decade **~0.6** ⇒ "limited
  diversification potential." Diversification multiplier is small in crypto; breadth is NOT the lever
  it is in futures trend (cf. AQR D multiplier, Lead 4).
- Their own honesty note: Sharpe level "higher than expected for a concentrated trend-following
  system (and is probably a function of the short history)."
- Vol-scaled BTC left-tail claim repeated from the 2022 guide: "Once volatility is scaled, the left
  tails of Bitcoin are more benign than those of the S&P 500."

**Who loses money and why they persist:** trend shops that push breadth into coin #20+ pay
costs > diversification gain (they persist because breadth is the futures-trend habit); retail trend
in illiquid alts pays the same tax without knowing.

**Desk mapping:** the desk's investable perp universe (Binance/OKX/BitMEX liquid names) is ~the same
top-10/15 ADV set Man identifies as the entire capacity-positive zone — desk breadth ambitions
beyond ~15 names are formally priced as NEGATIVE-EV by the one manager who measured it net.
Publication timing: Dec 2024 = Man re-publishing trend-works-in-crypto 2.5y AFTER the 2022 guide —
qualitative post-publication persistence evidence (exact post-2022 Sharpe not recoverable; figures
are images).
**Replication status:** consistent with their 2022 JPM guide; independent of AlphaArchitect-class
replication. NOT independently verified; net-of-cost construction is self-reported.
**Depth:** interior (HTML verbatim); figure values unrecovered — logged as the run's main extraction
failure.

---

### LEAD 4 — AQR "You Can't Always Trend When You Want" (JPM 2020): trend P&L = f(|move|) decomposition  [MECHANISM] [ENGINE] [PRIMARY]

**Source:** author-side PDF https://images.aqr.com/-/media/AQR/Documents/Journal-Articles/JPM-You-Cant-Always-Trend-When-You-Want.pdf
(AQR page: https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want).
Babu, Hoffman, Levine, Ooi, Schroeder, Stamelos. Data late-1800s–2018, Hurst–Ooi–Pedersen construction.
Full text extracted locally.

**Mechanism:** decompose trend-following excess return into (1) magnitude of market moves,
(2) trend efficacy — ability to convert a given move into profit, (3) cross-market diversification
multiplier D. Estimated per-market-per-year: **SR_trend(i,t) = α + β·|SR_market(i,t)|** (WLS), with
**α NEGATIVE** (trend bleeds in directionless markets — the cost of whipsaw) and **β < 1** (some of
every move is lost to dynamic positioning). Historical fit stable; the 2010s trend winter was
**muted |moves|** (fewer large risk-adjusted moves), NOT lower efficacy and NOT lower diversification.
Supporting numbers: SG Trend Index Sharpe **0.05 (2010–2018)** vs **0.28 (2000–2018)**; index peak
2015-04-13, −19.7% through 2018. Cash-rate drag noted as a separate additive factor.

**Who loses money and why they persist:** trend allocators who read a muted-move decade as "trend is
broken" sell at the bottom of the move-magnitude cycle; conversely anyone extrapolating crisis-decade
trend Sharpe into a range regime overpays. Both persist because move magnitude is not forecastable —
AQR's own framing is attribution, not timing.

**Desk mapping:**
- Crypto's |SR_market| per year is structurally huge (BTC yearly |move| routinely >1 vol-unit) ⇒ the
  SAME model that explains the futures trend winter PREDICTS trend viability in crypto — mechanism-level
  agreement with Man's crypto trend results, from AQR's independent frame.
- ENGINE use: this is the honest ATTRIBUTION frame for the desk's existing trend book — when the book
  bleeds, compute realized |move| magnitude first; only an efficacy (α,β) deterioration is evidence
  against the strategy, a move drought is not. Cheap to implement on desk data (yearly or quarterly
  per-market regression), no forecasting claimed.
- Do NOT convert into a regime-timing overlay (desk graveyard: overlay class killed 3x; and AQR
  themselves do not claim |move| is predictable).
- Exact fitted α/β coefficients not cleanly extractable from the PDF text layer (equation glyphs
  mangled) — form and signs verified, magnitudes not recorded. Honest gap.

**Replication status:** decomposition is arithmetic on a standard TSMOM construction (HOP 2013/2017 —
widely replicated); the muted-moves explanation is corroborated by SG index arithmetic. Post-2018:
2019-2023 included trend revival years (2022 rates trend) consistent with move-magnitude channel.
**Depth:** interior. Citations: Hurst–Ooi–Pedersen 2013/2017, Levine–Pedersen 2016 (not chased —
academic TSMOM canon already in desk priors).

---

### LEAD 5 — Two Sigma "A Machine Learning Approach to Regime Modeling" (Street View, Oct 2021)  [ENGINE/NULL] [PRIMARY-FETCH]

**Source:** https://www.twosigma.com/articles/a-machine-learning-approach-to-regime-modeling/
(also mirrored on venn.twosigma.com).

**Method (the transferable part):** Gaussian Mixture Model, unsupervised, on **17 factors of the
Two Sigma Factor Lens**, data from early 1970s; **number of clusters = the ONLY hyperparameter**,
chosen by cross-validated log-likelihood (AIC and multivariate GoF checked, similar). Output: 4
regimes — Crisis (equity/credit down, rates up, correlations highest, **trend-following large
positive**), Steady State (most frequent, everything mildly up), Inflation (local-inflation factor
double-digit, FX best), Walking-on-Ice (equities up at elevated vol; style-factor vols ~2x long-term:
Value 18.2% vs 8.9%, Momentum 19.1% vs 10.5%, Low-Risk 20% vs 10.4%). Other three regimes ~15-20% of
periods each.

**The load-bearing admissions (why this is filed ENGINE/NULL, not MECHANISM):**
- **"This model is not predictive"** — their words. GMM treats periods as IID; no temporal structure,
  no transition model, no forecast claim. It LABELS, it does not LEAD.
- Early-2021 inflation scare: model assigned ~zero probability to the Inflation regime — i.e. the
  regime library failed exactly when a new regime variant arrived (their own reported miss).
- Crowding factor EXCLUDED from the GMM for data-length reasons.

**Who loses money:** anyone who wires an unsupervised regime classifier as a TIMING signal — the
publisher itself declines that claim. Persist because regime narratives sell and cluster plots look
like foresight.

**Desk mapping:** corroborates, from the buy-side, the desk's 3x-killed regime-overlay class: even
Two Sigma publishes regime models only as DESCRIPTIVE risk lenses. If the desk ever wants a regime
tag for attribution/risk-report cosmetics, GMM-on-return-factors with CV-chosen k is the honest
recipe (and cheap); as alpha it is pre-killed by both desk evidence and the publisher's own claim.
**Replication status:** method standard (sklearn-class GMM); their specific regime dates not
independently verified. **Depth:** surface+ (full article fetched; no citations worth chasing beyond
McAssey 2013 GoF — skipped).

---

### LEAD 6 — Man AHL / Harvey et al. "The Impact of Volatility Targeting" (JPM Fall 2018): WHERE vol-scaling works and the mechanism WHY  [MECHANISM] [ENGINE] [COST-PRIOR] [PRIMARY]

**Source:** author copy https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf
(JPM 45(1):14-33; SSRN 3175538 — 403, routed around). Harvey, Hoyle, Korgaonkar, Rattray, Sargaison,
Van Hemert. 60+ assets. Full text extracted locally.

**Mechanism (the three-part answer — this is the boundary law the desk's own kill needed):**
1. **Only risk assets (equities, credit) display a leverage effect** — negative contemporaneous
   correlation between returns and vol changes (Black 1976).
2. **Where a leverage effect exists, vol-scaling mechanically introduces MOMENTUM** (vol up after
   losses ⇒ scale down after losses = trend-follow your own asset).
3. That implicit momentum overlay is what improves the Sharpe. Cross-sectional variation in
   Sharpe-improvement is "empirically explain[ed]" by the induced momentum.
**Therefore:** for bonds, currencies, commodities — no leverage effect — "the effect of a simple
volatility scaling on the Sharpe ratio is **negligible**." US equities 1927–2017: SR 0.40 unscaled →
**0.48–0.51 scaled**, insensitive to vol-estimate half-life; significance via daily regression
intercept 0.64bp (t=3.05, NW-30). **The universal benefit is tail/vol-of-vol reduction, not Sharpe.**

**Cost priors (their published futures assumptions, per notional traded, post-2008 levels):**
**1.0 bp equities, 0.5 bp bonds, 0.5 bp credit (CDX IG), 1.0 bp gold, 2.0 bps oil, 3.5 bps copper.**
Vol-scaling cost drag at 10% vol: 0.066%/yr (gross SR 0.4831 vs net 0.4766 — rounding-invisible).
Turnover definition worth stealing: mean absolute daily exposure change, annualized, ÷ 2× mean
exposure = round-trips of mean exposure per year.

**Desk mapping (this lead UNIFIES three desk facts):**
- Desk carry-book vol-target kill (1.40→1.07): carry P&L has no leverage effect — high-vol periods
  are the harvest periods, so de-levering them cuts the mean. EXACTLY the paper's negligible/harmful
  zone. The desk kill is the paper's mechanism observed live.
- Man's own 2022 crypto table (Lead 2B): BTC modest gain / ETH none ⇒ crypto's leverage effect is
  weak/absent (crypto vol spikes in rallies too). Practitioner evidence AGREES vol-scaling in crypto
  is a RISK tool (vol-of-vol, tails, sizing), not an alpha tool.
- ENGINE: desk sizing should keep vol-forecast-based POSITION SIZING (stability, drawdown control)
  while never booking it as expected-Sharpe improvement; use slow/blended vol estimates (Lead 2B:
  fast-only scaling hurt ETH).
**Replication status:** consistent with Moreira–Muir (2017) on equities; the asset-class boundary
independently argued by Bongaerts/Kang/van Dijk and Cederburg et al. (out-of-sample critiques of
vol-management live in the same zone — not fetched this run). **Depth:** interior; citations chased
1 level (Black 1976 leverage effect canon; Moreira–Muir noted).

---

### LEAD 7 — Two Sigma / Venn "Crowding" factor: short-interest-based crowding measurement  [ENGINE-adjacent] [SURFACE]

**Sources:** Venn Factor Lens FAQ https://help.venn.twosigma.com/en/articles/1392786-two-sigma-factor-lens-faq ;
"Revisiting the Two Sigma Factor Lens" PDF (hubspot mirror) ; crowding special-edition report
https://www.venn.twosigma.com/insights/may-2024-factor-performance .

**What it is:** an 18-factor risk lens; the **Crowding factor = short the widely-shorted US stocks,
long the lightly-shorted** (short-interest data as the crowding gauge; US-only, beta-neutral; the one
style factor NOT region-neutral). Venn reports Sharpe ~0.92 since Jan 2008 for the factor
[SUMMARY-ONLY number — from FAQ/search, primary table not fetched]. Two Sigma EXCLUDED this factor
from their regime GMM for history-length reasons (Lead 5).

**Desk mapping (thin, honesty over reach):** crypto has no short-interest tape; nearest desk
analogues (funding, OI, long-short account ratios) are ALREADY tested and mostly dead
(smart_dumb_divergence, elite ratios — graveyard) or live as carry (funding). The transferable
content is only the DESIGN: crowding measured from an explicit POSITIONING quantity (short interest),
never from price; and crowding treated as a RISK FACTOR to hedge/attribute, not an alpha to time.
No desk action beyond attribution vocabulary. **Depth:** surface (deliberate — low mappability).

---

### LEAD 8 — AQR/Asness on crypto: the skeptic's falsifiable residue  [NULL/GRAVEYARD-candidate] [SUMMARY-ONLY]

**Sources (all secondary summaries — AQR hosts no formal crypto research paper found this run):**
DL News on Asness halving analysis https://www.dlnews.com/articles/markets/wall-street-quant-cliff-asness-analyses-bitcoin-halving/ ;
aqr.com fraud notice confirms "AQR does not offer direct investments in cryptocurrencies."

**Falsifiable claims extracted (opinion stripped):**
1. **Halving effect: "The returns to Bitcoin have been large over these halving periods, but not
   really abnormally large"** (Asness, 2024, "too good to check (so I checked it)") — i.e. halving-
   window returns ≈ unconditional BTC drift. External NULL on halving seasonality. [SUMMARY-ONLY —
   primary post not reachable on aqr.com Perspectives page, which lists only a 2014 entry.]
2. Bitcoin co-moves with equities, not gold — corroborated at primary level by Harvey et al. 2022
   (sharply increased crypto-equity correlation, risk-on asset) — so the claim is admissible via
   Lead 2 even though Asness's version is summary-grade.
**Desk mapping:** halving-cycle narrative is pervasive; the desk has never tested it (checked
graveyard — absent) and probably never should: price-only seasonality family, EV-gate would price it
near zero, and the one quant who publicly checked reports null. Route: graveyard as
`external-literature` prior ONLY IF primary text of the Asness piece is ever read (SUMMARY-ONLY is
barred today); until then this is a do-not-spend note.
**Depth:** surface — blocked at primary level; logged per discipline, not defeated.

---

### LEAD 9 — Post-publication check on crypto TSMOM: OOS 2022–2024 net-of-cost measurement  [MECHANISM — decay quantified] [PRIMARY]

**Source:** arXiv 2602.11708 (Bui & Nguyen, Feb 2026, academic — NOT practitioner, but it tests the
practitioner window): https://arxiv.org/pdf/2602.11708 . Full text extracted locally.
Universe: **150+ Binance Futures perps, 6h bars, Jan 2021–Dec 2024**; IS = 2021 only; **OOS =
Jan 2022–Dec 2024**, all reported metrics OOS. Cost model: **4 bps taker fee per trade + slippage
linear in trade size vs prevailing 5-min volume (order-book calibrated) + funding charges/rebates**.

**Table 1 (OOS, NET of costs) — the rows that matter are the BENCHMARKS, not their pet strategy:**
- **TSMOM-1M (classic 1-month lookback, monthly rebal): ann ret 18.4%, vol 21.3%, Sharpe 0.65, MDD 34.8%**
- **TSMOM-3M: 15.1% / 19.7% / Sharpe 0.54 / MDD 38.2%**
- **Vol-scaled TSMOM (10% vol target): 22.8% / 10.0% / Sharpe 1.83 / MDD 16.1%**
- BTC buy-and-hold: Sharpe 0.17, MDD 64.1%; EW top-20 B&H: Sharpe 0.07, MDD 72.4%
- (Their "AdaptiveTrend" 2.41 Sharpe: 1-year IS calibration + adaptive machinery + internal
  inconsistencies (OOS end date Dec 2024 vs Figure 1 Oct 2025; "4-times-daily funding cycle" vs
  their own 8h cost model) ⇒ treat as unreviewed overfit-risk, NOT evidence.)

**THE DECAY ARITHMETIC (desk's standing −58% prior, tested):** Man/Harvey published crypto TSMOM
Sharpe **1.46–1.65 gross** (2016–2022, Lead 2). Post-publication classical TSMOM net:
**0.54–0.65** ⇒ ratio ≈ 0.35–0.42 of published, i.e. **−58% to −65% decay — the McLean–Pontiff
haircut lands almost exactly**, with the caveat that construction/universe/cost basis differ (BTC+ETH
gross vs 150-perp net, monthly rebal). Direction and magnitude of the desk prior: CONFIRMED in
crypto. Trend did NOT die: it still beat B&H by ~0.5 Sharpe with half the drawdown.

**Vol-scaling interaction:** vol-targeting the TSMOM sleeve tripled OOS Sharpe (0.65→1.83) in a
window containing the 2022 crash — consistent with Lead 6's mechanism (2022 crypto DID display a
leverage-effect-like path: vol spiked as prices fell, so vol-scaling de-levered the crash). One
window, one paper; do not book as law. But it is the third independent line (Man 2022 table, desk
carry kill inverse, this) all consistent with: **vol-scaling helps DIRECTIONAL crypto exposure in
bear/high-vol regimes, does nothing-to-harm for carry.**

**Capacity note (their order-book analysis):** short leg (low-cap names) is the bottleneck —
**~$5–10M practical capacity before short-leg slippage exceeds 10bps/trade; ~$50M portfolio-level.**
At desk size ($5k) capacity is a non-issue by 3-4 orders of magnitude.
**Replication status:** unreviewed preprint; benchmark rows are simple constructions on public data —
desk can re-run them exactly (Binance perp archive on hand). **Depth:** interior.

---

### LEAD 10 — Two Sigma "Risk Analysis of Crypto Assets" (Street View, Jul 2021)  [MECHANISM-context] [PRIMARY-FETCH]

**Source:** https://www.twosigma.com/articles/risk-analysis-of-crypto-assets/

**Numbers (Apr 2013–May 2021 unless noted):** BTC ann. return ~110%, ann. vol **81%**, Sharpe ~1.3;
**91% of Bitcoin's risk since Jan 2015 unexplained by the 17-factor lens** — the explained 9% loads
positive Equity (**beta 0.74 but correlation only 18%** — high beta, low R²), positive
Trend-Following factor, negative EM. **BTC–ETH correlation 74%**; top-10-by-volume coin average
pairwise correlation **48%**, which "substantially picked up around the Q1 2018 crypto crash."
Their own bias flag: 10-coin universe selection "may have bias."

**Reading for the desk:**
- 91% idiosyncratic = crypto is its own risk axis: macro-factor overlays on crypto are fighting a 9%
  explained share — external corroboration for the desk's FRED-overlay kills (the desk killed macro
  conditioning on crypto 3x; Two Sigma's decomposition says why: there is almost nothing to condition ON).
- Positive loading on the trend-following FACTOR (BTC co-moves with what CTAs are long) — a crowding
  channel: when trend books de-lever, BTC gets sold with everything else. Matches increased
  equity-crypto correlation in Harvey 2022 (Lead 2) and Asness's risk-asset claim (Lead 8).
- Correlation levels (48% daily 10-coin avg; Man 0.6 HF pairwise, Lead 3) bracket the desk's
  diversification reality: breadth in crypto buys ~half the diversification equity breadth buys.
**Replication status:** consistent with Man/AQR-side claims; lens loadings not independently
verifiable (proprietary factor lens). **Depth:** surface+ (article fetched in full).

---

### LEAD 11 — AQR "Craftsmanship Alpha" (Israel–Jiang–Ross, JPM 2017): implementation priors  [ENGINE] [COST-PRIOR] [PRIMARY]

**Source:** https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/JPM-Craftsmanship-Alpha.pdf
(page: https://www.aqr.com/Insights/Research/Journal-Article/Craftsmanship-Alpha-An-Application-to-Style-Investing).
Full text extracted locally.

**The implementation priors worth stealing (each verbatim-anchored):**
1. **Position NETTING across signals:** in an integrated multi-signal portfolio, a name long on one
   signal and short on another "would not appear in the implemented portfolio because of position
   netting" — the trade is never sent, the cost never paid. Integrated construction beats sleeve-by-
   sleeve construction on costs (and taxes) mechanically.
2. **Patient trading:** "if managers want to trade 6% of a stock's daily volume... they may spread
   them out across three days (roughly 2% of trading volume per day)"; participation rate is the
   cost lever (Frazzini et al. live data); "price impact often dwarfs explicit costs" for size —
   while most investors watch the explicit costs.
3. **No magic turnover number:** rebalance frequency is a per-signal tradeoff between signal decay
   and cost; "low, or high, turnover by itself should not be seen as" good or bad; compare
   strategies net-of-cost only. Momentum earns its high turnover; value doesn't need it.
4. **Hedged/within-group construction:** within-industry value long-short has "about the same to
   slightly higher expected return, but less variance" than unconditional sorts (Asness–Porter–
   Stevens) — risk falls at no return cost when the comparison set is tightened.
5. Signal-definition choices, rebalance details, and execution together are "craftsmanship alpha" —
   dispersion between managers running the "same" factor is largely these choices.

**Desk mapping:**
- (1) is directly actionable: the desk runs multiple sleeves (carry book + trend book) on the SAME
  instruments — orders should be generated from the NETTED target position across sleeves, not per
  sleeve. If the executor nets already, verify; if not, this is free cost reduction. → inbox row.
- (2) inverts at desk size: at $5k, %ADV≈0 ⇒ impact≈0 and FEES/SPREAD dominate ⇒ the desk's lever is
  maker-vs-taker and venue fee tiers, not participation. The prior still binds the GROWTH path: the
  first thing that changes as the book grows is that (2) starts to matter, on the Lead-1 sqrt curve.
- (3) endorses the desk's EV-gate practice of pricing turnover against half-life per signal.
- (4) maps to cross-venue / cross-instrument spreads: tighten comparison sets (e.g. same-asset
  perp-vs-perp) before unconditional bets.
**Replication status:** design-choice effects independently documented (e.g. HML-Devil vs HML).
**Depth:** interior.

---

## §27 DATA-LOOT (free/public assets referenced by this family)

1. **AQR Data Library** — https://www.aqr.com/Insights/Datasets — verified live this run, updated
   through May/Jun 2026: **Time Series Momentum factors (monthly)**, Momentum indices (US/intl),
   Betting-Against-Beta factors (US + 23 markets, monthly + daily), Quality-Minus-Junk (1956-/1986-),
   HML-Devil (monthly). Free (registration status unverified). Desk use: benchmark TSMOM return
   series for trend-book attribution (Lead 4 frame) without building cross-asset futures data.
2. **SG Trend Index** — public CTA trend benchmark (Société Générale); referenced by AQR as the
   industry yardstick (Sharpe 0.05 2010-2018 vs 0.28 2000-2018). Daily levels are publicly posted.
3. **Venn/Two Sigma monthly Factor Performance Reports** — free factor-return commentary incl. the
   Crowding factor; https://www.venn.twosigma.com/insights/ .
4. **Duke Harvey paper archive** — https://people.duke.edu/~charvey/Research/ — publisher-version
   PDFs of every Harvey/Man paper, the reliable SSRN-403 bypass for this whole family.
5. **CoinGecko market-cap API** (daily granularity) used by Lead 9 for universe construction —
   free tier sufficient for cap-ranked universe filters.
6. arXiv 2602.11708 replication targets: Binance Futures 6h OHLCV — desk already holds superior data.

## NULLS / not verified (honest close-out)

- **[NULL] Two Sigma alternative-data evaluation methodology:** their PUBLIC archive (tag sweep,
  article list fetched) contains regime/inflation/ESG/macro method pieces + Venn factor lens, but NO
  published alt-data evaluation framework at useful depth. The famous alt-data rigor is not public.
  Priority target 3 is therefore only half-fillable: METHODS extracted = GMM regime recipe (Lead 5),
  crowding-factor design (Lead 7). Nothing more exists to mine at primary level.
- **[NULL] Robeco on crypto:** searched; Robeco's public quant research (Blitz et al.) is
  equity-factor-centric; no crypto momentum/factor paper surfaced. Secondary ground not needed —
  primary ground (Man/AQR/TS) did not run thin.
- **DE Shaw: NOT VISITED** (secondary-only per mission; budget spent on primary ground).
- **Man "In Crypto We Trend" Fig 2/3 Sharpe LEVELS unrecovered** (chart images; PDF gated behind a
  JS confirmation page — logged, not defeated). The qualitative claims + peak-at-10-15-coins are
  verbatim-anchored from HTML.
- **Asness halving analysis: SUMMARY-ONLY** (aqr.com Perspectives page does not surface it; barred
  from graveyard until primary text read).
- **AQR "You Can't Always Trend" fitted α/β coefficients:** form/signs verified, exact magnitudes
  not extractable from the PDF text layer (equation glyphs mangled).
- **Frazzini–Israel–Moskowitz "Trading Costs of Asset Pricing Anomalies" (2018, capacity numbers
  per factor):** NOT fetched this run (equity-specific capacities; the cost MODEL from Lead 1
  subsumes the desk-relevant content). NYU-hosted PDF exists if ever needed:
  https://pages.stern.nyu.edu/~afrazzin/pdf/Trading%20Cost%20of%20Asset%20Pricing%20Anomalies%20-%20Frazzini,%20Israel%20and%20Moskowitz.pdf

## Routing summary

| Lead | Route |
|---|---|
| 1 AQR Trading Costs (sqrt impact, 85% permanent, ~10bps live) | execution-physics law: adopt sqrt-form cost curve for growth path |
| 2 Man crypto guide (TSMOM Sharpes, vol-target table, 1bp live cost) | watchlist-card: post-pub decay measurement on desk data (measurement, NOT new sleeve) |
| 3 Man 2024 (10-15 coin capacity wall, net) | watchlist-card note on breadth ceiling; no action |
| 4 AQR trend decomposition (SR=α+β·\|move\|) | ENGINE: trend-book attribution frame; inbox |
| 5 Two Sigma regime GMM ("not predictive") | corroborates regime-overlay kills; no action |
| 6 Man vol-targeting boundary (leverage-effect mechanism) | ENGINE: unifies desk carry-kill + sizing doctrine; inbox note |
| 7 Two Sigma crowding factor | vocabulary only; discard |
| 8 Asness halving null | do-not-spend note; graveyard IF primary ever read |
| 9 OOS 2022-24 decay (1.65→0.6 ≈ −60%) | confirms −58% prior; attach to Lead 2 card |
| 10 Two Sigma crypto risk (91% idiosyncratic) | corroborates FRED-overlay kills; no action |
| 11 Craftsmanship (netting, patience, turnover) | inbox: verify cross-sleeve order netting in executor |

