---
id: L0308
cost: blind
tags: ["governance", "staleness"]
---

# L0308

Never filter a census with '== <one enum member>' on a field the desk is designed to extend. Test MEMBERSHIP against a named constant and PRINT the unrecognised values -- an equality filter under-counts, which reads as a shortfall rather than an error, so it survives review.

## Evidence

2026-09-13 shadow_cycle.py represented_legacy matched gate_admission=='ORIGINAL_UNIVERSAL_10_PASS' only; the cure lane stamps VALIDITY_PASS_POWER_DEFICIENT, so 230 rows / 218 ACTIVE on disk censused as 95 and published missing_sleeves:['86 certified sleeve(s)'] hourly with a non-zero exit. Same shape as live:0 (one JSON shape handled) and min_volume/volume_min.

## Tags

#governance #staleness

## Related

- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
