# Renaissance Technologies (Medallion): mining report

Cluster: renaissance. 42 sources read (listed in `renaissance.json`), 18 hypothesis rows and 19 capability-gap rows.
Evidence levels: **DOCUMENTED** means sworn, government or on-record primary material. **REPORTED** means credible secondary, mostly Zuckerman's 40+ interviews. **SPECULATED** means practitioner inference or my own mapping.

## What the primary record actually establishes (sworn / government / on-record)

- **Hit rate and breadth.** The sworn Senate statement says the model is "profitable only slightly more often than not". It makes up for this by generating "a large number of recommendations" and relying on the law of large numbers. Unlevered returns "would be very small", so leverage is what makes the returns. Mercer's figure of 50.75% (via Zuckerman) is consistent with this.
- **Turnover and horizon** (SEC exam cited in the PSI report; RenTec chart for 2007-01 to 2009-03):
  - 129M trade orders in one year, across ~10,000 instruments in 18 countries.
  - An estimated 26-39M trades per year through the option accounts alone.
  - 87% of positions held under 3 months and <1% over 6 months.
  - Zuckerman (on record, Ritholtz) puts the average hold at about 2 days, sometimes 2 weeks.
  - Berlekamp's 1989-90 rebuild: holds of 1.5 days to 1.5 weeks, "profitable almost every day".
- **Leverage.** Barclays offered up to 20:1 and Deutsche Bank up to 18:1 (PSI). The barrier options gave non-recourse leverage plus loss protection. Brown's oral testimony: March 2000, positions in Nasdaq stocks that the models "thought were hedged" by NYSE stocks diverged, and "never put your full faith in a model".
- **Inputs, under oath:** "news stories, analysts' reports, energy reports, crop reports, weather reports, regulatory filings, accounting data" and global quotes and trades.
- **Process (PSI):** one algorithm "encompassing many different strategies". New factors are modelled and introduced gradually. An "objective function" and an "allocation function" are adjusted manually, for example during the 2011 Greek crisis. Management "intervened" and ran "at reduced levels" in Nov-2008.
- **Execution:** a Mercer/Brown patent, US20160035027A1. A large order is split into child orders, each is stamped with one execution time, and GPS-clocked co-located servers submit them simultaneously so HFT cannot front-run them.
- **Methods the principals published:** the Baum-Welch EM for HMMs (Baum 1970), Jelinek-Mercer interpolated estimation (1980), class-based n-gram / mutual-information clustering (Brown, Mercer et al. 1992), and maximum-entropy models (the Della Pietras, with a Renaissance affiliation, 1996).
- **Returns:** Cornell (JPM 2020) reports a 66.1% mean gross return, 31.7% standard deviation, a beta of about -1.0 to CRSP, and negative (insignificant) SMB/HML loadings. Guo (arXiv 2024) disputes the compounding and puts it at under 35% before fees.

## Top 15 additions for the desk, ranked by expected value

