---
id: L0357
cost: blind
tags: ["scheduling", "reliability", "hourly-cycle", "governance"]
enforced_by: desks/mt5/tests/test_cycle_plans_and_resume.py::test_department_plans_partition_the_heavy_legs
---

# L0357

A cycle whose legs' budgets sum past its task limit runs its head every hour and its tail never: the hourly cycle summed to 110-200 min under a 55-min limit, so deepen, forward_reconcile, falsifier_run, credit, mutation_yield and closed_loop had not run for a day, the daily chain had not completed for three days (its stamp was written only at the end), and the adopt task's 20-min limit terminated it before the seal -- all read as 'FAILED' or as stale artifacts, never as the scheduling defect they were. Split the cycle by plan (core every hour, heavy on a limit that fits it), stamp resumable chains after every step, set every task's limit from its measured duration, and let every organ publish its provenance envelope so the ledger shows which sha ran what and when.

## Evidence

compute_ledger 2026-09-16: cycle 19:58->23:16 UTC 112 legs 200 min; 00:08->01:46 33 legs 111 min; MT5-Hourly limit PT55M rc=267014 on every run since 02:00; daily_cycle_state last_run 2026-09-13; MT5-AdoptRelease PT20M rc=267014 with no seal line after 19:00Z. Fixed: HOURLY_PLAN core|heavy|all, MT5-HourlyCore, PT3H/PT2H, daily stamp per step, close_run envelope.

## Enforced by

`desks/mt5/tests/test_cycle_plans_and_resume.py::test_department_plans_partition_the_heavy_legs`

## Tags

#scheduling #reliability #hourly-cycle #governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
