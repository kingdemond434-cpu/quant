---
id: L0055
cost: blind
tags: ["governance"]
enforced_by: tests/ops/test_carryover.py::TestDeferralIsNotAvoidance::test_brief_does_not_order_the_brain_to_redo_disposed_work
---

# L0055

A false-positive gate is SELF-AMPLIFYING when its metric counts sightings. Each correct walk-past increments the 'you ignored this' counter, so the noisiest items climb the ranking. Before trusting any 'survived N sweeps' number, check what fraction of the list is already disposed.

## Evidence

§37 brief escalated to '41 items survived 13 awake sweeps' while max_audit simultaneously reported those same items acked; measured false-positive rate 57%, top-12 100% (2026-08-01)

## Enforced by

`tests/ops/test_carryover.py::TestDeferralIsNotAvoidance::test_brief_does_not_order_the_brain_to_redo_disposed_work`

## Tags

#governance

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
