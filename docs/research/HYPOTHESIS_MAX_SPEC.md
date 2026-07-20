# HYPOTHESIS-MAX MACHINERY -- BUILD SPEC (principal directive 2026-07-20)
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
the full gauntlet (the pre-filter must never become a silent alpha killer: log pass/fail
counts + spot-audit a sample of rejects in the weekly panel).

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
