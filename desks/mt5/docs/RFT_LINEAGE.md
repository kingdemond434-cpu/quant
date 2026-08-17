# RFT LINEAGE — ResponsibleForexTrading / Ryan Brown hypothesis family

Source mined from: public channel (486-video catalog), ForexFactory history, MQL5
products + changelogs, current RFT site, public Myfxbook fleet. Registered 2026-08-17.

## Parent genealogy
SOURCE_FAMILY = RESPONSIBLE_FOREX_TRADING_RYAN_BROWN
All seeds below are descendants of this ONE parent. Multiplicity is tracked via
geneology_id = RFT_xxx everywhere (registry, queue, reports). Never inflate trial
counts by treating RFT descendants as independent.

## Registry: RFT_001 - RFT_081 (81 canonical seeds)
- RFT_001-004  RMI + inside candle: reversal / breakout / crossback / vol-conditioned
- RFT_005-007  RMI HTF trend pullback; RMI-Pro scalp; MAMA/FAMA + RMI
- RFT_008-013  Ranger: range MR / trend pullback / countertrend / S/R MR / pivot MR /
               fresh-signal add (NO uncapped grid)
- RFT_014-015  Pinpoint trend pullback; Failed-Pinpoint reversal
- RFT_016-019  BlastBands: Bollinger/TMA fade; band+RMI reversion; failed-fade continuation
- RFT_020-023  Vigorous M1 scalp: RMI+HTF trend; MAMA/FAMA; fresh-RMI add; hard-SL variant
- RFT_024-025  Sharpshooter M15 trend pullback; failed pullback
- RFT_026-029  CBK consecutive-candle: momentum / exhaustion / trend / countertrend
- RFT_030-033  CBK W1+D1 trend + Aroon + candle (Aroon+engulfing/inside/displacement)
- RFT_034-035  CBK ADX + candle; MAMA/FAMA + candle
- RFT_036-039  Retrack: continuation / reversal; displacement shallow/deep pullback
- RFT_040-042  Virtual (counterfactual) entry: 2nd / 3rd / failure-sequence entry
- RFT_043-045  Serenity double-trend pullback; +S/R; fresh-signal structural add
- RFT_046-050  S/R touch / rejection / breakout momentum / retest / failed breakout
- RFT_051-055  Candle breakout / buffered / retest / inverted / failed fade
- RFT_056-057  Candle pattern + AI veto; + regime meta-label
- RFT_058-065  Black-box reverse-engineering: Crackerjack, EVA, Slugger, HFT-EU-M1,
               Architect S1-S4 (S4 highest priority)
- RFT_066-068  AI meta-label over Vigorous / Sharpshooter / RMI (AI = veto, never entries)
- RFT_069-072  News veto / news regime; volatility-shock veto; post-shock cooldown
- RFT_073-076  TrendGuard entry / exit / reentry / add (trend influences whole lifecycle)
- RFT_077-081  Stops: active-session time / signal candle / breakout box / ATR / structure

## Evidence from public history (failure intelligence, NOT claims of edge)
- Vigorous official ~ -40.8% / DD ~57.5%; Ranger positive moderate; Sharpshooter +15.1%
  / 29.5%; Serenity ~ -24.2% / 30.9%; ENG AI ~ -11.85%; several Vigorous-AI accounts
  -96% to -99%; manual high-risk ~ -99%. Public GBPCAD incident: 3 accounts devastated.
  Conclusion: risk architecture dominates outcomes; signal-before-recovery is the only
  testable asset. A +95% win-rate with rare -20R events is economically worse than a
  45% winner with convex payoff.

## Tier S (implemented in hunt19)
1. RFT_030 CBK double-HTF + Aroon + candle
2. RFT_036/037 Retrack excursion -> retracement -> response
3. RFT_001 RMI + inside candle
4. RFT_046-050 Architect S/R four-family (touch/reject/breakout/retest)
5. RFT_051/054 Candle breakout + inversion
6. RFT_040-042 Virtual (counterfactual) failure-sequence entry
7. RFT_071-072 Volatility shock/cooldown states (meta-filter, universal)
8. Separate AI decision models: P_ENTRY/P_HOLD/P_ADD/P_PARTIAL/P_EXIT/P_REENTRY

## Tier A (queued)
Vigorous MAMA/FAMA+RMI; Pinpoint pullback; Serenity double trend+S/R; consecutive
candle momentum/exhaustion; Ranger pure-range entry (no grid); BlastBands/TMA fade
(no martingale); ADX+candle; active-session time stop.

## Tier B (reverse-engineering queue — needs trade-history fingerprints first)
Architect S4, HFT-EU-M1, Crackerjack, EVA, Slugger, Architect S1-3.

## What we do NOT copy (RFT_NEGATIVE)
Uncapped grid, martingale, keep-adding-until-BE, high leverage as return source,
win-rate optimization, recovery as substitute for entry edge, no-stop tails,
vendor backtest projections. Rule: if ENTRY_ALPHA + SAFE_EXIT dies when the
recovery layer is removed, it was never alpha.

## System additions made permanent (statuses)
- SIGNAL_INVERSION_ENGINE: every entry gets inverse/failure tested -> EXISTING
  (failed-breakout states in hunt12; Architect inversion in hunt19 families)
- COUNTERFACTUAL_ENTRY_QUEUE: virtual early signals, enter only after N failures
  -> BUILDING (hunt19 rft_fail_seq)
- NEW_VS_ADD_DECISION_MODELS: separate posterior for adds -> QUEUED
- VOLATILITY_SHOCK_COOLDOWN: expectancy conditional on shock state + age -> QUEUED
- TRADE_LIFECYCLE_REGIME_ROUTING: regime influences entry/size/lock/runner/add/reentry/exit
  -> PARTIAL (regime permission filter validated OOS; lifecycle routing queued)
- ACTIVE_MARKET_TIME: signal age in economically active time -> QUEUED
- SIGNAL_SPECIFIC_STOP_ENGINE: candle/box/structure/ATR stops compete -> QUEUED
- BROKER_FRICTION_AWARENESS: EDGE_GROSS -> SPREAD_R/COMMISSION_R/SLIPPAGE_R/SWAP_R
  -> EDGE_NET; COST/EXPECTED_MFE -> PARTIAL (costs inside engine; friction-to-target
  metric queued)
- PORTFOLIO_EXPOSURE_GUARD: factor/mechanism/tail exposure, marginal E[log W]
  -> PARTIAL (182-population orthogonality audit running; factor exposure queued)
- BLACK_BOX_STRATEGY_REVERSE_ENGINEER: public trades -> inferred rules -> QUEUED
- FAILURE_ACCOUNT_MINER: losing accounts as negative training labels -> QUEUED
- CHAMPION/CHALLENGER with frozen OOS + genealogy + forward clocks -> EXISTING
  (shadow_forward + freeze discipline)