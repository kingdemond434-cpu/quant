---
id: L0343
cost: capital
tags: ["ops", "monitoring"]
enforced_by: desks/mt5/tests/test_plumbing_watchdog.py::test_an_absent_task_is_a_critical_defect_naming_its_installer
---

# L0343

A MISSING SCHEDULED TASK IS INVISIBLE TO EVERY ARTIFACT-READING FENCE. Check that the desk's declared clocks EXIST, not just that their outputs are fresh. A task that does not exist writes no artifact, raises no error and fails no check -- it is indistinguishable from one that ran and found nothing to do. Also treat a git/ssh writer older than an hour as STUCK, not busy: a polite mutex wait against a dead holder is permanently wrong.

## Evidence

2026-09-15 on the trading box: Get-ScheduledTask returned TWO tasks (MT5-DashMirror, and a disabled MT5DataSyncToVps) against TWENTY declared by Install-QuantWindows.ps1. Eighteen were gone including MT5-Gateway, MT5-Hourly and MT5-AdoptRelease. That one absence explains every operational complaint made for a month: sync_marker frozen since 08-17, the box never adopting, state never pushed, gateway_state frozen at 09-12, forex sleeves never trading, pf_allocation 32h stale. Separately a hung ssh.exe from 2026-09-12 01:18 held Local\MT5-GitWriter for THREE DAYS and every adopt was refused with 'another git writer held the mutex for the full 9 min' -- correct, polite, and permanently wrong.

## Enforced by

`desks/mt5/tests/test_plumbing_watchdog.py::test_an_absent_task_is_a_critical_defect_naming_its_installer`

## Tags

#ops #monitoring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
