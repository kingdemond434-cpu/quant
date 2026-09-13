---
id: L0305
cost: capital
tags: ["allocator", "growth"]
---

# L0305

A fallback that is OUT OF BAND makes a failure permanent. If the recovery path produces a state the guard rejects, the system can never climb back and every later pass repeats the failure. Check that every fallback lands INSIDE the band its own guard enforces.

## Evidence

2026-09-12: pf_allocator's current_book() fell back to Q_OPT x roster size = 58.43% heat, outside the mandated [20%,30%] band, so bind_verdict declined to hold it and published the EMPTY solve again. Once the book emptied it could never come back under its own power; the gateway logged 'sizing: no allocator book' every pass while the allocator logged 'the previous book stands'.

## Tags

#allocator #growth

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
