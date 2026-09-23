---
id: L0126
cost: blind
tags: ["testing"]
enforced_by: tests/scripts/test_coverage_stall.py::test_A_REAL_RAISE_MOVES_THE_STAMP_AND_THE_FLOOR
---

# L0126

When a new guard trips an existing test, check the FIXTURE width before weakening the guard: a synthetic report narrower than any real one cannot exercise the branch you just added, and the cheap read is that your guard is wrong.

## Evidence

L1.60 build 2026-08-12: test_coverage_stall._report() synthesised 1 of the 5 MONEY_PATH modules -- a shape no real pytest --cov run can produce -- so the new absent-module refusal fired on all 5 tests. The guard was correct; the fixture was the defect. Third recurrence of the widest-real-schema rule (libs/features/validation.py, then the mode-stamping fixtures).

## Enforced by

`tests/scripts/test_coverage_stall.py::test_A_REAL_RAISE_MOVES_THE_STAMP_AND_THE_FLOOR`

## Tags

#testing

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
