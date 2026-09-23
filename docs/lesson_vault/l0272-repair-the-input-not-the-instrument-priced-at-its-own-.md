---
id: L0272
cost: would have shifted 28 posterior means on a producer bug
tags: ["execution", "cost", "provenance", "refusal"]
---

# L0272

Repair the INPUT, not the instrument. Priced at its own fill hour against a broken registry, the desk's execution error read 11-16x on 28 sleeves -- including a MAJOR cross, which contradicted cost_surface's own finding that the majors read clean. Gating on provenance dropped it to zero priced sleeves, which was the honest answer; recomputing `median_spread_pts` from the H1 bars (the value was on disk the whole time) then produced the real number: 1.00-1.15x on the live book, and three CHF crosses OVER-charged. An instrument tuned until its output looks plausible measures the tuning. An instrument that refuses until its input is sound measures the market.

## Evidence

EURUSD registry 0.0 vs its own bars 12.0; after repair GBPJPY_asia 1.15x, USDJPY 1.00x, AUDCHF 0.53x

## Tags

#execution #cost #provenance #refusal

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
