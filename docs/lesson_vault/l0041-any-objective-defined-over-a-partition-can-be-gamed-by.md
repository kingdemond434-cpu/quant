---
id: L0041
cost: wasted
tags: ["statistics", "design"]
enforced_by: tests/validation/test_campaign_window.py::test_splitting_is_priced_so_fragmenting_cannot_buy_power_for_free
---

# L0041

Any objective defined over a partition can be gamed by re-partitioning. Price the partition itself -- if splitting the data improves the score, the score is measuring the split.

## Evidence

the strata planner fragmented to 34 minimum-size strata to evade multiplicity and reported a fictional 279x improvement; fixed by pricing CAMPAIGN_ALPHA/k. ADVERSARIAL_REVIEW_RUBRIC class 6

## Enforced by

`tests/validation/test_campaign_window.py::test_splitting_is_priced_so_fragmenting_cannot_buy_power_for_free`

## Tags

#statistics #design

## Related

- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0131-a-parser-that-skips-an-unreadable-entry-makes-a-100pct]]
- [[l0162-a-tmpfs-entry-s-owner-is-the-fact-that-makes-freeing-i]]
