---
id: L0292
cost: blind
tags: ["ops", "delivery"]
enforced_by: desks/mt5/tests/test_hourly_cycle_paths.py::test_one_leg_failure_cannot_terminate_later_independent_legs
---

# L0292

Two machines on two branches with a silent conflict-abort between them are one machine each. An automatic merge that aborts on conflict and writes no artifact is indistinguishable from one that succeeds: both sides keep committing, each believes it is deploying the other's work, and the divergence is found only when someone asks why a fix pushed two days ago has not run. Any automatic merge must publish its own status as an artifact (behind count, last success, last conflict paths), a both-sides state file must have exactly one writer with the other side a copy, and after any commit that touches a both-sides path, confirm the desk branch is an ancestor of the VPS branch before believing it deployed.

## Evidence

2026-09-08 21:00 UTC: origin/desk-sync-clean (the VPS's branch, Codex author) and origin/claude/llm-auto-upgrade-verify-gcjac3 (the box's) had no common commit after 023cc43a (2026-09-06 17:08). quant-desk-refresh (ops/refresh_desk_state.sh, every 3 min, `git merge --abort` on conflict, no artifact) had failed ~960 times on the same three paths: desks/mt5/data/moat_coverage.json (VPS: 108-byte stub), desks/mt5/data/universe/universe.json (VPS: the 6.7 KB stump), desks/mt5/research/hourly_cycle.py (the same leg-isolation fix made twice). 57 VPS commits with 4,822 intelligence artifacts never reached the compiler the box runs; 147 desk commits (hourly kimi, lit DeepSeek, prose extraction) never ran on the VPS. Converged in 7264e420 and pushed to all three branches.

## Enforced by

`desks/mt5/tests/test_hourly_cycle_paths.py::test_one_leg_failure_cannot_terminate_later_independent_legs`

## Tags

#ops #delivery

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
