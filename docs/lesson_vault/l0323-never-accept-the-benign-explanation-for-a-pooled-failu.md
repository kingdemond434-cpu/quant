---
id: L0323
cost: capital
tags: ["execution"]
---

# L0323

Never accept the benign explanation for a pooled failure without splitting it. 'Unfilled' pools two opposite defects: price reached the level and no fill arrived (execution), versus price never got there (strategy price-selection). They have nothing in common and no shared fix.

## Evidence

2026-09-14: I twice called 34 unfilled orders 'the strategy declining to enter, the expected shape for a breakout book'. Split with the bars already on disk: 25 of 34 were TOUCHED -- price reached the entry and no fill arrived -- and only 9 were never reached. 74% were fills the desk should have had. The split cost one afternoon and the bars were already there.

## Tags

#execution

## Related

- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
- [[l0056-a-drawdown-rail-measures-a-ratio-so-an-accounting-chan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
