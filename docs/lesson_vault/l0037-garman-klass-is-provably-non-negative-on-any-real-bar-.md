---
id: L0037
cost: blind
tags: ["data", "measurement"]
enforced_by: tests/test_volatility_signals.py::test_a_negative_garman_klass_flags_a_corrupt_bar
---

# L0037

Garman-Klass is provably non-negative on any real bar, so a negative value is proof the DATA is corrupt -- a free integrity check on every stored bar. Never clip it into silence.

## Evidence

open and close lie inside [low,high] so |ln(C/O)|<=ln(H/L), giving GK >= 0.1137*ln(H/L)^2; invalid_bars() in libs/research/volatility_signals.py

## Enforced by

`tests/test_volatility_signals.py::test_a_negative_garman_klass_flags_a_corrupt_bar`

## Tags

#data #measurement

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
