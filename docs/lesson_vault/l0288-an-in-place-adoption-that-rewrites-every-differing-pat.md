---
id: L0288
cost: blind
tags: ["box"]
enforced_by: desks/mt5/tests/test_adopt_release_survives_an_undeletable_file.py::test_the_box_s_own_state_is_kept_and_only_origin_s_inputs_are_adopted
---

# L0288

An in-place adoption that rewrites EVERY differing path rolls the box's live evidence back to origin's older copy and can die mid-write leaving a half-adopted, uncommitted code tree that no later merge can land. The box's state paths are the box's: keep what the box changed since it diverged, adopt code and origin-only inputs, verify code == target, record the merge. And a locked file is a moment, not a verdict -- retry before reporting it.

## Evidence

2026-09-07: Adopt-Release ran twice ('Box state captured before release adoption' x2), no 'Adopt ... in place' commit followed either; the box was left with uncommitted edits to gateway.py/decision_core.py, 42 untracked paths, ShadowSync result 1 every hour since, gateway refusing new risk on the drift, five sleeves placing nothing while 39 commits of fixes sat on origin.

## Enforced by

`desks/mt5/tests/test_adopt_release_survives_an_undeletable_file.py::test_the_box_s_own_state_is_kept_and_only_origin_s_inputs_are_adopted`

## Tags

#box

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
