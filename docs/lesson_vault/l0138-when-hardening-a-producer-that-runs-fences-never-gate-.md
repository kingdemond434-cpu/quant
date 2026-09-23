---
id: L0138
cost: blind
tags: ["fences"]
enforced_by: tests/scripts/test_max_push_input_provenance.py::test_a_fence_that_FIRED_is_a_healthy_refresh_not_a_failure
---

# L0138

When hardening a producer that runs FENCES, never gate on the exit code -- ask whether the ARTIFACT was rewritten. A fence exits non-zero when it CATCHES something, so check=True fails precisely on the days the desk has most to work on.

## Evidence

R0395 c1611fa3: run_max_push refreshes 6 producers, 5 of them fences; _refresh now compares artifact mtime before/after and records rc as context only. tests/scripts/test_max_push_input_provenance.py::test_a_fence_that_FIRED_is_a_healthy_refresh_not_a_failure

## Enforced by

`tests/scripts/test_max_push_input_provenance.py::test_a_fence_that_FIRED_is_a_healthy_refresh_not_a_failure`

## Tags

#fences

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
