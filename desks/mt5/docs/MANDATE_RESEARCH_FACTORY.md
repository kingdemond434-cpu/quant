# MANDATE_RESEARCH_FACTORY — INSTITUTIONAL ARCHITECTURE v2

**Status: ACTIVE (standing)** — governs all research compute from now on.
Supersedes ad-hoc hunting. MT5 = execution surface only; alpha engine ingests
every data family that can be legally obtained, and every hypothesis enters one
pipeline: `data anomaly → economic mechanism → asset mapping → horizon →
falsifiable rule → costs → OOS → forward → shadow → live`.

## 0. Core principle

Price/OHLC is ONE data family among many. Institutions win on informational
asymmetry: futures order flow, positioning, options-implied expectations, macro
state, events, flows, alternative data. Compete by layering these onto the
proven mechanism pipeline. Every desk competes for research budget; the
Research-Capital Governor gives compute and capital to whichever market
(crypto vs MT5) produces the highest marginal validated geometric growth.

End state: ONE closed loop —
`discover information → generate mechanism → falsify → validate → forward-test
→ allocate → execute → measure reality gap → update beliefs → mine failures →
redeploy` — continuous, with no fixed "done" state.

## 1. Institutional desk roster (competing divisions)

Every desk generates independent hypotheses, journals in `docs/desks/`, and is
scored by survivors delivered + marginal portfolio value, not activity.

| Desk | Mandate | Current state |
|---|---|---|
| **Data Advantage** | continuously discover → score → acquire → normalize → timestamp → backfill free/paid/relationship-only feeds by expected marginal E[log W]; priority: CME MBO/PCAP, CLS FX flow, OTC vol/skew, rates, physical gold, prime-broker/custodian/RFQ | Tier-1 free stack live (CFTC COT legacy+disaggregated+TFF, FRED 32-series lake, FX data); BIS/CME/LBMA blocked-registered; `data_registry.json`; dataset frontier doc in progress |
| **Intraday Structure** | session-range, momentum, gap, DOW, level-breakout mechanisms across universe | LIVE (hunt6 sleeves + hunt7/9 sweeps) |
| **Relative Value** | pair/basket/spread residuals, cointegration | RV triangle: NO AUTHORITY on Vantage costs; corroborated by Deux/RAZOR trade attribution (RV is the elite public engine); conditional re-test on ECN (Fusion Zero) |
| **Alpha Independence** | reward = NOT standalone Sharpe but **incremental portfolio growth during the current book's worst regimes**; dedicated drawdown-alpha mining, cross-asset lead/lag, event/fixing, carry, RV, momentum, breakout, MR, vol, options, macro, flow, seasonal, microstructure, alt-data families all competing | P3 architecture; bounties for profit during Gold/JPY family's worst weeks |
| **Mechanism** | decompose every survivor into **causal/state variables** — Asia/Gold/JPY cluster first: session subwindows, rates, JPY basket state, futures flow, vol, prior-session path, news, positioning, options, liquidity — then search local siblings around whatever proves causal, not blindly cloned params | P2 flagship (§3); trade-path evidence banked (TRADE_PATH_REPORT.md) |
| **Validation** | full genealogy of every test; family-level multiplicity (deflated t); purged walk-forward; CPCV/PBO/deflated-Sharpe; neighborhood perturbations; symbol/timeframe/session counterfactuals; 2×/3×/5× cost stress; block bootstrap; Monte Carlo; regime splits; synthetic gaps; latency/fill failures; adversarial **"kill the champion"** agent | multiplicity.py LIVE (family+total haircuts, gate_ds); 3-fold WF + 2× stress in every hunt; PBO/killer agent P3 |
| **Forward Evidence** | shadow → tiny live → learning allocation → full allocation → growth allocation; **Bayesian updating from realized fills**, MAE/MFE, expectancy, DD, costs, trigger frequency, regime behavior; accelerate on agreement, not calendar time | shadow→promoter ladder LIVE; regime_monitor LIVE (rolling-90 realized exp per sleeve); Bayesian upgrade P3 |
| **Portfolio/Allocator** | cluster correlated sleeves; residual covariance + latent factors; marginal E[log W] per next unit of risk; fractional/dynamic Kelly with uncertainty haircuts; **rotate capital into highest conditional edge; scale by state not static q**; explicitly reward drawdown-offsetting strategies | auto_lot Kelly ramp LIVE; cluster-aware allocator + dynamic Kelly P3 |
| **Execution** | log every quote/fill/rejection/latency/markout across Fusion + additional brokers; predict spread/slippage/toxicity; market vs limit vs delayed/retrace entries; partial fills; stop placement, trailing, time exits, re-entries; route to highest expected realized R venue | spread_gate LIVE; gateway reality audit LIVE (live_ledger); Fusion Zero plan = venue routing v1; markout/toxicity P2 |
| **Trade-Path** | mine every winner/loser path: profit locking, runner size, dynamic TP/SL, time stops, add-on spacing, re-entry persistence, convex winner capture — **extract more R from the same signal** | SEEDED: trade_path.py on armed gold book — top 10% trades = 159% of total R; TTL exits are the engine (+0.252R); 16% of losers had +1R available → H_TP1 breakeven-trail hypothesis (re-validate before use) |
| **Regime/Decay** | change-points in expectancy, win rate, payoff, MAE/MFE, spread, holding time, correlation; alpha half-life; **hibernate weakening expressions before negative, reactivate on posterior recovery** | regime_monitor.py LIVE (90-trade window, warn/hibernate flags); promoter auto-retire LIVE |
| **Capacity** | model fills/slippage/margin/broker limits/correlation as capital scales €1k→€10m+; change strategy mix as sleeves hit capacity | P3; EUR-400 equity guard = first capacity rule |
| **External Intelligence** | mine MQL5/Myfxbook/Darwinex, papers, GitHub, YouTube, forums, conferences, broker research, patents, job listings, vendor catalogs, new datasets; convert ideas to falsifiable hypotheses; **never copy headline returns without reconstructing the payoff/risk mechanism** | ACTIVE: survivor reverse-engineering of RAZOR/Deux/Goldtrade/Reaper → 5 hypothesis families; hunt9 (level breakouts + failed-breakout) LIVE; payoff-structure thesis CONFIRMED on own book |
| **Unknown-Unknown** | fixed exploration budget outside current taxonomies; continuously ask "what information source, market relationship, venue, transform, time horizon, or economic mechanism have we never tested?" | standing agent role |
| **Research-Capital Governor** | rank every next action — dataset, code improvement, execution fix, survivor family, model, broker, experiment — by **marginal E[log W] × P(success) × scalability × orthogonality ÷ compute/time/cost**; auto-send compute and money to highest-value items first | standing role; governs this backlog (§9) |

