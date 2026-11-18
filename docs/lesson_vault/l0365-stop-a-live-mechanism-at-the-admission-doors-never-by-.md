---
id: L0365
cost: capital
tags: ["capital", "live"]
enforced_by: desks/mt5/tests/test_live_policy.py::test_a_row_the_policy_refuses_cannot_survive_a_promoter_write
---

# L0365

Stop a live mechanism at the ADMISSION doors, never by retiring its rows: automatic promotion rewrites a matured clock's row the same hour, so row-deletion loses that race forever. The forex sleeves were retired twice (decay monitor, discovered-family ban) and traded again both times, costing -73.24 EUR in three days on the live Fusion account while XAUUSD made +24.94. The fix is a policy both the only writer (promoter.save_sleeves) and the trader (decision_core.load_sleeves) consult, failing closed when its file is unreadable.

## Evidence

desks/mt5/mt5desk/live_policy.py; docs/LAWS.md 5j; measured 2026-09-17 the live Fusion account: EURCHF -43.54 over 100 deals

## Enforced by

`desks/mt5/tests/test_live_policy.py::test_a_row_the_policy_refuses_cannot_survive_a_promoter_write`

## Tags

#capital #live

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
