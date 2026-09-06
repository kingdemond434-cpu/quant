---
id: L0122
cost: blind
tags: ["calibration"]
enforcement_retired: tests/scripts/test_promote_moat_survivors.py::test_the_forecast_is_a_persistence_rate_NOT_the_p_value -- deleted with the retired crypto desk (MT5 universe mandate 2026-08-18); the property is no longer enforced by anything, so this lesson is back at full weight
---

# L0122

Before logging any number into the L1.29 calibration store, check it is a PROBABILITY OF THE EVENT and not a p-value. A tail probability under the null points the OPPOSITE way to a success probability (smaller = stronger), so calibrating against it grades the desk on a meaningless curve while every dashboard reads as instrumented. Also Laplace-smooth ((k+1)/(n+2)): a raw k/n logs p=1.0 for every unbroken record, which is the exact overconfidence the law exists to catch.

## Evidence

R0363 proposed logging promote_moat_survivors' p_persistence = binom_tail(k,n,p_base) because it 'already varies'. binom_tail returns P(X>=k) under the null. Implemented forecast_p=(k+1)/(n+2) instead in 6e88571f, with the resolver in the same commit.

## Tags

#calibration

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
