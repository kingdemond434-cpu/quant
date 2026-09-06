---
id: L0166
cost: wasted
tags: ["shared-tree"]
---

# L0166

In a shared tree, end every session by grepping HEAD for your own section markers -- a committed change is not durable there. A cron desk-snapshot can commit a STALE working-tree copy OVER fresh HEAD, pure-deleting sibling commits' content while reading as a routine snapshot; 'commit within minutes' is necessary but NOT sufficient. The run-end check is 'does HEAD still contain it', never 'did I commit it'. Repair from the pinned sha of your own commit, never from the working tree.

## Evidence

a5c30542 (desk snapshot 03:23Z) pure-deletion-reverted f0301d75 (02:32Z): RU graveyard 3rd instance + CN-s9 10th instance both deleted from HEAD; restored @ 4dd08abf. 6th R0423-class instance

## Tags

#shared-tree

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
