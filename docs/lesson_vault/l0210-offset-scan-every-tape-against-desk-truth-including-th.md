---
id: L0210
cost: blind
tags: ["data-provenance"]
---

# L0210

Offset-scan every tape against desk truth -- including the desk's own. The MT5 universe parquets are stamped +00:00 but carry broker EET: +3h summer, +2h winter, so no constant shift repairs it, and every join to a real-UTC series (macro release times) is silently 2-3h off. Cheapest detector needs no external data: no FX/metals bar may fall on a Friday at/after 22:00 UTC.

## Evidence

XAUUSD offset scan locked +180min (Aug 2026) and +120min (Jan 2026), median|diff| 0.11-0.17 vs 0.7-1.9 adjacent; Friday close 23:56 + Monday open 01:00; max-Friday-hour 23 in BOTH Jan and Jul 2018-2026; 191/197 _H1.parquet hold Friday bars >=22:00 UTC

## Tags

#data-provenance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
