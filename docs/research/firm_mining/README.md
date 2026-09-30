# Firm mining: what the top systematic firms do that this desk can use (2026-09-27)

Five parallel miners covered five clusters:

- Renaissance.
- AQR, Man AHL, Winton, Bridgewater and the CTAs.
- D.E. Shaw, Two Sigma, Citadel, Millennium, Jane Street, WorldQuant and XTX.
- The practitioner and academic literature.
- Podcasts, forums and free data.

Between them they read **320 primary and secondary sources**. The session's shared web-search budget (200) ran out partway through, and after that the miners fetched known URLs directly. Every quote is 25 words or fewer. A quote is left empty where no verbatim text was seen, and no source, quote or number was invented. Rows read through a page-summarising tool are marked REPORTED. One such summary invented a Sharpe of 2–3 for Krohn et al.; the paper itself says 0.5–0.7. That is why summaries are never trusted as primary.

## Where the output lives

**In the testing pipeline**, `desks/mt5/data/intelligence/firm_mining/discoveries_20260927_*.json`, which holds **168 hypotheses**. On this checkout, `miner_candidate_compiler.compile_row` gave:

- 110 EXACT_RECIPE, 2 STRUCTURED_HYPOTHESIS and 1 TEXT_EXTRACTED, which make **430 executable candidates**.
- 44 NEEDS_SYMBOL_EXTRACTION. These rows name index, bond and soft symbols whose H1 bars are not on this clone; `known_symbols()` reads the bars directory, so they compile on the box.
- 11 NEEDS_EXACT_RULE_EXTRACTION. These have no explicit params and go to deepening by design.

Every row uses a registered family (never `discovered`) and universe.json symbols. Each row is a hypothesis for the ten gates, not a claim, and each is charged as a trial.

**In the build backlog** (this folder):

- `capability_gaps.json` — 115 things the desk lacks, each with a spec, the data it needs, its evidence and its source.
- `data_sources.json` — 21 free or cheap sources.
- `sources.json` — every URL, by cluster.
- `<cluster>.md` — each miner's ranked report.

The compiler's window is 7 days, so these rows age out of the docket unless they are re-donated. Cells that get judged stay in `gauntlet_seen_cells.json`.

## The ranked build list (synthesised across all five clusters)

The ranking is by expected contribution to robust forward E[log W] through more **independent** bets. Evidence levels are those of the underlying sources.

