---
id: L0146
cost: blind
tags: ["testing"]
enforced_by: tests/execution/test_tape_test_harness_guard.py::test_driving_forensics_leaves_the_live_tape_untouched
---

# L0146

A test that redirects a module's OWN paths can still write live state through a SECOND module's default. When a test monkeypatches output paths, ask which other module the code under test writes through -- and put the refusal at that module's write chokepoint, never in the test.

## Evidence

2026-08-13: tests/execution/test_carry_entry_gate.py patched run_trade_forensics._TRADES/_OUT/_TRACKED/_COST_MODEL but backfill() wrote libs/execution/execution_tape._TAPE; 16 fixture rows, coverage()['days'] 2415.15 vs true 30.69

## Enforced by

`tests/execution/test_tape_test_harness_guard.py::test_driving_forensics_leaves_the_live_tape_untouched`

## Tags

#testing

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
