---
id: L0377
cost: blind
tags: ["plumbing", "adoption"]
enforced_by: desks/mt5/tests/test_adoption_never_collides.py::test_a_lost_lock_race_gets_a_repair_pass_before_the_adoption_refuses
---

# L0377

An hourly deployment must not spend its lock window on paths another organ already delivers, and must retry a path that lost an index.lock race before it refuses the whole tree: skip what has its own route, repair the residual, then publish every path that still differs.

## Evidence

Adopt-Release diffed 23,270 paths against the branch tip and 22,910 were the discovery corpus MT5-IntelShip ships hourly; one pass ran 5h (56s CPU) holding Global\MT5-GitWriter-v2, the next hour's pass declined after 9 min, and 13 paths lost the index.lock race -- 2 of them code (ops/gates.sh, scripts/recommendations.py) that staged by hand a minute later. Four days of 'Adopt-Release exited 1 -- partial adoption' naming nothing. After the skip+repair+ADOPTION_STATE.json: 23,270 -> 360 paths, ~6 min per pass.

## Enforced by

`desks/mt5/tests/test_adoption_never_collides.py::test_a_lost_lock_race_gets_a_repair_pass_before_the_adoption_refuses`

## Tags

#plumbing #adoption

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
