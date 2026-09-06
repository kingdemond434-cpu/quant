---
id: L0136
cost: blind
tags: ["provenance"]
enforced_by: tests/ops/test_claim_registry.py::TestRepairAttribution::test_block_measured_flag_alone_does_not_taint_a_real_measurement
---

# L0136

A block-level provenance/measured flag must never be inherited per-key. Register the taint per criterion from a read of the producer's code, or a fence sends readers to repair an input the value never read.

## Evidence

2026-08-12: L1.61's first run inherited live_guard's block-level measured=false and labelled all 4 Gate-0 contradictions FABRICATED; 4 of 5 criteria are computed AFTER and override the absent input, so keys_present and connector_verified were genuine measurements. Pinned by test_block_measured_flag_alone_does_not_taint_a_real_measurement.

## Enforced by

`tests/ops/test_claim_registry.py::TestRepairAttribution::test_block_measured_flag_alone_does_not_taint_a_real_measurement`

## Tags

#provenance

## Related

- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
