---
id: L0036
cost: blind
tags: ["measurement", "data"]
enforced_by: tests/test_volatility_signals.py::test_a_frozen_series_produces_no_position_rather_than_a_fictional_one
---

# L0036

A '> 0' guard does not survive floating-point dust. Use a meaningful floor, or a frozen series divides dust by dust and manufactures an enormous edge on exactly the symbols nobody questions.

## Evidence

prediction_premium returned 1.4e31 on a constant return series because numpy variance gave 5e-38 rather than 0.0; pegged pairs, halted markets and frozen feeds all hit this path. _VAR_FLOOR in libs/research/volatility_signals.py

## Enforced by

`tests/test_volatility_signals.py::test_a_frozen_series_produces_no_position_rather_than_a_fictional_one`

## Tags

#measurement #data

## Related

- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0044-removing-a-common-factor-manufactures-negative-residua]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0076-counting-dated-rows-is-not-counting-observations-and-t]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
- [[l0102-reading-an-append-only-log-positionally-assumes-write-]]
