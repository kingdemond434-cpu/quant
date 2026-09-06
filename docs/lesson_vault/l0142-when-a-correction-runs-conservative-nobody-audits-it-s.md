---
id: L0142
cost: blind
tags: ["statistics"]
enforced_by: tests/research/test_panel_breadth.py::test_an_unmeasured_panel_can_never_be_powered
---

# L0142

When a correction runs CONSERVATIVE, nobody audits it -- so ask of any such quantity: what would its being WRONG look like? If the answer is a verdict nobody records, it is unaudited however often it runs. The screen's cross-sectional power divisor sat at two OPPOSITE unmeasured endpoints one change apart, and the surviving error's only symptom was SCREEN-UNDERPOWERED, which writes no graveyard entry, no clock and no alert.

## Evidence

libs/research/axis_screen.py:175 divided by full panel_width (K symbols = 1 obs/bar); pre-2026-08-11 it divided by nothing (K obs/bar). Measured 2026-08-13 on the 139-symbol futclose panel: product-term rho +0.0036 -> 92.76 bets, so the honest divisor is 1.50 not 139 (detection floor 9.6x too high). 380 of 711 verdicts on disk were SCREEN-UNDERPOWERED.

## Enforced by

`tests/research/test_panel_breadth.py::test_an_unmeasured_panel_can_never_be_powered`

## Tags

#statistics

## Related

- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0019-measured-family-survival-volume-0-387-mean-reversion-0]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0033-before-comparing-two-quantities-check-they-share-a-sca]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0043-the-crypto-cross-section-is-1-54-independent-bets-raw-]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
