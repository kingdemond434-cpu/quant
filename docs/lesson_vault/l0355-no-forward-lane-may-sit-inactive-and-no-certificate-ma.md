---
id: L0355
cost: blind
tags: ["forward", "governance"]
enforced_by: tests/research/test_layers.py::test_every_scheduled_leg_has_a_layer
---

# L0355

No forward lane may sit inactive and no certificate may lack a running clock: the identity healer FREEZES every running clock whose identity was never frozen (with the forward_start the clock already carries), re-enrols every certificate the reconciler reports unreachable, and the reconciliation artifact is read by the closed-loop attestation as counts, never as key lengths. A reconciler that reports 'freezing is the engine's job' and retires nothing has measured a defect and left it standing.

## Evidence

forward_reconcile.json 2026-09-16: identity_unfrozen 46 (XAUUSD.london_am, GBPJPY.asia, CADJPY.asia.FAILED_BREAK -- legacy hunt16 keys enrolled before the registry froze identities), RETIRED_ORPHAN 302, unreachable_certified n=0 read as 8 by a checker that took the length of a dict; MT5-Hourly task path corrupted since 01:46 UTC so no hourly leg ran for 16 hours while every artifact still looked alive

## Enforced by

`tests/research/test_layers.py::test_every_scheduled_leg_has_a_layer`

## Tags

#forward #governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0038-from-spoken-sources-mechanisms-convert-at-0-13-and-num]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
