# MANDATE_FREE_DATA_SUPREMACY

**Status: ACTIVE (standing)** — Data-Advantage division governing document.
Supersedes the "buy institutional data someday" posture.

## Supreme objective

Continuously maximize forward net **E[log W]** by using the entire paid
institutional data universe as a **map of information advantages**, while
aggressively locating, acquiring, constructing, validating, and exploiting the
best **free/open/legal substitutes, shadows, proxies, reconstructions, and
derived equivalents** for every paid dataset we do not currently own.

This desk never buys subscriptions. `PAID DATASET → identify informational
content → hunt free equivalents → ingest → normalize point-in-time → construct
proxy features → measure information recovery → generate hypotheses → backtest
→ validate → forward test → portfolio-test → deploy if economically useful →
monitor decay → continue searching for better replacements.` Permanently.

## 1. Paid frontier → free replacement graph

The seed frontier (terminals, exchange/MBO/PCAP, institutional FX flow,
options/dealer positioning, rates/credit, positioning/crowding, machine
news, energy/physical, gold/metals, shipping, satellite, consumer/payments,
web/app, employment/supply-chain, alt-data marketplaces — full list in
`data/free_data_frontier.json`) is a **map of information content**, not a
shopping list.

For every paid source:
1. What unique information it contains.
2. What economic mechanism makes it predictive.
3. What portion is observable indirectly for free.
4. Every free/open source with a related observable.
5. Every mathematical reconstruction of the unavailable variable.
6. Every cross-dataset combination that synthesizes a better proxy.
7. Expected information loss vs the paid original.
8. Whether the remaining gap is material for trading.

Never search for a brand-name substitute — search for the **underlying
information content**. Example: `CLS institutional JPY flow` maps to CFTC
JPY TFF positioning, CME JPY futures volume/OI, intraday JPY futures price
impact, USDJPY spot movement, JPY-cross breadth, Tokyo-session volume state,
US/Japan yield differential, retail positioning, fixing behavior, futures
basis, options information, cross-pair flow proxies → synthesize
`FREE_SYNTHETIC_JPY_FLOW_STATE` and test whether it predicts what
institutional-flow data theoretically should.

## 2. Hard classification (machine-readable in data/free_data_frontier.json)

| Class | Meaning |
|---|---|
| FREE_EQUIVALENT_FOUND | Strong free substitute exists (SEC EDGAR/13F, CFTC SDR, FINRA short interest, DTCC public, GDELT, Sentinel/Landsat, EIA, Baltic free indices, Freightos Baltic Index, national stats, central banks) |
| FREE_PROXY_ENSEMBLE | No direct substitute, but combined proxies recover useful information (CLS flow, Bloomberg/Macrobond macro, Kpler/Vortexa energy, State Street/EPFR flows, OptionMetrics-style surface, RavenPack, shipping analytics) |
| PARTIAL_PROXY | Some economic information recoverable (Platts/Argus assessments, Clarksons, Databento/dxFeed delayed truth, LinkUp/Revelio, payment-adjacent) |
| PAID_MATERIALLY_SUPERIOR | Free alternatives leave economically important residual information (kept theoretical — we do not buy) |
| RELATIONSHIP_ONLY | Structurally unavailable publicly; build best observable proxy, quantify loss, keep legal-access queue (see §5) |
| NOT_WORTH_ACQUIRING | No measurable marginal E[log W] |
| ACQUIRE_WHEN_CAPITAL_JUSTIFIES / ACQUIRE_NOW | Theoretical purchase classes retained for ranking only — never executed; the operative action for these is "maximize proxy" |

Never leave a source unclassified.

## 3. Proxy ensembles (priority builds)

- `FX_FLOW_PROXY = f(futures signed return/volume, volume shock, OI change,
  COT positioning, cross-pair breadth, yield differential, spot/futures basis,
  session structure, retail positioning, fixing behavior, event state)`
- `DEALER_GAMMA_PROXY = f(public option OI, strike concentration, IV surface,
  expiry calendar, distance from strikes, approximate Greeks, vol/OI changes)`
- `PHYSICAL_ENERGY_STATE = f(EIA, JODI, AIS, customs, port statistics,
  Sentinel-1/2, refinery reports, futures curve, inventories)`
