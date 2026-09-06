---
id: L0057
cost: blind
tags: ["ci", "testing"]
enforced_by: tests/test_suite_collectable.py::test_module_cannot_kill_the_collector
---

# L0057

A red pytest leg can mean ZERO tests ran. A test module that executes at import and raises SystemExit aborts the whole session with INTERNALERROR, so read the exit code (3 = collector died, not 1 = tests failed) and check a test COUNT before believing any pass/fail number -- and the failures it was hiding only become visible once collection is repaired.

## Evidence

tests/test_gate0_soak.py was a script wearing a test name (raise SystemExit at line 56); pytest exited 3 with no report, and repairing it revealed 5 failures that had been invisible, including 2 the desk had never seen. Its own 7 Gate-0 soak cases had never once run under CI. 2026-08-01

## Enforced by

`tests/test_suite_collectable.py::test_module_cannot_kill_the_collector`

## Tags

#ci #testing

## Related

- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
