---
id: L0218
cost: blind
tags: ["mt5-data"]
---

# L0218

A COUNT IS NOT A FREQUENCY: check bars-per-day before computing any intraday statistic from desks/mt5/data/universe/*_H1.parquet. They are a D1/H1 splice -- an hour-00 bar on ~every day of the span plus true H1 on only ~1730 days. EURPLN: 56.7% of 4004 days hold ONE bar whose high-low range is 47.2bp vs 7.7bp for a genuine hour-0 bar. D1 2012->2025-01 and H1 2019-10->2026-06 OVERLAP. Row/day-count coverage checks read these as fully-covered H1; a study filtering hour==0 reads daily bars.

## Evidence

docs/research/improvement_inbox.md M5; commit f0bb890e 2026-08-28

## Tags

#mt5-data

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
