# Institution design (derived)

> DERIVED by `scripts/build_institution_design.py --render` from the component registry, the hourly cycle's budgets, the experiment contracts and the capability graph. Never edit this file: change the code it reads and re-render. The hourly leg `institution_design` republishes the same content as `desks/mt5/reports/INSTITUTION_DESIGN.json` on the box.

Rendered from the tree at 2026-11-10T21:43:07+00:00.

## Interfaces

1455 registered components; 1035 declare outputs, 482 declare inputs, 466 name a consumer. Each component's full contract (inputs, outputs, consumers, owner, schedule, restart action, budget) is its row in `desks/mt5/ops/components.py`.

| owner | components | outputs | inputs |
|---|---:|---:|---:|
| `vps` | 323 | 104 | 32 |
| `UNMEASURED` | 322 | 274 | 122 |
| `department:rest` | 114 | 118 | 357 |
| `law_gate` | 82 | 82 | 0 |
| `batteries:organs` | 68 | 68 | 0 |
| `department:meta` | 63 | 68 | 196 |
| `daily_cycle` | 62 | 25 | 11 |
| `batteries:fences` | 44 | 44 | 0 |
| `department:intel` | 44 | 43 | 133 |
| `department:validate` | 42 | 50 | 131 |
| `department:discovery` | 40 | 41 | 130 |
| `department:data` | 37 | 37 | 117 |
| `lane:ops` | 35 | 13 | 14 |
| `department:macro` | 32 | 47 | 104 |
| `lane:research` | 32 | 7 | 16 |
| `department:forward` | 19 | 23 | 63 |
| `department:execution` | 19 | 28 | 73 |
| `lane:data` | 14 | 5 | 5 |
| `department:regions` | 10 | 10 | 27 |
| `lane:prop` | 10 | 5 | 0 |
| `department:mathlab` | 6 | 7 | 18 |
| `lane:money` | 4 | 1 | 0 |
| `git` | 3 | 0 | 0 |
| `moat` | 3 | 6 | 0 |
| `department:africa` | 2 | 2 | 3 |

## Timing

1453 components on a clock. Cadence classes: <=1d 404, <=1h 658, <=5m 24, UNMEASURED 369.

## State ownership

709 declared output paths; 612 have one owner and 97 are contested (below).

## Uncertainty

a component whose cadence is undeclared has an UNMEASURED max silence: nothing may call it late, and nothing may call it on time. 369 components carry an UNMEASURED max silence; 1108 declare a progress metric.

## Failure handling

Criticality: optional 1420, required 35. 1455 components declare a restart action, 0 do not.

## Resource budgets

