---
id: L0054
cost: wasted
tags: ["families"]
enforced_by: tests/research/test_mined_evidence_priority.py::test_every_miner_prompt_carries_the_mined_evidence_priority_block
---

# L0054

On CRYPTO specifically, rank mean-reversion families LAST for research effort. Three independent methods agree; none of them is strong alone, and the agreement is only about the ordering, not about trend being profitable.

## Evidence

desk permutation on 2,438 BTC bars: zscore_fade/shock_fade NEGATIVE ann Sharpe (-0.52), p~0.86; time_series_mom[40] +1.02, p=0.008. Algovibes 350k backtests: zero pure mean-reversion walk-forward survivors on BTC, trend only. IQCapital 10k traders: reversal last on pass rate (5%) and payout rate (1.8%). CAVEAT: prop-firm pass rates are confounded by selection and account rules; the three studies DISAGREE on what ranks first.

## Enforced by

`tests/research/test_mined_evidence_priority.py::test_every_miner_prompt_carries_the_mined_evidence_priority_block`

## Tags

#families

## Related

- [[l0013-positive-ic-is-not-a-profitable-strategy-ic-lives-mid-]]
- [[l0019-measured-family-survival-volume-0-387-mean-reversion-0]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0038-from-spoken-sources-mechanisms-convert-at-0-13-and-num]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
