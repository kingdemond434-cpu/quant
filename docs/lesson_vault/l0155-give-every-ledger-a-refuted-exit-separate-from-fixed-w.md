---
id: L0155
cost: blind
tags: ["governance"]
enforced_by: tests/scripts/test_findings_supersede.py::TestSupersessionIsNotAFix::test_the_scorecard_does_not_credit_a_superseded_finding
---

# L0155

Give every ledger a REFUTED exit, separate from FIXED. Without one, a finding a later pass proves wrong has only two moves and both are bad: rot forever demanding work nobody should do, or be marked fixed -- a false claim that also credits the author with a hit it never earned, corrupting the very scorecard used to judge who to keep.

## Evidence

2026-08-13: F0004 (superseded by F0020, 'whose mechanism and number are WRONG') and F0007 (F0008 says 'which was WRONG and is superseded' in its own first clause) had both been accepted-and-unfixed past the 14d bar with no legal way to close them. track_findings had raised->fixed->verified only.

## Enforced by

`tests/scripts/test_findings_supersede.py::TestSupersessionIsNotAFix::test_the_scorecard_does_not_credit_a_superseded_finding`

## Tags

#governance

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
