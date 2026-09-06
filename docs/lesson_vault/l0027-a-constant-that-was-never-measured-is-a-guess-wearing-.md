---
id: L0027
cost: hygiene
tags: ["design"]
enforced_by: tests/validation/test_campaign_window.py::test_the_stratum_cap_sits_above_the_measured_optimum
---

# L0027

A constant that was never measured is a guess wearing a number. Sweep it, record the sweep, and set the cap above the measured optimum.

## Evidence

MAX_STRATA was guessed at 8; the measured optimum was 26 and sat pinned at the cap. Set to 32 with the sweep recorded. libs/validation/campaign_window.py

## Enforced by

`tests/validation/test_campaign_window.py::test_the_stratum_cap_sits_above_the_measured_optimum`

## Tags

#design

## Related

- [[l0011-the-real-edge-oos-sharpe-band-is-0-5-1-5-a-backtest-sh]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0161-when-mining-any-foreign-venue-asset-class-or-instituti]]
- [[l0163-ask-of-any-verdict-whether-its-quietest-outcome-can-oc]]
- [[l0186-when-a-finding-is-measured-on-a-few-symbols-census-the]]
