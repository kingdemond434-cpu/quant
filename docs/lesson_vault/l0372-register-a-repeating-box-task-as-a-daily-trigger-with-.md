---
id: L0372
cost: blind
tags: ["plumbing", "scheduler"]
enforced_by: desks/mt5/tests/test_plumbing_watchdog.py::test_the_adoption_task_is_daily_repeating_hourly_under_system
---

# L0372

Register a repeating box task as a DAILY trigger with a one-day repetition, never a -Once trigger with a long RepetitionDuration. The scheduler folded MT5-AdoptRelease's duration to P9DT2H40M, the repetition expired on 2026-09-21, Next Run Time went to N/A, and later the task vanished from the scheduler entirely -- a task that does not exist writes no artifact, raises no error and fails no check.

## Evidence

desks/mt5/scripts/install_adopt_release_task.ps1:43-46; measured 2026-09-22 on the trading box

## Enforced by

`desks/mt5/tests/test_plumbing_watchdog.py::test_the_adoption_task_is_daily_repeating_hourly_under_system`

## Tags

#plumbing #scheduler

## Related

- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0080-libs-ops-input-provenance-inputs-read-json-records-a-s]]
- [[l0081-persist-accumulated-state-in-a-finally-never-only-at-t]]
- [[l0097-when-a-check-grades-a-timestamp-read-what-writes-it-a-]]
- [[l0099-an-absolute-path-in-an-edit-targets-the-tree-it-names-]]
