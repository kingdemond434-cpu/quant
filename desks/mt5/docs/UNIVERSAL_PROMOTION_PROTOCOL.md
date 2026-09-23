# UNIVERSAL PROMOTION PROTOCOL

Binding on every brain (opencode, Claude, any future agent) working on this desk.
No session starts without reading this file. Linked from AGENTS.md and CLAUDE.md.

## The nine defects this desk has actually shipped

1. Same-day label: an absent prior-day label became a same-day label
   (day_states classified day d with day d's own range).
2. Raw t-stat: an absent multiplicity correction became a raw t-stat
   (deflation applied only in some batteries).
3. Trade-every-day: an absent state field became "trade every day".
4. Fake zero return: an absent trade became a zero return in portfolio
   projections (build_daily fillna(0)).
5. Phantom runner: an absent runner became "it must be running".
6. (five more were logged at the time; the pattern is the same — absence read
   as permission — and the cure below is the same for all of them)
7-9. (logged: the discipline that prevents all nine is fail closed.)

## The single path to capital

Survivor claim → universal 10-gate pass (original quant-platform
libs/validation, verbatim thresholds) → signal-information gate → allocation
(E[log W], NaN-aware) → deployment. Nothing else promotes anything.

- signal gate (research/signal_gate.py): per-experiment block-bootstrap
  (999 reps, block 5) on forward returns at horizons 1/2/5/10 H4 bars.
  A survivor only enters allocation with verdict INFORMED (p < 0.05 at any
  horizon, n >= 60) on its exact cell; NULL / SPARSE / absent report =
  EXCLUDED (fail-closed). Allocation waits for the report, never assumes.
- gate runs are auto-discovered by the supervisor (new hunt18_* reports are
  gated automatically; resume from partial reports; per-experiment DONE
  markers reports/DONE_signal_gate_<stem>).
- universal gate retries pool deaths (3 attempts) and sizes workers to
  available memory (1 worker below 512MB free on POSIX).

## Fail closed — the operating rule

When information is absent, the system must treat the outcome as a FAILURE of
that stage, never as a permission:

- absent prior-day label → state = NONE → signals excluded (not all days)
- absent multiplicity correction → apply the hunt-wide deflation or refuse
- absent state field → no signal for that day
- absent trade → NaN day (never 0); flat only at portfolio level, explicitly
- absent runner → supervisor respawns; no assumptions
- absent evidence floor (n >= 60) → cell not tested, not "kept"
- absent gate result → no claim

Any new code path must state its failure mode for missing data before it is
wired. Absence is never permission.