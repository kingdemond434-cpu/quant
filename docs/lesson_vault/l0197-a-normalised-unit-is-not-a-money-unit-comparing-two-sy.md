---
id: L0197
cost: blind
---

# L0197

A normalised unit is not a money unit. Comparing two symbols in pips, points, ticks or percent compares relative price units and silently answers a different question than cost -- convert both legs to money per lot before publishing a ratio.

## Evidence

prospector 2026-08-28: the 08-27 headline 'gold slips 8.2x EURUSD' was pips-vs-pips on the MQL5 slippage panel. MQL5 normalises pip=10 points (USDJPY 3-digit 1.50 vs EURUSD 5-digit 0.93; raw points would give ~100x). In money per lot gold is 25.50 vs EURUSD 9.30 = 2.74x. Same family as L1.67, where MT5 priced every instrument's stop in gold's units. R0680.

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
