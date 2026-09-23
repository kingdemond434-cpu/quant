---
id: L0066
cost: blind
tags: ["ci"]
enforced_by: tests/ops/test_ci_gate_lock.py::test_committed_failure_still_escalates_even_amid_scratch_files
---

# L0066

On a box where several agent sessions share ONE working tree, attribute a red whole-tree gate to tracked-vs-untracked BEFORE fixing anything. A sibling's half-written files fail lint/tests as loudly as your own, they belong to no commit, and you cannot fix them -- while a REAL failure in committed code hides inside the same red verdict.

## Evidence

2026-08-05: ci-gate-red recurred 8x in 10.7d. All 5 ruff errors and every pytest failure came from a sibling's untracked input_provenance files; two genuine mypy errors in committed libs/research/natural_experiment.py sat buried in the same verdict. Proven by re-running each step with the untracked set excluded (ruff+pytest green, mypy still 2 errors).

## Enforced by

`tests/ops/test_ci_gate_lock.py::test_committed_failure_still_escalates_even_amid_scratch_files`

## Tags

#ci

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
