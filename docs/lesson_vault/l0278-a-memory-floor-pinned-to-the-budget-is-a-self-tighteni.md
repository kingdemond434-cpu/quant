---
id: L0278
cost: slow
tags: ["throughput"]
enforced_by: desks/mt5/tests/test_gauntlet_budgets_fit_the_box.py::test_on_a_box_with_room_the_budget_grows_into_it_up_to_the_cap
---

# L0278

A memory floor pinned to the BUDGET is a self-tightening throttle: budget = max(declared, p75 of observed peaks) can never rise past a cap that defers at the declaration. Unpin the budget from the floor and size it from the room the box measures at start -- never from a hardware figure someone reports. The box's own counters are the measurement; a claim is not.

## Evidence

2026-09-08: 1200MB declared, 42 cells judged an hour against a docket of 23,465 -- 558 passes, 23 days. Raised to 8192 on the principal's '80GB' the same morning; every counter the box publishes says 8GB (phys 142MB free / virt 11719MB; free RAM cycling 3329->448MB; one 4882MB process leaving 280MB free), so 8192 would have stood the sweep down every hour (rc=75). Reverted to the measured 1200 the same day with the budget taking HEADROOM_SHARE of measured free memory instead.

## Enforced by

`desks/mt5/tests/test_gauntlet_budgets_fit_the_box.py::test_on_a_box_with_room_the_budget_grows_into_it_up_to_the_cap`

## Tags

#throughput

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0027-a-constant-that-was-never-measured-is-a-guess-wearing-]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
