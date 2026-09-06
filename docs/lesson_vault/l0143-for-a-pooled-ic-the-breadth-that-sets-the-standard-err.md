---
id: L0143
cost: blind
tags: ["statistics"]
enforced_by: tests/research/test_panel_breadth.py::test_a_single_common_factor_collapses_breadth
---

# L0143

For a POOLED IC, the breadth that sets the standard error is the cross-sectional correlation of the PRODUCT terms (signal*target), never of the returns. Measuring the demeaned returns instead returns the full K by construction -- the demeaning constraint forces it there -- which is the over-claim, and measuring the raw returns returns ~1 bet, which is the opposite one.

## Evidence

Same 139-symbol panel, 1897 dates: RAW returns rho +0.5288 -> 1.88 bets; RELATIVE (demeaned) rho -0.0069 vs arithmetic floor -0.00725 -> 139 capped; PRODUCT terms rho +0.0036 -> 92.76. Only the product row is both measured and relevant.

## Enforced by

`tests/research/test_panel_breadth.py::test_a_single_common_factor_collapses_breadth`

## Tags

#statistics

## Related

- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
