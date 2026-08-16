# MANDATE_RESEARCH_FACTORY

**Status: ACTIVE (standing)** — governs all research compute from now on.
Supersedes ad-hoc hunting. MT5 = execution surface only; alpha engine ingests
every data family that can be legally obtained, and every hypothesis enters one
pipeline: `data anomaly → economic mechanism → asset mapping → horizon →
falsifiable rule → costs → OOS → forward → shadow → live`.

## 0. Core principle

Price/OHLC is ONE data family among many. Institutions win on informational
asymmetry: futures order flow, positioning, options-implied expectations,
macro state, events, flows, alternative data. Compete by layering these onto
the proven mechanism pipeline. Every desk competes for research budget; the
global allocator gives compute and capital to whichever market (crypto vs MT5)
produces the highest marginal validated geometric growth.

## 1. Research divisions (competing desks)

Each desk generates independent hypotheses, journals them in `docs/desks/`,
and is scored by survivors delivered + marginal portfolio value, not activity.

| Desk | Scope | Current state |
|---|---|---|
| Intraday Structure | session-range, momentum, gap, DOW mechanisms | LIVE (hunt6/hunt7) |
| Relative Value | pair/basket/spread relationships, residuals | RV triangle: verdict NO AUTHORITY on Vantage costs; conditional re-test on ECN (Fusion Zero) |
| Macro | rates, inflation, monetary policy (FRED lake) | lake exists; conditioning not yet wired |
| Flow | futures vol/OI, COT, CLS | COT fetch for gold exists; FX-major COT pending |
| Options | IV, skew, gamma, expiry, expected move | not started (data gated) |
| Microstructure | order book, MBO, aggressor flow, lead/lag | not started (data gated: CME MBO) |
| Event | news, economic surprises (actual − consensus), reaction patterns | not started |
| Alternative Data | search/attention/weather/etc. | not started |
| Cross-Asset | lead/lag, transmission, price-discovery leadership | not started |
| Execution | fills/spread/latency/venue quality | partial (spread_gate, cost models) |
| Seasonality/Calendar | fixings, month-end, expiry, holidays | DOW control tested (dead); calendar gates pending |
| External Alpha Intelligence | MQL5/Myfxbook/papers/GitHub/forums → falsifiable hypotheses only | ongoing habit; nothing adopted blindly |
| Unknown-Unknown | deliberate search outside taxonomies | standing agent role |

## 2. Super-miner standing programs

Priority tiers (P1 = wire into running pipeline now; P2 = next; P3 = queued):

- **P1 (in pipeline already):** shadow→promotion ladder w/ auto-verdict +
  auto-retire; dynamic Kelly sizing (Q_OPT from equity; ramp by live n); weekly
  universe sweep (hunt7, Mondays 23:00 UTC auto); research genealogy (every
  test logged with family tag — hunt6/hunt7 records); live-vs-backtest reality
  model (live_ledger vs forward ledger; spread/latency/MAE/MFE audit); alpha
  decay + change-point detectors (roll20 exp monitor in promoter).
- **P2 (next builds):** Asia-session super-miner (see §3); survivor-neighborhood
  expansion hammer; A/B/C trade-quality scoring + size-proportional capital;
  meta-labeler (skip/normal/increase/max on regime+spread+vol+family-health);
  cross-sleeve collision engine (XAU+JPY co-trigger → one macro exposure or four
  edges?); false-breakout classifier for gold (sweep depth, displacement,
  wick/body, reclaim speed); dynamic holding-period engine (exit on edge decay,
  not fixed TTL); MAE/MFE exploitation; profit-lock optimizer; re-entry engine;
  regime-conditioned parameter sets (high/low ATR, Asia range compression,
  prior-US impulse, correlation-break); DOW/month-end/quarter-end/holiday
  conditioning tags.
