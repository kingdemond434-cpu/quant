---
id: L0067
cost: blind
tags: ["governance"]
enforced_by: tests/governance/test_input_provenance_fence.py::test_idle_cost_does_not_erase_clamps_when_the_guard_is_unreadable
---

# L0067

Before replacing a fabricated default with UNMEASURED, read the CONSUMER first: if it fills the missing key with a loosening default, removing the fabrication OPENS the gate. Publish the absence beside the number and leave the number alone.

## Evidence

run_live_guard published ramp size_fraction 0.10 from data/ramp_state.json which has never existed; run_cashcarry_executor:1491 does .get(effective_size_fraction, 1.0) -- so emitting no value would have sized the book at FULL, not the floor. 2026-08-05 L1.55.

## Enforced by

`tests/governance/test_input_provenance_fence.py::test_idle_cost_does_not_erase_clamps_when_the_guard_is_unreadable`

## Tags

#governance

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0056-a-drawdown-rail-measures-a-ratio-so-an-accounting-chan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
