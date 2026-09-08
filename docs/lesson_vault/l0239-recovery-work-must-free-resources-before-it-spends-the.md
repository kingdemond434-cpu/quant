---
id: L0239
cost: the box could not pull the fix for the thing wrong with it
tags: ["ops", "recovery"]
---

# L0239

Recovery work must free resources BEFORE it spends them. A cleanup that measures first and deletes second is unusable in the emergency it exists for.

## Evidence

reclaim_disk --shed-bars ran duplicate_discoveries() -- read + SHA-256 of 326,224 discovery rows -- before deleting a single byte, on a box at 0 free where git could not write a loose object and git stash could not save the worktree. From outside, a long scan and a hang look identical, so the operator interrupted it twice. Bars now shed first and print what they freed before anything slow starts.

## Tags

#ops #recovery

## Related

- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0085-in-any-counterfactual-estimator-a-period-where-the-eve]]
- [[l0092-the-suite-ran-must-mean-n-tests-executed-never-the-com]]
- [[l0096-establish-a-source-s-legitimacy-posture-with-a-ua-matr]]
- [[l0099-an-absolute-path-in-an-edit-targets-the-tree-it-names-]]
- [[l0101-assert-the-discriminating-property-in-a-fixture-contro]]
