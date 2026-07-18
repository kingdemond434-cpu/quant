# EVIDENCE-GATED PROGRESSIONS -- single registry of every automatic advance

_Every progression the desk makes is gated on EVIDENCE, never a calendar or a hope. This is the auditable list: trigger, mechanism (CODED = fires in code automatically; BRAIN = brain executes it when its cadence duty flags, on evidence; PRINCIPAL = deliberately human-gated for safety), and where it lives. Reviewed at monthly governance; any progression found to be memory-dependent (no code/cadence trigger) is a defect._

| Progression | Trigger (evidence) | Mechanism | Where |
|---|---|---|---|
| Freeze lifts (S0->post-freeze) | Gate 0 done + >=4wk fills + cost model + >=10 calib rows + no criticals | CODED | run_cadence `_freeze_exit_met` -> POST_GATE0_MANIFEST |
| Validation fast-track (day 40 vs 90) | NW-t >= bar AND fwd >= 0.5x backtest AND a regime event in-window | CODED | run_cashcarry_shadow |
| Graveyard re-mine | a data family matures past its clock | CODED | run_cadence (clock-maturity trigger) |
| Digging biweekly -> monthly | every family >=2 sessions AND 2 consecutive zero-card sessions | BRAIN sets digging_saturated | run_cadence |
| **Growth / aggressiveness ramp (lambda up)** | trailing 8wk: cost <=1.25x modeled AND live Sharpe >=0.6x backtest AND slippage KS p>0.05 AND drill pass-streak >=8wk AND calib MAE falling 2 months | **CODED post-build** (numeric ramp gate) | LIVE_CONNECTOR_SPEC #6 -> built + activated via manifest at freeze-exit |
| **S1 -> S2 (full automation)** | >=8wk live AND >=10 calib rows AND 0 critical drills AND cost <=1.25x | **CODED post-build** (stage machine) | staging.py -> manifest |
| Down-steps (de-risk) | any tripwire / cost or Sharpe breach | CODED, unlimited + immediate | staging + risk controls |
| Leverage clamp LIFTS | confidence pipeline root-caused AND >=30 uncontaminated live days AND principal sign-off | PRINCIPAL (+brain evidence) | gap #14 + executor clamp |
| Live API keys | 7-day VPS gate + carry validation + connector verified + Gate-0 pre-mortem clean | PRINCIPAL (via PRINCIPAL_ACTION page) | connector spec + pager |
| EV-prior update | decision-outcome hit-rate accrues | BRAIN (monthly duty) | decision_outcomes.jsonl |
| Loop / organ sunset | 2 quarters zero documented positive change | BRAIN (monthly loop-audit) | tier1 rider |
| Source-yield re-weight | families that produced survivors vs noise | BRAIN (quarterly coverage audit) | digging doctrine |
| Component audit monthly -> biweekly | Gate 0 cleared (brain time frees) | BRAIN via manifest | gap #28 + manifest |
| Prompt self-rewrite | worst-scoring prompt by verified-hit rate | BRAIN (monthly) | prompt-review duty |
| Sequential validation (sub-40 graduation) | post-freeze + independent replication beats incumbent | BRAIN post-freeze | gap #25 |

RULE: PRINCIPAL-gated rows are deliberately human (fund movement, key/identity, lifting a survival clamp) -- never automated. Everything else fires on evidence via CODE or a cadence-flagged BRAIN duty -- never on memory. If any row's mechanism degrades to 'someone remembers,' that is a defect to fix.
