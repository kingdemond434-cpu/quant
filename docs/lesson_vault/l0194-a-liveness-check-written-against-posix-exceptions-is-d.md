---
id: L0194
cost: blind
tags: ["windows"]
enforced_by: desks/mt5/tests/test_job_lock_liveness.py::test_a_dead_windows_owner_is_recognised_as_dead
---

# L0194

A liveness check written against POSIX exceptions is dead code on Windows. os.kill(pid,0) raises ProcessLookupError on POSIX and plain OSError winerror=87 on win32, so 'except OSError: return False' makes every dead process read as ALIVE -- test the platform under test, not the platform running the tests.

## Evidence

job_lock._owner_is_dead could never return True on contabo-mt5; lock held by dead pid 6904 refused every hourly search with 'REFUSED duplicate writer'. Measured on the box 2026-08-27. Fixed e5b96341

## Enforced by

`desks/mt5/tests/test_job_lock_liveness.py::test_a_dead_windows_owner_is_recognised_as_dead`

## Tags

#windows

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
