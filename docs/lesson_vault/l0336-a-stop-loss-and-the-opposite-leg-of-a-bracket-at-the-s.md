---
id: L0336
cost: capital
tags: ["execution", "gold"]
enforcement_retired: desks/mt5/research/stop_reverse_census.py -- names an organ, not a test (repaired 2026-09-29): no test enforces this property, so the lesson stays at full weight rather than claiming a graduation that does not resolve
---

# L0336

A stop-loss and the opposite leg of a bracket at the SAME price means one move pays twice: the stop closes the position and the pending order opens the reverse in the same second, at the worst available tick. Before blaming variance for a bad day, check whether one price level closed one position and opened another -- and check it by deal TYPE, not by direction, because closing a long and opening a short are both SELL deals.

## Evidence

2026-09-11 on the live Fusion account: one M1 bar ran 4341.34 -> 4288.33 -> 4296.81 (60.10 points in 60 seconds) with spread NORMAL throughout (median 6, max 10) and tick volume 368 against a 350-380 baseline -- so not a broker or cost event. The wick took a gold_asia long's stop at 4298.87 and opened a short at 4298.87 in the same second; price was fully recovered by 15:36 and higher by 15:40, stopping the short at 4340.68. Two losses of ~72 EUR from one six-minute round trip that ended where it began: -144.83 against a month that made +193.50. The gateway has no OCO, no cooldown and no opposite-leg cancellation.

## Tags

#execution #gold

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
