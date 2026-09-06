---
id: L0198
cost: blind
tags: ["data-integrity"]
enforced_by: tests/mining/test_long_running_writers_stage_outside_repo.py::test_harvest_loop_appends_to_a_staging_path_not_the_tracked_artifact
---

# L0198

Stage a long-running writer's appends OUTSIDE the repo; automation unlinks tracked data files and the process keeps writing to an orphaned inode. cat /proc/<pid>/fd/N recovers it.

## Evidence

2026-08-28: fxblue harvesters logged row 50 with 28 rows on disk; /proc/1632419/fd/4 -> ...(deleted); recovered 152 vs 57 rows

## Enforced by

`tests/mining/test_long_running_writers_stage_outside_repo.py::test_harvest_loop_appends_to_a_staging_path_not_the_tracked_artifact`

## Tags

#data-integrity

## Related

- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0185-a-reader-that-raises-inside-a-fetch-chain-that-swallow]]
- [[l0194-a-liveness-check-written-against-posix-exceptions-is-d]]
- [[l0212-a-miner-that-swallows-its-fetch-exception-and-writes-t]]