1. **Truth in costs.** Use real per-hour spreads from Dukascopy ticks and a fill markout from our own deals (XTX), and replace the registry's 0-point FX spreads. Without this, every FX result is unreliable (see the 40-sleeve audit).
2. **The signal combiner (Renaissance's "one model"; Two Sigma; WorldQuant):**
   - A log-linear / ridge combiner of every family's signal.
   - An "is this new?" admission test against held-out likelihood.
   - A Two Sigma decorrelation gate against the live book, with the parameter inside the certificate hash (SEC v. Wu).
   - Kakushadze-Yu O(N) weights; shrink toward 1/N.
   - Judged as **one** strategy against the fixed bar.
3. **Breadth accounting.** Grinold-Kahn N_eff, factor-exposure accounting (dollar, carry, trend, US500 beta), and a count of independent bets. This makes "count mechanisms, not certificates" a number.
4. **Regime layer:**
   - Man "Regimes": similarity over 7 FRED state variables.
   - The Two Sigma 4-regime GMM.
   - An HMM (Baum-Welch lineage).
   - Named-series `macro_conditional`: VIX, 2y yield and CPI, where today it takes the first series available.
   - An inflation-regime flag.
5. **Public premia done properly (AQR/AHL, documented across all asset classes):**
   - 1/3/12-month vol-scaled trend. The desk's `style_premia` trend speeds are 1/5/20 *days*, which have decayed.
   - True 5-year value / PPP. The desk's "value" is about a 6-week mean.
   - Value × momentum.
   - Cross-sectional FX carry from swaps.
   - AQR macro momentum: Sharpe 1.2 alone, 1.4 blended with trend.
   - Restrict `defensive` to equity indices; AQR does not define it for FX or commodities.
6. **A signed calendar-window family plus exact fix clocks** (Tokyo, ECB, LBMA AM/PM, and gotobi days, DST-aware). These unlock the documented dated flows:
   - Pre-FOMC drift.
   - FOMC-day short USD (14.47bp vs 1.73bp).
   - The Treasury auction cycle.
   - Month-end dash-for-cash.
   - The FX-fix W-pattern (about 2bp per leg, raw spread only).
   - Month-end London fix conditioned on month-to-date S&P (≈2.17bp per 1pp, p=0.0002).
   - The Gotobi Tokyo fix.
   - Month-end 60/40 rebalancing (Man).
   - The European-open window for US indices (Sharpe 1.6, after costs, 2006-2018).
7. **Stat-arb residuals.** Avellaneda-Lee PCA / ETF-residual reversion on the FX majors, metals and index panels (60-day window, enter at 1.25σ), the volume-scaled "trading-time" contrarian, and relative value guarded by `correlation_regime` (Brown's March-2000 lesson).
8. **Two-sided sizing machinery.** Vol targeting per asset class with t-2 EWMA vol; meta-labelling as a sizing layer; dynamic momentum weighting; Kelly under parameter uncertainty; opportunity-conditioned leverage. Every item is two-sided and must prove forward E[log W] (Rule 1).
9. **Validation upgrades:**
   - BHY cross-check.
   - Sample-uniqueness weights.
   - Clustered feature importance.
   - Diurnal-periodicity-adjusted vol for every ATR-threshold family.
   - A pre/post-publication splitter with a ~50% out-of-sample haircut.
   - Negative controls: pre-FOMC drift in bonds, and COT momentum in FX. If either "passes", the harness leaks.
10. **New data:**
    - The full CFTC TFF/disaggregated set, plus ICE and LME COT.
    - LBMA fix history (free, since 1968).
    - TreasuryDirect auctions.
    - SNB sight deposits.
    - Japan MOF intervention.
    - JPX investor flows.
    - NY Fed dealer positions.
    - Dukascopy SWFX sentiment.
    - EIA inventories.
    - Commodity term structure (basis and basis-momentum; spot premia 5–14% p.a.).
    - Consensus surprises.

## Decay flags and falsifiers (so trials are not wasted)

- Unconditional overnight drift has been about zero since 2021 (NY Fed 2026).
- The pre-FOMC drift is contested.
- Crabel reports his worst opening-range years recently. A 2026 replication found it gross-only on 5 index CFDs.
- Winton's fast trend Sharpe went 1.85 → 0.85 → 0.00 (1984–2013).
- Buy-the-dip showed no alpha across AQR's 196 variants.
- Do not value-time style premia (AQR).
- 65% of 452 anomalies fail once microcaps are controlled (Hou-Xue-Zhang), and 96% of the trading-frictions category.

## Not reachable at retail

Sub-millisecond market making, latency and feed arbitrage, and last look (Citadel Securities, XTX, HRT, Jump, Virtu, Tower).

The POSIT / order-book strategies alleged in Renaissance v. Belopolsky & Volfbeyn are **do not copy**: they were alleged to be unlawful and are irrelevant to CFDs. The Jane Street SEBI expiry pattern was alleged manipulation in India; only the dated-flow *hypothesis* on US/EU opex is filed.

## What is not knowable

No live Medallion signal, parameter or feature set is public. Every signal-level Renaissance row is REPORTED or SPECULATED and mostly describes the 1988-1997 futures era.

Material from HRT, Jump, G-Research, Squarepoint, Qube, Millburn and Campbell is thin, as are podcast transcripts behind logins (Odd Lots, Hidden Forces, Macro Voices) and the forums behind Cloudflare (Nuclear Phynance, Wilmott, QuantNet, Glassdoor/WSO).

## Incident

One download batch in the stat-arb miner sent an HTTP User-Agent containing the principal's email to sec.gov, twosigma.com, hudsonrivertrading.com, worldquant.com and findlaw.com. It was not repeated, and no personal data appears in any file here.
