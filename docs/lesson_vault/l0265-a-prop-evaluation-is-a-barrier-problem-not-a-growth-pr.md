---
id: L0265
cost: would have been an evaluation fee on a coin flip
tags: ["prop-firm", "sizing", "barrier", "breadth", "e8"]
---

# L0265

A prop evaluation is a BARRIER problem, not a growth problem: you are permanently out at max drawdown, while hitting the target early only means passing sooner. So the growth-optimal size is far too large, and readiness is counted in INDEPENDENT MECHANISMS rather than certificates. Simulated at exp_R +0.20 on E8 One 8%/12%: 2 correlated sleeves at 0.5% pass 87% in 65d; 4 correlated pass 77% in 27d; 8 correlated pass 60% in 9d -- more of the same mechanism buys speed with leverage and pays in pass probability. 4 INDEPENDENT at the same 0.5% pass 92% in 36d, better on both axes. Plan and arithmetic: docs/PROP_FIRM_E8.md.

## Evidence

14 of 15 positive forward clocks were one mechanism (session_range_breakout) on 4 JPY crosses plus gold; USDJPY.asia#rr=2.5 showed +1.19R, implying a 62.6% breakout win rate from 8 trades

## Tags

#prop-firm #sizing #barrier #breadth #e8

## Related

- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
