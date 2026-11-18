---
id: L0362
cost: slow
tags: ["wiring", "clocks"]
enforced_by: desks/mt5/tests/test_wiring_ceo.py::test_no_auto_leg_ever_carries_dry_run_and_production_args_are_the_organs_own
---

# L0362

Wiring and clocks are never queued: the wirer runs hourly and drains its whole queue (probation 40 organs a pass, state saved after every organ), every organ that passes probation is clocked the same hour with production args (never --dry-run), and broken or silent clocked organs are revived first; a queue a session must notice is a defect.

## Evidence

desks/mt5/research/wiring_ceo.py revive_queue; probation_runner.py --max-organs; box 2026-09-17: 293 unwired, 282 queued, 0 auto-clocked because probation had never run

## Enforced by

`desks/mt5/tests/test_wiring_ceo.py::test_no_auto_leg_ever_carries_dry_run_and_production_args_are_the_organs_own`

## Tags

#wiring #clocks

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
