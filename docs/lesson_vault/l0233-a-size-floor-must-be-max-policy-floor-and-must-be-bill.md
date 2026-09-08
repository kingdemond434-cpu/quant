---
id: L0233
cost: near-miss
tags: ["sizing", "risk"]
---

# L0233

A size FLOOR must be max(policy, floor) and must be billed to the heat ledger at the floored size. A bare assignment is a size cut on every account the policy had already lifted above it, and an unbilled floor runs the book at risk the budget never reserved.

## Evidence

Principal asked for 0.02 lots per gold leg, then immediately: 'dont reduce their risk or size from before'. `lot = 0.02` satisfies the first sentence and violates the second wherever auto_lot already returns more. Separately, gateway's pre-cap loop set q_charge only for auto_ramp and allocator-book sleeves, so a gold row fell through to cap_by_heat's own realised_q(equity, None, XAUUSD) -- the POLICY lot. At EUR 1683.89 policy sizing is 0.01 and the floor sends 0.02, so the cap would have reserved half the risk the book was about to run, in the one direction a heat budget exists to prevent.

## Tags

#sizing #risk

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0023-never-accept-done-for-a-human-step-verify-with-the-act]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
