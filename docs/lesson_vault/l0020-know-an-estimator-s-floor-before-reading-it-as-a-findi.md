---
id: L0020
cost: blind
tags: ["statistics"]
enforced_by: tests/test_cohort_independence.py::test_the_demeaning_floor_is_where_zero_structure_lands
---

# L0020

Know an estimator's floor before reading it as a finding. At T<N the effective-number-of-tests estimator returns ~178 of 420 on INDEPENDENT columns -- only the ratio to that baseline means anything.

## Evidence

participation ratio (sum lambda)^2 / sum lambda^2 measured on synthetic independent data. scripts/audit_gate_power.py::effective_n_tests

## Enforced by

`tests/test_cohort_independence.py::test_the_demeaning_floor_is_where_zero_structure_lands`

## Tags

#statistics

## Related

- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
- [[l0100-a-collector-that-overwrites-a-revised-source-destroys-]]
- [[l0103-built-tested-registered-law-mapped-does-not-mean-invok]]
