---
id: L0028
cost: wasted
tags: ["statistics", "design"]
enforced_by: tests/validation/test_robustness_filters.py::test_a_real_edge_with_normal_degradation_is_untouched
---

# L0028

Price a filter in BOTH errors before shipping it. A luck filter that removes 35% of lucky nulls while rejecting 20-40% of genuine alphas is a net loss at every sample length.

## Evidence

re-specified studentised: 2.8% cost against 6.2% benefit, ~17 nulls removed per real edge lost. libs/validation/robustness_filters.py::not_too_lucky

## Enforced by

`tests/validation/test_robustness_filters.py::test_a_real_edge_with_normal_degradation_is_untouched`

## Tags

#statistics #design

## Related

- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0013-positive-ic-is-not-a-profitable-strategy-ic-lives-mid-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
