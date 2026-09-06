---
id: L0013
cost: wasted
tags: ["research", "priors"]
enforced_by: tests/validation/test_screen_admission.py::TestICIsNotPnL::test_ranking_is_driven_by_oos_sharpe_not_a_correlation_field
---

# L0013

Positive IC is not a profitable strategy. IC lives mid-distribution while the tradeable top and bottom buckets do not carry it -- require net-of-cost P&L before promoting anything.

## Evidence

reversal and leadlag both had positive Spearman IC and NEGATIVE gross Sharpe. institutional_knowledge.md meta-learnings

## Enforced by

`tests/validation/test_screen_admission.py::TestICIsNotPnL::test_ranking_is_driven_by_oos_sharpe_not_a_correlation_field`

## Tags

#research #priors

## Related

- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
- [[l0161-when-mining-any-foreign-venue-asset-class-or-instituti]]
