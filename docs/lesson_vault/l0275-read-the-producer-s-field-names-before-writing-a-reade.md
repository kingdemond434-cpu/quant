---
id: L0275
cost: blind
tags: ["plumbing"]
enforced_by: desks/mt5/tests/test_scalp_ledger_field_join.py::test_a_real_row_carries_none_of_the_old_spellings
---

# L0275

Read the producer's field names before writing a reader. A silent or-chain over the wrong keys returns None and reads downstream as no evidence, never as a bug.

## Evidence

2026-09-08: scalp ledgers carry opened_at/closed_at; two readers asked for exit_time/entry_time/time; 344 real forward trades on four gold clocks were refused as '0 forward day(s)', so no scalp sleeve was ever priced and three PROMOTION CANDIDATES sat at STANDBY 0.00% for weeks.

## Enforced by

`desks/mt5/tests/test_scalp_ledger_field_join.py::test_a_real_row_carries_none_of_the_old_spellings`

## Tags

#plumbing

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
