---
id: L0090
cost: blind
tags: ["feeds"]
---

# L0090

For any feed JOIN, verify the PUBLICATION CADENCE of both sides, not just liveness: a collector can run green daily and still deliver monthly.

## Evidence

dl_oi_ls_universe closes leg: '+0 closes x139' every in-month day; futclose ended 2026-07-31 while metrics stayed current; fixed 2026-08-11 with daily-zip tail fetch

## Tags

#feeds

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0080-libs-ops-input-provenance-inputs-read-json-records-a-s]]
- [[l0081-persist-accumulated-state-in-a-finally-never-only-at-t]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
