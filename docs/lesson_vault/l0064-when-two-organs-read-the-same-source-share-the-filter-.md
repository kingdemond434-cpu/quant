---
id: L0064
cost: blind
tags: ["governance"]
enforced_by: tests/ops/test_carryover.py::TestDeferralIsNotAvoidance::test_acked_item_is_never_reported_as_skipped
---

# L0064

When two organs read the SAME source, share the FILTER as well as the source. A filter that lives inside one organ's main() is invisible to every other caller, and the second organ then judges the desk from a partial view -- and escalates on it.

## Evidence

scripts/max_audit.py shared CHECKS module-level to stop exactly this drift, but kept the ack filter inside main(); carryover_brief enumerated CHECKS and so reported 26 dated acks as avoidance -- top-12 of the brain's FIRST-priority queue was 12/12 acked (2026-08-01)

## Enforced by

`tests/ops/test_carryover.py::TestDeferralIsNotAvoidance::test_acked_item_is_never_reported_as_skipped`

## Tags

#governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
