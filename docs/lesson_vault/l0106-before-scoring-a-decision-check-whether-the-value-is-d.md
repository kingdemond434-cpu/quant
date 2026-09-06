---
id: L0106
cost: blind
---

# L0106

Before scoring a decision, check whether the value is DERIVED from the thing you are scoring it against. If the constructor guarantees the property, the binary check is a constant-pass gate measuring the constructor rather than the decisions -- score the MARGIN instead, and publish the constant-pass finding rather than the perfect score.

## Evidence

run_conviction_trader.derive_stop_pct widens every stop past the measured noise floor, so 0 of 17 entries sit inside the noise band and a binary stop-quality check would have scored 17/17. libs/research/execution_quality.py scores stop_pct/noise_floor_pct and reports n_inside_noise with an L1.49 warning.

## Related

- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
