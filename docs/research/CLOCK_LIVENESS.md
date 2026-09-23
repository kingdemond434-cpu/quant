# CLOCK LIVENESS -- every forward clock advancing, or repaired in the same pass

> DERIVED. Regenerate with `python desks/mt5/research/clock_liveness.py --once`;
> never edit this file. Source: `desks/mt5/reports/CLOCK_LIVENESS.json`.

Measured 2026-09-23T09:34:47.823305+00:00 on **trading_box** (`vmi3571445`) over **489 forward clocks**. FROZEN **0 -> 0** this pass (ratchet floor 0).

| verdict | before | after |
|---|---:|---:|
| ACCRUING | 92 | 92 |
| BEHIND | 57 | 57 |
| FROZEN | 0 | 0 |
| DORMANT_BY_SESSION | 0 | 0 |
| RETIRED | 339 | 339 |
| UNMEASURED | 1 | 1 |

## What advances each lane

| lane | clocks | accruing | frozen | mechanism | lane state last written |
|---|---:|---:|---:|---|---|
| `main` | 483 | 88 | 0 | MT5-Shadow (hourly, research/shadow_cycle.py) + leg enrol_clocks inside MT5-Dept-Forward (resident, every 10 min) | 2026-09-23T09:33:20 |
| `qquant` | 1 | 0 | 0 | MT5-QQuantShadow (every 30 min, research/qquant_shadow.py) | 2026-09-23T09:25:06 |
| `scalp` | 4 | 4 | 0 | MT5-Shadow (hourly) -> the scalp lane inside research/shadow_cycle.py | 2026-09-23T09:23:25 |
| `precert` | 1 | 0 | 0 | leg precert_shadow inside MT5-Dept-Forward (resident, every 10 min) | None |

## 24/7: the tasks that advance clocks

| task | verdict | repeat | last run | rc | what it advances |
|---|---|---|---|---|---|
| `MT5-Shadow` | RUNNING_24X7 | 1 Hour(s), 0 Minute(s) | 9/23/2026 11:21:23  | 1 | runs shadow_cycle -> shadow_forward, the main and scalp lanes |
| `MT5-QQuantShadow` | RUNNING_24X7 | 0 Hour(s), 30 Minute(s) | 9/23/2026 11:25:01  | 0 | runs qquant_shadow, the qquant lane |
| `MT5-Dept-Forward` | RUNNING_24X7 | 0 Hour(s), 10 Minute(s) | 9/23/2026 11:30:01  | -2147020576 | the forward department resident: legs enrol_clocks and clock_liveness |
| `MT5-HourlyCore` | RUNNING_24X7 | 1 Hour(s), 0 Minute(s) | 9/23/2026 10:36:01  | 267014 | the core hourly pass: leg forward_reconcile |
| `MT5-ForwardReconcile` | RUNNING_24X7 | 1 Hour(s), 0 Minute(s) | 9/23/2026 4:00:01 A | 0 | the standalone forward reconciler |

## Repairs raised this pass

No clock was FROZEN, so no repair was raised.

## Still frozen, and why

Nothing is frozen.

Host: MetaTrader5 installed and 83 of 84 MT5-* task(s) enabled: this host advances clocks
Sessions from: libs/research/market_constitution.py venue_fusion()
Roster: shadow_forward.certified_sleeves() -> 147 key(s)

_accrual is counted in the VENUE'S bars, never the wall clock; a FROZEN clock is repaired in the same pass and the postcondition is its own stamp moving, never a zero exit code (LAWS 7: A REPORT IS NOT A REMEDY)_
