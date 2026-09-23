---
id: L0289
cost: blind
tags: ["money-path"]
enforced_by: desks/mt5/tests/test_release_identity.py::test_a_state_sync_that_commits_an_unlisted_evidence_file_is_still_the_same_release
---

# L0289

Fix the function the money path CALLS, and prove it with the caller's own test. Two classifiers can answer 'is this the sealed code' -- libs.ops.release.accepts and mt5desk.release_identity.verdict -- and the gateway reads only the second. A rule added to the first is a fix for nobody; grep the gateway for the symbol it imports before declaring an identity refusal fixed.

## Evidence

2026-09-08: STATE_PREFIXES landed in release.accepts at 15:55; the gateway calls release_identity.verdict, which still held every path outside an eleven-file allowlist to be code -- an adoption's 'Box state captured' commit (~190 evidence paths) would have refused new risk again the minute the box adopted. Found by a trace of the money path, not by the tests that passed.

## Enforced by

`desks/mt5/tests/test_release_identity.py::test_a_state_sync_that_commits_an_unlisted_evidence_file_is_still_the_same_release`

## Tags

#money-path

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
