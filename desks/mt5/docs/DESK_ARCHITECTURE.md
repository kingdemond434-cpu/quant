# DESK ARCHITECTURE — coverage inventory + conversion ladder (moratorium in force)

Generated 2026-08-17 under QUANT_AGENT_PROTOCOL_VERSION = 2 (architecture moratorium,
rule 11). This is the closed inventory. New ideas go to research_queue.json — they do
NOT enter this table until the quant explicitly reopens architecture.

## Coverage (quant directive 2026-08-17: this is the full intended coverage)
directional alpha | mean reversion | breakout | trend | relative value | carry |
volatility/options | microstructure/order flow | execution | macro | instant
public-news reaction | cross-asset lead/lag | correlation/residuals | positioning/
crowding | forced flows | market plumbing | cross-sectional FX | commodities/physical
flows | crypto/on-chain | alternative data | regime transitions | crisis/convexity |
multi-horizon | AI meta-labeling | veto alpha | exit/position-management alpha |
capital allocation | alpha-decay prediction | unknown-unknown discovery.

## Conversion ladder (the only accepted progress metric)
CODED -> WIRED -> RUNNING -> PRODUCING DATA -> TESTED -> AFFECTING DECISIONS ->
MEASURED BY INCREMENTAL E[log W]

## Coverage -> mechanism status
- directional alpha ............ RFT/SALEH/DAVIDD families; hunt19 DONE, hunt20 RUNNING (gate: universal)
- mean reversion ............... cmr_* hunt21 DONE, retrack/rft_sr_reject hunt19 (gate: universal)
- breakout ..................... rft_candle_break, dav_breakout_fakeout (gate: universal)
- trend ........................ rft_aroon_candle, dav hull/macd (gate: universal)
- relative value ............... pairs RV hunt20 (XAU-XAG log), triangles hunt21 DONE (gate: universal)
- carry ........................ not coded (yields absent; QUEUED with options/policy data)
- volatility/options ........... meta_desk item 4 — QUEUED (no options data)
- microstructure/order flow .... not coded (no tick data); QQQ ticks queued after Fusion
- execution .................... live layer only (engine exec + banked R / runner trail)
- macro ........................ hunt22 event-hour effects RUNNING (gate: universal)
- instant public-news reaction . NEWS corpus registered; news_desk.py watcher RUNNING idle (no licensed feed)
- cross-asset lead/lag .......... cmr_xau_factor_lag hunt21 DONE (gate: universal)
- correlation/residuals ......... cmr_xau_factor_resid, cmr_tri_resid hunt21 DONE (gate: universal)
- positioning/crowding .......... meta_desk item 7 (internal proxies) — not yet spawned
- forced flows .................. no data (QUEUED)
- market plumbing ............... no data (QUEUED)
- cross-sectional FX ............ 22-sym universe + pairs (gate: universal)
- commodities/physical flows .... XAU/XAG/XAU factors (gate: universal); physical flow data QUEUED
- crypto/on-chain ............... BTCUSD/ETHUSD in universe; on-chain data QUEUED
- alternative data .............. GLOBAL_GOLD mandate; externally QUEUED
- regime transitions ............ fragility.py (REAL2) RUNNING + meta_desk item 6
- crisis/convexity .............. Turtle crisis sleeve SALEH_xxx, dav crisis families (gate: universal)
- multi-horizon ................. M15/H1/H4/D1 tiers in hunts + forward clock (gate: universal)
- AI meta-labeling .............. frontier layer docs; not coded (QUEUED)
- veto alpha .................... not coded (QUEUED — market_model_errors / veto stack)
- exit/position mgmt alpha ...... bank_frac/bank_protect_k/runner_trail_k engine, unit-tested; hunt20 families
- capital allocation ............ meta_desk items 1/8/10/13 (opportunity_density, alpha_stack, capacity_ladder, info_value_allocator) — not yet spawned
- alpha-decay prediction ........ meta_desk item 11 (decay_detector) — not yet spawned
- unknown-unknown discovery ..... meta_desk item 15 (failure_mutation -> research_queue) — not yet spawned

## Meta-desk items (research/meta_desk.py, spawns after DONE_merge + DONE_universal_*)
1 opportunity_density (risk mult) | 2 impact_network (lead-lag edges) |
3 participant_inference (heuristic) | 4 options_implied QUEUED | 5 policy_path QUEUED |
6 drawdown_forecast | 7 crowding (internal proxies) | 8 alpha_stack (sizing) |
9 synthetic_discovery (stationarity scan) | 10 capacity_ladder | 11 decay_detector |
12 counterfactual_learner | 13 info_value_allocator | 14 market_model_errors |
15 failure_mutation -> research_queue.

## Pipeline (only surviving path)
hunt cells -> battery (diagnostic only) -> UNIVERSAL 10-GATE (universal_gate.py) ->
registry -> shadow forward -> capital. 182 REAL (105+77) -> fragility REAL2 ->
qquant REAL3 -> merge -> universal_gate hunts -> meta_desk states -> decisions.

Status codes: CODED | WIRED | RUNNING | DATA | TESTED | DECISIONS | E[log W] |
QUEUED (data/idea only, no code).