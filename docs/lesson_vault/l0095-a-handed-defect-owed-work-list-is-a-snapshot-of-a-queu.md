---
id: L0095
cost: wasted
tags: ["coordination"]
---

# L0095

A handed defect/owed-work list is a SNAPSHOT of a queue siblings drain concurrently: before building any fix, re-verify the item still fires (fresh max_audit for defects, git log / ledger status for rows). ack_defect enforces this by refusing non-live ids.

## Evidence

2026-08-12 batch3: 10 of 11 handed defects were already acked/resolved by a sibling session hours earlier (acks cite d75dfda-era commits); ack_defect refused daemon-stale-code until max_audit re-confirmed it live

## Tags

#coordination

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
