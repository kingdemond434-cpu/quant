---
id: L0039
cost: blind
tags: ["verification", "design"]
enforced_by: tests/autodiscovery/test_gate_wiring.py::test_the_luck_filter_is_a_real_gate_not_a_dead_import
---

# L0039

A module with passing tests and no PRODUCTION importer is drafted, not built. Tests prove it works; only the import graph proves it runs. Count callers before counting coverage.

## Evidence

5 transcript modules, 1424 LOC, 56 passing tests, and the production import graph reaches NONE of them -- every importer was a test or an unscheduled script. Audited 2026-08-01

## Enforced by

`tests/autodiscovery/test_gate_wiring.py::test_the_luck_filter_is_a_real_gate_not_a_dead_import`

## Tags

#verification #design

## Related

- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
