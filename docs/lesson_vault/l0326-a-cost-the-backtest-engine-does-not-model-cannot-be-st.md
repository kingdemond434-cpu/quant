---
id: L0326
cost: capital
tags: ["gates"]
---

# L0326

A cost the backtest engine does not model cannot be stressed by a cost-stress gate. Check what the model CONTAINS before trusting a gate that multiplies it: stressing spread at 3x says nothing about swap if swap was never a field.

## Evidence

2026-09-14: mt5desk.engine.Costs carries spread_per_lot, commission_per_lot, contract_oz, quote_per_account and nothing else -- grep for 'swap' is empty. The gauntlet's stress_costs gate multiplies that model by 3 and every overnight_gap_decay certificate passed it while paying 0.011-0.061R per night in financing that was never counted. GBPMXN 0.246R and GBPNOK 0.202R round trip against a +0.135R expectancy.

## Tags

#gates

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