## 2. Super-miner standing programs

Priority tiers (P1 = wired into running pipeline now; P2 = next; P3 = queued):

- **P1 (in pipeline already):** shadow→promotion ladder w/ auto-verdict +
  auto-retire; dynamic Kelly sizing (Q_OPT from equity; ramp by live n); weekly
  universe sweep (hunt7 structure + hunt8 COT + hunt9 survivor-level families,
  Mondays 23:00 UTC auto, 6-day freshness guard); research genealogy (every test
  logged with family tag); live-vs-backtest reality model (live_ledger vs
  forward ledger; spread/latency/MAE/MFE audit); multiplicity correction
  (research/multiplicity.py — deflated t per family + total, gate_ds on every
  survivor); regime/decay monitor (research/regime_monitor.py — rolling-90
  realized exp per sleeve, warn/hibernate flags, watchdog-only); trade-path
  evidence (research/trade_path.py — winner/loser path mining on armed book).
- **P2 (next builds):** Asia-session mechanism decomposition (§3); survivor-
  neighborhood expansion hammer; A/B/C trade-quality scoring + size-proportional
  capital; meta-labeler (skip/normal/increase/max on regime+spread+vol+family-
  health); cross-sleeve collision engine (XAU+JPY co-trigger → one macro
  exposure or four edges?); false-breakout classifier for gold (sweep depth,
  displacement, wick/body, reclaim speed — hunt9 failed_breakout = first cut);
  dynamic holding-period engine (exit on edge decay, not fixed TTL — informed by
  trade-path exit attribution); MAE/MFE exploitation (H_TP1: trail stop to
  breakeven after +1R — re-validate before any use); profit-lock optimizer;
  re-entry engine; regime-conditioned parameter sets (high/low ATR, Asia range
  compression, prior-US impulse, correlation-break); DOW/month-end/quarter-end/
  holiday conditioning tags; event/fixing engine (Tokyo/London/NY opens,
  CPI/NFP/FOMC/BoJ dates from official schedules); options-derived state (skew,
  term structure, expected move) via free IV mirrors; macro/rates relative-value
  conditioning (yield differentials × intraday triggers); cross-market
  price-discovery lead/lag (futures-state → MT5 spot); execution markout/
  toxicity from live fills.
