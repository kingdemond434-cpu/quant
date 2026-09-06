---
id: L0004
cost: capital
tags: ["ops", "verification"]
---

# L0004

A committed fix is INERT until the process actually restarts. Verify it is live by inspecting the running process's behaviour, never by confirming the code was edited.

## Evidence

the --hold-top 3000 churn fix sat committed and dead for 2 days because the executor had run continuously since 07-03; 48% of closes still held <8h. institutional_knowledge.md 2026-07-10

## Tags

#ops #verification

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
