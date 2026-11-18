---
id: L0349
cost: blind
tags: ["allocator", "covariance"]
---

# L0349

Never let a covariance that needs overlapping history be the ONLY covariance: a new sleeve has no common days with anything for its first month, so every pair reads 0.0 (independent) exactly when crowding is most likely. Fit factor loadings on the sleeve's OWN days against a factor history that exists for every day (currency legs, metals, dVIX, d10y) and blend the realised |corr| with the factor-implied one by common-day count.

## Evidence

gateway.log 2026-09-16: 'k_eff UNMEASURED: no sleeve pair has 20 overlapping trading days yet (16 sleeves)' on every pass; robust_elog._corr_abs returned 0.0 for every pair without common history

## Tags

#allocator #covariance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