- **P3 (architecture):** Alpha Independence Hunter (reward = expectancy ×
  robustness × scalability × regime complementarity × DD complementarity ÷
  correlation with live book — bounties for profit during Gold-Asia's worst
  weeks); family-aware allocator (10 hunt6 sleeves = ONE family until residual
  correlations prove otherwise; size cluster for E[log W]); portfolio-first
  promotion (promote on marginal E[log W] gain, not standalone t); Bayesian live
  updater (live evidence dominates posterior); PBO/selection-bias audit beyond
  deflated t; counterfactual robustness engine (perturb sessions, entries,
  exits, delays; prefer plateaus over points); adversarial killer agent
  (leakage, DST, stale bars, future info, symbol quirks); synthetic disaster
  simulator (gaps, 5× spread, disconnect, duplicate orders, broker rejection);
  winner-feature extractor (survivors vs graveyard predictors); graveyard
  resurrection detector (retest only when hypothesis structurally changed);
  capacity-aware roadmap (€1k→€10m: which edges scale); return-source
  decomposition (daily attribution: edge/leverage/vol/execution/asset/session);
  automated champion replacement; portfolio self-improvement loop (one change
  per batch: test → validate → deploy → repeat).

## 3. Asia-session mechanism decomposition (Mechanism Desk flagship)

Decompose the single most valuable label — "XAU/JPY Asia works" — into causal
state variables and test each separately: Tokyo open; prior-NY exhaustion
(range, trend-day, failed-US-breakout states); Asia range compression;
liquidity sweeps of Asia extremes; Tokyo fixing; USDJPY impulse; Nikkei/rates
co-move; gold–JPY coupling; overnight inventory; prior-day levels (pivot/VAH/
VAL analogues); volatility transitions (compressed→expanded). Each variable
becomes its own family with the SAME gate battery. Session label → causal state
machine.

## 4. Survivor-neighborhood expansion

Once a sleeve survives, hammer its neighborhood with most of the compute:
±15/30/60-min session shifts; adjacent symbols (JPY complex, metals); adjacent
horizons; alternate exits (ATR trail, time stop); alternate regime filters;
alternate spread gates. Proven veins get the compute (research-compute
allocator: majority to survivors' neighborhoods, substantial minority to
orthogonal search, small exploration budget).

## 5. Institutional data stack — acquisition queue

Every source passes: uniqueness × latency × history × coverage × accessibility ×
cost × likely alpha × overlap × hypotheses enabled → ROI-ranked queue.
Free sources acquired immediately; paid sources only when capital justifies.

**TIER 1 — free, acquire now (mostly DONE):**
- CFTC COT legacy (11 contracts, 1986→2026: gold, silver, JPY, GBP, CAD, AUD,
  NZD, CHF, DXY, S&P, Nasdaq — `data/cot/`) + **disaggregated** (gold/silver,
  2006→2026, `data/cot_disagg/`) + **TFF financial-futures** (JPY/EUR/GBP/CAD/
  AUD/NZD/CHF/S&P/Nasdaq, 2018→2026, `data/cot_tff/` — EUR now covered, unblocks
  the legacy-schema gap). FX not in disaggregated (59 commodity markets only).
- FRED macro state vector (32 series lake: yields, real yields, breakevens,
  DXY, VIX, credit, crude, copper, S&P/Nasdaq/Nikkei, ECBDFR, JP 3M). Rates-
  expectation alpha: US-JP 2Y differential, US-EU, UK-US, AU-NZ, curve slope.
- CME daily futures volume/OI (GC + currencies) — free via CME settlement
  files; volume shocks, price+OI co-movement (pending fetch).
- Calendar/seasonality engine (fixings: Tokyo, London 4pm, WM/Reuters;
  month-end/quarter-end/year-end; futures/options expiry; roll weeks) — pure
  derived data.
- Physical gold indicators where free: LBMA prices (blocked page, probe again),
  COMEX inventories (registered vs eligible — CME API bot-blocked), Shanghai
  premium, futures basis, gold/silver ratio shock, ETF holdings/flows.
