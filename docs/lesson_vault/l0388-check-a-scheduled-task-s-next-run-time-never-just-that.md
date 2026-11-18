---
id: L0388
cost: blind
tags: ["ops", "scheduling", "duty_cycle"]
enforced_by: desks/mt5/tests/test_duty_cycle.py::test_an_expired_repetition_window_reads_as_dead_not_healthy
---

# L0388

Check a scheduled task's NEXT RUN TIME, never just that it exists and is Enabled: a Windows repetition window with a finite Duration and StopAtDurationEnd expires and leaves the task Enabled with a real Last Run Time and no next run. schtasks /Change /RI sets the interval and leaves the duration, so re-arm with /RI <existing> /DU 9999:59 and VERIFY by re-reading Next Run Time.

## Evidence

2026-09-24: MT5-Gauntlet (the judge's 5-minute clock) last fired 06:51 on 2026-09-23 and produced verdicts in 2 of 24 hours (80,603 against a demonstrated 44,310/hour = 8% duty cycle); its trigger carried Interval PT5M inside Duration P7DT1H35M. stall_watch heals missing or disabled tasks and this was neither. desks/mt5/research/duty_cycle.py, scripts/check_duty_cycle.py

## Enforced by

`desks/mt5/tests/test_duty_cycle.py::test_an_expired_repetition_window_reads_as_dead_not_healthy`

## Tags

#ops #scheduling #duty_cycle

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
