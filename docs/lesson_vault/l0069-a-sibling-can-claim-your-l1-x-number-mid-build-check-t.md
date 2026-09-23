---
id: L0069
cost: slow
tags: ["governance"]
enforced_by: tests/governance/test_enforcement_map_keys.py::test_map_has_no_duplicate_law_keys
---

# L0069

A sibling can claim your L1.x number mid-build. Check the REMOTE BRANCH tip (not local, not master) before writing a law, and on merge resolve union + renumber-once; renumber SURGICALLY by artifact name because the shared files then contain BOTH laws.

## Evidence

2026-08-05: local max L1.51, origin/claude/wonderful-darwin-7uiobi already had L1.52/53, and L1.54 NO-GIVING-UP landed while this build wrote its own L1.54 -- a duplicate key in _MAP in build_enforcement_matrix.py, second literal silently winning with 0 orphans still reported.

## Enforced by

`tests/governance/test_enforcement_map_keys.py::test_map_has_no_duplicate_law_keys`

## Tags

#governance

## Related

- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
