---
id: L0307
cost: capital
tags: ["lookahead", "regime"]
---

# L0307

Viterbi labels know the future. hmm.predict() has a BACKWARD pass, so every historical label is assigned using observations after the day it describes. A smoothed label may DESCRIBE history; it may never reach a number that sizes a position. Use the forward filter's argmax for anything conditional.

## Evidence

2026-09-12: pf_allocator built its by_day regime map from eng.hmm_states and that map conditions the state growth curves that SET HEAT; asset_state and regime_coverage did the same. 27 of 1,200 days (2.2%) carried a label the desk could not have held, concentrated at transitions -- exactly where a state-conditional number does the most work. Found by reading the Aurum desk's regime_hmm.py, whose docstring names the trap.

## Tags

#lookahead #regime

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
