---
id: L0379
cost: slow
tags: ["governance", "research"]
enforced_by: tests/scripts/test_check_no_queues.py::test_row_older_than_one_cycle_is_a_breach
---

# L0379

NOTHING IS QUEUED: a row is processed ON ARRIVAL, and where a budget genuinely runs out the leftover is the FIRST work of the next pass with its AGE PUBLISHED - never an indefinite park. Measure every queue in one artifact or the backlog stays invisible: each organ knew its own number, in its own unit, and no file put them side by side. A queue with no drainer at all is worse than a slow one and must be counted separately. A queue whose rows carry no enqueue timestamp is UNMEASURED, which FAILS: the fix is to stamp the rows, and a fence that passed there would make that fix optional forever.

## Evidence

desks/mt5/reports/QUEUE_CENSUS.json first pass 2026-09-23: 14 queues, 63,110 rows waiting, 6 BREACH, 1 PARKED, 2 UNMEASURED, oldest row 654 h (27 days) in requeue_named. research_queue.json held 21,373 open rows with NO SCHEDULED DRAINER - the only readers are report builders and an archive restorer that puts rows BACK. registry.claim_candidates, the lease meant to drain 5,769 queued sqlite candidates, has zero callers outside registry.py. miner_deepening_queue.json holds 28,450 rows carrying no per-row timestamp, so their age was literally unknowable. mechanism_naming_queue.json is a 4,000-row ring buffer that silently drops the oldest row on every write while the drain reads the newest first. Fenced by scripts/check_no_queues.py in run_law_gate _STATE_FENCES.

## Enforced by

`tests/scripts/test_check_no_queues.py::test_row_older_than_one_cycle_is_a_breach`

## Tags

#governance #research

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
