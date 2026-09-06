---
id: L0074
cost: blind
tags: ["alarms"]
---

# L0074

An alarm must name the cause its DATA supports, never the one the SHAPE suggests. Before an alarm asserts a diagnosis, check the diagnosis is even POSSIBLE in the current state -- a remedy that cannot be performed closes the search instead of opening it.

## Evidence

2026-08-05: carry_bleed_report fired BLEED(inverted) for 4 days ordering 'reconcile spot vs perp qty' against a book holding ZERO open legs (web/cashcarry_live.json n_carries=0). No legs existed to reconcile; the real cause was an inception re-base leak of $4,807.75 that the same file already published, unnamed, in leak_attribution.residual.

## Tags

#alarms

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
