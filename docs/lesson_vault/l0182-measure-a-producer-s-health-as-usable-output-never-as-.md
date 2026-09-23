---
id: L0182
cost: blind
tags: ["measurement"]
enforced_by: tests/scripts/test_miner_health.py::TestClassifyRow::test_selector_stub_is_not_real
---

# L0182

Measure a producer's health as USABLE output, never as rows. An error row, a selector stub and an empty archive are all 'rows', and every one of them scores as healthy under errors/rows -- a ratio blind in the only direction nothing downstream catches. Count what carries information, and report a zero-output source rather than dropping it from the table.

## Evidence

2026-08-26: data/research_facts.json reported 41 miners with 6 in error (implying 35 healthy); measured on usable output 21 of 54 produced anything. 'if rows:' had dropped 13 zero-row sources from the file entirely, so the most broken were the most invisible. fbs_tape: 21 rows, 21 stubs, error_rate 0.0. Arrivals 24/week vs 160 baseline.

## Enforced by

`tests/scripts/test_miner_health.py::TestClassifyRow::test_selector_stub_is_not_real`

## Tags

#measurement

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