- FX options surface (free mirrors: ATM IV, 25Δ RR/BF where scrapable).
- Cross-market lead/lag: Treasury futures → gold; USDJPY → gold; Nikkei → JPY
  crosses; copper → AUD; oil → CAD; CNH → AUD; DXY → EURUSD; GC futures →
  XAUUSD spot.

**TIER 2 — conditional (capital/licensing justifies):**
- CME MBO/L2 order flow (gold + FX + index futures): aggressor flow, queue
  depletion, imbalance, sweeps, iceberg inference, absorption, microprice,
  book convexity → GC order flow predicting XAUUSD MT5 over 5s-60m.
- CLS FX flow data (directional imbalance, volume surges, currency-specific
  flow, stress-period flow, spot vs swaps) — for the Asia JPY family.
- Options-implied suite: CME CVOL/greeks, strike-level OI, gamma/delta
  concentrations, expiry pinning, expected move, vol-of-vol, smile curvature.
- Broker/client positioning (retail long/short, stop/limit concentrations)
  where licensable; contrarian feature: extreme retail + institutional flow
  opposite + price refusal to follow.
- Cross-broker feeds: quote/spread dispersion, lead-lag between venues,
  stale-quote probability, liquidity-shock propagation (as INFORMATION STATE
  for slower trades, not latency arb).
- Alternative data division: Google Trends, Wikipedia pageviews, social
  attention, news frequency, weather, prediction markets, freight rates,
  mining production, ETF creation/redemption, Asian physical demand proxies.
- NLP: central-bank language (Fed/ECB/BoJ/BoE/RBA/RBNZ/BoC statements, minutes,
  speeches) — hawkish/dovish embeddings, language DELTA not sentiment; news
  significance engine (novelty, surprise, credibility, historical analogue,
  price-already-reacted).

**TIER 3 — only at real scale:** LSEG Tick History/PCAP (30+ yr trades/quotes/
depth, 580+ venues), ICE datasets (FX, commodities, forward curves).

## 6. Universe expansion

Map MT5 instruments into economic families and mine each: metals (XAU, XAG, Pt,
Pd), FX majors/minors/EM, JPY complex (USDJPY/EURJPY/GBPJPY/CADJPY/AUDJPY/
NZDJPY/CHFJPY), commodity currencies (AUD/NZD/CAD crosses), indices (US500,
NAS100, US30, GER40, UK100, JP225, HK50, AUS200), energy (WTI, Brent, NG),
softs/agriculture where covered, rates/bond CFDs where supported, crypto CFDs
only where signal adds beyond crypto infra.

## 7. Data governance

Every source registers in `data_registry.json` (lifecycle, provenance, cost,
ROI_data, freshness). Same hypothesis factory regardless of source. Blocked
sources (BIS API, CME warehouse bot-block, LBMA JS page, legacy COT EUR)
registered as blocked; retry only via alternate free endpoints. `data/lake`
convention: large parquet mirrors untracked on disk, tracked in registry only.

## 8. Standing automation (already wired)

- Weekly universe sweep (hunt7 structure + hunt8 COT + hunt9 survivor-level
  families) Monday 23:00 UTC after universe refresh; hunt7_state.json freshness
  guard; results in reports/hunt7.json, hunt8.json, hunt9.json
  (multiplicity-annotated).
- Daily shadow-forward + promoter at 22:00 UTC + regime/decay monitor
  (regime_state.json, warn/hibernate flags per sleeve).
- Live reality audit continuous in gateway (spread/latency/MAE/MFE recorded
  in live_ledger.jsonl).
- All survivors enter portfolio-first evaluation before capital moves.

## 9. Highest-ROI next wave (Governor ordering)

1. **Asia/Gold/JPY mechanism decomposition** — convert the session label into
   causal state variables (§3); compute to the proven vein.
2. **Drawdown-orthogonal alpha hunting** — strategies that earn during the
   current book's worst regimes (Alpha Independence bounties; hunt7/8/9 already
   sweeping orthogonal families weekly).
3. **Dynamic Kelly / cluster-aware allocation** — residual covariance between
   the 10 sleeves, marginal E[log W] rotation, state-dependent q.
4. **Execution alpha + proprietary fill data** — markout/toxicity from
   live_ledger, multi-broker routing (Fusion), fill prediction; the realized
   fills DB becomes an information asset competitors cannot buy.
