---
id: L0121
cost: wasted
tags: ["merge"]
enforced_by: tests/scripts/test_scheduler_manifest.py::TestImportsResolve::test_a_present_script_with_a_deleted_callee_is_BROKEN
---

# L0121

Before accepting that a reachability scan missed a caller, check whether the caller EXISTED in the tree the scan ran against. On a forked repo the answer is often no: each lineage was individually correct and only their MERGE is wrong, so no scan on either side could have caught it. Verify with 'git merge-base --is-ancestor <caller-add-sha> <scan-sha>' and a worktree at the scan's parent, then fence the union at the schedule boundary rather than 'fixing' the scan.

## Evidence

R0359 claimed dormancy._external_importers was blind to scripts/. It already grepped scripts/ AT 3be2e3e, and scripts/run_geometric_review.py (added fee1214a 07-28) is NOT an ancestor of 3be2e3e -- absent from that tree entirely. Real cause: the 08-04 merge brought the caller from master while the callees stayed deleted. Fixed by check_scheduler_manifest (e); positive control at b86cf5c^ fires exactly twice.

## Enforced by

`tests/scripts/test_scheduler_manifest.py::TestImportsResolve::test_a_present_script_with_a_deleted_callee_is_BROKEN`

## Tags

#merge

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
