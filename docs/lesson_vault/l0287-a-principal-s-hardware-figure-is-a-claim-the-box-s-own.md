---
id: L0287
cost: slow
tags: ["box"]
enforced_by: desks/mt5/tests/test_stall_watch_disk.py::test_the_box_publishes_what_it_has_not_only_what_is_free
---

# L0287

A principal's hardware figure is a CLAIM; the box's own counters are the MEASUREMENT, and the two must be reconciled before any floor is sized off either. When they disagree by 10x, the counters are right until a counter says otherwise -- and the number that settles it (total memory) must be PUBLISHED, not just read.

## Evidence

2026-09-08: '80gb ram stop bsing' vs stall_watch 'phys 142MB free / virt 11719MB', page file full at 12,756MB, free RAM cycling 3329->448MB around a 3.7GB searcher, a 4882MB process leaving 280MB free. 80GB is the disk (CX32: 4 vCPU/8GB/80GB). The 8192MB gauntlet floor sized off the claim would have refused every hourly sweep (rc=75); TotalVisibleMemorySize was read on every watchdog pass and written nowhere until now.

## Enforced by

`desks/mt5/tests/test_stall_watch_disk.py::test_the_box_publishes_what_it_has_not_only_what_is_free`

## Tags

#box

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
