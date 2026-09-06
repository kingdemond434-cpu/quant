---
id: L0152
cost: blind
tags: ["graveyard"]
---

# L0152

When a kill's cause is MECHANICAL (leak, clock, alignment, denominator), find the file that produced the killed number and check whether IT changed. Retiring the axis does not disarm the generator.

## Evidence

bithumb_kr_premium_lookahead killed 2026-07 with the cause stated exactly; scripts/batch_premium.py:41-45 still keys Bithumb 24h bars (15:00 UTC start = KST day) by start-date against 00:00-UTC Binance bars, so any re-run re-manufactures the same 15h look-ahead. Verified live 2026-08-13. Coinone checked and clean -> the boundary is per-venue, not a KR rule.

## Tags

#graveyard

## Related

- [[l0010-textbook-mechanisms-on-daily-bars-are-picked-clean-spe]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
