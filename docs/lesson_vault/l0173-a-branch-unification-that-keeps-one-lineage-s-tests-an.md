---
id: L0173
cost: blind
tags: ["unification"]
enforced_by: tests/ops/test_collection_is_not_a_mass_grave.py::test_every_test_module_in_the_repo_can_be_collected
---

# L0173

A branch unification that keeps one lineage's TESTS and the other lineage's CODE turns every collection error into a mass grave: behind the first uncollectable test file, every guard test is silently dead and every fix those guards pinned may be gone. Fix collection FIRST, then treat each newly-visible failure as a candidate LOST FIX, never as test rot.

## Evidence

2026-08-26: desks/mt5/tests had 4 collection errors hiding 53 failures; adjudication recovered the causality-correct engine (fill-bar leak: 59.7% of trades resolved on fill bar, E[R] +0.283 vs +0.105), allocation Q_TOTAL 0.055-vs-0.0127, retained_exact_survivors, day_states live availability. Commits 73ca07b9, b0497287

## Enforced by

`tests/ops/test_collection_is_not_a_mass_grave.py::test_every_test_module_in_the_repo_can_be_collected`

## Tags

#unification

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
