---
id: L0374
cost: blind
tags: ["plumbing", "wiring"]
enforced_by: desks/mt5/tests/test_plumbing_watchdog.py::test_a_required_edge_whose_artifact_does_not_exist_is_a_defect
---

# L0374

A green producer is not a written artifact: check the LEDGER's own last write, not the exit code of the organ that feeds it. The recommendation ledger went 11.7 days without a write while the CEO docket that feeds it ran hourly and exited 0 every time.

## Evidence

scripts/check_recommendation_flow.py; measured 2026-09-22: 281.7 hours since the last recommendation row

## Enforced by

`desks/mt5/tests/test_plumbing_watchdog.py::test_a_required_edge_whose_artifact_does_not_exist_is_a_defect`

## Tags

#plumbing #wiring

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
