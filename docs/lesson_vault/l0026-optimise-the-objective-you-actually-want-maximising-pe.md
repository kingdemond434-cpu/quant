---
id: L0026
cost: wasted
tags: ["statistics", "campaign"]
enforced_by: tests/validation/test_campaign_window.py::test_stratifying_beats_truncating_on_a_realistic_campaign
---

# L0026

Optimise the objective you actually want. Maximising per-candidate power chose 4000 observations for 16 candidates and left 404 of 420 hypotheses untested; expected DISCOVERIES is the objective.

## Evidence

campaign stratification rewrite; E[discoveries] went 1.06 -> 191.65 at 92.0% of observations used, 24 strata. libs/validation/campaign_window.py

## Enforced by

`tests/validation/test_campaign_window.py::test_stratifying_beats_truncating_on_a_realistic_campaign`

## Tags

#statistics #campaign

## Related

- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
