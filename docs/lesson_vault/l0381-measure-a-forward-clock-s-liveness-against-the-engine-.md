---
id: L0381
cost: blind
tags: ["forward", "clocks", "liveness"]
enforced_by: desks/mt5/tests/test_clock_liveness.py::test_planted_frozen_clock_is_detected_with_its_cause
---

# L0381

Measure a forward clock's liveness against the ENGINE'S ROSTER, not its ledger row: a clock freezes silently when its identity leaves the certificate canon while its ACTIVE row survives, and repair it in the same pass by handing the exact identity back to shadow_forward.main(rows=...).

## Evidence

Measured on the trading box vmi3571445 2026-09-23: shadow_state.json held 483 rows against a 119-key roster from certified_sleeves(); 364 rows were off the roster and 35 still read status ACTIVE with their newest attempt 50.8 h old. Nothing failed -- shadow_forward rebuilds its `enrolled` roster from the canon every pass and never prunes the ledger, so it simply stopped visiting those keys, and the lane's own health file reported missing_sleeves: [] because from the roster's point of view nothing was missing. desks/mt5/research/clock_liveness.py found them, desks/mt5/research/clock_reenrol.py reconstructed 35 of 35 exactly from data/sleeve_registry.json, and the frozen count fell 39 -> 4 -> 0 with the clocks' own stamps as the proof.

## Enforced by

`desks/mt5/tests/test_clock_liveness.py::test_planted_frozen_clock_is_detected_with_its_cause`

## Tags

#forward #clocks #liveness

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
