---
id: L0239
cost: slow
tags: ["ops", "recovery"]
---

# L0239

Recovery work must free resources BEFORE it spends them. A cleanup that measures first and deletes second is unusable in the emergency it exists for.

## Evidence

reclaim_disk --shed-bars ran duplicate_discoveries() -- read + SHA-256 of 326,224 discovery rows -- before deleting a single byte, on a box at 0 free where git could not write a loose object and git stash could not save the worktree. From outside, a long scan and a hang look identical, so the operator interrupted it twice. Bars now shed first and print what they freed before anything slow starts. [cost as recorded: the box could not pull the fix for the thing wrong with it]

## Tags

#ops #recovery

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
