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
libs/validation, verbatim thresholds) → signal gate → allocation
(E[log W], NaN-aware) → deployment. Nothing else promotes anything.

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