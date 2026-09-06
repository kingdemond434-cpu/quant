---
id: L0104
cost: blind
---

# L0104

A rate measured once is a rate that will be wrong later. When a runway, fill rate or burn rate schedules an action, record it as a TREND with a floor -- a point estimate in a report is correct the day it is written and silently stale afterwards, and nobody re-derives it because the number is already there.

## Evidence

R0331 quoted 0.673 GB/day and 25.1 days to the 80pct recorder pause; the moat fill rate stepped up 53pct to 1.03 GB/day on ~2026-08-05 and the true runway on 2026-08-12 was 3.0 days -- quoted 11 days after it stopped being true. Confirmed two ways: mtime histogram over 39,098 moat files, and the miner's own growth_bytes_per_day 1.07. Fixed by disk_headroom_ratio in scripts/check_ratchets.py.

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