1. **One unified model: a maxent / log-linear combiner with an "is this new?" test.** REPORTED (Zuckerman: "one system"). The method is DOCUMENTED (Della Pietra 1996). Every family's signal becomes a feature, and a feature is admitted only if it adds held-out likelihood. This is Simons' "Is this really new, or embedded in what we've done already?"
2. **Jelinek-Mercer interpolated shrinkage for sparse conditional cells** (symbol × segment × day-of-week × vol regime). DOCUMENTED as a method. It attacks the desk's biggest cost, which is multiple testing on sparse cells.
3. **Breadth ledger plus opportunity-conditioned, two-sided leverage.** DOCUMENTED (Senate statement, PSI). Measure effective independent bets. Lever up when predicted net edge is broad (up to ~20:1 in Medallion), consistent with Rule 2.
4. **Joint "betting algorithm" optimizer re-run intraday**, with explicit cost and impact terms. REPORTED (orders went from 5 to 16 cycles a day; "every bet is a function of all the other bets").
5. **Data cleaning organ with cross-source tie-out.** REPORTED (Patterson: 7 PhDs cleaning data; Straus tied out against exchange yearbooks). Build it on Dukascopy, FRED, stooq and settlement prices, and feed a quality score into the gauntlet.
6. **`session_handoff`: morning to afternoon, and the 10-segment week** (5 overnight + 5 day). This is Laufer's "twenty-four-hour effect" and the Friday-morning to Friday-afternoon bands. REPORTED.
7. **`overnight_gap_decay`: fade unusually low or high opens versus the prior close** on index, gold, crude and bond CFDs. REPORTED (Laufer futures rule, 1989-90).
8. **`liquidity_gamma_reversal` / `drawdown_conditional`: reversal edge that scales with stress.** Performance is DOCUMENTED (beta about -1; 2008 +152% gross, 2020 +76%). The mechanism is REPORTED (Simons: "Tumult is usually good for us").
9. **`pca_residual` / `relative_value` across clusters** of index CFDs, USD-leg FX, gold/silver and Brent/WTI. REPORTED (Frey: relationships between clusters return to historic norms; the PSI cites the Avellaneda-Lee PCA stat-arb paper). Guard these with `correlation_regime`, because of Brown's March-2000 lesson.
10. **`ensemble` of weak, independent short-horizon members.** DOCUMENTED (Simons, Numberphile: "a collection of these subtle anomalies").
11. **Weather and commodity-report ingestion plus `event_reaction`** on XTIUSD, XBRUSD and XNGUSD (EIA) and the ag CFDs (USDA, NOAA). The input list is DOCUMENTED under oath. Whether RenTec profits from these reports is unknown.
12. **M5 segmentation research lane.** REPORTED (Laufer's five-minute bars surfaced the intraday and day-of-week "ghosts").
13. **`monday_gap` (momentum) and `dow_effect`**, the Friday-trend-into-Monday weekend effect. REPORTED. Admit a cell only at p<0.01 with sub-period stability, which is the reported bar.
14. **Duplication (crowding) monitor.** DOCUMENTED (PSI; the Barclays risk director: "duplication risk"; Quant Quake 2007). Report only.
15. **Graduated admission for non-intuitive signals, plus the univariate-regression discipline.** REPORTED for graduated admission (more than half of signals were non-intuitive by 1997). DOCUMENTED for the discipline (Patterson: "simple regression with one target and one independent variable").

Lower priority:
- `multi_speed_trend` on commodity CFDs. DOCUMENTED that Simons said "commodities especially used to trend". But Berlekamp found long-horizon trades weaker, and they were only ~10% of activity.
- `regime_transition` HMM on FX. SPECULATED: Baum's involvement is documented, the use of HMMs is inference.
- `lead_lag`. SPECULATED.
- Kernel regression. REPORTED.
- News-count features. REPORTED.
- Order-path bug containment. DOCUMENTED (Brown: "over a million lines of code").

## Governance notes for the desk

- The PSI record documents manual de-risking (Nov-2008 "reduced levels"; the 1998 futures cut of about 25%, REPORTED). The desk's standing order forbids risk reduction by fiat. I therefore framed every sizing row as **two-sided** and every risk row as **measurement-only unless Rule 1 is met**.
- Medallion's record supports levering *up* on high-breadth, low-volatility books more strongly than it supports cutting.
- **Do NOT copy:** the alleged POSIT information-leak and limit-order-book strategies from the Volfbeyn/Belopolsky filings (Infoproc, 2007). Both men alleged these were unlawful. They are also irrelevant to a retail CFD desk.
- Single-name equity stat-arb (4,000 long / 4,000 short) is out of lane. Only the *mechanism* is ported, to index, FX and commodity cross-sections.

## What is NOT knowable from public sources

- **The signals themselves.** No primary source discloses a single live Medallion signal, parameter or feature set. Simons told Zuckerman nothing about signals ("he wasn't opening the kimono"). Every signal-level row here is REPORTED or SPECULATED, and mostly describes the 1988-1997 futures era, not today's book.
- **Whether the historical effects still pay after costs at retail.** Medallion's edge is inseparable from its cost/impact modelling, leverage terms (18-20:1, cheap financing) and scale, none of which a retail CFD account has. Cornell notes the returns are after heavy trading costs, which implies unusual execution skill.
- **Medallion's true compounded return** is disputed: 66% gross mean (Cornell) versus under 35% compounded (Guo).
- **RIEF/RIDA** (6-12-month holds, factor-hedged, "uncorrelated" with Medallion) tell us nothing about Medallion's method. The 13F holdings reflect RIEF-type books and single names, so I did not mine them for hypotheses.
- **Fidelity of quotes.**
  - Checked against raw text: the Senate statement, PSI report, hearing transcript, Ritholtz transcript, Cornell paper, the Brown 1992 and Della Pietra 1996 papers, and the patent.
  - Not checked against raw text: quotes attributed to book-note sites (calvinrosser, bagerbach, twoquants, novelinvestor, mleverything) came through a summarising fetch tool. They are book passages as quoted by those sites and should be treated as REPORTED.
- **Unfetchable sources:**
  - Forbes excerpt (403), Justia Renaissance v. Millennium opinion (403), P&I IRS settlement (403), Seeking Alpha transcript (403).
  - Worth Frey Q&A (404), the original Talking Machines page (404), the X/QuantSeeker post (402).
  - HN 21659476 and 34447193 (429), Alphacution (403), the Medium timeline (403).
  - The TED transcript page had no transcript text.
  - The Jelinek-Mercer 1980 full text was not obtained; only metadata.
  - The Simons MIT 2010 and Berkeley/Stony Brook talks exist only as video. No transcript was found, and only notes (Infoproc) were used.
  - No Robert Frey lecture transcript was found.
  - The web-search budget was exhausted mid-run, so no further searches for Frey, Straus or Berlekamp interviews were possible.
