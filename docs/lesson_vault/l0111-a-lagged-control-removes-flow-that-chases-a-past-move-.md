---
id: L0111
cost: blind
tags: ["estimators"]
---

# L0111

A LAGGED control removes flow that CHASES a past move; it cannot touch simultaneity INSIDE the observation window. If cause and effect both sit in one 6s interval, no lagged regressor separates them and the fit still reports a large significant slope. When a confound test you expected to pass fails, suspect the ESTIMATOR's ceiling before the test -- then pin the ceiling with the test rather than deleting it.

## Evidence

tests/research/test_print_impact.py::test_contemporaneous_simultaneity_is_NOT_removed_and_that_is_documented; momentum_share 0.0009 on a synthetic where flow causes none of the return

## Tags

#estimators

## Related

- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
