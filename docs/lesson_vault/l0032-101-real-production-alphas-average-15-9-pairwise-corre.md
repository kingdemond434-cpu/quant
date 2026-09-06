---
id: L0032
cost: wasted
tags: ["research", "priors"]
enforced_by: tests/test_cohort_independence.py::test_width_buys_almost_nothing_at_the_benchmark_correlation
---

# L0032

101 real production alphas average 15.9% pairwise correlation, which is only 6.0 independent bets. Judge a cohort by its correlation, never by its count -- at that correlation 101 to 420 candidates buys 0.3 more bets.

## Evidence

published 101-alpha study via the 2026-08-01 transcript batch; encoded as BENCHMARK_MEAN_CORR in libs/research/cohort_independence.py and locked by test

## Enforced by

`tests/test_cohort_independence.py::test_width_buys_almost_nothing_at_the_benchmark_correlation`

## Tags

#research #priors

## Related

- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0038-from-spoken-sources-mechanisms-convert-at-0-13-and-num]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
