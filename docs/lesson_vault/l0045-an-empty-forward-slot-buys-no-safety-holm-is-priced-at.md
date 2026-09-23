---
id: L0045
cost: wasted
tags: ["law", "research"]
enforced_by: tests/validation/test_screen_admission.py::test_admissions_never_exceed_idle_slots
---

# L0045

An empty forward slot buys no safety. Holm is priced at the concurrent slot CAP, so the multiplicity of all 12 tests is paid whether or not they run -- idle slots forfeit experiments already funded.

## Evidence

12 slots, data/forward_slots.json never existed, 129 candidates -> 0 survivors; gauntlet power 0.0-2.5% at the real-edge band with 0/4800 false positives. libs/validation/screen_admission.py

## Enforced by

`tests/validation/test_screen_admission.py::test_admissions_never_exceed_idle_slots`

## Tags

#law #research

## Related

- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0026-optimise-the-objective-you-actually-want-maximising-pe]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
