# QUANT AGENT PROTOCOL — version-pinned managed rules

Every LLM/agent session touching this desk MUST read this file and the version pins.
Generated block — do not edit manually; regenerate when the quant changes.

QUANT_AGENT_PROTOCOL_VERSION = 2
RESEARCH_SCHEMA_VERSION     = 1   (research_queue.json / research_registry.jsonl schema)
VALIDATION_SCHEMA_VERSION   = 2   (UNIVERSAL 10-GATE ONLY; battery retired as survivor gate)
CAPITAL_RULE_VERSION        = 1   (forward E[log W], ruin-avoidance mandate)

## Non-negotiable rules
1. SUPREME ACCEPTANCE: incremental forward net E[log W] with survivable DD; ruin never.
2. Evidence chain: hypothesis -> deterministic engine -> battery (diagnostic ONLY) ->
   universal 10-gate gauntlet -> registry -> shadow forward. No claim of edge without
   the universal gauntlet.
3. LLM = researcher; deterministic system = truth. Never let an LLM certify its own
   strategy. THE ONLY SURVIVOR GATE = original quant-platform 10-gate gauntlet
   (libs/validation; research/universal_gate.py). The old battery (run_hunt12.py:94-97)
   is retired from survivor claims — descriptive statistics only, never a certificate.
4. Universal gauntlet order (qquant original, unchanged): economic_prior ->
   in_sample -> DSR>=0.95 (trials = cells x 7) -> PBO<=0.5 (CSCV) -> SPA p<0.05 ->
   CPCV mean OOS SR>0 -> walk_forward 4 splits (min_oos_sharpe 0, stability 0.5) ->
   stress_costs X3 exp>0 -> lockbox OOS SR>=0 -> expected_value mean>0. All original
   thresholds from C:\Users\dell\quant-platform\libs\validation — never re-tuned.
5. ENTRY_CODE_HASH changes -> prior statistical certificate INVALID -> rerun gates.
   Registry code_hash discipline is mandatory (research/registry.py).
6. Optimization only after raw edge at reasonable defaults. Never optimize a loser
   into a winner. Prefer parameter plateaus over peaks.
7. Anything claimed as a corpus/seed must be registered with source trust levels and
   a genealogy id (RFT_xxx, SALEH_xxx, NEWS_xxx, ...). Multiplicity must never be
   manufactured.
8. Sync to VPS hourly (last_sync.json gate); backtest/live observability identical.
9. All compute must be checkpointed + supervised (research_supervisor.py); DONE markers
   are the only completion signal.
10. Capita/risk: forward clock, frozen OOS, CHAMPION/CHALLENGER with genealogy; new
    challengers replace champions only on forward evidence, not backtest.
11. ARCHITECTURE MORATORIUM (2026-08-17, quant directive): no new desks/hunts/
    mechanisms. Highest ROI = conversion ladder on existing inventory:
    CODED -> WIRED -> RUNNING -> PRODUCING DATA -> TESTED -> AFFECTING DECISIONS ->
    MEASURED BY INCREMENTAL E[log W]. New ideas enter the queue, not the codebase.

## Protocol registry
RFT corpus: docs/RFT_LINEAGE.md (RFT_001-081; Tier S = CBK Aroon+candle, Retrack,
RMI+inside, S/R four-family, candle breakout+inverse, virtual-sequence, vola shock,
separate decision models).
SALEH corpus: docs/SALEH_LINEAGE.md (SALEH_001-145; Tier S = squeeze, pairs RV,
EMA bank/runner, cross-anchor, Turtle crisis sleeve, Alligator ablation, KAMA ER,
SIGNAL_INFORMATION_GATE).
NEWS corpus: docs/NEWS_LINEAGE.md (NEWS_001-036 + 9 cross-market classes + latency
taxonomy; hard boundary: no MNPI/leaks/embargoed).
DAVIDD corpus: prior hunts (hunt12 hunt16 families). NEGATIVE lists in each lineage
doc are binding.

## Current front
182 REAL survivors (105 hunt12 + 77 hunt16) -> fragility (REAL2) -> qquant 10-gate
(REAL3) -> merge_qquant -> universal_gate (hunt17/19/20/21/22 + hunt18_*) ->
meta_desk (15 architecture items). hunt19 DONE (16 battery-pass cells -> universal
gate), hunt21 DONE (15 cells), hunt22 RUNNING, news_desk watcher idle, universal +
meta_desk waiting on chain. Fusion live tomorrow; Vantage is CLOSEONLY, abandoned.