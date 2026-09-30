# SELF-REPAIR REGISTRY -- which defect classes close themselves

<!-- DERIVED. Written by desks/mt5/research/self_repair_registry.py on the clock `hourly_cycle:self_repair`. Edit the organ, never this file. -->

Measured **2026-09-23T17:42:40+00:00** over **12** declared classes.

| bucket | classes | meaning |
|---|---:|---|
| **AUTOMATED** | 0 | detector, repair and fence all present and the detector is inside its window: this class closes itself |
| **DETECTED** | 0 | found automatically, but a builder still closes each instance |
| **MANUAL** | 0 | no detector exists: instances are found by a person, which is the count that must reach zero |
| **UNMEASURED** | 12 | the detector exists but has not produced inside its own window -- a stopped detector is never a clean class |

**0 class(es) are still found by hand.** That is the number this registry exists to drive to zero; it ratchets down and `scripts/check_self_repair.py` fails when it rises.

| class | bucket | detector | repair | fence | last detection | found |
|---|---|---|---|---|---|---|
| `producer_without_clock` | **UNMEASURED** | `scripts/check_component_registry.py` | `run_once (libs/ops/control_plane/reconciler._actuator_for)` | `scripts/check_birth_obligations.py` | 6.73h | components=1293 |
| `artifact_nobody_reads` | **UNMEASURED** | `scripts/check_dead_architecture.py` | `wiring (libs/ops/control_plane/actuators.desk_actuators)` | `scripts/check_dead_architecture.py` | 171.86h | _=UNMEASURED |
| `store_emptied_by_second_writer` | **UNMEASURED** | `scripts/check_protected_records.py` | `UNMEASURED` | `scripts/check_protected_records.py` | UNMEASURED | UNMEASURED |
| `retirement_on_absence` | **UNMEASURED** | `scripts/check_no_retirement_on_absence.py` | `UNMEASURED` | `scripts/check_no_retirement_on_absence.py` | 7.22h | unguarded=2 |
| `queue_ordered_on_unmeasured` | **UNMEASURED** | `scripts/check_research_queue.py` | `run_once:leg:queue_census` | `scripts/check_research_queue.py` | 8.41h | _=UNMEASURED |
| `one_word_two_measurements` | **UNMEASURED** | `scripts/check_claim_consistency.py` | `UNMEASURED` | `scripts/check_claim_consistency.py` | UNMEASURED | UNMEASURED |
| `task_silently_expired` | **UNMEASURED** | `scripts/check_box_tasks.py` | `restart:task (libs/ops/control_plane/actuators.restart_resident)` | `scripts/check_scheduled_tasks.py` | 14.5h | _=UNMEASURED |
| `leaked_worker_pool` | **UNMEASURED** | `desks/mt5/scripts/reap_orphaned_workers.py` | `reap_orphans (libs/ops/control_plane/actuators.desk_actuators)` | `scripts/check_orphanable_writers.py` | 14.08h | orphans=0 |
| `lock_another_principal_cannot_open` | **UNMEASURED** | `scripts/check_plumbing_invariants.py` | `UNMEASURED` | `scripts/check_plumbing_invariants.py` | 7.25h | _=UNMEASURED |
| `clock_stops_accruing` | **UNMEASURED** | `desks/mt5/research/clock_liveness.py` | `heal_clocks (libs/ops/control_plane/actuators.desk_actuators)` | `scripts/check_clock_liveness.py` | 7.76h | _=UNMEASURED |
| `source_stops_at_bytes` | **UNMEASURED** | `scripts/check_source_drain.py` | `run_once:leg:ingestion_ledger` | `scripts/check_birth_obligations.py` | 6.12h | _=UNMEASURED |
| `family_never_reaches_judge` | **UNMEASURED** | `scripts/check_judge_coverage.py` | `run_once:leg:judge_coverage` | `scripts/check_judge_coverage.py` | 6.14h | _=UNMEASURED |

## What each class already cost

- **producer_without_clock** -- a producer exists and nothing ever runs it. 126 organs read NEVER on the build box and 8 on the trading box, 2026-09-23. the detector last produced 6.7h ago, past its 2.0h window: a stopped detector is not a clean class
- **artifact_nobody_reads** -- a producer writes an artifact no consumer is declared for. the wiring audit's standing finding; an unread artifact is compute spent on nothing. the detector last produced 171.9h ago, past its 2.0h window: a stopped detector is not a clean class
- **store_emptied_by_second_writer** -- two writers on one store, and the second one truncates the first. the 1,078 lines removed from gateway.py by the hourly Dell sync (CLAUDE.md). the detector exists but its artifact desks/mt5/reports/PROTECTED_RECORDS.json has never appeared on this host -- nothing here may call the class covered
- **retirement_on_absence** -- an organ retires or voids a row because a reference was absent or stale. GOLD_RETIRED re-derivation: an empty ledger once voided a live window. the detector last produced 7.2h ago, past its 2.0h window: a stopped detector is not a clean class
- **queue_ordered_on_unmeasured** -- a queue is ordered by a field nothing measured, so the order is noise. the research queue's priority field, repeatedly unmeasured. the detector last produced 8.4h ago, past its 2.0h window: a stopped detector is not a clean class
- **one_word_two_measurements** -- two organs use one word for two different measurements. 'coverage' meaning both axis coverage and bar coverage; verdicts silently disagreed. the detector exists but its artifact desks/mt5/reports/CLAIM_CONSISTENCY.json has never appeared on this host -- nothing here may call the class covered
- **task_silently_expired** -- a scheduled task expired, was disabled, or was never registered at all. MT5-Dept-Mathlab was declared in box_tasks.manifest with installer=NONE and had never existed on the box; its five legs read NEVER for as long as the manifest had claimed it. the detector last produced 14.5h ago, past its 2.0h window: a stopped detector is not a clean class
- **leaked_worker_pool** -- a worker pool leaks processes that hold commit until the box thrashes. 14 resident pythons and 239 MB free during an external_gauntlet stand-down. the detector last produced 14.1h ago, past its 2.0h window: a stopped detector is not a clean class
- **lock_another_principal_cannot_open** -- a lock is created so that the other principal can never take it. SYSTEM-created locks the interactive session could not open, and the reverse. the detector last produced 7.2h ago, past its 2.0h window: a stopped detector is not a clean class
- **clock_stops_accruing** -- a clock still fires but stops accruing, so nothing downstream advances. ~960 silent merge aborts; 57 VPS commits never reached the compiler. the detector last produced 7.8h ago, past its 2.0h window: a stopped detector is not a clean class
- **source_stops_at_bytes** -- a source is collected and never reaches cells the judge can read. 495 of 503 grounds hold no position in the chain (birth fence, 2026-09-23). the detector last produced 6.1h ago, past its 2.0h window: a stopped detector is not a clean class
- **family_never_reaches_judge** -- a family accumulates cells that no judge ever reads. 0 of 79 families showed a judge reach on the build box, 2026-09-23. the detector last produced 6.1h ago, past its 2.0h window: a stopped detector is not a clean class
