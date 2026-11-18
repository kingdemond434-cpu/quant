---
id: L0386
cost: blind
tags: ["governance", "forward", "clocks"]
enforced_by: desks/mt5/tests/test_clock_certificate.py::test_the_fence_fails_when_the_breach_ratchet_rises
---

# L0386

When a standing law makes most of the book non-compliant, enforce it on the AGE of each breach and on a ratchet, never on the breach COUNT -- a count-based fence pressures the next session into deleting the evidence instead of testing it.

## Evidence

Measured on the trading box vmi3571445 2026-09-23. The principal ruled CLOCK IMPLIES CERTIFICATE against a canon of 28 certificates and 489 forward clocks: BACKED 55, BREACHED 95, RETIRED 339. The obvious implementation -- retire the uncertified -- would have destroyed 95 running forward series and rebuilt the slot scarcity abolished two days earlier. Instead each breached cell is queued at priority 1000 (the front of the judge queue, 71 distinct cells submitted) and the clock keeps accruing as AWAITING_JUDGEMENT; only a reject at a gate no parameter can change takes a clock. The fence in scripts/check_clock_liveness.py fails on breach age past one judging cycle and on the ratchet rising, and is deliberately GREEN at 95 breaches, because the only honest way to lower that number is to judge the cells.

## Enforced by

`desks/mt5/tests/test_clock_certificate.py::test_the_fence_fails_when_the_breach_ratchet_rises`

## Tags

#governance #forward #clocks

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
