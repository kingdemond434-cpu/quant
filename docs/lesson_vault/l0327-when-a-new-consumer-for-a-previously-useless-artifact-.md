---
id: L0327
cost: blind
tags: ["research", "allocation"]
enforced_by: desks/mt5/tests/test_gauntlet_yield_allocation.py::test_power_deficient_cells_count_toward_family_yield
---

# L0327

When a new consumer for a previously-useless artifact goes live, RE-DERIVE every yield, ranking and allocation whose numerator was defined while that artifact had no consumer. The definition was correct before and is wrong from that hour, and neither organ reports anything unusual.

## Evidence

2026-09-14: weak_signals leg landed and consumed power-deficient cells; the SAME hour external_gauntlet._family_yield still scored pca_residual 0.0031 (0 survivors of 230 ruled) and trimmed it to the floor, while that family held 131 of the desk's 560 power-deficient cells -- the richest supplier of the lane that had just opened. Crediting them moved it to 0.21472, 69.3x.

## Enforced by

`desks/mt5/tests/test_gauntlet_yield_allocation.py::test_power_deficient_cells_count_toward_family_yield`

## Tags

#research #allocation

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
