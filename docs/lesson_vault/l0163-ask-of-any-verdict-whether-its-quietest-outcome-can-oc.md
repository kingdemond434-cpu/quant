---
id: L0163
cost: blind
tags: ["validation"]
enforced_by: tests/libs/test_order_sensitive_decay.py::TestDecayVerdictIsOrderSensitive::test_a_null_record_mostly_reads_STABLE_not_a_direction
---

# L0163

Ask of any verdict whether its QUIETEST outcome can occur at all, and test REFUSAL rather than symmetry. A statistic whose 'no signal' branch requires exact float equality of two continuous quantities can never take it, so it calls a direction on 100 percent of records -- and because the call is FAIR, every symmetry test it has passes. Symmetry and refusal are different properties and only one of them is the point; a docstring claiming 'must not manufacture X out of noise' beside a test asserting only balance is the signature. When you add the missing band, DERIVE it: if the statistic is a CDF, the probability integral transform makes each side exactly Uniform(0,1) under the null, so a closed form replaces a tuned constant.

## Evidence

libs/research/order_sensitive_decay.decay_verdict compared halves with a bare '>' so STABLE needed exact equality: measured 10,045 DECAYING / 9,955 STRENGTHENING / 0 STABLE over 20,000 pure-null records of 14 windows, while its null test (asserting 850<=n_decay<=1150) passed throughout. Band derived as t=1-sqrt(alpha)=0.776393 from the triangular difference of two U(0,1) halves; empirical P(|D|>t)=0.0484 vs 0.0500 target. Commit 94d870df, R0467.

## Enforced by

`tests/libs/test_order_sensitive_decay.py::TestDecayVerdictIsOrderSensitive::test_a_null_record_mostly_reads_STABLE_not_a_direction`

## Tags

#validation

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
