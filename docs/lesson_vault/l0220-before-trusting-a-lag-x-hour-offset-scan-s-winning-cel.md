---
id: L0220
cost: blind
tags: ["free-data"]
---

# L0220

Before trusting a lag x hour offset scan's winning cell, compute intraday-range / level-bias. The scan identifies a published fixing's clock only when that ratio is >> 1: EURHUF 41.5bp/3.3bp = 12.6 gives a sharp minimum; USDTRY 10.4bp/7.7bp = 1.3 gives a FLAT surface (0.68bp across 15 hours) where rank-1 is a coin flip. Near 1, record the clock UNMEASURED.

## Evidence

docs/research/improvement_inbox.md M6; docs/research/data_axis_watchlist.md run (s) ITEM 1c; commit 0eec1aa3 2026-08-28

## Tags

#free-data

## Related

- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
