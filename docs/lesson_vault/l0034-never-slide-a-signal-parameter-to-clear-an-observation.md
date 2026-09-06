---
id: L0034
cost: wasted
tags: ["statistics"]
enforced_by: tests/test_regime_trend.py::test_divergence_only_ever_takes_the_occupancy_side
---

# L0034

Never slide a signal parameter to clear an observation floor. Tuning an input so a gate passes is the same defect as relaxing the gate and is far harder to see afterwards.

## Evidence

occupancy_divergence min_disp 0.25 yields 208 events per 12x1500 bars vs the 250 validate() requires; 0.15 would yield 274. Default held, prerequisite recorded instead

## Enforced by

`tests/test_regime_trend.py::test_divergence_only_ever_takes_the_occupancy_side`

## Tags

#statistics

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0097-when-a-check-grades-a-timestamp-read-what-writes-it-a-]]
- [[l0134-a-reader-that-enumerates-field-names-its-producer-does]]
- [[l0143-for-a-pooled-ic-the-breadth-that-sets-the-standard-err]]
- [[l0153-ask-of-every-health-fence-what-observation-clears-this]]
