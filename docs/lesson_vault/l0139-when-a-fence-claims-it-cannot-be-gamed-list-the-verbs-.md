---
id: L0139
cost: blind
tags: ["governance"]
enforced_by: tests/governance/test_deferral_visibility.py::test_chronic_row_stays_owed_despite_a_future_due_date
---

# L0139

When a fence claims it cannot be gamed, list the verbs it exposes and ask which one moves the quantity the claim rests on. A deadline-based fence is defeated by whatever edits the deadline -- so record every move of a deadline, never just its current value.

## Evidence

scripts/recommendations.py:20 claimed 'scheduled' cannot become where rows go to die; measured over first-parent git history of docs/research/recommendation_ledger.json, 39 of 152 ever-scheduled rows (26%) had their due date moved and 38 were still scheduled -- fixed 6c64b608

## Enforced by

`tests/governance/test_deferral_visibility.py::test_chronic_row_stays_owed_despite_a_future_due_date`

## Tags

#governance

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
