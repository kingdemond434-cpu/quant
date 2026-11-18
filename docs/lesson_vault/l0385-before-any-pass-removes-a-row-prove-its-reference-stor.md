---
id: L0385
cost: capital
tags: ["governance", "evidence"]
enforced_by: tests/ops/test_reference_freshness.py::test_empty_reference_stands_the_pass_down_and_removes_nothing
---

# L0385

Before any pass REMOVES a row, prove its reference store is live: a reference that says nothing is not a reference that says no. Call libs/ops/reference_freshness.require_live_reference (or require_live_rows for a reference computed this pass) and stand down with the recorded reason when it reads EMPTY, STALE beyond its lease, or UNREADABLE -- those are verdicts about the measurement (L1.28a), never statements about the world.

## Evidence

2026-09-23: certificate_truth --apply judged every derived store against UNIVERSAL_SURVIVORS.canon.json holding n=0 and 46.7h stale, and retired 837 rows the empty canon 'did not back' -- three hours after the gauntlet sweep had written 'UNIVERSAL_SURVIVORS.json: 7 total (+7)', 114 ledger claims and 1,240 cells cleared for forward evidence. The arithmetic was correct; the reference was not in a position to answer. Inventory: desks/mt5/reports/DESTRUCTIVE_PATHS.json (35 destructive paths, 5 guarded, 26 positive-evidence-only, 2 unguarded).

## Enforced by

`tests/ops/test_reference_freshness.py::test_empty_reference_stands_the_pass_down_and_removes_nothing`

## Tags

#governance #evidence

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0027-a-constant-that-was-never-measured-is-a-guess-wearing-]]