5. **Paid institutional flow/order-book/options data** — CME MBO/PCAP, CLS,
   OTC vol/skew only when capital justifies (Tier 2).

## 10. Canonical 27-bucket backlog (status)

1. Mechanism mining around proven Gold/JPY family — causal/session
   decomposition + sibling expansion | P2, flagship §3
2. Orthogonal alpha across FX/metals/indices/rates/energy/cross-asset | hunt7
   LIVE; hunt8 (COT) LIVE + verdict: no standalone COT edge; hunt9 (levels)
   LIVE; indices/energy data = Tier-1 fetch pending
3. Proprietary/paid data (CME MBO, CLS, OTC vol, positioning, physical) |
   Tier-2/3 queue in §5, ROI-ranked
4. Portfolio-first research: every strategy scored by marginal E[log W] | P3
   (Alpha Independence Hunter; portfolio_hunt6 = prototype)
5. Adaptive leverage/Kelly with cluster-aware covariance + state-dependent
   risk | P1 (auto_lot/ramp); cluster-covariance upgrade P3
6. Execution alpha: market vs limit, entry delay, spread/slippage gating,
   venue routing, fill prediction, markout/toxicity | spread_gate LIVE;
   venue routing = Fusion Zero plan; markout/toxicity = P2
7. Trade-path optimization: MAE/MFE, dynamic exits, profit lock, runners,
   time stops, re-entry | SEEDED (trade_path.py evidence: TTL-engine,
   16%-losers-at-+1R → H_TP1 trail hypothesis; re-validate before use)
8. Regime/state models activating only positive-conditional-expectancy
   sleeves | SEEDED (regime_monitor.py); regime-conditioned params P2
9. Change-point/alpha-decay detection + automatic capital rotation | P1
   (regime_monitor + promoter roll20/maxDD/exp monitors + auto-retire)
10. Hierarchical models sharing info across related sleeves | P3 (JPY basket
    state model, gold macro-state model)
11. Deflated Sharpe/PBO/family-level multiplicity | P1 (multiplicity.py;
    PBO deeper audit P3)
12. Adversarial falsification: leakage, DST/session bugs, impossible fills,
    spread errors, overfit | P3 (killer agent); DST/session audit available
    on demand
13. Synthetic stress + operational fault simulation | P3
14. Multi-broker/live-feed shadow replication | Fusion Zero = active plan;
    cross-broker state (Tier 2)
15. Capacity/scalability modeling across capital scales | P3; €400 equity
    guard = first rule
16. Research-compute allocation: mine successful neighborhoods, reserve
    orthogonal budget | P2 convention (neighborhood hammer + unknown-
    unknown desk)
17. External alpha intelligence (papers/MQL5/Myfxbook/YouTube/GitHub/forums)
    → falsifiable hypotheses | ACTIVE: survivor reverse-engineering →
    hunt9 level/failed-breakout families; payoff-structure thesis confirmed
    on own book
18. Drawdown-alpha mining (profit when champions lose) | P3 (DD bounty in
    Alpha Independence Hunter)
19. Meta-labelers (skip/normal/increase/max-size) | P2
20. Automated champion/challenger replacement + Bayesian live updating | P1
    (promoter) + P3 (Bayesian posterior upgrade)
21. Cross-market price-discovery: futures/order flow → slower MT5 | P2;
    gated on Tier-2 futures data
22. Event/fixing engines: Tokyo/London/NY opens, CPI/NFP/FOMC/BoJ, month-end,
    expiry, benchmark flows | P2 (calendar-engine build); FRED/CFTC data
    ready; official schedules = free
23. Options-derived state: skew, term structure, gamma, expected move | P2
    (free IV mirrors); CME CVOL = Tier 2
24. Macro/rates relative-value conditioning | P2 (FRED lake ready: yield
    differentials × intraday triggers)
25. Physical commodity + alternative data branches | Tier-1 queue (LBMA/SGE/
    WGC registry entries) + Alt-Data desk
26. Permanent dataset frontier agent (discover → score → acquire queue) |
    standing role; registry + Tier 1/2/3 §5 = current frontier
27. Proprietary execution/market-state DB (compounding asset over time) |
    LIVE via live_ledger.jsonl + gateway reality audit + shadow ledgers

Status legend: P1 = wired and running; P2 = next build (data-ready where
noted); P3 = architecture queue; LIVE/SEEDED/ACTIVE = executing now.