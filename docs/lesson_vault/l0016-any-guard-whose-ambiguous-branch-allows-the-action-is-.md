---
id: L0016
cost: blind
tags: ["safety", "design"]
enforced_by: tests/autodiscovery/test_gate_wiring.py::test_a_gate_with_no_input_is_reported_unmeasured_never_passed
---

# L0016

Any guard whose ambiguous branch ALLOWS the action is the top defect class here. Unknown must BLOCK -- except in the discovery pre-filter, where unknown must ESCALATE, because the failure there is a killed alpha.

## Evidence

standing law; libs/execution/event_guard.py blocks on both EMPTY and STALE calendars rather than treating an unpopulated file as clear

## Enforced by

`tests/autodiscovery/test_gate_wiring.py::test_a_gate_with_no_input_is_reported_unmeasured_never_passed`

## Tags

#safety #design

## Related

- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0084-when-a-detector-fires-correctly-and-its-class-still-re]]
- [[l0085-in-any-counterfactual-estimator-a-period-where-the-eve]]
- [[l0088-a-guard-that-fails-closed-on-a-missing-data-file-must-]]
- [[l0102-reading-an-append-only-log-positionally-assumes-write-]]
- [[l0104-a-rate-measured-once-is-a-rate-that-will-be-wrong-late]]
- [[l0109-do-not-trust-clock-provenance-sort-key-to-linearise-a-]]
- [[l0111-a-lagged-control-removes-flow-that-chases-a-past-move-]]
