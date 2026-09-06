---
id: L0047
cost: blind
tags: ["design", "statistics"]
---

# L0047

Before penalising a quantity, check it is not already in the number. Turnover, multiplicity and costs are each priced somewhere upstream -- correcting twice is the defect that made this gauntlet 4x too strict.

## Evidence

positions_to_returns charges 6bps/turn but validate() applies no cost adjustment, so net-vs-gross is a property of the CALLER and nothing recorded it; GROSS_TURNOVER_PENALTY is conditional on a declared cost_basis. libs/validation/screen_admission.py

## Tags

#design #statistics

## Related

- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0027-a-constant-that-was-never-measured-is-a-guess-wearing-]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0052-a-403-from-a-public-venue-endpoint-is-a-user-agent-bot]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0065-a-green-local-gate-proves-nothing-unless-the-installed]]
