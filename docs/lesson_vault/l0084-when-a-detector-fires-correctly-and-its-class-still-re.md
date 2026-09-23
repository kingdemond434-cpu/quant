---
id: L0084
cost: slow
tags: ["conversion"]
---

# L0084

When a detector fires correctly and its class STILL recurs, the defect is the missing actuator, not the detection. Ask what repairs each fence's finding, and whether that path is reachable by the process that finds it.

## Evidence

max_audit.check_stale_daemons fired correctly on all three stale-code instances (2026-07-10 2d, 07-26 8.7h, 08-05 11.8h) and every one shipped only when a human looked, because pull_deploy.sh could only print 'OWED (permission denied)'. Fixed by scripts/ship_restart.py (505f5c1).

## Tags

#conversion

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
