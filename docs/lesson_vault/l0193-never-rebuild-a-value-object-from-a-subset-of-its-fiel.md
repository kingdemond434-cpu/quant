---
id: L0193
cost: capital
tags: ["costs"]
enforced_by: desks/mt5/tests/test_cost_stress_derivation.py::test_a_stressed_cost_is_never_cheaper_than_its_baseline
---

# L0193

Never rebuild a value object from a subset of its fields to make a variant. Derive with dataclasses.replace, so a field added later cannot be silently dropped by a call site that predates it -- a default chosen so 'no existing caller moves' becomes a silent REVERT in any re-derivation.

## Evidence

universal_gate:283 rebuilt Costs from 3 of 4 fields, dropping quote_per_account: CADJPY baseline round trip 1699.29, 'x3' stress 607.00 -- the cost-stress gate ran at 0.36x its own baseline. Fixed bc4b03ed

## Enforced by

`desks/mt5/tests/test_cost_stress_derivation.py::test_a_stressed_cost_is_never_cheaper_than_its_baseline`

## Tags

#costs

## Related

- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
- [[l0093-when-two-lineages-fix-the-same-bug-in-different-places]]
- [[l0107-when-two-instruments-judge-the-same-object-by-differen]]
- [[l0120-when-a-quality-fence-scores-text-against-a-marker-voca]]
- [[l0129-never-read-a-clean-git-status-as-evidence-your-output-]]
- [[l0133-when-a-fence-reports-an-organ-dead-that-you-can-see-pr]]
