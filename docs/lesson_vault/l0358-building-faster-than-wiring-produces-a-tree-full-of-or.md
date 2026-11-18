---
id: L0358
cost: blind
tags: ["wiring", "governance", "scheduling", "closed-loop"]
enforced_by: desks/mt5/tests/test_wiring_ceo.py::test_auto_legs_clock_only_organs_probation_ran_clean_and_pick_the_plan
---

# L0358

Building faster than wiring produces a tree full of organs nothing runs; the audit that only asks 'does anything import it' cannot see them. The standing cure is a hunter on a clock (wiring_ceo: every organ with a main() versus every clock the repo declares, transitively through imports), a probation lane that exercises the safe ones with a budget, an auto-clock that turns a clean probation run into a real costed leg the next hour (data/auto_legs.json, run by hourly_cycle.run_auto_legs), a ratchet on the unwired count, and the CEO docket carrying the rest as tasks. A new organ arrives with its clock or it is a defect the same hour.

## Evidence

2026-09-16 on the trading box: 774 organs, 481 on a clock, 291 UNWIRED (280 probation-eligible); trajectory.py, lineage_dag.py, novelty_v2.py, tri_alignment.py, research_os/surrogate.py, regime_discovery.py, run_research_loop.py all 'wired' by libs.ops.wiring_audit and never run. First probation pass clocked 7 organs automatically.

## Enforced by

`desks/mt5/tests/test_wiring_ceo.py::test_auto_legs_clock_only_organs_probation_ran_clean_and_pick_the_plan`

## Tags

#wiring #governance #scheduling #closed-loop

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0010-textbook-mechanisms-on-daily-bars-are-picked-clean-spe]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
