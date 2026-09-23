---
id: L0087
cost: blind
tags: ["validation"]
---

# L0087

When a fence watches a COUNT, check which way that count moves under the failure you actually fear. A degraded-mode fallback often makes a coverage number look BETTER, so a one-sided check silently inverts and reports the regression as progress.

## Evidence

R0270: plan_strata's min-length fallback emits ONE stratum holding EVERY candidate, so n_untested drops to 0 and n_tested rises to n_candidates while observation-retention collapses from 85.8% to 17%. The row asked to fire when n_untested RISES. tests/research/test_campaign_retention.py::test_min_length_fallback_is_not_read_as_inclusive

## Tags

#validation

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0075-a-function-that-takes-a-root-path-argument-must-honour]]