427 hourly legs, 118 with an explicit budget and 3 with a floor; declared leg budgets sum to 340510 s (legs run on several plans and residents, so the sum is the hour's ceiling of declared budget, not its wall time).

## Contradictions and how each is resolved

106 contradictions: CONTESTED_STATE 97, DEAD_BUDGET 1, STALE_BY_DESIGN 8.

| class | resolution |
|---|---|
| CONTESTED_STATE | one owner per path: the capability graph's producer, else the first registered; every other writer takes its own filename |
| STALE_BY_DESIGN | the consumer's tolerance governs: raise the producer's clock or read the input as UNMEASURED past the producer's silence |
| BUDGET_BELOW_FLOOR | the floor wins (the organ's own stopping point; applied by hourly_cycle._producer_impl) |
| DEAD_BUDGET | remove the budget line: a leg the cycle never costs spends nothing |
| METRIC_DIRECTION | the objective (robust forward E[log W]) decides; both stand and the pair is named until it does |
| REGISTRY_PROBLEM | fix the registry entry: a declared component must be true |

| class | subject | parties |
|---|---|---|
| CONTESTED_STATE | `data/alpha_state_ledger.jsonl` | desks/mt5/research/promoter.py, desks/mt5/scripts/check_gold_live.py, scripts/run_conversion_control.py |
| CONTESTED_STATE | `data/breadth_expansion.jsonl` | scripts/breadth_expander.py, scripts/doctrine.py |
| CONTESTED_STATE | `data/claim_verification.json` | scripts/claim_escalate.py, scripts/claim_verifier.py |
| CONTESTED_STATE | `data/data_universe_map.json` | desks/mt5/research/cost_truth.py, desks/mt5/research/hourly_cycle.py, libs/ops/account_withhold.py, libs/research/microstructure_census.py |
| CONTESTED_STATE | `data/data_vitals.json` | scripts/data_vitals.py, scripts/stage_a_executor.py |
| CONTESTED_STATE | `data/denominators.json` | libs/ops/denominator.py, scripts/check_denominators.py |
| CONTESTED_STATE | `data/desk_code_parity.json` | scripts/check_desk_code_parity.py, scripts/fold_hash.py |
| CONTESTED_STATE | `data/desk_integrity.json` | scripts/check_universe_floor.py, scripts/run_desk_integrity.py |
| CONTESTED_STATE | `data/desk_module_drift.json` | desks/mt5/research/allocation.py, desks/mt5/research/conservation_ledger.py, desks/mt5/research/daily_research_os.py, desks/mt5/research/free_shadows.py, desks/mt5/research/live_ma |
| CONTESTED_STATE | `data/enforcement_matrix.json` | scripts/build_enforcement_matrix.py, scripts/check_doctrine_diff.py, scripts/derive_walcl_clock.py, scripts/harvest_rfb_vintages.py, scripts/run_execution_intel.py |
| CONTESTED_STATE | `data/law_gate.json` | desks/mt5/research/book_sizing.py, libs/ops/host_identity.py, libs/ops/repair_mode.py, libs/ops/state_publication.py, scripts/check_adoption_freshness.py, scripts/check_allocator_l |
| CONTESTED_STATE | `data/max_audit_report.json` | scripts/check_readiness.py, scripts/check_sync_launder.py, scripts/generate_external_review_doc.py, scripts/max_audit.py, scripts/measure_gate_histogram.py, scripts/ops_server.py,  |
| CONTESTED_STATE | `data/organ_readiness.json` | scripts/check_organ_readiness.py, scripts/mine_gate.py |
| CONTESTED_STATE | `data/ratchet_report.json` | scripts/check_mypy_ratchet.py, scripts/check_ratchets.py |
| CONTESTED_STATE | `data/research_review.json` | desks/mt5/research/diagnose.py, scripts/run_research_review.py |
| CONTESTED_STATE | `desks/mt5/data/LIVE_SYSTEM_STATE.json` | desks/mt5/mt5desk/release_identity.py, desks/mt5/ops/components.py, desks/mt5/research/attribution_reconcile.py, desks/mt5/research/counterfactual_markout.py, desks/mt5/research/li |
| CONTESTED_STATE | `desks/mt5/data/conversion_ledger.json` | desks/mt5/research/conversion_ledger.py, scripts/backfill_hypothesis_graph.py |
| CONTESTED_STATE | `desks/mt5/data/cost_surface.json` | desks/mt5/research/cost_surface.py, desks/mt5/research/cost_to_edge.py, desks/mt5/research/execution_twin.py, desks/mt5/research/fill_attribution.py |
| CONTESTED_STATE | `desks/mt5/data/events.jsonl` | desks/mt5/research/queue_census.py, desks/mt5/scripts/recertify_canon.py, libs/ops/queue_cycle.py |
| CONTESTED_STATE | `desks/mt5/data/forward_reconcile.json` | desks/mt5/research/forward_reconcile.py, desks/mt5/research/hourly_cycle.py |
| CONTESTED_STATE | `desks/mt5/data/hypotheses/miner_candidates.json` | desks/mt5/research/engine_registry.py, desks/mt5/research/hourly_cycle.py, libs/research/proposer_seat.py, scripts/kimi_hunter.py |
| CONTESTED_STATE | `desks/mt5/data/lake/series/fs_cnx_shfe.parquet` | desks/mt5/research/free_stack_hunter.py, desks/mt5/research/free_stack_proposer.py |
| CONTESTED_STATE | `desks/mt5/data/research_artifacts.jsonl` | desks/mt5/research/research_artifacts.py, scripts/verify_artifact_chain.py |
| CONTESTED_STATE | `desks/mt5/data/state_vector.json` | desks/mt5/research/macro_state_engine.py, desks/mt5/research/regime_monitor.py, desks/mt5/research/state_vector_build.py |
| CONTESTED_STATE | `desks/mt5/data/task_queue.jsonl` | desks/mt5/research/queue_census.py, desks/mt5/scripts/recertify_canon.py, libs/ops/queue_cycle.py |
| CONTESTED_STATE | `desks/mt5/data/trader_genome_priors.json` | desks/mt5/research/daily_cycle.py, libs/ops/six_event_trace.py, scripts/context.py |
| CONTESTED_STATE | `desks/mt5/data/universe/venue_history_depth.json` | desks/mt5/research/deepen_universe.py, desks/mt5/research/fetch_universe.py |
| CONTESTED_STATE | `desks/mt5/reports/ABSOLUTE_CEILING_STATUS.json` | desks/mt5/research/execution_intelligence.py, scripts/check_absolute_ceiling.py |
| CONTESTED_STATE | `desks/mt5/reports/ADVERSARY.json` | desks/mt5/research/adversary.py, desks/mt5/research/blind_reviewer.py, desks/mt5/research/hourly_cycle.py |
| CONTESTED_STATE | `desks/mt5/reports/ALPHA_CAPTURE.json` | desks/mt5/research/execution_alpha_miner.py, desks/mt5/research/net_edge_spine.py |
| CONTESTED_STATE | `desks/mt5/reports/ANOMALY_FACTORY.json` | desks/mt5/research/anomaly_factory.py, desks/mt5/research/multiplicity.py |
| CONTESTED_STATE | `desks/mt5/reports/ATTRIBUTION_RECONCILE.json` | desks/mt5/research/attribution_reconcile.py, desks/mt5/research/wiring_ceo.py, scripts/build_lesson_vault.py, scripts/learn.py, scripts/vault_mcp_server.py, scripts/vault_search.py |
| CONTESTED_STATE | `desks/mt5/reports/BATTERY_FENCES.json` | desks/mt5/research/batteries.py, desks/mt5/scripts/check_desk_health.py, desks/mt5/scripts/check_llm_seat.py, desks/mt5/scripts/disk_census.py, libs/ops/completion.py, scripts/audi |
| CONTESTED_STATE | `desks/mt5/reports/BATTERY_ORGANS.json` | desks/mt5/moat/moat_lifecycle.py, desks/mt5/research/asia_transmission.py, desks/mt5/research/axis_ingest_all.py, desks/mt5/research/batteries.py, desks/mt5/research/counterexample |
| CONTESTED_STATE | `desks/mt5/reports/BOX_HEARTBEAT.json` | desks/mt5/scripts/box_heartbeat.py, libs/ops/provenance.py |
| CONTESTED_STATE | `desks/mt5/reports/COEVOLUTION.json` | desks/mt5/research/factor_model_coevolution.py, desks/mt5/research/model_search.py |
| CONTESTED_STATE | `desks/mt5/reports/CONTROL_PLANE.json` | desks/mt5/research/control_plane.py, libs/ops/control_plane/reconciler.py |
| CONTESTED_STATE | `desks/mt5/reports/COST_TRUTH.json` | desks/mt5/research/cost_to_edge.py, desks/mt5/research/cost_truth.py, desks/mt5/research/execution_twin.py, desks/mt5/research/fill_attribution.py, libs/ops/account_withhold.py, li |
| CONTESTED_STATE | `desks/mt5/reports/COUNTERFACTUAL_ATTRIBUTION.json` | desks/mt5/research/counterfactual_attribution.py, desks/mt5/research/world_model.py |
| CONTESTED_STATE | `desks/mt5/reports/CREDIT_ASSIGNMENT.json` | desks/mt5/research/credit_assignment.py, desks/mt5/research/mutation_yield.py |
| CONTESTED_STATE | `desks/mt5/reports/DATA_SCOUT.json` | desks/mt5/research/data_scout.py, desks/mt5/research/fetch_alfred.py, desks/mt5/research/fetch_gld.py |
| CONTESTED_STATE | `desks/mt5/reports/DEEP_FOREST.json` | desks/mt5/research/deep_forest_miner.py, scripts/fetch_video_transcript.py |
| CONTESTED_STATE | `desks/mt5/reports/DESK_DASHBOARD_STATE.json` | desks/mt5/research/desk_dashboard_state.py, desks/mt5/research/macro_desk.py |
| CONTESTED_STATE | `desks/mt5/reports/DUTY_CYCLE.json` | desks/mt5/research/duty_cycle.py, scripts/check_duty_cycle.py |
| CONTESTED_STATE | `desks/mt5/reports/ENGINE_REGISTRY.json` | desks/mt5/research/engine_registry.py, desks/mt5/research/factor_residual_engine.py, libs/research/proposer_seat.py, scripts/kimi_hunter.py |
| CONTESTED_STATE | `desks/mt5/reports/EVENT_GRAPH.json` | desks/mt5/research/event_graph_lab.py, desks/mt5/research/futures_lead_lag.py |
| CONTESTED_STATE | `desks/mt5/reports/EVENT_RESPONSE_ATLAS.json` | desks/mt5/research/event_response_atlas.py, desks/mt5/research/hourly_cycle.py, desks/mt5/research/news_event_stream.py |
| CONTESTED_STATE | `desks/mt5/reports/EVENT_SURPRISE.json` | desks/mt5/research/event_response_atlas.py, desks/mt5/research/event_surprise.py, desks/mt5/research/hourly_cycle.py, desks/mt5/research/news_event_stream.py, desks/mt5/research/tr |
| CONTESTED_STATE | `desks/mt5/reports/EXECUTION_ALPHA.json` | desks/mt5/research/execution_alpha_miner.py, desks/mt5/research/net_edge_spine.py |
| CONTESTED_STATE | `desks/mt5/reports/EXECUTION_COST_SURFACE.json` | desks/mt5/research/cost_to_edge.py, desks/mt5/research/execution_twin.py, desks/mt5/research/fill_attribution.py |
| CONTESTED_STATE | `desks/mt5/reports/FEATURE_ROI.json` | desks/mt5/research/feature_roi.py, desks/mt5/research/research_org.py, libs/ops/allocators.py |
| CONTESTED_STATE | `desks/mt5/reports/FUND_PLAYBOOK.json` | desks/mt5/research/crowding_miner.py, desks/mt5/research/fetch_dukascopy.py, desks/mt5/research/fund_playbook.py |
| CONTESTED_STATE | `desks/mt5/reports/INGESTION_EXPLOITATION.json` | desks/mt5/research/ingestion_ledger.py, desks/mt5/research/macro_intelligence.py, scripts/check_ingestion_exploitation.py |
| CONTESTED_STATE | `desks/mt5/reports/ISSUE_BOARD.json` | desks/mt5/research/certificate_provenance.py, desks/mt5/research/issue_board.py, desks/mt5/scripts/check_enrolment_gap.py |
| CONTESTED_STATE | `desks/mt5/reports/JUDGE_COVERAGE.json` | desks/mt5/research/judge_coverage.py, scripts/check_judge_coverage.py |
| CONTESTED_STATE | `desks/mt5/reports/LAKE_PROMOTION.json` | desks/mt5/research/event_surprise.py, desks/mt5/research/lake_promote.py, scripts/check_pit_canaries.py, scripts/check_time_joins.py, scripts/collect_fred_macro.py |
| CONTESTED_STATE | `desks/mt5/reports/MACRO_INTELLIGENCE.json` | desks/mt5/research/ingestion_ledger.py, desks/mt5/research/macro_intelligence.py, scripts/check_ingestion_exploitation.py |
| CONTESTED_STATE | `desks/mt5/reports/MACRO_STATE_ENGINE.json` | desks/mt5/research/macro_state_engine.py, desks/mt5/research/regime_monitor.py |
| CONTESTED_STATE | `desks/mt5/reports/MOAT_FACTORY.json` | desks/mt5/research/discovery_compiler.py, desks/mt5/research/moat_candidate_compiler.py |
| CONTESTED_STATE | `desks/mt5/reports/MODEL_ROLE_BENCHMARK.json` | desks/mt5/research/counterexample_agent.py, desks/mt5/research/model_role_benchmark.py |
| CONTESTED_STATE | `desks/mt5/reports/MODEL_SELF_IMPROVEMENT.json` | desks/mt5/research/hourly_cycle.py, desks/mt5/research/model_self_improvement.py |
| CONTESTED_STATE | `desks/mt5/reports/MODEL_ZOO.json` | desks/mt5/research/hourly_cycle.py, desks/mt5/research/model_zoo.py |
| CONTESTED_STATE | `desks/mt5/reports/MODULE_RENT_RESEARCH.json` | desks/mt5/research/module_rent.py, desks/mt5/research/registry.py |
| CONTESTED_STATE | `desks/mt5/reports/MUTATION_YIELD.json` | desks/mt5/research/exit_study.py, libs/research/graveyard_model.py |
| CONTESTED_STATE | `desks/mt5/reports/NET_EDGE.json` | desks/mt5/research/execution_alpha_miner.py, desks/mt5/research/net_edge_spine.py |
| CONTESTED_STATE | `desks/mt5/reports/NIGHTLY_CATCHUP.json` | desks/mt5/research/nightly_catchup.py, desks/mt5/scripts/download_remaining.py, scripts/lessons.py |
| CONTESTED_STATE | `desks/mt5/reports/PIT_CENSUS.json` | desks/mt5/research/event_surprise.py, desks/mt5/research/lake_promote.py, scripts/check_pit.py, scripts/check_pit_canaries.py, scripts/check_time_joins.py, scripts/collect_fred_mac |
| CONTESTED_STATE | `desks/mt5/reports/PREREG_COVERAGE.json` | libs/ops/fence_exit.py, scripts/check_preregistration.py |
| CONTESTED_STATE | `desks/mt5/reports/QUEUE_CENSUS.json` | desks/mt5/research/queue_census.py, desks/mt5/scripts/recertify_canon.py, libs/ops/queue_cycle.py |
| CONTESTED_STATE | `desks/mt5/reports/REJUDGE_EVICTED.json` | desks/mt5/research/rejudge_evicted.py, desks/mt5/research/run_hunt16.py |
| CONTESTED_STATE | `desks/mt5/reports/RESEARCH_ARTIFACTS.json` | desks/mt5/research/research_artifacts.py, scripts/verify_artifact_chain.py |
| CONTESTED_STATE | `desks/mt5/reports/RESEARCH_BANDIT.json` | desks/mt5/research/factor_model_coevolution.py, desks/mt5/research/model_search.py, desks/mt5/research/search_paradigm_census.py |
| CONTESTED_STATE | `desks/mt5/reports/RESEARCH_ORG.json` | desks/mt5/research/counterexample_agent.py, desks/mt5/research/model_role_benchmark.py |
| CONTESTED_STATE | `desks/mt5/reports/RESEARCH_REGISTRY.json` | desks/mt5/research/moat_candidate_compiler.py, desks/mt5/research/registry_sync.py |
| CONTESTED_STATE | `desks/mt5/reports/RESIDUAL_GATE.json` | desks/mt5/research/orthogonality.py, desks/mt5/research/residual_gate_mount.py |
| CONTESTED_STATE | `desks/mt5/reports/SCALP_GAUNTLET.json` | desks/mt5/research/scalp_shadow.py, desks/mt5/scripts/scalp_gauntlet.py |
| CONTESTED_STATE | `desks/mt5/reports/SCOUT_ROSTER.json` | desks/mt5/research/cb_tone_screen.py, desks/mt5/research/fetch_fred.py, desks/mt5/research/placebo_test.py, desks/mt5/research/scout_roster.py |
| CONTESTED_STATE | `desks/mt5/reports/SOURCE_DRAIN.json` | desks/mt5/research/source_drain.py, desks/mt5/research/source_evig.py |
| CONTESTED_STATE | `desks/mt5/reports/SOURCE_REGISTRY.json` | desks/mt5/research/source_registry.py, desks/mt5/side_channels/world_crawler.py |
| CONTESTED_STATE | `desks/mt5/reports/SPREAD_PROVENANCE.json` | desks/mt5/research/fusion_spread_tape.py, desks/mt5/scripts/repair_universe_spreads.py |
| CONTESTED_STATE | `desks/mt5/reports/STANDING_QUESTIONS.json` | desks/mt5/research/hourly_cycle.py, desks/mt5/research/standing_questions.py, desks/mt5/research/unknown_unknowns.py |
| CONTESTED_STATE | `desks/mt5/reports/TICK_INTEGRITY.json` | desks/mt5/moat/moat_fence.py, desks/mt5/recorders/tick_integrity.py |
| CONTESTED_STATE | `desks/mt5/reports/TRADER_GENOME.json` | desks/mt5/research/daily_cycle.py, libs/ops/six_event_trace.py, scripts/context.py |
| CONTESTED_STATE | `desks/mt5/reports/TRIAL_ALLOCATION.json` | desks/mt5/research/trial_allocator.py, libs/ops/module_rent.py |
| CONTESTED_STATE | `desks/mt5/reports/WORLD_CAUSAL_GRAPH.json` | desks/mt5/research/event_graph_lab.py, desks/mt5/research/futures_lead_lag.py, desks/mt5/research/world_causal_graph.py |
| CONTESTED_STATE | `desks/mt5/reports/WORLD_MODEL.json` | desks/mt5/research/counterfactual_attribution.py, desks/mt5/research/world_model.py |
| CONTESTED_STATE | `desks/mt5/reports/aurum_findings.jsonl` | desks/mt5/research/export_aurum_findings.py, desks/mt5/research/run_cot_macro_sweep.py, desks/mt5/research/run_dip_buy_sweep.py, desks/mt5/research/run_macro_swing_sweep.py |
| CONTESTED_STATE | `desks/mt5/reports/dataset_acquisition.json` | desks/mt5/research/acquire_datasets.py, scripts/read_xls.py |
| CONTESTED_STATE | `desks/mt5/reports/execution_quality.json` | desks/mt5/research/cost_to_edge.py, desks/mt5/research/cost_truth.py, desks/mt5/research/execution_twin.py, desks/mt5/research/fill_attribution.py, libs/ops/account_withhold.py, li |
| CONTESTED_STATE | `desks/mt5/reports/factor_residual.json` | desks/mt5/research/orthogonality.py, desks/mt5/research/residual_gate_mount.py |
| CONTESTED_STATE | `desks/mt5/reports/hour_surface.json` | desks/mt5/research/event_response_atlas.py, desks/mt5/research/hourly_cycle.py, desks/mt5/research/news_event_stream.py |
| CONTESTED_STATE | `desks/mt5/reports/pf_allocation.json` | desks/mt5/research/alpha_breadth.py, desks/mt5/research/pf_allocator.py, desks/mt5/research/portfolio_projection.py, desks/mt5/research/run_hunt17.py, scripts/check_allocator_join. |
| CONTESTED_STATE | `desks/mt5/reports/pyramid_sweep.json` | desks/mt5/research/pyramid_sweep.py, desks/mt5/research/run_hunt11.py |
| CONTESTED_STATE | `desks/mt5/reports/shadow/shadow_health.json` | desks/mt5/research/external_shadow.py, desks/mt5/research/fetch_gold_scalp.py, desks/mt5/research/shadow_cycle.py |
| CONTESTED_STATE | `reports/admission_power.json` | scripts/audit_gate_power.py, scripts/measure_admission_power.py |
| CONTESTED_STATE | `web/desk_state.json` | desks/mt5/research/hourly_cycle.py, scripts/build_zentech_state.py |
| CONTESTED_STATE | `web/intelligence_cycle.json` | libs/ops/intelligence_inputs.py, scripts/run_intelligence_cycle.py |
| STALE_BY_DESIGN | `exe:desks/mt5/scripts/judge_stall_pager.py` | leg:judging_throughput, exe:desks/mt5/scripts/judge_stall_pager.py |
| STALE_BY_DESIGN | `exe:desks/mt5/scripts/judge_stall_pager.py` | leg:external_gauntlet, exe:desks/mt5/scripts/judge_stall_pager.py |
| STALE_BY_DESIGN | `leg:external_gauntlet` | executable:desks/mt5/scripts/scalp_gauntlet.py, leg:external_gauntlet |
| STALE_BY_DESIGN | `leg:promoter` | systemd:quant-recertify-canon.timer, leg:promoter |
| STALE_BY_DESIGN | `systemd:quant-external-pipeline.timer` | executable:desks/mt5/scripts/scalp_gauntlet.py, systemd:quant-external-pipeline.timer |
| STALE_BY_DESIGN | `task:MT5-AllocatorFast` | leg:macro_state_engine, task:MT5-AllocatorFast |
| STALE_BY_DESIGN | `task:MT5-AllocatorFast` | leg:capacity, task:MT5-AllocatorFast |
| STALE_BY_DESIGN | `task:MT5-AllocatorFast` | leg:state_admission, task:MT5-AllocatorFast |
| DEAD_BUDGET | `deep_forest_miner` | 1020s |
