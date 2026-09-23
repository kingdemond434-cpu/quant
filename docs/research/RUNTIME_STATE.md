# RUNTIME STATE -- what actually ran on the box

<!-- DERIVED. Written by desks/mt5/research/runtime_attestation.py on the clock `hourly_cycle:runtime_attestation`. Edit the organ, never this file. -->

**This document attests to ONE host: `vmi3500897` (Windows 2022Server), and describes no other machine.** Role measured as `non_trading_host`: gateway_state.json is 168.8h old -- no live trading loop is attested by this document.

- Measured at **2026-09-23T10:36:06+00:00** (cadence 60 min; stale past 120 min)
- Tree: `16eca3cabb2e` on `llm-auto-upgrade-verify-gcjac3`; release seal ok=`False` running=`b794c18abb61` sealed=`1eba97937191`
- Organs attested **365** of 1281 registry components (916 declare no artifact, so there is nothing to hash: component declares no output artifact -- nothing to hash; the registry's own completeness is check_component_registry.py)
- Pass cost 1.09s; 0 hash(es) skipped over budget; 0 summary/-ies trimmed for size

| state | organs | meaning |
|---|---:|---|
| **LIVE** | 111 | artifact present and newer than the organ's derived max silence |
| **STALE** | 95 | artifact present but older than the organ's derived max silence |
| **MISSING** | 33 | artifact absent while this host recorded the organ running |
| **NEVER** | 126 | no artifact and no run record on this host |
| **UNMEASURED** | 0 | artifact present, cadence undeclared -- nothing here may call it late |

The hash is not the body. `desks/mt5/reports/**` is ~50 MB the box rewrites hourly and this repository deliberately does not carry it; the SHA-256 below lets a reader ask for any one artifact by name and check that what arrives is what this host published at the time stamped here.

## LIVE (111)

| organ | clock | last run | artifact | age | size | sha256 | published |
|---|---|---|---|---:|---:|---|---|
| `battery:desks/mt5/moat/moat_lifecycle.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/africa_interaction.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/asia_transmission.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/axis_ingest_all.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/counterexample_agent.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/counterfactual_attribution.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/countries/kr/lattice.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/countries/kr/miners.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/countries/kr/nowcast.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/empty_cluster_forcer.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/engine_registry.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/event_surprise.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/frontier_ceo.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/gold_hour_sweep.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/hour_prior.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/hour_surface.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/index_discovery.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/institutional_cards.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/japan/dashboard.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/japan/miners.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/local_converter.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/macro_state_engine.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/middle_east_interaction.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/research_artifacts.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/search_paradigm_census.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/south_america_interaction.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/trend_core.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/research/validate_fusion.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/check_desk_health.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:desks/mt5/scripts/check_llm_seat.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:desks/mt5/scripts/disk_census.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:desks/mt5/scripts/fxblue_digest.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/fxblue_mechanism_summary.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/heal_orphaned_clocks.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/heal_silent_demotions.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/migrate_identity_venue.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/reap_orphaned_workers.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:desks/mt5/scripts/retire_uncashable_certs.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/audit_mt5_capability_reuse.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/autofix_defects.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/backfill_live_ledger_r.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/backfill_pit.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/build_audit_shards.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/build_family_evidence.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/build_graveyard_priors.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/build_midnight_operations_report.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/build_mt5_midnight_state.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/build_scoreboard.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/check_bar_coverage.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_bar_history_floor.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_blueprint_coverage.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_breadth_mandate.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_cert_yield.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_credentials.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_data_recoverability.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_desk_cycles.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/check_desk_manifest.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_dig_roi.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_disposition_landed.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_forward_clock.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/check_frozen_values.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_governance_pulse.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_ground_conversion.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_knob_sensitivity.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_ledger_reversion.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_oom_pressure.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_pegged_duplicates.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_perishability.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_producer_yield.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_reachability.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_recommendation_flow.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_research_allocation.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_research_health.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_row_conversion.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_scheduled_tasks.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_seat_health.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_shell_hygiene.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_swap_reliability.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_tier5_audit.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_unit_health.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/check_unmeasurable_claims.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/check_worktree_reap.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/collector_author.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/compare_book_growth.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/controller_checkpoint.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/convert_question_queues.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/daily_max.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/have_memory.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/heal_forward_lane.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/info_class_map.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/monitor_data_decay.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/monitor_mt5_shadow_sync.py` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json` | 8.9h | 11K | `0728ba9908226fdb` | UNMEASURED |
| `battery:scripts/overnight_frontier_handoff.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/probe_language_moat.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/reap_worktrees.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/research_allocator.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/run_allocation.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/run_factory_status.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/run_ict_strategy.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/run_restore_drill.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/score_panel.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/stageb_capacity.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/study_promotion_selection_bias.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `battery:scripts/sync_research_ledger.py` | `hourly_cycle:organ_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_ORGANS.json` | 8.0h | 20K | `2956b7e8cfacb4d1` | UNMEASURED |
| `leg:discovery_compiler` | `hourly_cycle:discovery_compiler` | UNMEASURED UNMEASURED | `desks/mt5/reports/DISCOVERY_COMPILER.json` | 0.5h | 33K | `136fe526d7a8db27` | UNMEASURED |
| `leg:global_research_os` | `hourly_cycle:global_research_os` | UNMEASURED UNMEASURED | `desks/mt5/reports/KR_DATA_PLANE.json` | 1.4h | 1K | `b9ec53c4b2420d37` | UNMEASURED |
| `leg:health` | `hourly_cycle:health` | 2026-09-16T14:07:21+00:00 ok | `data/duplicate_organs.json` | 0.1h | 38K | `2bb29d127808c4d8` | UNMEASURED |
| `leg:judge_coverage` | `hourly_cycle:judge_coverage` | UNMEASURED UNMEASURED | `desks/mt5/reports/JUDGE_COVERAGE.json` | 0.3h | 28K | `f1598551f2ff3e5d` | verdict=COVERED |
| `leg:kimi_hunt` | `hourly_cycle:kimi_hunt` | UNMEASURED UNMEASURED | `desks/mt5/reports/SEAT_HEALTH.json` | 0.1h | 56K | `c832a6af7b894819` | verdict=UNMEASURED |
| `leg:producer_census` | `hourly_cycle:producer_census` | UNMEASURED UNMEASURED | `desks/mt5/reports/PRODUCER_CENSUS.json` | 1.4h | 926K | `5ba9432fdc2ff2d1` | UNMEASURED |
| `leg:sandbox_runner` | `hourly_cycle:sandbox_runner` | UNMEASURED UNMEASURED | `desks/mt5/reports/SANDBOX_RUNNER.json` | 0.7h | 99K | `058aa00d79ce7a08` | UNMEASURED |

## STALE (95)

| organ | clock | last run | artifact | age | size | sha256 | published |
|---|---|---|---|---:|---:|---|---|
| `component:control_plane` | `MT5-ClockFixer` | UNMEASURED UNMEASURED | `desks/mt5/reports/CONTROL_PLANE.json` | 19.5h | 160K | `617a9e23f32d6712` | UNMEASURED |
| `leg:acceptance` | `hourly_cycle:acceptance` | 2026-09-16T13:49:42+00:00 exit_code=1 | `desks/mt5/reports/acceptance_properties.json` | 10.6d | 3K | `94c94a26da3fa473` | UNMEASURED |
| `leg:allocator_join` | `hourly_cycle:allocator_join` | 2026-09-16T14:38:33+00:00 ok | `desks/mt5/reports/pf_allocation.json` | 6.8d | 98K | `f0e322ca5e977848` | UNMEASURED |
| `leg:alpha_evolution` | `hourly_cycle:alpha_evolution` | 2026-09-16T14:31:19+00:00 ok | `desks/mt5/reports/alpha_evolution.json` | 6.8d | 56K | `b409870a0c40e329` | UNMEASURED |
| `leg:alpha_replenishment` | `hourly_cycle:alpha_replenishment` | UNMEASURED UNMEASURED | `desks/mt5/reports/ALPHA_REPLENISHMENT.json` | 13.3h | 860B | `444cccdecbdc2234` | status=UNMEASURED |
| `leg:analyst_pipeline` | `hourly_cycle:analyst_pipeline` | UNMEASURED UNMEASURED | `desks/mt5/reports/ANALYST_PIPELINE.json` | 6.4d | 1K | `9a66bbe2cfa5064d` | UNMEASURED |
| `leg:arena` | `hourly_cycle:arena` | 2026-09-16T13:49:46+00:00 exit_code=1 | `desks/mt5/reports/COEVOLUTION.json` | 8.2h | 140K | `0e6596d25deac327` | UNMEASURED |
| `leg:asia_collector` | `hourly_cycle:asia_collector` | 2026-09-16T12:40:12+00:00 exit_code=1 | `desks/mt5/reports/ASIA_COLLECTOR.json` | 6.9d | 5K | `b88b9ed89c6e0e1b` | UNMEASURED |
| `leg:asia_parser` | `hourly_cycle:asia_parser` | 2026-09-16T12:40:32+00:00 ok | `desks/mt5/data/lake/series` | 7.1d | 25K | `UNMEASURED` | UNMEASURED (not a readable JSON object) |
| `leg:axis_registry` | `hourly_cycle:axis_registry` | UNMEASURED UNMEASURED | `desks/mt5/reports/AXIS_REGISTRY.json` | 6.6d | 98K | `0becc3a032b96271` | UNMEASURED |
| `leg:blind_reviewer` | `hourly_cycle:blind_reviewer` | UNMEASURED UNMEASURED | `desks/mt5/reports/EVALUATOR_LAB.json` | 6.5d | 8K | `5145bc714fe3f310` | status=MEASURED |
| `leg:bottleneck_attack` | `hourly_cycle:bottleneck_attack` | UNMEASURED UNMEASURED | `desks/mt5/reports/BOTTLENECK_ATTACK.json` | 7.1h | 5K | `87a1c3c26e6dc6fe` | UNMEASURED |
| `leg:bottleneck_law` | `hourly_cycle:bottleneck_law` | UNMEASURED UNMEASURED | `desks/mt5/reports/BOTTLENECK_LAW.json` | 13.3h | 2K | `19b8710a28390953` | UNMEASURED |
| `leg:causal_invariance` | `hourly_cycle:causal_invariance` | UNMEASURED UNMEASURED | `desks/mt5/reports/CAUSAL_INVARIANCE.json` | 9.2h | 38K | `91b24cd64b76b971` | status=OK |
| `leg:causal_lab` | `hourly_cycle:causal_lab` | UNMEASURED UNMEASURED | `desks/mt5/reports/CAUSAL_LAB.json` | 6.5d | 17K | `f2ad25bfe52ae4cd` | status=OK |
| `leg:closed_loop` | `hourly_cycle:closed_loop` | 2026-09-16T14:31:21+00:00 ok | `desks/mt5/data/architecture/closed_loop_attestation.json` | 8.7h | 4K | `ddbad9cc423bdac3` | UNMEASURED |
| `leg:coevolution` | `hourly_cycle:coevolution` | 2026-09-23T02:21:40+00:00 coevolution | `desks/mt5/reports/COEVOLUTION.json` | 8.2h | 140K | `0e6596d25deac327` | UNMEASURED |
| `leg:compute_economics` | `hourly_cycle:compute_economics` | UNMEASURED UNMEASURED | `desks/mt5/reports/COMPUTE_ECONOMICS.json` | 13.7h | 71K | `c5c4d8ed512afc00` | UNMEASURED |
| `leg:control_plane` | `hourly_cycle:control_plane` | UNMEASURED UNMEASURED | `desks/mt5/reports/CONTROL_PLANE.json` | 19.5h | 160K | `617a9e23f32d6712` | UNMEASURED |
| `leg:cost_to_edge` | `hourly_cycle:cost_to_edge` | 2026-09-16T12:39:55+00:00 ok | `desks/mt5/data/cost_surface.json` | 6.2h | 1.0M | `d431a587715284ca` | UNMEASURED |
| `leg:counterfactual_world` | `hourly_cycle:counterfactual_world` | 2026-09-16T13:43:18+00:00 ok | `desks/mt5/reports/COUNTERFACTUAL_WORLD.json` | 14.7d | 8K | `6b992b8bed07fffd` | status=MEASURED |
| `leg:coverage_tensor` | `hourly_cycle:coverage_tensor` | UNMEASURED UNMEASURED | `desks/mt5/reports/COVERAGE_TENSOR.json` | 5.9d | 151K | `502c670bf0da1e03` | UNMEASURED |
| `leg:cycle_pricing` | `hourly_cycle:cycle_pricing` | UNMEASURED UNMEASURED | `desks/mt5/reports/CYCLE_PRICING.json` | 7.6h | 62K | `2097c818a4ce0064` | UNMEASURED |
| `leg:dead_architecture` | `hourly_cycle:dead_architecture` | 2026-09-16T13:51:17+00:00 ok | `desks/mt5/reports/dead_architecture.json` | 6.9d | 57K | `f46d5610154d8438` | UNMEASURED |
| `leg:deep_forest` | `hourly_cycle:deep_forest` | 2026-09-16T13:19:53+00:00 ok | `desks/mt5/data/deep_forest_frontier.json` | 6.8d | 127K | `7913a94d15258286` | UNMEASURED |
| `leg:drawdown_alpha_miner` | `hourly_cycle:drawdown_alpha_miner` | UNMEASURED UNMEASURED | `desks/mt5/reports/DRAWDOWN_ALPHA_MINER.json` | 13.3h | 108K | `d014083d591651ec` | UNMEASURED |
| `leg:edge_reliability` | `hourly_cycle:edge_reliability` | 2026-09-16T13:49:45+00:00 ok | `desks/mt5/reports/edge_reliability.json` | 6.9d | 386K | `6af459956b792f30` | status=MEASURED |
| `leg:evaluator_lab` | `hourly_cycle:evaluator_lab` | UNMEASURED UNMEASURED | `desks/mt5/reports/EVALUATOR_LAB.json` | 6.5d | 8K | `5145bc714fe3f310` | status=MEASURED |
| `leg:evidence_router` | `hourly_cycle:evidence_router` | UNMEASURED UNMEASURED | `desks/mt5/reports/EVIDENCE_ROUTER.json` | 5.9d | 2K | `ba91e131f9321348` | UNMEASURED |
| `leg:execution_twin` | `hourly_cycle:execution_twin` | 2026-09-16T12:32:47+00:00 ok | `desks/mt5/reports/EXECUTION_TWIN.json` | 6.9d | 52K | `b9265d0f4f8f32b1` | status=MEASURED |
| `leg:exit_study` | `hourly_cycle:exit_study` | 2026-09-16T13:44:07+00:00 ok | `desks/mt5/reports/MUTATION_YIELD.json` | 8.9h | 4K | `7c8345b056d4a7bb` | UNMEASURED |
| `leg:experiment_spine` | `hourly_cycle:experiment_spine` | 2026-09-23T01:36:17+00:00 ok | `desks/mt5/reports/EXPERIMENT_SPINE.json` | 9.0h | 35K | `5030bed144900243` | UNMEASURED |
| `leg:exposure_decomposition` | `hourly_cycle:exposure_decomposition` | UNMEASURED UNMEASURED | `desks/mt5/reports/EXPOSURE_DECOMPOSITION.json` | 6.6d | 82K | `82d7906f4c2cd339` | UNMEASURED |
| `leg:fill_attribution` | `hourly_cycle:fill_attribution` | 2026-09-16T12:39:52+00:00 exit_code=1 | `desks/mt5/data/cost_surface.json` | 6.2h | 1.0M | `d431a587715284ca` | UNMEASURED |
| `leg:forced_flow_calendar` | `hourly_cycle:forced_flow_calendar` | UNMEASURED UNMEASURED | `desks/mt5/data/forced_flow_calendar.json` | 6.6d | 1.3M | `2ae898e4f906c532` | UNMEASURED |
| `leg:forward_slot_ranker` | `hourly_cycle:forward_slot_ranker` | UNMEASURED UNMEASURED | `desks/mt5/reports/FORWARD_SLOT_RANKER.json` | 6.4d | 173K | `034f86359f30a7cc` | UNMEASURED |
| `leg:fred_macro` | `hourly_cycle:fred_macro` | 2026-09-16T14:38:34+00:00 FRESH | `desks/mt5/reports/PIT_CENSUS.json` | 6.6d | 479B | `5be445a2d2629332` | UNMEASURED |
| `leg:frontier` | `hourly_cycle:frontier` | 2026-09-16T13:19:23+00:00 ok | `desks/mt5/reports/CEO_DOCKET.json` | 8.0d | 24K | `aec458f20adb0f1c` | UNMEASURED |
| `leg:frontier_unknowns` | `hourly_cycle:frontier_unknowns` | 2026-09-16T13:43:27+00:00 exit_code=1 | `desks/mt5/reports/STANDING_QUESTIONS.json` | 6.6d | 34K | `3dd8d80667b4724e` | UNMEASURED |
| `leg:futures_lead_lag` | `hourly_cycle:futures_lead_lag` | 2026-09-16T14:38:04+00:00 ok | `desks/mt5/reports/WORLD_CAUSAL_GRAPH.json` | 6.9d | 214K | `9f036cb7b86b563c` | status=OK |
| `leg:gauntlet_backpressure` | `hourly_cycle:gauntlet_backpressure` | UNMEASURED UNMEASURED | `desks/mt5/reports/GAUNTLET_BACKPRESSURE.json` | 6.4d | 28K | `0bf4fb9826140b71` | UNMEASURED |
| `leg:graveyard_model` | `hourly_cycle:graveyard_model` | 2026-09-16T13:44:08+00:00 ok | `desks/mt5/reports/MUTATION_YIELD.json` | 8.9h | 4K | `7c8345b056d4a7bb` | UNMEASURED |
| `leg:implementer` | `hourly_cycle:implementer` | 2026-09-23T03:11:45+00:00 ok | `docs/research/recommendation_ledger.json` | 7.4h | 1.4M | `fec4cbb899bf645c` | UNMEASURED |
| `leg:input_identity` | `hourly_cycle:input_identity` | 2026-09-16T13:51:25+00:00 ok | `desks/mt5/data/input_identity.json` | 6.9d | 121K | `3cba2d193cf8c491` | UNMEASURED |
| `leg:lake_promote` | `hourly_cycle:lake_promote` | 2026-09-16T12:39:07+00:00 ok | `desks/mt5/reports/PIT_CENSUS.json` | 6.6d | 479B | `5be445a2d2629332` | UNMEASURED |
| `leg:layer_census` | `hourly_cycle:layer_census` | 2026-09-16T13:49:35+00:00 ok | `desks/mt5/reports/layer_census.json` | 6.9d | 7K | `d2938954e1675a59` | UNMEASURED |
| `leg:markout` | `hourly_cycle:markout` | 2026-09-16T13:15:58+00:00 ok | `desks/mt5/reports/ALPHA_CAPTURE.json` | 14.7d | 19K | `23b13f574708d0fd` | status=UNMEASURED |
| `leg:math_lab` | `hourly_cycle:math_lab` | UNMEASURED UNMEASURED | `desks/mt5/reports/MATH_LAB.json` | 8.4h | 173K | `74787bbb0e03023f` | UNMEASURED |
| `leg:mine` | `hourly_cycle:mine` | 2026-09-16T14:52:19+00:00 ok | `data/data_universe_map.json` | 17.0d | 418K | `99267432b16ffa72` | UNMEASURED |
| `leg:miner_conversion` | `hourly_cycle:miner_conversion` | 2026-09-16T13:25:42+00:00 ok | `data/agent_value.json` | 6.9d | 15K | `35dc60df54edb2b9` | status=UNMEASURED |
| `leg:miner_specialisation` | `hourly_cycle:miner_specialisation` | UNMEASURED UNMEASURED | `desks/mt5/reports/MINER_SPECIALISATION.json` | 6.4d | 7K | `089ef950fbd04ec4` | UNMEASURED |
| `leg:missed_trade_archaeologist` | `hourly_cycle:missed_trade_archaeologist` | UNMEASURED UNMEASURED | `desks/mt5/reports/MISSED_TRADES.json` | 13.5h | 255K | `a1130e04c3679eab` | UNMEASURED |
| `leg:ml_layer` | `hourly_cycle:ml_layer` | 2026-09-16T13:43:11+00:00 ok | `desks/mt5/reports/ML_LAYER.json` | 6.9d | 16K | `5ec525390c125e2b` | UNMEASURED |
| `leg:model_role_benchmark` | `hourly_cycle:model_role_benchmark` | UNMEASURED UNMEASURED | `desks/mt5/reports/MODEL_ROLE_BENCHMARK.json` | 6.6d | 217K | `92edc6f634a7a2ac` | UNMEASURED |
| `leg:model_search` | `hourly_cycle:model_search` | 2026-09-23T02:35:52+00:00 model_search | `desks/mt5/reports/MODEL_SEARCH.json` | 8.0h | 34K | `78b99f7409662652` | UNMEASURED |
| `leg:model_skill` | `hourly_cycle:model_skill` | 2026-09-16T13:16:30+00:00 verdict_exit=2 | `desks/mt5/reports/MODEL_SELF_IMPROVEMENT.json` | 6.9d | 6K | `fd29333f95a9f70e` | status=BREACH |
| `leg:mutation_yield` | `hourly_cycle:mutation_yield` | UNMEASURED UNMEASURED | `desks/mt5/reports/MUTATION_YIELD.json` | 8.9h | 4K | `7c8345b056d4a7bb` | UNMEASURED |
| `leg:net_edge` | `hourly_cycle:net_edge` | 2026-09-23T05:33:52+00:00 OK | `desks/mt5/reports/NET_EDGE.json` | 5.8h | 322K | `74fb847142750b73` | UNMEASURED |
| `leg:netting_report` | `hourly_cycle:netting_report` | UNMEASURED UNMEASURED | `desks/mt5/reports/NETTING.json` | 6.4d | 18K | `65c94e81c1dc136d` | UNMEASURED |
| `leg:novelty_gate` | `hourly_cycle:novelty_gate` | UNMEASURED UNMEASURED | `desks/mt5/reports/NOVELTY_GATE.json` | 6.6d | 15K | `6cad1ca7fcf30db4` | UNMEASURED |
| `leg:opportunity_cost` | `hourly_cycle:opportunity_cost` | 2026-09-16T13:49:39+00:00 exit_code=1 | `desks/mt5/reports/opportunity_cost.json` | 12.4d | 5K | `04a5b153890b9a0a` | UNMEASURED |
| `leg:opportunity_forecast` | `hourly_cycle:opportunity_forecast` | 2026-09-16T13:49:44+00:00 ok | `desks/mt5/reports/opportunity_forecast.json` | 6.9d | 25K | `0f5dd0b07c4e0d3f` | status=MEASURED; rows=35199 |
| `leg:orthogonality` | `hourly_cycle:orthogonality` | 2026-09-16T12:39:22+00:00 ok | `desks/mt5/reports/factor_residual.json` | 6.8d | 12.1M | `091dd17f7696b184` | UNMEASURED (artifact 12.1 MB, not parsed within budget) |
| `leg:pf_allocator` | `hourly_cycle:pf_allocator` | 2026-09-16T12:32:34+00:00 ok | `desks/mt5/reports/pf_allocation.json` | 6.8d | 98K | `f0e322ca5e977848` | UNMEASURED |
| `leg:pit_canaries` | `hourly_cycle:pit_canaries` | UNMEASURED UNMEASURED | `desks/mt5/reports/PIT_CENSUS.json` | 6.6d | 479B | `5be445a2d2629332` | UNMEASURED |
| `leg:plumbing_watchdog` | `hourly_cycle:plumbing_watchdog` | UNMEASURED UNMEASURED | `desks/mt5/reports/PLUMBING_WATCHDOG.json` | 7.1h | 32K | `b5c90b2720f0c5f5` | UNMEASURED |
| `leg:portfolio_bounty` | `hourly_cycle:portfolio_bounty` | 2026-09-22T21:16:13+00:00 PORTFOLIO_BOUNTY | `desks/mt5/reports/PORTFOLIO_BOUNTY.json` | 13.3h | 28K | `1e97310217ddabdb` | UNMEASURED |
| `leg:posterior_alpha` | `hourly_cycle:posterior_alpha` | UNMEASURED UNMEASURED | `desks/mt5/reports/POSTERIOR_ALPHA.json` | 6.6d | 154K | `77b0b2353d1ccd3b` | UNMEASURED |
| `leg:program_alpha_lane` | `hourly_cycle:program_alpha_lane` | UNMEASURED UNMEASURED | `desks/mt5/reports/PROGRAM_ALPHA_LANE.json` | 6.5d | 7K | `03ecb05df6b5b470` | UNMEASURED |
| `leg:promoter` | `hourly_cycle:promoter` | 2026-09-16T12:32:40+00:00 ok | `data/alpha_state_ledger.jsonl` | 9.1d | 650B | `dbdf24496ca6f129` | UNMEASURED (not a readable JSON object) |
| `leg:proposer_seat` | `hourly_cycle:proposer_seat` | UNMEASURED UNMEASURED | `desks/mt5/reports/PROPOSER_SEAT.json` | 7.3h | 7K | `2fdfac37b55a3f1d` | verdict=UNMEASURED |
| `leg:prosecutor` | `hourly_cycle:prosecutor` | 2026-09-16T13:50:14+00:00 ok | `desks/mt5/reports/prosecutor_census.json` | 6.4d | 30K | `d2bc24a65bf284c5` | UNMEASURED |
| `leg:refresh_bars` | `hourly_cycle:refresh_bars` | 2026-09-16T14:06:42+00:00 ok | `desks/mt5/data/universe/derived_series.json` | 6.8d | 4K | `2b2b4f66aee58e67` | UNMEASURED |
| `leg:regime_monitor` | `hourly_cycle:regime_monitor` | 2026-09-16T14:09:58+00:00 ok | `desks/mt5/data/state_vector.json` | 12.8d | 38K | `3d33bc13ffa3b4b0` | UNMEASURED |
| `leg:regime_router` | `hourly_cycle:regime_router` | UNMEASURED UNMEASURED | `desks/mt5/reports/REGIME_ROUTER.json` | 6.4d | 44K | `433b7b5f6ab88450` | UNMEASURED |
| `leg:representation_forge` | `hourly_cycle:representation_forge` | UNMEASURED UNMEASURED | `desks/mt5/reports/REPRESENTATION_FORGE.json` | 13.8h | 8K | `21358162017edd20` | refused=24 |
| `leg:research_auction` | `hourly_cycle:research_auction` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_AUCTION.json` | 13.3h | 14K | `54aef70839d9cc09` | UNMEASURED |
| `leg:research_evolution` | `hourly_cycle:research_evolution` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_EVOLUTION.json` | 13.7h | 34K | `aa6ff6d252a2e08c` | status=OK |
| `leg:research_gap_map` | `hourly_cycle:research_gap_map` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_GAP_MAP.json` | 6.4d | 31K | `034c3c2b2cc179ca` | UNMEASURED |
| `leg:research_latency` | `hourly_cycle:research_latency` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_LATENCY.json` | 13.3h | 2K | `a59a877026f7a61b` | UNMEASURED |
| `leg:research_roi` | `hourly_cycle:research_roi` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_ROI.json` | 5.9d | 133K | `b668b66cdf4d5135` | UNMEASURED |
| `leg:residual_factors` | `hourly_cycle:residual_factors` | 2026-09-16T13:15:53+00:00 ok | `desks/mt5/data/research_queue.json` | 13.0h | 25.0M | `dd12ef0db2da7701` | UNMEASURED (artifact 25.0 MB, not parsed within budget) |
| `leg:residual_hunt` | `hourly_cycle:residual_hunt` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESIDUAL_HUNT.json` | 5.9d | 15K | `33001ed8d066c84d` | UNMEASURED |
| `leg:scaling_laws` | `hourly_cycle:scaling_laws` | 2026-09-16T13:50:17+00:00 exit_code=1 | `desks/mt5/reports/scaling_laws.json` | 12.4d | 1K | `4fee7972429a5b4d` | UNMEASURED |
| `leg:scout_roster` | `hourly_cycle:scout_roster` | UNMEASURED UNMEASURED | `desks/mt5/reports/SCOUT_ROSTER.json` | 6.4d | 62K | `b87bc1760bea35ce` | UNMEASURED |
| `leg:search` | `hourly_cycle:search` | 2026-09-16T15:04:22+00:00 TIMEOUT | `libs/research/alpha_grammar.py` | 19.0h | 67K | `792d9d1ff4d979e3` | UNMEASURED (not a readable JSON object) |
| `leg:session_capital` | `hourly_cycle:session_capital` | 2026-09-16T13:51:30+00:00 ok | `desks/mt5/reports/session_capital.json` | 6.9d | 2K | `b445a689b89a3184` | UNMEASURED |
| `leg:source_registry` | `hourly_cycle:source_registry` | UNMEASURED UNMEASURED | `desks/mt5/reports/SOURCE_REGISTRY.json` | 6.5d | 12K | `576c95909b64f7ae` | UNMEASURED |
| `leg:standing_questions` | `hourly_cycle:standing_questions` | UNMEASURED UNMEASURED | `desks/mt5/reports/STANDING_QUESTIONS.json` | 6.6d | 34K | `3dd8d80667b4724e` | UNMEASURED |
| `leg:sweep` | `hourly_cycle:sweep` | 2026-09-16T15:16:24+00:00 TIMEOUT | `desks/mt5/mt5desk/families_orthogonal.py` | 6.6d | 111K | `1d8f29714884aa30` | UNMEASURED (not a readable JSON object) |
| `leg:tier1_scorecard` | `hourly_cycle:tier1_scorecard` | UNMEASURED UNMEASURED | `desks/mt5/reports/TIER1_SCORECARD.json` | 6.6d | 7K | `aade1bb05973ec47` | UNMEASURED |
| `leg:time_joins` | `hourly_cycle:time_joins` | 2026-09-16T14:38:32+00:00 ok | `desks/mt5/reports/PIT_CENSUS.json` | 6.6d | 479B | `5be445a2d2629332` | UNMEASURED |
| `leg:value_of_data` | `hourly_cycle:value_of_data` | UNMEASURED UNMEASURED | `desks/mt5/reports/VALUE_OF_DATA.json` | 6.5d | 22K | `3111d41ddc6ba9be` | UNMEASURED |
| `leg:world_crawler` | `hourly_cycle:world_crawler` | 2026-09-16T13:49:18+00:00 ok | `desks/mt5/reports/SOURCE_REGISTRY.json` | 6.5d | 12K | `576c95909b64f7ae` | UNMEASURED |
| `leg:world_lab` | `hourly_cycle:world_lab` | UNMEASURED UNMEASURED | `desks/mt5/reports/WORLD_LAB.json` | 6.5d | 106K | `3f8f1dafdd8ec521` | status=OK |

## MISSING (33)

| organ | clock | last run | artifact | age | size | sha256 | published |
|---|---|---|---|---:|---:|---|---|
| `leg:adversaries` | `hourly_cycle:adversaries` | 2026-09-16T13:17:28+00:00 ok | `desks/mt5/reports/ADVERSARY.json gate_detail` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:allocator_liveness` | `hourly_cycle:allocator_liveness` | 2026-09-23T10:01:35+00:00 OK | `desks/mt5/reports/ALLOCATOR_LIVENESS.json` | UNMEASURED | - | `UNMEASURED` | outcome=OK; verdict=LIVE |
| `leg:alpha_breadth` | `hourly_cycle:alpha_breadth` | 2026-09-16T14:26:53+00:00 ok | `desks/mt5/reports/pf_allocation.json (allocator_evidence block: forward_posterior, marginal_breadth, factor_tier and their per-sleeve factors)` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:brain_ab` | `hourly_cycle:brain_ab` | 2026-09-16T14:26:15+00:00 ok | `desks/mt5/reports/BRAIN_AB.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:burn_in` | `hourly_cycle:burn_in` | 2026-09-16T13:49:32+00:00 ok | `desks/mt5/reports/burn_in.json; release records` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:causal_graph` | `hourly_cycle:causal_graph` | 2026-09-16T12:37:15+00:00 ok | `desks/mt5/reports/CAUSAL_GRAPH.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:certificate_truth` | `hourly_cycle:certificate_truth` | 2026-09-22T20:51:34+00:00 STATE_PUBLISHED | `desks/mt5/reports/CERTIFICATE_TRUTH.json (repaired block) + desks/mt5/data/certificate_history.jsonl` | UNMEASURED | - | `UNMEASURED` | n=32; divergences=251 |
| `leg:clock_liveness` | `hourly_cycle:clock_liveness` | 2026-09-23T09:48:36+00:00 CLOCKS_ENROLLED | `desks/mt5/reports/CLOCK_LIVENESS.json, docs/research/CLOCK_LIVENESS.md` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:compile_candidates` | `hourly_cycle:compile_candidates` | 2026-09-16T15:28:25+00:00 TIMEOUT | `desks/mt5/data/hypotheses/miner_candidates.json genome_id` | UNMEASURED | - | `UNMEASURED` | outcome=TIMEOUT |
| `leg:cost_truth` | `hourly_cycle:cost_truth` | 2026-09-23T05:34:31+00:00 COST_TRUTH_MEASURED | `desks/mt5/reports/COST_TRUTH.json + docs/research/COST_TRUTH.md` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:counterexample_agent` | `hourly_cycle:counterexample_agent` | 2026-09-23T01:54:52+00:00 ok | `desks/mt5/reports/SEARCH_PARADIGMS.json; desks/mt5/reports/COUNTEREXAMPLE_AGENT.json; desks/mt5/data/research_queue.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:coverage_drain` | `hourly_cycle:coverage_drain` | 2026-09-23T10:03:16+00:00 ok | `desks/mt5/reports/COVERAGE_DRAIN.json + desks/mt5/data/coverage_drain_ledger.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok; seeded=0; gap=DECLARED_BUT_UNVERIFIED_LAYERS |
| `leg:daily` | `hourly_cycle:daily` | 2026-09-16T14:24:59+00:00 TIMEOUT | `desks/mt5/data/research_budget.json controller_variant` | UNMEASURED | - | `UNMEASURED` | outcome=TIMEOUT |
| `leg:deepen` | `hourly_cycle:deepen` | 2026-09-16T15:28:48+00:00 ok | `desks/mt5/data/research_queue.jsonl worked rows` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:engine_registry` | `hourly_cycle:engine_registry` | 2026-09-23T01:54:16+00:00 ENGINE_REGISTRY | `desks/mt5/reports/ENGINE_REGISTRY.json; desks/mt5/reports/SOURCE_REGISTRY.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:enrol_clocks` | `hourly_cycle:enrol_clocks` | 2026-09-16T16:27:55+00:00 ok | `reports/shadow/shadow_state.json e_* fields` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:execution_resolver` | `hourly_cycle:execution_resolver` | 2026-09-16T13:43:18+00:00 ok | `desks/mt5/reports/EXECUTION_INTELLIGENCE.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:exogenous_search` | `hourly_cycle:exogenous_search` | 2026-09-16T13:16:03+00:00 ok | `desks/mt5/reports/UNKNOWN_UNKNOWNS.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:experiment_design` | `hourly_cycle:experiment_design` | 2026-09-16T13:38:24+00:00 ok | `desks/mt5/reports/EXPERIMENT_DESIGN.json docket` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:external_gauntlet` | `hourly_cycle:external_gauntlet` | 2026-09-16T16:10:22+00:00 TIMEOUT | `desks/mt5/reports/universal_gates_external.json (desks/mt5/scripts/external_gauntlet.py:1605-1606); desks/mt5/reports/UNIVERSAL_SURVIVORS.json (:1637); desks/mt5/reports/POWER_CURE_CANDIDATES.json (:1805, measured n=9 at 2026-09-06T03:15)` | UNMEASURED | - | `UNMEASURED` | outcome=TIMEOUT |
| `leg:falsifier_run` | `hourly_cycle:falsifier_run` | 2026-09-16T16:22:57+00:00 TIMEOUT | `desks/mt5/reports/FALSIFIER_VERDICTS.json` | UNMEASURED | - | `UNMEASURED` | outcome=TIMEOUT |
| `leg:forward_reconcile` | `hourly_cycle:forward_reconcile` | 2026-09-16T13:16:25+00:00 ok | `desks/mt5/reports/forward_reconcile.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:heal_clocks` | `hourly_cycle:heal_clocks` | 2026-09-16T14:24:59+00:00 ok | `desks/mt5/data/forward_reconcile.json family_budget` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:model_league` | `hourly_cycle:model_league` | 2026-09-16T13:16:34+00:00 ok | `desks/mt5/reports/MODEL_ZOO.json generator_entrants` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:opportunity_gap` | `hourly_cycle:opportunity_gap` | 2026-09-16T13:43:13+00:00 ok | `desks/mt5/reports/RESEARCH_MISSIONS.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:physics_lab` | `hourly_cycle:physics_lab` | 2026-09-23T01:34:22+00:00 MATH_CARDS_JUDGED | `desks/mt5/reports/PHYSICS_LAB.json (`engines` block: one row per engine with status, trials, findings, unmeasured and compute_s)` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:publish_dashboard` | `hourly_cycle:publish_dashboard` | 2026-09-16T13:26:15+00:00 ok | `web/desk_state.json graph` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:publish_state` | `hourly_cycle:publish_state` | 2026-09-16T13:53:37+00:00 ok | `web/desk_state.json graph` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:queue_census` | `hourly_cycle:queue_census` | 2026-09-23T09:17:51+00:00 QUEUE_CENSUS_TAKEN | `desks/mt5/reports/QUEUE_CENSUS.json + desks/mt5/data/queue_census_history.jsonl` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:release_identity` | `hourly_cycle:release_identity` | 2026-09-16T13:49:28+00:00 exit_code=1 | `desks/mt5/data/LIVE_SYSTEM_STATE.json` | UNMEASURED | - | `UNMEASURED` | outcome=exit_code=1 |
| `leg:research_org` | `hourly_cycle:research_org` | 2026-09-16T13:38:23+00:00 ok | `desks/mt5/reports/FEATURE_ROI.json source_ablation` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:search_paradigm_census` | `hourly_cycle:search_paradigm_census` | 2026-09-23T01:54:56+00:00 ok | `desks/mt5/reports/SEARCH_PARADIGMS.json; desks/mt5/reports/COUNTEREXAMPLE_AGENT.json; desks/mt5/data/research_queue.json` | UNMEASURED | - | `UNMEASURED` | outcome=ok |
| `leg:state_vector` | `hourly_cycle:state_vector` | 2026-09-16T14:09:56+00:00 TIMEOUT | `desks/mt5/data/state_admission.json` | UNMEASURED | - | `UNMEASURED` | outcome=TIMEOUT |

## NEVER (126)

| organ | clock | last run | artifact | age | size | sha256 | published |
|---|---|---|---|---:|---:|---|---|
| `federation:aeon` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/aeon.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:causal_learn` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/causal_learn.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:dowhy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/dowhy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:dspy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/dspy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:easytpp` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/easytpp.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:featuretools` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/featuretools.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:kymatio` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/kymatio.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:mapie` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/mapie.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:nevergrad` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/nevergrad.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:openevolve` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/openevolve.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pgmpy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pgmpy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pydmd` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pydmd.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pyextremes` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pyextremes.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pymc` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pymc.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pymoo` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pymoo.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pysindy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pysindy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pysr` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pysr.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:pyvinecopulib` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/pyvinecopulib.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:quantconnect_cloud` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/quantconnect_cloud.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:quantrocket` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/quantrocket.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:ray` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/ray.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:reservoirpy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/reservoirpy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:ripser` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/ripser.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:river` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/river.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:roughpy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/roughpy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:ruptures` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/ruptures.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:sbi` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/sbi.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:scikit_mine` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/scikit_mine.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:stumpy` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/stumpy.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:tensorly` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/tensorly.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:tigramite` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/tigramite.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:tsfresh` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/tsfresh.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `federation:tslearn` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/data/intelligence/external_federation/tslearn.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:actor_atlas` | `hourly_cycle:actor_atlas` | UNMEASURED UNMEASURED | `desks/mt5/reports/ACTOR_ATLAS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:allocator_trigger` | `hourly_cycle:allocator_trigger` | UNMEASURED UNMEASURED | `desks/mt5/reports/ALLOCATOR_REACTION.json, desks/mt5/data/allocator_reactions.jsonl` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:artifact_chain` | `hourly_cycle:artifact_chain` | UNMEASURED UNMEASURED | `desks/mt5/data/research_artifacts.jsonl (append-only) + desks/mt5/reports/RESEARCH_ARTIFACTS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:attribution_reconcile` | `hourly_cycle:attribution_reconcile` | UNMEASURED UNMEASURED | `desks/mt5/reports/ATTRIBUTION_RECONCILE.json (beside desks/mt5/data/LIVE_SYSTEM_STATE.json)` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:axis_proposer` | `hourly_cycle:axis_proposer` | UNMEASURED UNMEASURED | `desks/mt5/reports/AXIS_PROPOSER.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:breadth_ladder` | `hourly_cycle:breadth_ladder` | UNMEASURED UNMEASURED | `desks/mt5/reports/BREADTH_LADDER.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:counterfactual_attribution` | `hourly_cycle:counterfactual_attribution` | UNMEASURED UNMEASURED | `desks/mt5/reports/COUNTERFACTUAL_ATTRIBUTION.json; desks/mt5/reports/WORLD_MODEL.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:data_scout` | `hourly_cycle:data_scout` | UNMEASURED UNMEASURED | `desks/mt5/reports/DATA_SCOUT.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:descendants` | `hourly_cycle:descendants` | UNMEASURED UNMEASURED | `desks/mt5/reports/DESCENDANTS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:dislocation_lab` | `hourly_cycle:dislocation_lab` | UNMEASURED UNMEASURED | `desks/mt5/reports/DISLOCATION_LAB.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:event_graph_lab` | `hourly_cycle:event_graph_lab` | UNMEASURED UNMEASURED | `desks/mt5/reports/EVENT_GRAPH.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:event_response_atlas` | `hourly_cycle:event_response_atlas` | UNMEASURED UNMEASURED | `desks/mt5/reports/COST_SURFACE.json (five-dimensional cost + NetAlpha) beside desks/mt5/data/cost_surface.json (the symbol x hour spread surface, unchanged)` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:event_sleeves` | `hourly_cycle:event_sleeves` | UNMEASURED UNMEASURED | `desks/mt5/data/event_sleeve_posteriors.json, desks/mt5/reports/EVENT_SLEEVES.json, desks/mt5/data/program_candidates.jsonl` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:event_surprise` | `hourly_cycle:event_surprise` | UNMEASURED UNMEASURED | `desks/mt5/reports/EVENT_SURPRISE.json; desks/mt5/reports/TREND_CORE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:expression_factory` | `hourly_cycle:expression_factory` | UNMEASURED UNMEASURED | `desks/mt5/reports/EXPRESSION_FACTORY.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:external_federation` | `hourly_cycle:external_federation` | UNMEASURED UNMEASURED | `desks/mt5/reports/EXTERNAL_FEDERATION.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:federation_ops` | `hourly_cycle:federation_ops` | UNMEASURED UNMEASURED | `desks/mt5/data/federation_registry.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:fence_battery` | `hourly_cycle:fence_battery` | UNMEASURED UNMEASURED | `desks/mt5/reports/BATTERY_FENCES.json and desks/mt5/reports/BATTERY_ORGANS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_africa` | `hourly_cycle:forest_africa` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_asean` | `hourly_cycle:forest_asean` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_china` | `hourly_cycle:forest_china` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_europe` | `hourly_cycle:forest_europe` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_global_web` | `hourly_cycle:forest_global_web` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_korea` | `hourly_cycle:forest_korea` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_latam` | `hourly_cycle:forest_latam` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_mena` | `hourly_cycle:forest_mena` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_north_america` | `hourly_cycle:forest_north_america` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_oceania` | `hourly_cycle:forest_oceania` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_russia_cis` | `hourly_cycle:forest_russia_cis` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:forest_south_asia` | `hourly_cycle:forest_south_asia` | UNMEASURED UNMEASURED | `desks/mt5/reports/FOREST_KOREA.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:hazard_engine` | `hourly_cycle:hazard_engine` | UNMEASURED UNMEASURED | `desks/mt5/reports/ALPHA_HAZARD.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:ingestion_exploitation` | `hourly_cycle:ingestion_exploitation` | UNMEASURED UNMEASURED | `desks/mt5/reports/INGESTION_EXPLOITATION.json; desks/mt5/reports/MACRO_INTELLIGENCE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:ingestion_ledger` | `hourly_cycle:ingestion_ledger` | UNMEASURED UNMEASURED | `desks/mt5/reports/INGESTION_EXPLOITATION.json; desks/mt5/reports/MACRO_INTELLIGENCE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:knowledge_graph` | `hourly_cycle:knowledge_graph` | UNMEASURED UNMEASURED | `desks/mt5/reports/KNOWLEDGE_GRAPH.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:lead_replication` | `hourly_cycle:lead_replication` | UNMEASURED UNMEASURED | `desks/mt5/reports/LEAD_REPLICATION.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:live_system_state` | `hourly_cycle:live_system_state` | UNMEASURED UNMEASURED | `desks/mt5/data/LIVE_SYSTEM_STATE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:loop_liveness` | `hourly_cycle:loop_liveness` | UNMEASURED UNMEASURED | `desks/mt5/reports/LOOP_LIVENESS.json; docs/research/LOOP_LIVENESS.md` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:macro_department` | `hourly_cycle:macro_department` | UNMEASURED UNMEASURED | `desks/mt5/reports/REGION_MACRO.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:macro_intelligence` | `hourly_cycle:macro_intelligence` | UNMEASURED UNMEASURED | `desks/mt5/reports/INGESTION_EXPLOITATION.json; desks/mt5/reports/MACRO_INTELLIGENCE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:macro_state_engine` | `hourly_cycle:macro_state_engine` | UNMEASURED UNMEASURED | `desks/mt5/reports/MACRO_STATE_ENGINE.json; desks/mt5/reports/EXPOSURE_DECOMPOSITION.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:market_constitution` | `hourly_cycle:market_constitution` | UNMEASURED UNMEASURED | `desks/mt5/reports/MARKET_CONSTITUTION.json (incl. the `constraints` counts); desks/mt5/data/rule_states/<venue>.parquet (JSON fallback beside it); desks/mt5/data/market_constraints.json (one row per registry symbol: sessions, halts, tick, margin, settlement, rule ids, unverified rows, status)` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:mining_objective` | `hourly_cycle:mining_objective` | UNMEASURED UNMEASURED | `desks/mt5/reports/MINING_OBJECTIVE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:moat_collectors` | `hourly_cycle:moat_collectors` | UNMEASURED UNMEASURED | `desks/mt5/reports/MOAT_COLLECTORS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:moat_series` | `hourly_cycle:moat_series` | UNMEASURED UNMEASURED | `desks/mt5/reports/MOAT_SERIES.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:news_event_stream` | `hourly_cycle:news_event_stream` | UNMEASURED UNMEASURED | `desks/mt5/reports/NEWS_EVENT_STREAM.json, desks/mt5/data/world_state.json, desks/mt5/data/allocator_resolve_request.json, desks/mt5/data/events/events.jsonl` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:paradigm_router` | `hourly_cycle:paradigm_router` | UNMEASURED UNMEASURED | `desks/mt5/reports/PARADIGM_ROUTER.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:qd_frontier` | `hourly_cycle:qd_frontier` | UNMEASURED UNMEASURED | `desks/mt5/reports/QD_FRONTIER.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:registry_sync` | `hourly_cycle:registry_sync` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_REGISTRY.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:replication_civilization` | `hourly_cycle:replication_civilization` | UNMEASURED UNMEASURED | `desks/mt5/reports/REPLICATION.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:research_api_status` | `hourly_cycle:research_api_status` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_API.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:research_artifacts` | `hourly_cycle:research_artifacts` | UNMEASURED UNMEASURED | `desks/mt5/data/research_artifacts.jsonl (append-only) + desks/mt5/reports/RESEARCH_ARTIFACTS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:research_dashboard` | `hourly_cycle:research_dashboard` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_DASHBOARD.json; docs/research/RESEARCH_DASHBOARD.md` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:research_departments` | `hourly_cycle:research_departments` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_DEPARTMENTS.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:research_os_archive` | `hourly_cycle:research_os_archive` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESEARCH_OS_ARCHIVE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:residual_queue` | `hourly_cycle:residual_queue` | UNMEASURED UNMEASURED | `desks/mt5/reports/RESIDUAL_QUEUE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:sares` | `hourly_cycle:sares` | UNMEASURED UNMEASURED | `desks/mt5/reports/SARES.json; desks/mt5/data/intelligence/sares/discoveries_<ts>.json; registry discoveries generator archaeology:sares:<agent>` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:science_controller` | `hourly_cycle:science_controller` | UNMEASURED UNMEASURED | `desks/mt5/reports/SCIENCE_CONTROLLER.json; research_candidates.genome_json / family_id / science_state` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:scout_swarm` | `hourly_cycle:scout_swarm` | UNMEASURED UNMEASURED | `desks/mt5/reports/SCOUT_SWARM.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:semantic_memory` | `hourly_cycle:semantic_memory` | UNMEASURED UNMEASURED | `desks/mt5/data/semantic_memory/manifest.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:source_frontier` | `hourly_cycle:source_frontier` | UNMEASURED UNMEASURED | `desks/mt5/reports/SOURCE_FRONTIER.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:synthetic_regimes` | `hourly_cycle:synthetic_regimes` | UNMEASURED UNMEASURED | `desks/mt5/reports/SYNTHETIC_REGIMES.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:trade_autopsy` | `hourly_cycle:trade_autopsy` | UNMEASURED UNMEASURED | `desks/mt5/data/autopsies.jsonl; desks/mt5/reports/TRADE_AUTOPSY.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:trajectory_evolution` | `hourly_cycle:trajectory_evolution` | UNMEASURED UNMEASURED | `desks/mt5/reports/TRAJECTORY_EVOLUTION.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:trend_core` | `hourly_cycle:trend_core` | UNMEASURED UNMEASURED | `desks/mt5/reports/EVENT_SURPRISE.json; desks/mt5/reports/TREND_CORE.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:unseen_frontier` | `hourly_cycle:unseen_frontier` | UNMEASURED UNMEASURED | `desks/mt5/reports/UNSEEN_FRONTIER.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:wiring_ceo` | `hourly_cycle:wiring_ceo` | UNMEASURED UNMEASURED | `desks/mt5/reports/ATTRIBUTION_RECONCILE.json (beside desks/mt5/data/LIVE_SYSTEM_STATE.json)` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `leg:world_model` | `hourly_cycle:world_model` | UNMEASURED UNMEASURED | `desks/mt5/reports/COUNTERFACTUAL_ATTRIBUTION.json; desks/mt5/reports/WORLD_MODEL.json` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_africa` | `MT5-Forest-Africa` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_africa.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_asean` | `MT5-Forest-Asean` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_asean.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_china` | `MT5-Forest-China` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_china.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_data` | `MT5-Dept-Data` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_data.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_discovery` | `MT5-Hourly` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_discovery.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_europe` | `MT5-Forest-Europe` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_europe.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_execution` | `MT5-Dept-Execution` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_execution.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_forward` | `MT5-Dept-Forward` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_forward.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_intel` | `MT5-Dept-Intel` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_intel.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_japan` | `MT5-Dept-Japan` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_japan.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_korea` | `MT5-Forest-Korea` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_korea.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_latam` | `MT5-Forest-Latam` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_latam.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_macro` | `MT5-Dept-Macro` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_macro.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_mathlab` | `MT5-Dept-Mathlab` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_mathlab.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_mena` | `MT5-Forest-Mena` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_mena.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_meta` | `MT5-Dept-Meta` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_meta.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_north_america` | `MT5-Forest-NorthAmerica` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_north_america.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_oceania` | `MT5-Forest-Oceania` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_oceania.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_regions` | `MT5-Dept-Regions` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_regions.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_rest` | `MT5-Dept-Rest` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_rest.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_russia_cis` | `MT5-Forest-RussiaCis` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_russia_cis.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_south_asia` | `MT5-Forest-SouthAsia` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_south_asia.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:dept_validate` | `MT5-Dept-Validate` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/dept_validate.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:moat_exploit` | `MT5-Moat-Exploit` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/moat_exploit.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:moat_explore` | `MT5-Moat-Explore` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/moat_explore.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |
| `resident:moat_resurrect` | `MT5-Moat-Resurrect` | UNMEASURED UNMEASURED | `desks/mt5/data/locks/moat_resurrect.lock` | UNMEASURED | - | `UNMEASURED` | UNMEASURED |

