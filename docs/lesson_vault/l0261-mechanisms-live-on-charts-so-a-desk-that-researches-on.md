---
id: L0261
cost: blind
tags: ["timeframes", "breadth", "data", "edge-discovery"]
---

# L0261

Mechanisms live on charts, so a desk that researches one timeframe cannot discover anything faster or slower than it -- and produces no evidence of what it missed, because an untested mechanism leaves no trace. download_all_symbols keyed 'already downloaded' by SYMBOL from *_H1.parquet, so a symbol with an H1 file was considered finished and never got a second chart. The keying is fixed; nothing checked the RESULT, and a fixed downloader that never ran leaves the lake as it was. Measured: M30, H4 and D1 absent entirely; 28 of 32 hunted symbols H1-only.

## Evidence

lake = 101 H1, 4 M15, 1 M5, 1 M1; check_timeframe_coverage exits 1 [cost as recorded: a research ceiling nobody chose]

## Tags

#timeframes #breadth #data #edge-discovery

## Related

- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
