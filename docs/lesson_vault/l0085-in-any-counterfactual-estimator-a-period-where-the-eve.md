---
id: L0085
cost: blind
tags: ["estimation"]
---

# L0085

In any counterfactual estimator, a period where the event did NOT happen is an OBSERVATION, not a missing row. Skipping the empty ones conditions every bucket on the outcome, and the bias points the way that makes the effect look real.

## Evidence

R0267 first live run: passive-fill decay came back with a POSITIVE slope (fill probability RISING with distance from mid) because levels with zero through-volume were skipped, so deep buckets were measured only on the rare windows price walked down to them. Counting untouched levels as zeros -- 598,489 of 617,409 observations, 96.9% -- flipped it to lam=4.88bps at R2=0.918. The planted-coefficient positive control passed 12/12 BOTH times: a positive control proves the estimator, never the study.

## Tags

#estimation

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
