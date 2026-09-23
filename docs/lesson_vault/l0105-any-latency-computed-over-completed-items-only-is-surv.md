---
id: L0105
cost: blind
---

# L0105

Any latency computed over COMPLETED items only is survivorship-biased, and the bias is largest exactly when the queue is worst. Use a censoring-aware estimator (Kaplan-Meier), publish the censored fraction beside it, and treat NOT-REACHED as a real answer rather than extrapolating past the last observation.

## Evidence

docs/research/recommendation_ledger.json 2026-08-12: 42.8pct censored, naive completed-only median 3.373d vs KM 5.269d, p75 NOT-REACHED, and 64 of the 83 open rows had already waited longer than the 3.37d the naive figure called typical. libs/research/repair_capacity.py

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
