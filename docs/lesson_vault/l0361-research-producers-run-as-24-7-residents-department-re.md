---
id: L0361
cost: slow
tags: ["departments", "box"]
enforced_by: desks/mt5/tests/test_department_resident.py::test_singleton_lock_is_exclusive
---

# L0361

Research producers run as 24/7 residents (department_resident.py: singleton lock, a pass restarts the moment the last ends, memory guard), never as hourly tasks with dead time between passes; the hourly trigger is only a keep-alive. Register box tasks from a script written with the file tool: a heredoc through the shell turned a backslash-r in a Windows path into a carriage return and every resident exited with code 1 on 2026-09-17.

## Evidence

desks/mt5/research/department_resident.py; desks/mt5/ops/box_tasks.manifest MT5-Dept-* rows; box registration 2026-09-17 00:45 rc=1 then 02:11 Running

## Enforced by

`desks/mt5/tests/test_department_resident.py::test_singleton_lock_is_exclusive`

## Tags

#departments #box

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
