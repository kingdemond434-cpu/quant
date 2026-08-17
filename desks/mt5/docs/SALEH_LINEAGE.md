# SALEH LINEAGE — Mir Saleh / Jesse ecosystem hypothesis family

Mined from: indexed channel catalog (~70 uploads, partial captions), current public
Jesse strategy profile, official Telegram announcement feed, Jesse docs, archived
tutorials. Registered 2026-08-17. SOURCE_GENEALOGY = SALEH_MIR_JESSE.

SOURCE_TRUST: code/docs HIGH; strategy mechanism MEDIUM/HIGH where exact;
video headline returns LOW; forward evidence UNKNOWN until independently verified.
SUPREME ACCEPTANCE: incremental forward net E[log W].

## Registry: SALEH_001 - SALEH_145 (145 canonical seeds)
- SALEH_001-010  EMA family: EMA21/50 trend, EMA+ATR stop, MTF confirmation, EMA50/100/200
                 alignment, EMA50 pullback-touch, prev-20-bar target, partial->BE->runner,
                 RSI runner exit, reward/risk gate, failed-pullback reversal
- SALEH_011-017  Cross-TF/cross-market anchor: 2x/4x/6x anchor, dual-anchor agreement,
                 anchor transition, anchor disagreement reversal, CROSS-ASSET anchor
                 (XAU<-DXY/rates, JPY<-yield spread, AUD<-commodity, CAD<-crude, silver<-gold)
- SALEH_018-024  Supertrend: continuation, flip entry, pullback, +HTF alignment, +ADX,
                 failed flip, stop-and-reenter
- SALEH_025-035  BB/Keltner squeeze: BB-inside-KC breakout, +linreg direction, +ADX,
                 duration-conditioned, HTF squeeze->LTF sync entry, first-LTF-bar-of-new-HTF,
                 +ATR trail, +structural target, failed-squeeze fade, release-retest, recompress
- SALEH_036-043  Keltner/MTF vol: KC breakout, pullback, extreme MR, MTF agreement,
                 HTF channel + LTF breakout, width expansion/compression, failed breakout
- SALEH_044-050  MTF momentum: LTF momentum, +2x anchor, dual-TF agreement, acceleration,
                 deceleration/exhaustion, HTF momentum -> LTF pullback, disagreement reversal
- SALEH_051-058  KAMA: direction, slope, price/KAMA cross, dual-KAMA cross, pullback,
                 +ADX, +Choppiness, failed continuation. EXPOSE: KAMA_EFFICIENCY_RATIO,
                 delta-ER, KAMA_ADAPTATION_SPEED as regime features
- SALEH_059-069  Alligator: direction, spread/widening, +ADX, +HTF Alligator, +HTF EMA100,
                 +CMO, +StochRSI pullback, FULL AlligatorAI stack, breakout, pullback,
                 failed trend. MUST be ablation-tested component by component
- SALEH_070-079  Ichimoku: price/Kumo breakout, +trend, TK cross, TK+cloud, cloud pullback,
                 cloud retest, Kumo thickness regime, Kumo twist, MTF agreement, failed breakout
- SALEH_080-091  Turtle/Donchian: breakout, short/long channel, +ATR/N sizing, +vol scaling,
                 pyramid profitable, no-pyramid, channel exit, ATR trail exit, failed fade,
                 retest, long/short asymmetry. Crisis/convexity sleeve candidate
- SALEH_092-101  ADX/MACD/Williams: ADX+MACD continuation, ADX rising, MACD cross+ATR trail,
                 histogram acceleration, ADX+Williams oversold/overbought pullback, Williams MR,
                 Williams failure continuation, DI+/DI- state, ADX acceleration regime.
                 PREFER: ADX percentile, delta-ADX, delta^2-ADX, DI spread
- SALEH_102-108  TEMA: price/TEMA, slope, dual-TEMA cross, pullback, acceleration, MTF, failed
- SALEH_109-118  RSI: extreme MR, crossback MR, extreme+range regime, trend continuation,
                 pullback-in-trend, divergence, failure continuation, RUNNER EXIT, profit-lock
                 trigger, MTF state. RSI entry/regime/exit are SEPARATE questions
- SALEH_119-130  Pairs/RV: price-ratio MR, log-spread MR, OLS residual, rolling-beta residual,
                 cointegrated residual, Kalman hedge, z-score entry, half-life-conditioned,
                 relative momentum, spread breakout, 3-asset basket, cross-sectional residual.
                 BEST source of uncorrelated P&L. MT5 pairs: AUDCAD/NZDCAD, AUDNZD/NZDCAD,
                 EURGBP/GBPUSD, XAU/XAG, AUDJPY/CADJPY, EURJPY/GBPJPY
- SALEH_131-138  Breakout/ATR/trail: trend-filtered breakout, +ATR fixed exit, +ATR trail,
                 best-price trail, +time exit, retest, failed fade, re-entry
- SALEH_139-145  TrendWaveRider V1/V2, TrendSwing V1/V2, ETHTrendBB, SlowTrend, SuperScalper:
                 reconstruction/delta-analysis only, never invented rules

