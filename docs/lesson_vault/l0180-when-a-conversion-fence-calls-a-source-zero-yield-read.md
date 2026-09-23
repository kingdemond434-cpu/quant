---
id: L0180
cost: blind
tags: ["miners"]
enforced_by: tests/test_central_bank_miner.py::test_every_emitted_row_is_dated
---

# L0180

When a conversion fence calls a SOURCE zero-yield, read the READER before believing it. A broken collector and a barren ground are indistinguishable from outside the miner, and the reader is the cheaper of the two to fix.

## Evidence

central_bank_miner scraped landing pages, emitted NO timestamp (so it could never feed event_reaction/macro_conditional, the two absent-but-reachable families) and substring-matched EURUSD against federalreserve.gov, returning [] every run and emitting USDUSD for the Fed. Repaired 2026-08-26 to dated RSS/RDF: 162 dated docs, 0 undated, in the first run. Same class as MQL5/R0660.

## Enforced by

`tests/test_central_bank_miner.py::test_every_emitted_row_is_dated`

## Tags

#miners

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
