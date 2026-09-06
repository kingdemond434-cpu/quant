---
id: L0153
cost: blind
tags: ["governance"]
enforced_by: tests/ops/test_seat_blank_recency.py::TestTheFenceClearsFromSuccessNotOnlyFromANewBlank::test_a_seat_that_only_succeeds_clears_the_fence
---

# L0153

Ask of every health fence: WHAT OBSERVATION CLEARS THIS? If only a new FAILURE can, the fence is inverted -- it is lit precisely while the thing is healthy, and it goes quiet only when the thing breaks. Record attempts, not just failures.

## Evidence

seat-chronic-*-unmeasured, 2026-08-13: recency was measured from seat_blank_events, so a seat that never blanked again produced no events, read UNMEASURED forever, and kept prescribing a SWAP off an under-driven roster (403/406). record_attempt() fires whether the seat answers or dies, so health clears it. Same inverted-gate class as R0492, one level up inside the instrument built to fix it.

## Enforced by

`tests/ops/test_seat_blank_recency.py::TestTheFenceClearsFromSuccessNotOnlyFromANewBlank::test_a_seat_that_only_succeeds_clears_the_fence`

## Tags

#governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
