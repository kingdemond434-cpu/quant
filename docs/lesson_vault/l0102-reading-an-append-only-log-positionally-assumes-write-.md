---
id: L0102
cost: blind
tags: ["data"]
---

# L0102

Reading an append-only log POSITIONALLY assumes write order equals event order. Resolve by the event key (vintage, timestamp, sequence) with file position only as tie-break -- backfill is normal, and the failure inverts the sign of the measurement rather than merely adding noise.

## Evidence

libs/research/vintage.py: as_of/latest_known took the last matching row and revisions() the first, correct only while the file is chronological -- true of the live collector, false of the module's whole premise (Wayback CDX backfill, 23+ RFB publication dates). On its own headline case (RFB March 2023, 15828 -> 22308) latest_known returned the SUPERSEDED 15828 as current belief and revisions() reported the +40.9pct move as -29.0pct. Fixed in 7c6e3b2; 4 of 5 new tests fail against the previous reader.

## Tags

#data

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0048-rank-when-the-source-is-noisy-z-score-when-it-is-expen]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
