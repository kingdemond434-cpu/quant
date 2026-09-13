---
id: L0291
cost: blind
tags: ["money-path"]
enforced_by: desks/mt5/tests/test_placement_health.py::test_a_two_week_old_streak_is_not_evidence_about_today
---

# L0291

A 'consecutive failures' counter without a clock is a landmine on any desk that can go quiet: 'consecutive' must mean consecutive in TIME as well as in count, or a two-week-old streak pauses the desk on its first modern attempt. Likewise a measurement with exactly one scheduler is a measurement that stops the day that scheduler stalls -- put the organ that consumes it on a clock the box owns as a fallback.

## Evidence

2026-09-08: consecutive_total_rejections=2 from 2026-08-25's 10027 was still standing (no pass had run since identity refused every order 09-05 -> 09-08), one rejection from GATEWAY_PAUSED. The admission scan that lets a PROMOTION_CANDIDATE leave STANDBY ran only in the persistent MT5-ResearchSupervisor's heavy pass. Both fixed 1a019c62: a 24h streak window; MT5-Hourly runs heavy when the last measured scan is missing or >2h old.

## Enforced by

`desks/mt5/tests/test_placement_health.py::test_a_two_week_old_streak_is_not_evidence_about_today`

## Tags

#money-path

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0054-on-crypto-specifically-rank-mean-reversion-families-la]]
