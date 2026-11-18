---
id: L0391
cost: slow
tags: ["release"]
---

# L0391

Do not expect a gated push to land on a branch another writer touches every 15 minutes: the pre-push battery takes longer than the interval, so the remote ref moves first and the push is rejected after the gates have already passed. Run the gates, then land the identical code tree from a worktree at the current tip.

## Evidence

2026-11-14: gates all green and LAW GATE 43 fences PASS (attestation 2a324f0123e3), then '! [remote rejected] cannot lock ref: is at 8f800ba61d but expected e4e93543e4'; MT5-ShadowSync pushes state every ~15 min and does so with --no-verify.

## Tags

#release

## Related

- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
