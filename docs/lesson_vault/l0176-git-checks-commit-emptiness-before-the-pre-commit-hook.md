---
id: L0176
cost: hygiene
tags: ["git"]
enforced_by: tests/scripts/test_moneypath_precommit_guard.py::test_local_marker_strip_restored
---

# L0176

git checks commit-emptiness BEFORE the pre-commit hook, so a hook that unstages everything yields an EMPTY commit (rc=0), never a refusal. Design hook guards to restore-and-continue and read an empty sync commit as the truthful all-refused outcome.

## Evidence

moneypath_precommit_guard scratch-repo tests 2026-08-26, commit 6fed406d

## Enforced by

`tests/scripts/test_moneypath_precommit_guard.py::test_local_marker_strip_restored`

## Tags

#git

## Related

- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0080-libs-ops-input-provenance-inputs-read-json-records-a-s]]
