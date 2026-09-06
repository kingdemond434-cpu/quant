---
id: L0224
cost: slow
tags: ["governance"]
---

# L0224

To convert a source_backlog row you must change the GRADE TEXT, not just add a [§33:] tag. _classify() checks 'unverified'/'needs-monitoring' substrings BEFORE any terminal verb and fails open to 'verification', so a row tagged [§33: screened] on its heading line still reads as pending while the word UNVERIFIED survives anywhere in that heading.

## Evidence

libs/research/source_backlog.py:106 (substring check precedes the fail-open return at :110); _CARD_RE at :58 captures the grade to end-of-heading-line only. Cost 3 failed disposition attempts on watchlist card 72 before the grade itself was restated; backlog then went 1-pending -> 0.

## Tags

#governance

## Related

- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
