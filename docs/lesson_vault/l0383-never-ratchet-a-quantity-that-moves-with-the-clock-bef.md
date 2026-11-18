---
id: L0383
cost: wasted
tags: ["governance"]
enforced_by: tests/scripts/test_check_coverage_drain.py::test_the_raw_oldest_wait_is_published_and_fails_nothing
---

# L0383

Never ratchet a quantity that moves with the clock. Before you fence a number, ask what it does when the organ works perfectly and an hour passes: if it still rises, the gate is unsatisfiable and it will be switched off rather than met. Fence the part of the quantity that only NEGLECT can move -- for a queue that is the excess over the lease, max(0, wait - LEASE), which is zero while the drain keeps up. Publish the raw number beside it so nothing is hidden.

## Evidence

check_coverage_drain.py ratcheted oldest_wait_h and went FAIL on its third live pass at 6.0h -> 6.3h, for a queue entirely inside its own 24h lease; the fix was overdue_wait_h. Same pass: a typed max_sources of 60 against a 1594-row backlog would have fallen behind 154/day forever, so pass_size() is now derived as backlog/LEASE_H.

## Enforced by

`tests/scripts/test_check_coverage_drain.py::test_the_raw_oldest_wait_is_published_and_fails_nothing`

## Tags

#governance

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
