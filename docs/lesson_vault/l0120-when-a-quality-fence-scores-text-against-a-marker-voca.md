---
id: L0120
cost: blind
tags: ["governance"]
enforced_by: tests/ops/test_dig_depth_markers.py::test_archive_verification_depth_is_depth
---

# L0120

When a quality fence scores text against a marker vocabulary, check WHICH MODALITY the vocabulary encodes before believing a low score. A lexicon built from one kind of work rejects ~100pct of every other kind structurally, however deep that work goes. Widen to the missing modality's VERIFICATION ACTS and hold the threshold constant -- never lower the threshold. And do not claim the vocabulary separates acts from intentions: a bag-of-words fence cannot, so pin that residual as a characterisation test instead of asserting it away.

## Evidence

max_audit.check_dig_depth 2026-08-12: dataaxis_20260812T1530 scored 1/2 and was called breadth-theater, having verified a published sha256 sidecar, run archive-vs-live to 0 mismatches over 31 bars x 7 fields, and found the S3 lister truncates at 1000 keys silently (3.7y understatement). All 20 markers were community-mining or code-replication words. Adding 8 verification-act markers flipped exactly 1 of 9 substantial digs. The act-vs-intent test FAILED on first run at assert 2 < 2 -- two PROMISED acts score as depth -- and became test_the_fence_cannot_tell_a_performed_act_from_a_promised_one.

## Enforced by

`tests/ops/test_dig_depth_markers.py::test_archive_verification_depth_is_depth`

## Tags

#governance

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
