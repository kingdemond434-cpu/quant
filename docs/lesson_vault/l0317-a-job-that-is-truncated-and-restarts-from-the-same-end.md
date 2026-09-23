---
id: L0317
cost: capital
tags: ["wiring", "measurement"]
---

# L0317

A job that is TRUNCATED and restarts from the same end is not slow, it is BROKEN -- and it looks identical to slow on every dashboard. Either give a gap-closing pass the budget to finish, or make it consume its backlog FIRST so truncation still makes progress. Never give an enrolment or reconciliation pass the same budget as a sampling search.

## Evidence

2026-09-14: enrol_clocks ran shadow_forward under the hourly cycle's 720s SEARCH_BUDGET_SEC and was killed partway through the same prefix every hour, so the tail was never reached -- not once. 84 of 186 authorized runs, every one through all ten gates, had no forward clock and accrued nothing indefinitely while the leg reported scheduled and running. The gauntlet already had the other half of the answer: never-judged cells sort first.

## Tags

#wiring #measurement

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
