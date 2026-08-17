# NEWS + CROSS-MARKET LINEAGE — macro reaction desk

Source: user architecture directive 2026-08-17 (cross-market residual machinery +
NEWS_SHOCK_ALPHA_DESK). SOURCE_GENEALOGY = CROSS_MARKET_NEWS_DESK.

SUPREME ACCEPTANCE: incremental forward net E[log W]. No claim of edge without
the evidence chain. Boundary (binding): exploit information only once legitimately
public; NO embargoed/leaked/MNPI/insider material; first credible source wins —
50 websites repeating one wire = ONE event.

## Cross-market residual machinery (alpha + risk control)
1. Contemporaneous correlation: assets moving together now.
2. Lead-lag: market A moves before B (rates->USDJPY/Gold, oil->CAD, BTC->ETH,
   ES/NQ->risk FX).
3. Conditional correlation: relationships only hold in risk-off/inflation/trend/
   Asia-London/high-vol regimes.
4. Correlation breakdown: stable relation disconnects -> regime-transition signal.
5. Relative-value residuals: trade mispricing after removing common factors
   (the strongest version: predict what an asset SHOULD do, trade the divergence).
6. Cross-sectional ranking: strongest vs weakest currency rather than per-pair
   prediction.
7. Triangular consistency: EURUSD+GBPUSD->EURGBP; AUD/NZD/CAD triples.
8. Cross-asset causal states: yields->USD->Gold; oil->CAD; China/commodities->AUD;
   rate differentials->JPY.
9. Portfolio correlation: new trade must add NEW residual exposure, not duplicate
   hidden factors (USD/JPY/CAD/commodity/risk/rate factor decomposition).

## NEWS_001-036 canonical event-alpha families
NEWS_001 raw surprise momentum        | NEWS_002 raw surprise fade
NEWS_003 revision-adjusted surprise   | NEWS_004 component-weighted surprise
NEWS_005 consensus-dispersion inter.  | NEWS_006 first-move continuation
NEWS_007 first-move reversal          | NEWS_008 delayed second-wave continuation
NEWS_009 delayed second-wave reversal | NEWS_010 Gold reaction residual
NEWS_011 FX reaction residual         | NEWS_012 rates->FX lag
NEWS_013 rates->Gold lag              | NEWS_014 oil->CAD lag
NEWS_015 equities->risk-FX lag        | NEWS_016 positioning x surprise
NEWS_017 crowding squeeze             | NEWS_018 implied-move overreaction
NEWS_019 implied-move underreaction   | NEWS_020 FOMC semantic delta
NEWS_021 Powell novelty               | NEWS_022 ECB novelty
NEWS_023 BOJ novelty                  | NEWS_024 news breakout
NEWS_025 failed-news breakout         | NEWS_026 post-news retest
NEWS_027 post-news vol compression    | NEWS_028 post-shock continuation
NEWS_029 good-news/no-rally           | NEWS_030 bad-news/no-selloff
NEWS_031 cross-market disagreement    | NEWS_032 leader-laggard propagation
NEWS_033 correlation-break after ev.  | NEWS_034 event-day trend
NEWS_035 event-day reversal           | NEWS_036 next-day drift

Each family = event x instrument x surprise bucket x positioning x regime x
reaction state x horizon (0-1s, 1-5s, 5-30s, 30s-2m, 2-10m, 10-60m, session,
1 day, 2-5 days). We do NOT race colocated HFT on the first tick; the realistic
target is the second-to-hours propagation cascade where interpretation,
revisions, cross-asset spread and positioning still matter.

## Core vectors
INFORMATION = SURPRISE + REVISION + COMPONENTS + POSITIONING + EXPECTATION
  SURPRISE = (actual - consensus) / historical surprise volatility, z-scored;
  also CONSENSUS/HIGH/LOW/WHISPER/REPRICING/IMPLIED_MOVE/POSITIONING.
MARKET_RESPONSE = rates + USD + commodities + equities + vol (observed 0-60m).
ALPHA = EXPECTED_RESPONSE - OBSERVED_RESPONSE  (REACTION_FAILURE_ALPHA family)
Pre-event state (public info only) may predict P(overreaction/continuation/gap/
vol) without predicting the number.

## Source hierarchy (affects confidence and sizing)
TIER0 official agency/exchange/regulator | TIER1 licensed wire | TIER2 quality
financial media | TIER3 specialist reporters | TIER4 social media | TIER5 noise.

## Timestamp taxonomy (prove the edge, kill the latency leaks)
scheduled_release_time -> source_publish_time -> our_arrival_time ->
parse_complete_time -> decision_time -> order_send_time -> broker_ack_time ->
fill_time. TOTAL_ALPHA_LATENCY decomposed; LLM NEVER in the fastest execution
loop (structured parser -> deterministic model -> execution; LLM only offline
for textual releases and discovery).

## Broker reality (mandatory)
Event strategies must be validated against EVENT_SPREAD_DISTRIBUTION,
EVENT_SLIPPAGE_DISTRIBUTION, FILL_PROBABILITY, LATENCY_DECAY_CURVE from the
actual broker. +0.20R raw expectancy with 0.25R news slippage does not exist.

## Implementation status
- CROSS_ASSET_RESIDUAL_DESK: BUILDING (research/run_hunt21.py — XAU factor model
  vs EURUSD/USDCAD/AUDJPY/BTCUSD/XAGUSD + triangular residuals on
  EURGBP/AUDNZD/AUDCAD/NZDCAD/EURCHF/GBPJPY)
- EVENT_HOUR_EFFECTS: BUILDING (research/run_hunt22.py — US-macro window hours
  12/13 UTC and 14:00-window hours 18/19 UTC; drift/reversal; honest label:
  event-TIME effects, no surprise conditioning yet)
- NEWS_CAPTURE_DESK: BUILDING (research/news_desk.py — schedule ingestion,
  surprise schema, reaction capture to data/news_captures.jsonl, ready for
  Fusion gateway; schedule table stays EMPTY until a licensed calendar source
  populates it; no invented release data)
- LLM-in-fast-loop removal, latency decomposition, event cost distributions:
  QUEUED (require live gateway + licensed data)
- Positioning/options/consensus data sources: QUEUED (external)