---
id: L0341
cost: blind
tags: ["execution", "data"]
enforcement_retired: desks/mt5/research/unfilled_fork.py -- names an organ, not a test (repaired 2026-09-29): no test enforces this property, so the lesson stays at full weight rather than claiming a graduation that does not resolve
---

# L0341

READ YOUR BROKER'S REGULATORY DISCLOSURES BEFORE INFERRING EXECUTION SEMANTICS FROM FILL RECORDS. An ASIC/FCA/CySEC-regulated broker is legally required to publish how it fills you, free and in English. Fusion's PDS states it deals AS PRINCIPAL, MAKES A MARKET, and has 'absolute discretion whether to accept a Stop-loss Order', which may 'not be executed at all'; its Hedging Counterparty Policy states not all client flow is hedged back-to-back. So the counterparty is the HOUSE, and 'price touched, no fill' does not reduce to queue position and latency the way it would on an exchange. Never describe a dealer venue in an exchange's vocabulary.

## Evidence

2026-09-15: unfilled_fork.py attributed every TOUCHED order to 'queue position, latency, broker stop-distance, or an expiry that fired before the trigger' -- an exchange's causes -- across 34 unfilled of 52 orders. The broker's own PDS (35 pages) and Hedging Counterparty Policy were public the whole time and name a fourth cause the desk cannot engineer away. Both fetched and read in under a minute from the box.

## Tags

#execution #data

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
