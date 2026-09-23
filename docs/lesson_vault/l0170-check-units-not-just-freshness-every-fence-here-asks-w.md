---
id: L0170
cost: capital
tags: ["units"]
enforced_by: desks/mt5/tests/test_risk_units.py::test_non_gold_sleeves_are_sized_in_their_own_currency
---

# L0170

Check UNITS, not just freshness. Every fence here asks whether a number was fresh, present, agreed-upon or produced by a gate that ran -- none asks whether it is in the units it claims, and a units error passes all of them while opening a real position. When one constant prices many instruments, derive the per-instrument figure from the venue and make the unpriceable case RAISE.

## Evidence

gateway.auto_lot priced every sleeve as dist*CONTRACT_OZ*FX_EUR=92.00; venue tick economics say 0.86 (BTCUSD) to 86,414 (EURUSD) EUR per price unit per lot. A promoted CADJPY sleeve sized 0.46 lot, logged 1.26% risk and ran 7.41%. L1.67 / scripts/check_risk_units.py

## Enforced by

`desks/mt5/tests/test_risk_units.py::test_non_gold_sleeves_are_sized_in_their_own_currency`

## Tags

#units

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