- `INSTITUTIONAL_RISK_FLOW_PROXY = f(CFTC AM/LM, ETF flows, 13F changes, ICI
  flows, futures positioning, FX price/volume response, rates, risk assets)`
- `MACRO_STATE = FRED + ALFRED + BIS + IMF + OECD + Eurostat + World Bank +
  Treasury + central banks + internal feature engineering` (ALFRED free key =
  point-in-time vintages upgrade path)

## 4. Proprietary derived state lake (self-made IP)

Free does not mean commodity information. Build states nobody publishes:
`JPY_INSTITUTIONAL_PRESSURE`, `JPY_CROWDING`, `JPY_RATE_PRESSURE`,
`JPY_CROSS_BREADTH`, `JPY_INTERVENTION_RISK`, `ASIA_JPY_LIQUIDITY`,
`GOLD_PHYSICAL_PAPER_PRESSURE`, `GOLD_BREAKOUT_QUALITY`,
`GOLD_OPTIONS_PRESSURE_PROXY`, `GOLD_MACRO_STRESS_STATE`,
`GOLD_FUTURES_SPOT_DISLOCATION`, `GLOBAL_USD_LIQUIDITY_STATE`,
`CROSS_ASSET_RISK_TRANSMISSION`, `MACRO_SURPRISE_STATE`,
`INSTITUTIONAL_RISK_APPETITE_PROXY`, `COMMODITY_CURRENCY_PHYSICAL_PRESSURE`,
`LIQUIDITY_VACUUM_SCORE`, `CROWDING_REVERSAL_SCORE`, `SESSION_FLOW_IMBALANCE`,
`PRICE_DISCOVERY_LEADERSHIP`, `REALIZED_EXECUTION_STRESS`.

v1 of the lake is built by `research/free_shadows.py` from the COT legacy/
disaggregated/TFF lakes + FRED lake + H1 universe + live ledger
(→ `data/states/*.parquet`, tracked). Every state carries the **first usable
timestamp** (report as-of + publication lag) so conditioning never leaks.

## 5. Stop futile hunts (STRUCTURALLY_PRIVATE)

Do not search for free copies of: prime-broker client books, bank client FX
order flow, dealer proprietary inventory/quote skew, custodian FX hedges,
genuine RFQ response data, private OTC executable runs, LP internal toxicity,
bank payment networks, card transaction panels, private corporate cash,
private commodity merchant flow, true broker stop databases, private
hedge-fund books. Mark them `STRUCTURALLY_PRIVATE`, build the best observable
proxy graph, quantify expected loss, keep legal-access queue, and never waste
compute pretending an exact free copy exists.

## 6. Gold-specific replacement program

Free shadows: COMEX futures (CME settlement volume/OI — free), warehouse
stocks registered/eligible (free reports), LBMA, WGC, ETF holdings, central-
bank reserves, real yields, DXY, USDJPY, silver, gold/silver ratio, Treasury
futures, CPI/inflation expectations, GDELT, CFTC positioning (legacy + TFF +
disaggregated), macro releases, futures curve, import/export statistics,
Asian market activity, public options data.

Hypothesis families to generate: inventory shock → XAU session return; COT
extreme × failed breakout; real-yield impulse × Gold Asia signal; futures OI
shock × breakout continuation; ETF flow × trend persistence; central-bank
accumulation × downside asymmetry; gold/silver divergence; JPY shock → XAU
behavior; futures/spot dislocation → MT5 opportunity; physical pressure ×
technical trigger. (v1 states: gold_physical_paper, gold_macro_stress,
gold_real_yield_z, gold_ratio_z — hunt10 ablation wiring.)

## 7. JPY-specific replacement program

Free shadows: JPY futures vol/OI, CFTC TFF, BoJ data, JGB yields, Treasury
yields, US/Japan differential, Nikkei/TOPIX, CNH, Asian equities, JPY-cross
breadth, Tokyo fixing, Japan holidays, MoF intervention data, foreign
securities-flow statistics, public options proxies, macro-news state →
`JPY_FLOW_STATE`, `JPY_CROWDING`, `JPY_RATE_PRESSURE`, `JPY_ASIA_LIQUIDITY`,
`JPY_CROSS_BREADTH`, `JPY_INTERVENTION_RISK`; test directly against the Asia
JPY survivors. (v1 states: jpy_tff_dealer/am/lm pct, jpy_am_minus_lm pct,
jpy_rates_z, jpy_cross_breadth.)

