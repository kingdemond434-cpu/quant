---
id: L0254
cost: every admission decision made as if size did not matter
tags: ["capacity", "sizing", "small-capital", "unmeasured"]
---

# L0254

CAPACITY at a small account is a FLOOR problem, not the institutional ceiling one. A large fund asks where its own order moves the price; at EUR 742 on 0.01-lot minimums this desk has no measurable impact, and importing that machinery would be pure complexity rent. The binding constraint is the opposite: the venue's minimum lot forces MORE risk than policy below a computable equity (min_lot_risk_eur / q_target). Measured: a 0.5% gold target actually runs 4.44x policy at EUR 742, and the floor only stops binding above EUR 3,293. The ceiling stays UNMEASURED because matched_fills is 0 -- a ceiling from an unvalidated cost model would be believed and should not be.

## Evidence

realised_over_policy(742, 0.005, XAUUSD) = 4.44; floor_binding_equity = 3293.13

## Tags

#capacity #sizing #small-capital #unmeasured

## Related

- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0077-a-single-tokenized-commodity-chart-cannot-tell-a-real-]]
- [[l0078-a-fence-with-an-ordered-status-ladder-can-have-a-fabri]]
