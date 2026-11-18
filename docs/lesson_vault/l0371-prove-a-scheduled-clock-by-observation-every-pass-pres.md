---
id: L0371
cost: blind
tags: ["plumbing", "ops", "box"]
enforced_by: desks/mt5/tests/test_plumbing_watchdog.py::test_all_four_git_writers_use_the_lock_helper
---

# L0371

Prove a scheduled clock by OBSERVATION every pass -- present, Enabled, next run inside its window, last result not an error -- never by the fact that its installer exists. MT5-AdoptRelease could not OPEN the named mutex Local\MT5-GitWriter for FOUR DAYS, logged the refusal correctly every hour to a file nobody read, and the box ran code 232 commits behind the branch it was supposed to adopt.

## Evidence

desks/mt5/scripts/GitWriterMutex.ps1 moved the lock to MT5-GitWriter-v2; plumbing_watchdog measured HEAD 232 commits behind origin/claude/llm-auto-upgrade-verify-gcjac3 on 2026-09-23

## Enforced by

`desks/mt5/tests/test_plumbing_watchdog.py::test_all_four_git_writers_use_the_lock_helper`

## Tags

#plumbing #ops #box

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
