---
id: L0290
cost: capital
tags: ["money-path"]
enforced_by: desks/mt5/tests/test_gateway_adapter.py::test_the_end_of_day_close_leaves_the_scalp_lane_s_positions_to_their_own_exit
---

# L0290

A force-close keyed by SYMBOL closes every lane on that symbol. When two lanes trade the same instrument, every backstop must be scoped by the lane's own tag (order comment), or one lane's end-of-day rule executes the other lane's positions at the worst moment -- and live stops matching the behaviour the forward clock certified.

## Evidence

2026-09-08: CLOSE_HOUR (19:30 UTC, the gold windows' day end) closed every XAUUSD position; a basket an 'all'-session M15 scalp sleeve opened at 19:31 was flat at 19:32, spread paid for nothing, while its certifying clock held to the time exit. Scoped by DW<name> tag; Friday's weekend close stays every lane's.

## Enforced by

`desks/mt5/tests/test_gateway_adapter.py::test_the_end_of_day_close_leaves_the_scalp_lane_s_positions_to_their_own_exit`

## Tags

#money-path

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