- **P3 (architecture):** Alpha Independence Hunter (reward = expectancy ×
  robustness × scalability × regime complementarity × DD complementarity ÷
  correlation with live book — bounties for profit during Gold-Asia's worst
  weeks); family-aware allocator (10 hunt6 sleeves = ONE family until residual
  correlations prove otherwise; size cluster for E[log W]); portfolio-first
  promotion (promote on marginal E[log W] gain, not standalone t); Bayesian
  live updater (live evidence dominates posterior); Deflated-Sharpe/PBO haircut
  on multi-test survivors; counterfactual robustness engine (perturb sessions,
  entries, exits, delays; prefer plateaus over points); adversarial killer agent
  (leakage, DST, stale bars, future info, symbol quirks); synthetic disaster
  simulator (gaps, 5× spread, disconnect, duplicate orders, broker rejection);
  winner-feature extractor (survivors vs graveyard predictors); graveyard
  resurrection detector (retest only when hypothesis structurally changed);
  capacity-aware roadmap (€1k→€10m: which edges scale); return-source
  decomposition (daily attribution: edge/leverage/vol/execution/asset/session);
  automated champion replacement; portfolio self-improvement loop (one change
  per batch: test → validate → deploy → repeat).

## 3. Asia-session super-miner (P2 flagship)

Decompose the single most valuable label — "XAU/JPY Asia works" — into causal
state variables and test each separately:
Tokyo open; prior-NY exhaustion (range, trend-day, failed-US-breakout states);
Asia range compression; liquidity sweeps of Asia extremes; Tokyo fixing;
USDJPY impulse; Nikkei/rates co-move; gold–JPY coupling; overnight inventory;
prior-day levels (pivot/VAH/VAL analogues); volatility transitions
(compressed→expanded). Each variable becomes its own family with the SAME
gate battery. Session label → causal state machine.

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

**TIER 1 — free, acquire now:**
- CFTC COT for FX majors + GC (positioning: asset manager vs leveraged fund vs
  dealer; percentile extremes; positioning × price divergence). COT for gold
  already fetched; extend to USDJPY/EURJPY/GBPJPY/CADJPY/AUDJPY etc.
- FRED macro state vector (lake exists): yields 2Y/5Y/10Y/30Y, real yields,
  breakevens, DXY, VIX, MOVE, credit spreads, crude, copper, silver,
  gold/silver ratio, S&P/Nasdaq/Nikkei, CNH. Rates-expectation alpha:
  US-JP 2Y differential, US-EU, UK-US, AU-NZ, curve slope, OIS repricing.
- CME daily futures volume/OI (GC + currencies) — free via CME settlement
  files / barchart-ish mirrors; volume shocks, price+OI co-movement, roll
  behavior, overnight vs RTH participation.
- Calendar/seasonality engine (fixings: Tokyo, London 4pm, WM/Reuters;
  month-end/quarter-end/year-end; futures/options expiry; roll weeks; first/
  last business day; Japanese fiscal year-end) — pure derived data.
- Physical gold indicators where free: LBMA prices, COMEX inventories
  (registered vs eligible), Shanghai premium, futures basis, spot/futures
  dislocation, gold/silver ratio shock, ETF holdings/flows (GLD/SPDR blocked
  previously — retry via other free endpoints).
- FX options surface (free mirrors: investing.com-style IV quotes for
  EURUSD/USDJPY majors; 1W/1M/3M ATM IV, 25Δ RR/BF where scrapable).
- Cross-market lead/lag: Treasury futures → gold; USDJPY → gold; Nikkei → JPY
  crosses; copper → AUD; oil → CAD; CNH → AUD; DXY → EURUSD; GC futures →
  XAUUSD spot. Price-discovery leadership: rolling info-share between futures
  and MT5 spot; trade the lagging instrument from the leading venue.

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
ROI_data, freshness). Same hypothesis factory regardless of source. GLD/SPDR
blocked → registry marks blocked; retry only via alternate free endpoints.

## 8. Standing automation (already wired)

- Weekly universe sweep (hunt7) Monday 23:00 UTC after universe refresh;
  hunt7_state.json freshness guard; results in reports/hunt7.json.
- Daily shadow-forward + promoter at 22:00 UTC.
- Live reality audit continuous in gateway (spread/latency/MAE/MFE recorded
  in live_ledger.jsonl).
- All survivors enter portfolio-first evaluation before capital moves.