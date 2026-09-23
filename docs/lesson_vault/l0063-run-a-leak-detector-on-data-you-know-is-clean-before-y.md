---
id: L0063
cost: blind
tags: ["validation"]
enforced_by: tests/research/test_shift_leak_detector.py::test_clean_premium_is_not_flagged
---

# L0063

Run a leak detector on data you KNOW is clean before you believe it. A detector that fires on clean data does not get ignored -- it gets 'fixed' in the direction of the damage, by someone doing exactly what the evidence appears to say. Any statistic that rebuilds a ratio signal from mixed-date legs is measuring its own arithmetic.

## Evidence

revalidate_clocks.shift_ic shifted only the numerator leg, so for a premium whose DENOMINATOR is the target's own price it reconstructed gb[i+1]/gb[i] -- the forward return. It scored +0.931 on an i.i.d.-noise premium with zero predictive content. That false positive produced the 2026-07-29 'kimchi is a ~73% timestamp artifact' verdict, which justified a +1d Upbit keying change that 24h-mispaired 3 days of live collection and put a refuted mechanism in the graveyard as fact. Controls now in tests/research/test_shift_leak_detector.py.

## Enforced by

`tests/research/test_shift_leak_detector.py::test_clean_premium_is_not_flagged`

## Tags

#validation

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
