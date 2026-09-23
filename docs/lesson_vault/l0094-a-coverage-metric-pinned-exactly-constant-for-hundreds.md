---
id: L0094
cost: blind
tags: ["denominator"]
---

# L0094

A coverage metric pinned EXACTLY constant for hundreds of runs means the numerator has saturated its reachable universe -- audit the DENOMINATOR before adding capacity. A grid built as a cartesian product of marginals (symbols x days) counts cells that never existed; check filled == reachable arithmetic first (here 1776 on-disk cells x 7 mechs = 12,432 = cells_filled exactly).

## Evidence

data/moat_miner.log runs 37765-37969: 53.05% (12432/23436) unchanged 200+ runs, holes all phantom -- bybit/1000CATUSDT/20260717 in next_targets has zero files on disk (tape starts 20260801); fixed in commit 6a3f30f

## Tags

#denominator

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
