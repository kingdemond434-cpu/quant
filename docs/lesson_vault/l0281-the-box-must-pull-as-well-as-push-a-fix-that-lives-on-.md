---
id: L0281
cost: capital
tags: ["release"]
enforced_by: desks/mt5/tests/test_certificates_cannot_be_lost_to_an_outage.py::test_adopt_and_seal_runs_in_the_only_safe_order
---

# L0281

The box must PULL as well as push. A fix that lives on origin is not a fix. Adopt hourly, seal only on a clean tree and only when HEAD is not already sealed, commit RELEASE.json alone, restart the gateway so the seal is read.

## Evidence

2026-09-08: the gateway could not import libs and refused every new order all day while the fix for both sat on origin; two live gold sleeves and three promotion candidates placed nothing.

## Enforced by

`desks/mt5/tests/test_certificates_cannot_be_lost_to_an_outage.py::test_adopt_and_seal_runs_in_the_only_safe_order`

## Tags

#release

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
