---
id: L0284
cost: hygiene
tags: ["process"]
---

# L0284

Never pipe pytest through tail in a commit chain. The exit code is the gate; capture it, and refuse to commit on red.

## Evidence

69a3438e (2026-09-08) carried a failing test because 'pytest | tail -4' returned tail's exit code; 63f8cf01 claimed eleven lessons after every add had raised behind 'tail -1'.

## Tags

#process

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
