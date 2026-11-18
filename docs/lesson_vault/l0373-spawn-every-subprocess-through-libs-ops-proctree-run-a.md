---
id: L0373
cost: blind
tags: ["plumbing", "memory"]
enforced_by: desks/mt5/tests/test_plumbing_watchdog.py::test_the_reaper_runs_first_in_the_reconcilers_apply_pass
---

# L0373

Spawn every subprocess through libs/ops/proctree.run and reap orphaned pool workers FIRST in any repair pass. subprocess.run(timeout=) kills only the child it started, so a timed-out job leaves its worker pool charged against the commit limit forever: 72 orphans held 147 GB of a 251 GB limit while 67 GB of RAM was free, and every later leg died of STATUS_COMMITMENT_LIMIT leaving no artifact -- which reads on a board exactly like nothing to report.

## Evidence

libs/ops/proctree.py; measured 2026-09-22 on the trading box

## Enforced by

`desks/mt5/tests/test_plumbing_watchdog.py::test_the_reaper_runs_first_in_the_reconcilers_apply_pass`

## Tags

#plumbing #memory

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
