---
id: L0080
cost: hygiene
tags: ["provenance"]
---

# L0080

libs.ops.input_provenance.Inputs.read_json RECORDS a stale read and still RETURNS the data -- by design (L1.44: the CALLER names its degrade direction). Never rely on the default to withhold a stale artifact; check records[-1].status != READ explicitly, or a month-old file produces a confident verdict.

## Evidence

2026-08-05 libs/ops/repair_mode.py: a 30-day-old conversion_status.json yielded direction=DRAIN while the docstring claimed UNMEASURED. Caught by tests/governance/test_repair_actuator.py::test_stale_artifact_is_unmeasured, which failed on first run.

## Tags

#provenance

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
