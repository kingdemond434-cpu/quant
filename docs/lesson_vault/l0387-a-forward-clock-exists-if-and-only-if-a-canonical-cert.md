---
id: L0387
cost: blind
tags: ["governance", "forward", "clocks"]
enforced_by: desks/mt5/tests/test_clock_certificate.py::test_there_is_no_awaiting_judgement_state_left
---

# L0387

A forward clock exists if and only if a canonical certificate backs it. Never build a cure, power-cure or awaiting-judgement lane that lets an uncertified cell accrue forward evidence while it queues for the judge -- retire it, keep its cell at the front of the queue, and give it a NEW clock from zero if it certifies.

## Evidence

Principal 2026-09-23, superseding his own ruling of the same day: allow evidence only if they pass the 10 gates and are certificates, otherwise there is no point. Measured on the trading box vmi3571445 the pass this landed: 489 clocks, canon 28 certificates, BACKED 55; 94 clocks retired RETIRED_NO_CERTIFICATE and 1 RETIRED_GATE_FAIL, taking retired 339 to 433 and unbacked_live to 0. The reasoning that the earlier design got wrong: forward evidence on a cell that never certifies can never be cashed -- it cannot promote, size or pool -- so keeping it was a cost with no claim attached, paid in bar fetches, memory and engine passes. The stated price is that a cell certifying later restarts from zero; inheriting the old days would credit a pre-registration that did not exist when those bars printed. Enrolment of certified cells stays uncapped.

## Enforced by

`desks/mt5/tests/test_clock_certificate.py::test_there_is_no_awaiting_judgement_state_left`

## Tags

#governance #forward #clocks

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
