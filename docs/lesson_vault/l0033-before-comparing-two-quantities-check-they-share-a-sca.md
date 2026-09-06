---
id: L0033
cost: blind
tags: ["statistics", "design"]
enforced_by: tests/test_regime_trend.py::test_divergence_is_actually_sparse
---

# L0033

Before comparing two quantities, check they share a scale. A difference between an occupancy fraction and a clipped t-statistic measures the scale mismatch, not the disagreement you named it after.

## Evidence

occupancy_divergence at threshold 0.25 fired on ~87% of bars while being called a divergence signal; median |occ-disp| measured 0.700. libs/research/regime_trend.py

## Enforced by

`tests/test_regime_trend.py::test_divergence_is_actually_sparse`

## Tags

#statistics #design

## Related

- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
