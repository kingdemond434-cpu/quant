# LOOP LIVENESS -- is the research loop alive, stage by stage

> DERIVED. Regenerate with `python desks/mt5/research/loop_liveness.py --once`;
> never edit this file. Source: `desks/mt5/reports/LOOP_LIVENESS.json`.

Measured 2026-09-23T01:24:21+00:00 on **box_clocks_off** (`vmi3500897`) -- 3 ALIVE, 3 SLOW, 2 STALLED, 2 UNMEASURED.

Host: MetaTrader5 present but 0 MT5-* scheduled tasks are enabled -- the box's clocks are OFF, so a box-only stage has nothing scheduled to advance it

**loop_alive: False** -- first stalled stage: `sources_ingested`

| # | stage | verdict | organ | 1h | 24h | newest | waiting | organ last run |
|---|---|---|---|---|---|---|---|---|
| 1 | `sources_ingested` | STALL  | `world_crawler` | 0 | 26 | 4.6h | 148 | 2026-09-10T23:11:23 |
| 2 | `discoveries_mined` | ALIVE  | `deep_forest` | 164 | 527 | 0.0h | None | 2026-09-10T22:44:35 |
| 3 | `conversion` | ALIVE  | `miner_conversion` | 61 | 1084 | 0.0h | 1089 | UNMEASURED |
| 4 | `candidates_compiled` | ALIVE  | `compile_candidates` | 61 | 1093 | 0.0h | None | 2026-09-11T01:50:00 |
| 5 | `ten_gates_judged` | STALL  | `external_gauntlet` | 0 | 0 | 154.3h | 4082 | UNMEASURED |
| 6 | `survivors_certified` | SLOW   | `external_gauntlet` | 0 | 0 | 154.3h | 0 | UNMEASURED |
| 7 | `clocks_enrolled` | SLOW   | `enrol_clocks` | 0 | 0 | 154.1h | 0 | UNMEASURED |
| 8 | `clocks_accruing` | UNMEAS | `shadow_forward` | 0 | 0 | 152.8h | 651 | UNMEASURED |
| 9 | `promoter_reading` | UNMEAS | `promoter` | 0 | 0 | 152.8h | None | UNMEASURED |
| 10 | `allocator_sizing` | SLOW   | `pf_allocator` | 0 | 0 | 152.8h | None | UNMEASURED |

## Why each verdict

- **sources_ingested** (STALLED): 148 input row(s) waiting on `world_crawler` and newest output 4.6 h old (window 120 min), oldest waiting 133.3 h -- DEFECT
- **discoveries_mined** (ALIVE): 164 in the last hour, 527 in 24h; newest 1 min old, inside the 120 min window
- **conversion** (ALIVE): 61 in the last hour, 1084 in 24h; newest 1 min old, inside the 120 min window
- **candidates_compiled** (ALIVE): 61 in the last hour, 1093 in 24h; newest 1 min old, inside the 120 min window
- **ten_gates_judged** (STALLED): 4082 input row(s) waiting on `external_gauntlet` and newest output 154.3 h old (window 120 min), oldest waiting 143.4 h -- DEFECT
- **survivors_certified** (SLOW): nothing waiting, but newest output is 154.3 h old against a 120 min window
- **clocks_enrolled** (SLOW): nothing waiting, but newest output is 154.1 h old against a 120 min window
- **clocks_accruing** (UNMEASURED): clocks_accruing needs a live trading_box; measured on `box_clocks_off`, where nothing is scheduled to advance it -- absence here is not a stall (L1.28a: UNMEASURED is the answer, not zero)
- **promoter_reading** (UNMEASURED): promoter_reading needs a live trading_box; measured on `box_clocks_off`, where nothing is scheduled to advance it -- absence here is not a stall (L1.28a: UNMEASURED is the answer, not zero)
- **allocator_sizing** (SLOW): nothing waiting, but newest output is 152.8 h old against a 120 min window

## Defects

- `sources_ingested` -- organ `world_crawler`, last run 2026-09-10T23:11:23+00:00: 148 input row(s) waiting on `world_crawler` and newest output 4.6 h old (window 120 min), oldest waiting 133.3 h -- DEFECT
- `ten_gates_judged` -- organ `external_gauntlet`, last run UNMEASURED: 4082 input row(s) waiting on `external_gauntlet` and newest output 154.3 h old (window 120 min), oldest waiting 143.4 h -- DEFECT

_a stage with input waiting and no output inside two cadences is STALLED and is a DEFECT; a stage that needs the trading box is UNMEASURED off it, never STALLED; an absent source is UNMEASURED, never zero_