## 8. Information value measurement

For every proxy target maintain a **recovery score**: correlation with any
overlapping benchmark, mutual information, predictive equivalence, regime
agreement, directional agreement, incremental OOS expectancy, incremental
Sharpe, portfolio contribution, redundancy. Scale: 0–25% weak shadow;
25–50% partial substitute; 50–75% strong proxy; 75–90% near-equivalent for
our horizon; 90%+ paid dataset likely low marginal value. The goal is
reproducing the **tradable informational advantage**, not the raw dataset.

Ablation framework (run whenever a state is added — v1 = hunt10 on the armed
gold book): A) base strategy; B) base + state gate; C) free proxy ensembles;
compare Δ net expectancy, Δ Sharpe, Δ max DD, Δ tail, Δ regime detection,
Δ portfolio E[log W]. Kill any gate that does not earn its complexity.

## 9. Data-quality + point-in-time discipline

Every observation retains: observation/event timestamp, publication
timestamp, first-known timestamp, arrival timestamp, revision timestamp/
number, source, timezone, session, licensing status. Use ALFRED/vintage data
where revisions exist. Automatically test: gaps, duplicates, timezone/DST
errors, stale observations, survivorship bias, look-ahead, revisions,
outliers, schema changes, outages, symbol mapping, contract rolls, unit
changes. Bad free data must not manufacture alpha. (v1: COT states activate
at report_date + 6 days = next Monday open; FRED daily states activate at
next H1 bar after close; trailing-window percentiles only — no full-sample
statistics.)

## 10. Information-to-alpha factory

For every new proxy state generate the economically motivated transform set
(level, diff, % change, z-score, percentile, surprise, acceleration,
deviation from trend/expectation, cross-market divergence, ×volatility,
×session, ×existing-signal interactions, regime-conditioned, lags, rolling
persistence, extreme indicators, reversal states, cross-sectional ranks),
then feed plausible versions into the hypothesis factory **with family-level
multiplicity control** (research/multiplicity.py). No indiscriminate
brute-force.

## 11. Portfolio objective + permanent bounty

A dataset is valuable only if it improves forward net **marginal E[log W]**;
reward orthogonality, drawdown complementarity, persistence, scalability,
cost robustness, regime complementarity. Permanent bounty loop: "What
expensive institutional dataset do professional funds use that we do not
possess, and what combination of free observables could reconstruct its
tradable information content?" — every answer becomes a research ticket.
Continuously scan exchange catalogs, government APIs, GitHub, papers,
central banks, clearing houses, regulators, Kaggle, AWS Open Data, Google
Dataset Search, Nasdaq Data Link free catalog, brokers, new open-source
projects. Never stop. Every new source enters the evaluation pipeline.

## 12. Desired end state

For every expensive institutional information advantage in the world, we
know one of three things: (A) already reproduce it adequately for free;
(B) cannot reproduce exactly but have a validated free synthetic proxy that
captures economically useful information; (C) residual information is
genuinely unique — keep on the theoretical purchase queue (never bought).
Move sources continuously: unknown → understood → proxied → tested →
exploited. The objective is a proprietary information system built from
thousands of free/open observations and derived signals capturing as much
institutional advantage as legally possible.

## Permanent loop

MAP PAID FRONTIER → FIND FREE SHADOWS → BUILD PROXY GRAPH → INGEST →
SYNTHESIZE PROPRIETARY FEATURES → TEST INFORMATION VALUE → GENERATE
HYPOTHESES → ADVERSARIALLY VALIDATE → FORWARD TEST → PORTFOLIO TEST →
DEPLOY → MEASURE LIVE VALUE → IMPROVE PROXY → REASSESS WHETHER PAID SOURCE
IS STILL NEEDED → DISCOVER NEXT DATASET → REPEAT FOREVER.

## Artifacts

- `docs/MANDATE_FREE_DATA_SUPREMACY.md` (this file)
- `data/free_data_frontier.json` — machine-readable classification of the
  seeded paid frontier (categories, classes, proxy graphs, private list)
- `research/free_shadows.py` → `data/states/*.parquet` — derived state lake
- `research/run_hunt10.py` — paid-vs-free ablation on the armed gold book
  (state-conditioned gates vs base)
- `data_registry.json` — states + frontier entries