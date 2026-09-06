---
id: L0172
cost: blind
tags: ["shared-tree"]
---

# L0172

After committing on a shared tree, diff your commit's file list against what you staged. A staged file MISSING from your own commit's --stat means a sibling committed it in the gap between your edit and your commit — the change is in HISTORY under THEIR message, not lost. Check 'git log <parent>..HEAD -- <file>' before re-editing or re-adding; re-committing would duplicate or clobber.

## Evidence

2026-08-25 prospector: staged 6 files, commit 3e0fa108 showed 5; d317925d (18:27:20Z) had swept the staged data_axis_watchlist re-grades; 0 lines lost

## Tags

#shared-tree

## Related

- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
