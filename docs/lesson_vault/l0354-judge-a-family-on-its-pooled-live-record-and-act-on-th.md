---
id: L0354
cost: capital
tags: ["money-path", "governance"]
enforced_by: desks/mt5/tests/test_decay_pooled_fade.py::test_a_pool_past_the_retirement_bar_retires_every_live_sleeve_and_queues_their_close
---

# L0354

Judge a family on its pooled live record and act on the same bar a sleeve retires on: t <= -2.5 at n >= 20 across the pool retires every live sleeve of it, its positions are closed the same pass, and a family the principal bans is written to data/banned_families.json so the search leg, the compiler, the gauntlet, the promoter and the E8 book all refuse it from one file. Twenty-four sleeves with 3-8 trades each cannot each reach a verdict while the family they share is losing at t=-5.

## Evidence

live_ledger 2026-09-16: discovered forex family n=85, mean -0.24R, pooled t=-5.19 across 24 sleeves (gold windows n=21 +179.76 EUR, t=+1.4); the decay monitor's per-sleeve rule needed n>=20 per sleeve and none had it; retired 16:57 UTC, 6 open positions closed 16:59 UTC, account flat at 550.28

## Enforced by

`desks/mt5/tests/test_decay_pooled_fade.py::test_a_pool_past_the_retirement_bar_retires_every_live_sleeve_and_queues_their_close`

## Tags

#money-path #governance

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
