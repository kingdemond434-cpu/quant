---
id: L0164
cost: blind
tags: ["validation"]
enforced_by: tests/validation/test_partition_power.py::test_partition_where_every_group_is_positive_is_welded
---

# L0164

Before trusting a test's verdict, check its decisive criterion CAN fire on the data it was handed. A pass/fail rule that no observed value could have tripped carries zero information, and the verdict then silently falls through to whatever weaker branch remains -- answering a different question under the original question's name.

## Evidence

falsify_funding_state_axis.py first run printed REFUTED from finds_dead_state on a carry proxy non-positive on only 3.0% of days, so neither axis could ever have failed; hardened to UNDERPOWERED. Same class one level up: 4/4 desk robustness partitions WELDED (data/partition_power.json).

## Enforced by

`tests/validation/test_partition_power.py::test_partition_where_every_group_is_positive_is_welded`

## Tags

#validation

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
