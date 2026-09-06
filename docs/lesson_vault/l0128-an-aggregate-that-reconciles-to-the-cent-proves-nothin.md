---
id: L0128
cost: blind
tags: ["measurement"]
enforced_by: tests/test_fee_attribution.py::test_spot_leg_and_row_level_are_refused_not_faked
---

# L0128

An aggregate that reconciles to the cent proves NOTHING about whether the row-level join is valid. Before attributing a total to individual rows, measure the gap distribution of the join key -- and if it does not support the join, publish the level that does and REFUSE the level that does not.

## Evidence

R0371 2026-08-12: 11,194 venue COMMISSION events summed to 1750.8780 against the dashboard's 1750.88 -- exact. The same events time-joined to the trade tape were random: the income ledger emits one row per PARTIAL fill (48 events share one timestamp, median inter-event gap 1s), so the median gap from an event to the nearest same-symbol tape fill instant was 15,407s (4.3h), p95 22.8h. Per-symbol attribution was truth; per-round-trip would have been fiction wearing the same reconciled total.

## Enforced by

`tests/test_fee_attribution.py::test_spot_leg_and_row_level_are_refused_not_faked`

## Tags

#measurement

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
