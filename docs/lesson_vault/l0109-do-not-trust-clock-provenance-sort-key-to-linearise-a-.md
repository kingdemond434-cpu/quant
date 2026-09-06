---
id: L0109
cost: blind
tags: ["clocks"]
---

# L0109

Do not trust clock_provenance.sort_key to linearise a MIXED-CLOCK file. It rescues only rows whose receipt is recoverable; a Binance trade row has no 'r' field so recv_ms returns None and the key silently falls through to the VENUE t, while depth rows key on receipt. Merging them re-creates the interleave the helper exists to prevent. For an append-only recorder, FILE ORDER is receipt order and needs no timestamp arithmetic -- use it.

## Evidence

libs/research/clock_provenance.py:195-207 vs a fut partition where depth carries c=recv/E/T and trades carry c=venue with no r; measured 2026-08-12

## Tags

#clocks

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
