---
id: L0328
cost: blind
tags: ["research", "schema"]
enforced_by: desks/mt5/tests/test_weak_signal_power_deficient.py::test_stages_schema_is_read_and_gates_schema_still_works
---

# L0328

A .get() against a field name that does not exist returns an EMPTY CONTAINER, not an error, so a filter built on it silently passes nothing and the organ reports 'there was nothing to do'. When a lane reports zero, verify the field names it reads against the artifact it reads, before concluding the lane has no material.

## Evidence

2026-09-14: weak_signal_compiler.power_deficient() read v.get('gates'); the gauntlet has always written 'stages'. It printed '0 symbols with members, 0 combinations, 0 proposed' for its entire existence. Measured on the box: 7,831 verdicts, 0 carrying 'gates', 7,831 carrying 'stages', 560 qualifying cells across 67 eligible symbols. 0 -> 560 on one field name.

## Enforced by

`desks/mt5/tests/test_weak_signal_power_deficient.py::test_stages_schema_is_read_and_gates_schema_still_works`

## Tags

#research #schema

## Related

- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
