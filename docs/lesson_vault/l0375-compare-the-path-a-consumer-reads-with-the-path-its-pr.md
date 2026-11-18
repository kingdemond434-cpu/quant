---
id: L0375
cost: blind
tags: ["plumbing", "wiring"]
enforced_by: desks/mt5/tests/test_plumbing_watchdog.py::test_a_path_read_by_two_modules_and_written_by_none_is_the_research_bandit_shape
---

# L0375

Compare the path a consumer READS with the path its producer WRITES, mechanically, every pass. A bandit wrote data/research_budget.json while six readers read reports/RESEARCH_BANDIT.json, which nothing wrote -- both halves green, the wire absent, for weeks. A path read by two or more modules and written by none is a wire that was never connected.

## Evidence

libs/research/bandit.py:85-86 vs desks/mt5/research/research_budget.py:31; reports/PLUMBING_WATCHDOG.json orphan_artifact_path rows

## Enforced by

`desks/mt5/tests/test_plumbing_watchdog.py::test_a_path_read_by_two_modules_and_written_by_none_is_the_research_bandit_shape`

## Tags

#plumbing #wiring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
