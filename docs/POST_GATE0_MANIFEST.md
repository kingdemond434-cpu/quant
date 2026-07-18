# POST-GATE-0 ACTIVATION MANIFEST

_The deterministic list of EVERYTHING deferred under the execution lockdown. When the freeze-exit criteria are all met (checked automatically each cycle by run_cadence), the cadence engine flags activation and the brain works this manifest top to bottom, marking each `done` in data/cadence_state.json. Nothing here depends on memory -- it is a checklist the code surfaces._

## FREEZE-EXIT CRITERIA (all must hold; auto-checked)
1. Gate 0 completed (data/gate0_complete flag written).
2. >=4 weeks of live fills exist (data/fills.csv age + rows).
3. Execution-cost model populated from live fills.
4. >=10 resolved calibration rows (data/calibration.csv).
5. No open critical incidents (no DEADMAN_FIRED / unresolved criticals).

## ON ACTIVATION -- the brain processes, in order:
1. **Improvement inbox** (docs/research/improvement_inbox.md) in EV-rank order -- the expansion-package items (liquidation-cascade forecaster, funding term structure, FRED lead-lag, feature factory, knowledge graph, edge-decay lab, negative-space, etc.).
2. **Every gap-register row marked queued / queued-post-freeze / ev-gated**, in rank order: #25 sequential validation (needs independent replication), #27 full-surface conservatism automation, #22 negative-space, #23 clustering, #24 edge-decay lab, others as ranked.
3. **Stage-aware accelerations**: full-depth component audit monthly->biweekly; digging budget may rise; any duty tagged 'raisable post-Gate-0'.
4. **The monthly self-improvement engine** runs on the full queue under the independence gate + complexity budget + shadow-proof, at max safe throughput (no numeric cap).
5. **Growth/aggressiveness ramp + stage machine BUILT and ARMED**: the numeric ramp gate (LIVE_CONNECTOR_SPEC #6 -- lambda rises only on the 8-week evidence bundle) and the S1->S2 auto-transition (staging.py) go live; down-steps stay unlimited+immediate. This is the earned-aggression engine -- it makes the desk more aggressive strictly as evidence permits, automatically.
6. **Live-phase organs arm**: Crisis Autopsy (S1 trigger), venue-side protective stops + no-naked-position invariant, pager de-risk ladder, canary, tax-aware sizing, net-exposure consolidator, Effective-N gate.

RULE: activation is ALL-or-by-rank, never silent-skip. Each item marked done with a ledger entry. If any item is retired instead of built, that too is ledgered with a reason. The manifest is append-only until its items are resolved; new deferrals add rows here.