## Infrastructure steals (deepest value)
- RULE_SIGNIFICANCE_GATE (-> SIGNAL_INFORMATION_GATE): signal-only backtest, LONG/SHORT
  separated, horizons 1/2/5/10 bars, detrended returns, block-bootstrap null, family
  multiplicity correction, OOS recurrence. BUILDING (research/signal_gate.py)
- CANDLE_MONTE_CARLO: trade bootstrap, moving-block candle bootstrap, regime-stratified
  block bootstrap, vol-scaled synthetic paths, jump injection, spread/latency shock.
  Compare ORIGINAL/MEDIAN/p05/p01; selection-luck penalty for absurd results. QUEUED
- MCP_TYPED_RESEARCH_TOOLS (quant.backtest/walk_forward/significance/cost_stress/monte_carlo/
  parameter_surface/portfolio_residual/forward_status): EXISTING in our loop
  (battery, registry, run_hunt18, diagnose.py), typed results to LLM researcher
- VERSION_PINNED_AGENT_RULES: QUANT_AGENT_PROTOCOL_VERSION / RESEARCH_SCHEMA_VERSION /
  VALIDATION_SCHEMA_VERSION / CAPITAL_RULE_VERSION; every LLM session reads the same
  generated rules. BUILDING (docs/QUANT_AGENT_PROTOCOL.md)
- MULTI_MODEL_RESEARCH_HARNESS: RESEARCHER_SCORE = validated survivors x forward survival
  x marginal E[log W] / tokens / compute / wall time. QUEUED
- 24/7 PARALLEL_RESEARCH_JOBS: RESEARCH_JOB first-class object (family, EV, compute budget,
  agent, checkpoint, trials, best candidate, failure reason, next action). EXISTING
  (research_queue.json + research_loop.py)
- OPTIMIZATION_ONLY_AFTER_RAW_EDGE: mechanism with defaults -> prove edge -> THEN surface.
  Never optimize a loser into a winner. EXISTING (battery-first discipline)
- PARAMETER_PLATEAU_SEARCH: broad profitable basin > peak; gradient/sensitivity; interior
  point. QUEUED
- PERIOD_STABILITY_MATRIX: yearly/rolling-3m/6m/12m/regime windows -> % profitable windows,
  worst window, median, regime dependence, edge half-life. QUEUED
- BACKTEST_SPEED_AS_RESEARCH_ALPHA: vectorize/cache hot paths; 3x throughput = 3x rational
  experiments. PARTIAL (numpy vectorized; rmi/aroon loops could go C-accelerated)
- SAME_BACKTEST/LIVE_OBSERVABILITY: benchmark matrix on one surface (IS/OOS/WF/cost1x/2x/
  delay/MC median/p05/forward/corr/marginal E[log W]/capacity). EXISTING (battery + reports)
- STRATEGY_GRAVEYARD: losing variants retained with WHAT STOPPED/CHANGED/HELPED; complexity
  that did nothing deleted. EXISTING (research_registry.jsonl failure_reason)
- SIGNIFICANCE_RERUN_ON_ENTRY_CHANGE: entry code hash changed -> invalidate prior
  statistical certificate -> rerun gate. EXISTING (registry code_hash discipline)

## Do NOT copy (SALEH_NEGATIVE)
Headline percentages (432%/319%/795%/1721%/257%...) as expected returns; 3-5% risk-per-trade
educational sizing; p=0.0 as mathematical zero (finite null samples); significance replacing
chronological OOS/WF; LLM inventing AND certifying its own strategy; stacking 5 indicators
because an AI-generated strategy did.

## Tier S queue (implemented in hunt20)
1. BBSqueezeTrend family: H4 squeeze (BB inside KC, persistence) -> release -> linreg
   direction -> ADX -> first H1 bar of new H4 (SALEH_025/026/027/030/031)
2. Pairs/residual RV (SALEH_120/121/125/128): rolling-OLS spread, z-score MR + breakout
3. EMA pullback + bank/runner (SALEH_006/007): engine bank_frac/bank_protect/runner_trail;
   optimize bank fraction + lock location instead of blind 50/50
4. Cross-market anchor (SALEH_017): base-currency anchor states (AUD/NZD/CAD/JPY/EUR/GBP
   motherships) -> QUEUED (needs external series: DXY, yields, commodities)
5. Turtle/Donchian crisis sleeve (SALEH_080/083/087)
6. AlligatorAI ablation (SALEH_059-069): direction-only vs +ADX vs +CMO vs +StochRSI vs
   +HTF EMA100; kill filters with no incremental edge
7. KAMA + efficiency-ratio state (SALEH_051/052/056)
8. SIGNAL_INFORMATION_GATE infra (used by every future strategy)

## Tier A queue
MTF momentum, MTF Keltner, Supertrend pullback, Ichimoku breakout/retest (XAU M15/H1,
Kijun pullback, failed Kumo breakout), ADX+Williams, ADX+MACD, TEMA trend, RSI
entry/regime/exit separation, breakout+ATR trail, squeeze-failure fade, SALEH_010/023/043/
058/069/079/089/099/108/115/137 failed-mechanism inversions.

## Black-box queue (reconstruct from public sources/trades only, never invent)
TrendWaveRider V1/V2, TrendSwing V1/V2, SuperScalper, SlowTrend, ETHTrendBB,
ADXMacdTrail, MtfKelt2xA, MtfMomo2xA exact thresholds.