# HYPOTHESIS-MAX MACHINERY -- BUILD SPEC (principal directive 2026-07-20)

## BUILD STATUS (added 2026-07-29 — this spec was a BUILDER'S FOSSIL for 9 days)

The 2026-07-28 external panel flagged this file by name: *"HYPOTHESIS_MAX_SPEC.md built (07-20)
but **6 components NOT implemented**"*. Verified — five of six had no implementation anywhere in
`scripts/` or `libs/`. The panel also measured the cost: **420 candidates tested, ZERO
survivors**, every one burning full gauntlet compute because component 1 — the one marked "build
first" — did not exist.

| # | Component | Status | Where |
|---|---|---|---|
| 1 | Tiered gauntlet pre-filter | **BUILT 07-29** | `libs/hypmax/hypothesis_max.py::prefilter` |
| 2 | Failed-hypothesis telemetry → generator feedback | **PARTIAL** | weighting rule built (`family_weight`, floored per charter s18); the graveyard field additions (`rejection_stage`, `rejection_reason`, `feature_family`, `data_axes`) still owe a writer |
| 3 | Trivial-variation blocker at source | **BUILT 07-29** | `hypothesis_max.py::TrivialVariationBlocker` + `fingerprint` |
| 4 | Breeder | **NOT BUILT** | blocked on a validated axis to cross against — the desk has 1 |
| 5 | Orthogonality seeker | **NOT BUILT** | needs an existing book to score correlation against; 0 deployed alphas |
| 6 | Generator collapse detector | **BUILT 07-29** | `hypothesis_max.py::batch_diversity` |

Components 1, 3 and 6 shipped together because the spec itself makes them one object: #3's
mechanism fingerprint is explicitly reused by #6, and #1 consumes both. 24 tests.

**Why #6 became urgent rather than optional:** generation moved from one lens per day to a full
lens × seat sweep this session (3 → 15 jobs/run). Independent seats sweeping the same lens set is
precisely the condition that produces near-identical candidates, and mode collapse is invisible
in throughput — measured volume rises while information falls.

**The pre-filter's default is ESCALATE, not REJECT, and that inversion is deliberate.** Everywhere
else on this desk an ambiguous branch must block. Here the failure being guarded against is a
silently killed alpha, not a bad trade — the full gauntlet is unchanged behind it. Wasted compute
is recoverable; a discarded edge is not. Missing evidence can therefore never contribute to a
rejection.

Items 4 and 5 are recorded with their blockers rather than left silent, which is the failure this
status block exists to correct.

---

_Implements the Hypothesis Generation Maximization standing directive (constitution addendum
2026-07-20). Research-lane tooling: no risk-path, sizing, or executor code. Brain builds in
EV order; each component independently shippable, CI-gated, reversible._

## 1. Tiered gauntlet pre-filter (build first -- pure efficiency win)
A lightweight analytical stage BEFORE recorder-replay/gauntlet compute:
- in-sample significance screen (cheap t-stat / IC on existing daily-bar history),
- basic logic checks (sign stability, non-degenerate turnover, cost-floor sanity: gross edge
  must exceed 2x modeled round-trip cost before any heavy test),
- graveyard + do_not_repeat + trivial-variation match (see #3).
PASS -> full gauntlet (unchanged bar: Holm/DSR/PBO with true cumulative N, walk-forward,
regime gate, shadow). FAIL -> graveyarded with reason, zero heavy compute spent.
The pre-filter REJECTS ONLY on cheap, unambiguous evidence -- borderline always escalates to
the full gauntlet (the pre-filter must never become a silent alpha killer: log pass/fail counts + spot-audit a sample of rejects EVERY 3 DAYS once >=50 rejects accumulate in the window, weekly otherwise (principal 2026-07-20: this audit's cadence is gated by throughput volume, not data drift)).

## 2. Failed-hypothesis telemetry -> generator feedback
Every rejection already lands in the graveyard; ADD structured fields: rejection_stage
(pre-filter | gauntlet | shadow), rejection_reason (statistical | economic | cost | data),
feature_family, data_axes used. Generator reads the aggregate before each run: dead-end
families get demoted weight (never zero -- negative knowledge is reversible per charter s18).

## 3. Trivial-variation blocker at source
When a hypothesis is rejected for a SPECIFIC statistical reason, parameter-level variations
of the same mechanism/feature-set are blocked at generation time (mechanism fingerprint =
feature family + signal transform + horizon bucket; a variation only re-enters if it changes
the MECHANISM, not the parameters). Fingerprints stored beside do_not_repeat.

## 4. Breeder
Surviving mechanics (anything that clears the pre-filter with strong margin, plus the
existing deployed edge) are systematically crossed with each NEWLY validated dataset/axis
(charter s22 already queues new datasets for hypothesis generation -- this closes the loop
from the other side). Output feeds the same pre-filter; no special credibility.

## 5. Orthogonality seeker
Generator scores candidate batches on pairwise feature/return correlation vs the existing
book and the current candidate set; prefers low-correlation combinations (cross-sectional
factor families first, per the 2026-07-19 standing targeting order).

## KPIs (factory dashboard): hypotheses generated/pre-filtered/gauntleted/surviving per week,
compute per survivor, pre-filter false-reject audit rate. Success = gauntlet throughput up
with FDR detector flat.

## 6. Generator collapse detector (principal micro-addition 2026-07-20 -- Lane-A instrumentation)
Uncapped generation has a known failure mode: mode collapse -- multiple generators/seats
converging on near-identical hypotheses, so measured throughput rises while INFORMATION
throughput falls. Track diversity explicitly per generation batch and across generators:
- MECHANISM diversity: entropy over mechanism fingerprints (reuses #3's fingerprint =
  feature family + signal transform + horizon bucket) -- collapse shows as entropy dropping
  while volume holds.
- FEATURE diversity: distribution across feature families / data axes used.
- MARKET diversity: symbol/venue coverage breadth of the batch (cross-sectional families
  count the universe they rank, not 1 name).
- SEMANTIC diversity: cheap deterministic proxy -- pairwise Jaccard on normalized mechanism-
  description token sets (no embeddings, no extra model calls); plus CROSS-GENERATOR overlap
  rate (share of near-duplicate pairs between different seats/diggers in the same window).
WIRING (single Lane-A task, no new governance): metrics computed per batch and appended to
the seat scoreboard (scripts/build_scoreboard.py -> data/panel_scorecard.json fields
`gen_diversity`); shown in factory KPIs. TRIGGER: any metric dropping >40% below its
trailing-8-batch median, or cross-generator near-duplicate rate >25%, flags a DIVERSITY
AUDIT in the next weekly panel (audit asks: which seats collapsed, onto what, and why --
telemetry-induced herding, shared-prompt drift, or a genuinely dominant regime). Thresholds
are starting values, tuned on evidence; the detector never blocks generation -- it is
instrumentation that pages the process, not a gate on ideas.
