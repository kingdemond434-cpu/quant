---
id: L0051
cost: blind
tags: ["calibration"]
enforced_by: tests/stage14/test_survival_calibration.py::test_the_default_drawdown_limit_rejects_the_entire_real_edge_band
---

# L0051

An INERT gate's constants are never calibrated, so wiring one is not a small change. Measure what its defaults reject BEFORE connecting it, or the first campaign returns zero and reads as 'no edge exists' rather than 'the limit was never set'.

## Evidence

monte_carlo_survival dd_limit=0.20 has no production caller and rejects 100% of REAL_EDGE_OOS_SHARPE_BAND (0.5-1.5) at crypto vol: survival 0.000 at every level. tests/stage14/test_survival_calibration.py

## Enforced by

`tests/stage14/test_survival_calibration.py::test_the_default_drawdown_limit_rejects_the_entire_real_edge_band`

## Tags

#calibration

## Related

- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
