---
id: L0061
cost: wasted
tags: ["validation"]
enforcement_retired: tests/data/test_multiexchange.py::TestOkxInstRedenomination::test_redenominated_tickers_resolve_to_the_bare_okx_name -- deleted with the retired crypto desk (MT5 universe mandate 2026-08-18); the property is no longer enforced by anything, so this lesson is back at full weight
---

# L0061

Before grading a cross-venue join defect, check whether the venues merely NAME the same asset differently -- a re-denomination multiplier lives in the TICKER on one venue and in the CONTRACT SIZE on another, so a string join MISSES the asset rather than mismatching it. And check the unit of the quantity you are joining before writing the severity: a dimensionless rate is not corrupted by a multiplier.

## Evidence

Binance 1000SHIBUSDT vs OKX SHIB-USDT-SWAP ctVal=1e6. okx_inst() resolves 260/653 and drops SHIB/PEPE/FLOKI/BONK/SATS. The tempting '1000x scaling bug' headline would have been WRONG -- funding is a rate, so it is a coverage loss, not a corruption. docs/research/improvement_inbox.md, R0294.

## Tags

#validation

## Related

- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
