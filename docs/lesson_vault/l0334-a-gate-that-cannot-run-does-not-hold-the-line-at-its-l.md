---
id: L0334
cost: blind
tags: ["testing", "coverage"]
enforced_by: tests/scripts/test_daily_max.py::test_dry_run_attempts_nothing
---

# L0334

A gate that cannot RUN does not hold the line at its last reading -- it stops observing, and decay accumulates behind it at full speed while the recorded number still looks healthy. When a ratchet, fence or floor has not produced a fresh measurement, treat its last value as UNKNOWN rather than as holding, and fix the thing blocking the measurement before trusting anything downstream of it.

## Evidence

2026-09-14: scripts/daily_max.py called _run_audit() before checking --dry-run, spawning max_audit.py with timeout=1800. pytest-timeout killed the whole session at test_dry_run_attempts_nothing, so coverage.json was never written and check_coverage_floors reported 'cannot read coverage.json' for 36 days. First completed run since: repo 78.92% against an 86.48% floor, with 81 files at LITERALLY 0% coverage totalling 8,479 statements (12.8% of the codebase) -- fill_corpus.py 520, memory.py 358, state_admission.py 238, completion.py 234 -- and the largest were all added 2026-09-04 to 2026-09-10, inside the blind window. At merely 80% on those files the repo would read 89.14%, above the floor.

## Enforced by

`tests/scripts/test_daily_max.py::test_dry_run_attempts_nothing`

## Tags

#testing #coverage

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
