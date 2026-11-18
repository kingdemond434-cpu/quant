---
id: L0346
cost: capital
tags: ["allocation", "money-path"]
---

# L0346

JOIN THE ALLOCATOR'S BOOK TO THE REGISTRY BY DERIVED IDENTITY, NEVER BY RAW NAME, and assert the join is non-empty. The two sides spell a sleeve differently -- the book uses SYMBOL_family_selector (upper-cased), the registry uses symbol_family_selector_p_<hash> (lower-cased). A lookup of s['name'] in book therefore matched almost nothing, from_book was False everywhere, and every sleeve fell through promoted_lot's ramp to clamp_risk_frac's BASE_RISK_FRAC floor. The optimiser, the baseline contest, the proof certificate and the heat budget all resolved to one flat base fraction at the venue. A book that joins nothing sizes nothing, and it fails SILENTLY: every artifact looks correct and every sleeve is mis-sized.

## Evidence

2026-09-15: exact intersection of pf_allocation.json book x sleeves.json LIVE was 1 of 40, fallback book 0 of 40. GBPNOK at forward +1.77R and AUDUSD at -0.574R were sized identically; the book ran six deep on CHF. Deriving the key took the join to 6 of 38 live on BOTH paths, and the winners went from a flat 3% to 1.85-5.50% heat. Fixed in mt5desk/gateway.py::_book_key.

## Tags

#allocation #money-path

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0056-a-drawdown-rail-measures-a-ratio-so-an-accounting-chan]]
