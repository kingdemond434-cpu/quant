---
id: L0322
cost: capital
tags: ["execution", "measurement"]
---

# L0322

When two ledgers describe the same event, find the one that is AUTHORITATIVE before joining them. A join that produces a far better number than the authoritative ledger reports is not evidence, it is the join being wrong -- and it will read as success.

## Evidence

2026-09-14: fill_attribution joined order_intents to fill_corpus on ticket and reported FILLED 31 with a 100% fill rate. fill_corpus carries the authoritative status field and holds UNFILLED 34, REJECTED 10, UNRESOLVED 7, FILLED 1. A ticket in fill_corpus means the broker CREATED an order, not that it filled. The two cannot be row-joined at all: order_intents has no intent_id and the only shared field is ticket, which is 0 on every rejection.

## Tags

#execution #measurement

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
