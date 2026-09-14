---
id: L0321
cost: capital
tags: ["execution"]
---

# L0321

A broker reporting stops_level 0 is saying it has no minimum DISTANCE, not that any price is legal. Never gate an order-legality check on a nonzero level: the SIDE requirement is unconditional, and a buy_stop below the ask is not a stop order at all.

## Evidence

2026-09-14: gateway guarded entry_is_legal on '_lvl > 0' and Fusion reports trade_stops_level 0 on every symbol, so the function whose docstring reads 'THE CAUSE OF EVERY 10015 THIS DESK HAS SEEN' was never called on the only venue the desk trades. Every 10015 in the intent ledger was a buy_stop below the ask: 0.28, 0.24 and 13.78 below. Three of the desk's eight lifetime rejections.

## Tags

#execution

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
