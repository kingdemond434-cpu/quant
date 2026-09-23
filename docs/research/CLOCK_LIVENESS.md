# CLOCK LIVENESS -- every forward clock advancing, or repaired in the same pass

> DERIVED. Regenerate with `python desks/mt5/research/clock_liveness.py --once`;
> never edit this file. Source: `desks/mt5/reports/CLOCK_LIVENESS.json`.

Measured 2026-09-23T09:47:04.439293+00:00 on **box_clocks_off** (`vmi3500897`) over **653 forward clocks**. FROZEN **0 -> 0** this pass (ratchet floor None).

| verdict | before | after |
|---|---:|---:|
| ACCRUING | 0 | 0 |
| BEHIND | 0 | 0 |
| FROZEN | 0 | 0 |
| DORMANT_BY_SESSION | 0 | 0 |
| RETIRED | 0 | 0 |
| UNMEASURED | 653 | 653 |

## What advances each lane

| lane | clocks | accruing | frozen | mechanism | lane state last written |
|---|---:|---:|---:|---|---|
| `main` | 647 | 0 | 0 | MT5-Shadow (hourly, research/shadow_cycle.py) + leg enrol_clocks inside MT5-Dept-Forward (resident, every 10 min) | 2026-09-16T16:37:33 |
| `qquant` | 1 | 0 | 0 | MT5-QQuantShadow (every 30 min, research/qquant_shadow.py) | 2026-09-16T16:37:32 |
| `scalp` | 4 | 0 | 0 | MT5-Shadow (hourly) -> the scalp lane inside research/shadow_cycle.py | 2026-09-16T16:37:32 |
| `precert` | 1 | 0 | 0 | leg precert_shadow inside MT5-Dept-Forward (resident, every 10 min) | None |

## CLOCK IMPLIES CERTIFICATE

Canon: **58** certificate(s) -- 58 certificate(s) in the canon (read, never written).

| backing | clocks |
|---|---:|
| BACKED | 46 |
| BREACHED | 0 |
| AWAITING_JUDGEMENT | 31 |
| RETIRED | 576 |
| UNMEASURED | 0 |

**breached 31** (of which awaiting judgement 31), backed 46, retired 576; 0 past one judging cycle. Breach ratchet floor None.

Judge's queue: dry run: the cells that would be queued are listed, nothing was submitted


## 24/7: the tasks that advance clocks

| task | verdict | repeat | last run | rc | what it advances |
|---|---|---|---|---|---|
| `MT5-Shadow` | UNMEASURED | -- | -- | -- | runs shadow_cycle -> shadow_forward, the main and scalp lanes |
| `MT5-QQuantShadow` | UNMEASURED | -- | -- | -- | runs qquant_shadow, the qquant lane |
| `MT5-Dept-Forward` | UNMEASURED | -- | -- | -- | the forward department resident: legs enrol_clocks and clock_liveness |
| `MT5-HourlyCore` | UNMEASURED | -- | -- | -- | the core hourly pass: leg forward_reconcile |
| `MT5-ForwardReconcile` | UNMEASURED | -- | -- | -- | the standalone forward reconciler |

## Repairs raised this pass

No clock was FROZEN, so no repair was raised.

## Still frozen, and why

Nothing is frozen.

Host: the MetaTrader5 package is installed and all 0 MT5-* scheduled task(s) are disabled: nothing is scheduled to advance a clock on this host
Sessions from: libs/research/market_constitution.py venue_fusion()
Roster: shadow_forward.certified_sleeves() -> 163 key(s)

_accrual is counted in the VENUE'S bars, never the wall clock; a FROZEN clock is repaired in the same pass and the postcondition is its own stamp moving, never a zero exit code (LAWS 7: A REPORT IS NOT A REMEDY)_
