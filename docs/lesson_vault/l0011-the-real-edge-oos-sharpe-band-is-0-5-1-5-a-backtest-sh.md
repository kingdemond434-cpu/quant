---
id: L0011
cost: wasted
tags: ["statistics", "priors"]
enforced_by: tests/validation/test_screen_admission.py::test_the_floor_sits_below_the_real_edge_band_so_noisy_measurement_is_not_fatal
---

# L0011

The real-edge OOS Sharpe band is 0.5-1.5. A backtest Sharpe above ~2 is a defect signal to investigate, not a discovery to celebrate.

## Evidence

measured over 131,441 backtests in the transcript study; encoded as REAL_EDGE_OOS_SHARPE_BAND in libs/validation/robustness_filters.py

## Enforced by

`tests/validation/test_screen_admission.py::test_the_floor_sits_below_the_real_edge_band_so_noisy_measurement_is_not_fatal`

## Tags

#statistics #priors

## Related

- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0019-measured-family-survival-volume-0-387-mean-reversion-0]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0027-a-constant-that-was-never-measured-is-a-guess-wearing-]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0038-from-spoken-sources-mechanisms-convert-at-0-13-and-num]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
