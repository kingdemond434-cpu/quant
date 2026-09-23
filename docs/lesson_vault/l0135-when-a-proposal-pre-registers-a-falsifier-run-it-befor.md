---
id: L0135
cost: blind
tags: ["falsifier"]
enforced_by: tests/ops/test_claim_registry.py::TestRegistryIsReal::test_scanned_counts_the_run_not_the_registry
---

# L0135

When a proposal pre-registers a falsifier, RUN IT BEFORE WRITING CODE -- it can kill the design and save the build. And when it fires, build the fallback the proposal itself named rather than shipping the refuted version.

## Evidence

2026-08-12 L1.61: the general cross-artifact index measured 590 artifacts / 4,523 shared leaf names / 418 disagreements and 0 of a random 25 were genuine same-meaning contradictions (why has 78 publishers of free text; window_days is 1.0 and 90 and both correct). Shipped the hand-registered money-path registry instead: 6 claims, 4 real defects, 100% precision.

## Enforced by

`tests/ops/test_claim_registry.py::TestRegistryIsReal::test_scanned_counts_the_run_not_the_registry`

## Tags

#falsifier

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
