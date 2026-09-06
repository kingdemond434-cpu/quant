---
id: L0149
cost: blind
tags: ["fences"]
enforced_by: tests/research/test_cross_section_floor.py::test_fence_is_not_satisfied_by_a_comment_describing_the_fix
---

# L0149

A fence that substring-matches raw source is satisfied by a COMMENT describing the fix. Match ast.unparse'd code with docstrings stripped -- prose about a guard is not a guard, and the failure certifies exactly the files whose authors thought hardest and then did nothing.

## Evidence

scripts/check_cross_section_floor.py first run scored run_derivative_shadow FLOORED because the comment explaining the repair contained the string notna().sum(axis=1).

## Enforced by

`tests/research/test_cross_section_floor.py::test_fence_is_not_satisfied_by_a_comment_describing_the_fix`

## Tags

#fences

## Related

- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0076-counting-dated-rows-is-not-counting-observations-and-t]]
- [[l0079-grep-for-a-governance-flag-s-consumers-not-its-writers]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
- [[l0084-when-a-detector-fires-correctly-and-its-class-still-re]]
