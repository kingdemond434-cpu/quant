---
id: L0175
cost: blind
tags: ["scheduler"]
enforced_by: tests/scripts/test_producer_schedules.py::test_no_decision_affecting_producer_is_unscheduled
---

# L0175

When several unrelated producers go stale TOGETHER, check the SCHEDULER first, not each organ: every ops/crontab.manifest row died with root cron on 08-20 and each stale artifact got its own bespoke diagnosis (ratchet stall, deploy-stale, cadence rot) for 6 days. data/manifest_dispatch_state.json now meters uncovered rows.

## Evidence

law gate, check_ratchets (16d L1.50 stall), check_conversion, pull_deploy (126h), run_cadence all dead since 08-20; quant-manifest-dispatch.timer resurrection commit 71edc743

## Enforced by

`tests/scripts/test_producer_schedules.py::test_no_decision_affecting_producer_is_unscheduled`

## Tags

#scheduler

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
