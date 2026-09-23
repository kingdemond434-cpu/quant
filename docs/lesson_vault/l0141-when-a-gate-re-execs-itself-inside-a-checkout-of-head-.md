---
id: L0141
cost: wasted
tags: ["governance"]
enforced_by: tests/governance/test_law_families.py::test_a_DIRTY_tree_is_judged_at_HEAD_not_as_it_sits
---

# L0141

When a gate re-execs itself inside a checkout of HEAD, suppress the recursion with an ENV VAR, never a CLI flag: the checkout may PREDATE the flag, and an unknown argument kills the child in argparse with empty stdout while an unknown env var is simply ignored and the older copy degrades to its old behaviour.

## Evidence

run_law_gate.py --laws-only at-HEAD re-exec: first run returned 'LAW GATE -- 0 fences: FAIL / head-gate-unrunnable: Expecting value: line 1 column 1' because HEAD had no --in-place yet. Fixed with QUANT_LAWGATE_IN_PLACE=1 in be0f1d27.

## Enforced by

`tests/governance/test_law_families.py::test_a_DIRTY_tree_is_judged_at_HEAD_not_as_it_sits`

## Tags

#governance

## Related

- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0078-a-fence-with-an-ordered-status-ladder-can-have-a-fabri]]
