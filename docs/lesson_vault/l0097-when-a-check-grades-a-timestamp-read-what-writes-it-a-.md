---
id: L0097
cost: blind
tags: ["governance"]
---

# L0097

When a check grades a timestamp, read what WRITES it. A producer's one-way PRESENCE latch graded as a recency clock welds the gate: the only way to clear it is a re-stamp the producer deliberately refuses, so it rejects 100% forever on a quantity it never measured.

## Evidence

max_audit.check_clock_saturation graded gen_done_<axis> and fired 9/9 on 2026-08-12, while run_axis_generate.py:196 refuses to re-stamp that key ('the same lie in a quieter file') and forward_slots.json showed crossasset ACCRUING for 52 days and idle_slots 0

## Tags

#governance

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
