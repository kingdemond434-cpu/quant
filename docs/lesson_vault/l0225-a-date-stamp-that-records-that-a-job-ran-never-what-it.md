---
id: L0225
cost: blind
enforced_by: tests/ops/test_daily_cycle_runs_steps_the_stamp_never_named.py::test_a_step_the_stamp_never_named_runs_on_a_day_already_stamped
---

# L0225

A date-stamp that records THAT a job ran, never WHAT it ran, silently suppresses every step added after that day's tick -- and a file-level drift fence cannot see it, because the code genuinely IS on the box. Stamp the step SET, and make the skip run whatever the stamp does not name.

## Evidence

desks/mt5/research/daily_cycle.py: the box ran a 6-step version at 00:01, stamped 2026-08-28 done, then the 14-step chain shipped. check_desk_module_drift read 'all 50 match HEAD on both boxes' the whole time and was RIGHT. daily_cycle.log holds 14 consecutive ticks 16:50-23:01 all 'already ran; skip'. Cost: execution_quality 43.1h stale (consumer: the promotion gate), decay_live 43.1h (L1.59 had no clock), forward_reconcile 39.1h -- which on its first forced run took 3 AUTHORITY_REVOKED actions. Fix f3854081: readiness 3/7 -> 6/7 checks, job manifest 16/16 fresh.

## Enforced by

`tests/ops/test_daily_cycle_runs_steps_the_stamp_never_named.py::test_a_step_the_stamp_never_named_runs_on_a_day_already_stamped`

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
