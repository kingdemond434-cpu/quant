---
id: L0345
cost: capital
tags: ["ops"]
enforced_by: desks/mt5/tests/test_job_lock_liveness.py::test_a_dead_owner_actually_lets_the_next_writer_in
---

# L0345

A TIMEOUT IS NOT A LIVENESS CHECK. Lock by OWNER PID, never by age: a lock whose writer is still running is held however long the work takes, and one whose writer is gone is free immediately. An age-based steal window is a bet that the work finishes inside it -- and the bet loses precisely when the work gets MORE valuable, because doing more takes longer. Fail towards 'holder alive' when the platform cannot be asked: a second copy placing orders beside a live one is worse than a pass skipped.

## Evidence

2026-09-15: run_gateway_loop stole any lock older than 5 minutes, which was fine while most sleeves refused instantly on unresolvable parameters. Once the forex sleeves actually started computing signals a pass took minutes, so on a 1-minute trigger a second copy stole the lock every 5 minutes while the first still ran. Measured: EIGHT concurrent gateway processes, one 138 minutes old holding 588 MB, on a box with 1.2 GB free -- and three background jobs killed by the OS for memory pressure. Fixing the strategies made the stacking worse, which is the signature of a timeout standing in for a liveness check.

## Enforced by

`desks/mt5/tests/test_job_lock_liveness.py::test_a_dead_owner_actually_lets_the_next_writer_in`

## Tags

#ops

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
