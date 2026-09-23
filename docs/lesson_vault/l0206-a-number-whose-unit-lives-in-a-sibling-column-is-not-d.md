---
id: L0206
cost: blind
tags: ["costs"]
---

# L0206

A number whose UNIT lives in a sibling column is not data until you read that column. Convert to money BEFORE ranking anything.

## Evidence

MT5 swap_mode: 138/248 Fusion symbols are mode 5 (INTEREST_CURRENT = annual %), 110 are mode 1 (POINTS). _swap_to_money converts only mode 1, via point*contract_size = currency_profit, never the EUR account ccy: 246/248 wrong, median 4.33x, max 20695x (USDIDR), 185.5x on JPY crosses. The 2 correct symbols are the USD majors a spot-check tries first -- perishability.py:145 predicted this in writing. I hit it myself: ranked USDTRY worst at -10264 before learning it was POINTS.

## Tags

#costs

## Related

- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
