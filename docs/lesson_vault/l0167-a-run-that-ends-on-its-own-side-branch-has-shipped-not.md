---
id: L0167
cost: blind
tags: ["worktree"]
---

# L0167

A run that ends on its own side branch has shipped NOTHING: every cross-organ artifact (ledger row, graveyard entry, WS observation, repair demand) is real only once it is an ANCESTOR of the branch the organs read. The run-end check for a worktree session is 'git merge-base --is-ancestor <my-commit> <live-branch>' -- not 'did I commit', not 'did I push my branch'. Verifying your own branch and stopping is the private-worktree variant of the shared-tree HEAD check (L0166).

## Evidence

KR s3 (c32ed2be, 08-13) committed+pushed claude/kr-miner-s3-20260813 and closed clean; its batch_premium 15h look-ahead repair rows sat ledgered-into-a-void for 6 days while the leak producer stayed live on the branch cron reads; landed only when KR s4's resume read found ancestry FALSE (merge 0c691dc3)

## Tags

#worktree

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
