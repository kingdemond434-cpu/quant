---
id: L0350
cost: blind
tags: ["ops", "scheduler"]
---

# L0350

Register every unattended task with the SYSTEM principal like the tasks that work; an InteractiveToken task silently exits 1 with no log line the moment the RDP session is gone, and the box stops adopting releases while every artifact still looks alive. When a task's log stops moving, read its LogonType before its script.

## Evidence

schtasks XML: MT5-AdoptRelease LogonType=InteractiveToken, last result 1, adopt_and_seal.log untouched for 28h while every SYSTEM (S-1-5-18) task ran with result 0; changed to /RU SYSTEM -> result 0

## Tags

#ops #scheduler

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
