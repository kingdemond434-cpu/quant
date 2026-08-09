# DEEP COLD AUDIT — RESEARCH-ENGINE — 2026-07-29

_Auditor: Claude Fable 5 (interactive catch-up run; the scheduled auditor died BRAIN_AUTH_FAILED
three sweeps running — see finding I-0). Read-only sweep; every claim carries its proving command._

## SCORES (filled at end)

- current_capability_pct: TBD
- practical_ceiling_estimate: TBD
- ceiling_gap: TBD
- opportunity_cost_1y: TBD
- confidence: TBD
- unknown_unknown_score: TBD
- info_gain_if_investigated: TBD
- expected_alpha_contribution: TBD
- expected_compounding_contribution: TBD
- CEILING EXPANSION: TBD

## 1. WHAT WE KNOW (validated strengths, each with proving command)

**K-1. The axis-screen harness is statistically serious and actually used.**
`python3 -c "json.load(open('data/idle_axis_screen.json'))"` shows per-construction trial rows
with `n_eff`, `min_detectable_ic`, `powered`, `residual_ic`, de-contamination flags, explicit
`SCREEN-UNDERPOWERED` verdicts, and stage marked "A (zero promotion authority)". The novelty
gate is wired INSIDE this screen (novelty_score, nearest_id, n_priors=46 per candidate). Power
analysis before belief is a real strength most desks lack.

**K-2. Negative results dominate research memory — the duty is real, not aspirational.**
`sqlite3 data/sor_research.sqlite "select result,count(*) from research_memory"` →
failure=122, success=17, pending=5 (144 rows). The desk logs its failures at 7:1 over
successes; the graveyard-as-knowledge doctrine is being executed.

**K-3. Preregistration with honest EV gating exists and rejects its own ideas.**
`head docs/research/AXIS_PREREGISTRATIONS.md` — 11 axis hypotheses authored with mechanism,
falsification condition, EV and p_survive, 11/11 honestly REJECTED below threshold rather than
tuned to pass. The two-stage discipline (screen ≠ promotion) is culturally embedded.

**K-4. Failed-experiment learning has a resurrection path.**
`ls -la data/graveyard_resurrection_queue.json` → 14KB, updated 2026-07-27. Dead ideas are
queued for re-look under new capability rather than lost. (Quality assessed in I-findings.)

## 2. WHAT WE DON'T KNOW (ignorance ledger)

(incremental)

## 3. WHAT COULD MATTER MOST (ranked opportunities)

(final synthesis)

## 4. WHAT WE TEST NEXT (concrete experiments)

(final synthesis)

---

## FINDINGS LOG (raw, command-cited; perspectives tagged INTERNAL/EXTERNAL/FUTURE/CONTRARIAN/GREENFIELD/FRONTIER)

### I-0 [INTERNAL, meta] The research-engine audit organ itself has never completed a run

Evidence:
```
$ wc -c docs/research/deep_sweep/2026072{6,8,9}_research-engine.md
  48 20260726  (stub "# AUDITOR FAILED")
 490 20260728  (BRAIN_AUTH_FAILED stub)
 492 20260729  (BRAIN_AUTH_FAILED stub — before this manual run)
```
All three scheduled research-engine cold sweeps died at brain-auth before writing a single
finding, while other subsystems completed (validation-stats 56KB, alpha-discovery 36-46KB,
data-moat 33KB). The subsystem the doctrine calls "highest-return section" is the one that
has never been audited. The catch-up/resume logic (re-run below 1200 bytes) exists but three
sweeps in a row still ended in the failure stub — the retry loop is not converging on the
highest-value auditor, plausibly because research-engine runs late in the 8-auditor sequence
and inherits a drained pool. Fix: run the highest-ERV auditor FIRST in the sequence, not last.

