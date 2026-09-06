---
id: L0192
cost: capital
tags: ["forward-clock"]
enforced_by: desks/mt5/tests/test_registry_rebase.py::test_a_corrupt_registry_never_re_bases_a_live_clock
---

# L0192

A read helper that returns {} for BOTH 'file absent' and 'file unreadable' hands every writer above it a licence to rebuild the file from scratch. Split the two: absent may be empty, unreadable must RAISE, and writers must refuse to write on an unknown base.

## Evidence

desks/mt5/data/sleeve_registry.json history: all rows re-frozen 08-26T01:42, 08-27T01:13, 08-27T03:31 -- the whole forward book re-based to day 0 three times in 32h against a days>=14 promotion bar, while live_readiness blamed the market. sleeve_registry._read, fixed e3150633

## Enforced by

`desks/mt5/tests/test_registry_rebase.py::test_a_corrupt_registry_never_re_bases_a_live_clock`

## Tags

#forward-clock

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
