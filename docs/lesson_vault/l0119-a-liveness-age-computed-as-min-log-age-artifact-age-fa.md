---
id: L0119
cost: blind
tags: ["monitoring"]
enforced_by: tests/ops/test_organ_stale_liveness.py::test_brain_liveness_artifacts_match_organ_catchup_exactly
---

# L0119

A liveness age computed as min(log_age, artifact_age) fails OPTIMISTIC: one SHARED artifact any other organ can touch makes a dead organ look younger than it is. Liveness artifacts must be exclusive to the organ or absent.

## Evidence

max_audit ORGAN_ARTIFACTS kept decision_ledger.json for brain-cycle after organ_catchup dropped it 2026-07-26; reported 13h against 17.9h of real death through 4 consecutive failures (2026-08-12)

## Enforced by

`tests/ops/test_organ_stale_liveness.py::test_brain_liveness_artifacts_match_organ_catchup_exactly`

## Tags

#monitoring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
