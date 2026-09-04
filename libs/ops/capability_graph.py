"""The desk's producers, artifacts and consumers, as a graph a machine can check.

THE DEFECT CLASS THIS EXISTS FOR, in this repository's own words from one afternoon:

    the deepening queue had no reader
    session state was computed and not passed to the solve
    the optimiser's per-sleeve weights were solved and not what sized the book
    factor exposure was measured and did not bind breadth
    execution slippage was captured and the attribution never read it
    the shadow sync committed and did not push
    coverage measured the old money path

Not one of those was a missing capability. Every one was a capability that existed and could not
be reached from a decision. A reviewer can find that class once; a graph can find it every
commit.

WHAT A NODE DECLARES. Each component names the artifacts it WRITES and READS, and whether it
holds AUTHORITY -- can change a position, a size, a certificate, or what may condition capital.
Artifacts are file paths. Declarations are checked against the code: a node that declares a
write must contain the path literal, and a path literal in a node's source that no node declares
is reported as UNDECLARED so the graph cannot drift silently from the code it describes.

THE CHECKS, each of which has already cost this desk something:

    DEAD_PRODUCER        an artifact is written and nothing reads it
    DEAD_CONSUMER        an artifact is read and nothing writes it
    ADVISORY_ONLY        a node writes artifacts that only report-writers read; it computes and
                         nothing decides on it
    UNMEASURED_AUTHORITY a node conditions capital on a state dimension the admission report has
                         not judged, or that it has buried
    STALE_DECISION       an authority node reads an artifact older than its freshness SLA
    UNDECLARED           a path literal in the source that the graph does not know

The checker runs in CI and fails on any of the first four. Freshness is checked at runtime by
`generate_status`, which writes the generated-truth files the audit asked for:

    reports/CAPABILITY_STATUS.json   every node, its edges, its check results
    reports/LIVE_REACHABILITY.json   which artifacts reach an authority node, and by what path
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

#: Artifacts whose only purpose is to be read by a person. A node that feeds only these is
#: ADVISORY_ONLY unless it also holds authority itself.
REPORT_PREFIXES = ("reports/",)


@dataclass(frozen=True)
class Node:
    name: str
    module: str                        # path relative to ROOT
    writes: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    #: What this node may change. Empty means it decides nothing on its own.
    authority: tuple[str, ...] = ()
    #: Seconds an authority node may tolerate on an input before its decision is STALE.
    freshness_s: dict[str, int] = field(default_factory=dict)
    #: State dimensions this node conditions capital on; each must be admitted.
    conditions_on: tuple[str, ...] = ()


#: THE GRAPH. Every path is relative to ROOT. Adding a component means adding it here, and the
#: UNDECLARED check is what forces that: a new writer of a new path shows up red until named.
NODES: tuple[Node, ...] = (
    Node("miner_candidate_compiler", "desks/mt5/research/miner_candidate_compiler.py",
         writes=("desks/mt5/data/hypotheses/miner_candidates.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json",
                 "desks/mt5/data/hypothesis_graph.jsonl"),
         reads=("desks/mt5/data/intelligence/", "desks/mt5/reports/universal_gates_external.json")),
    Node("deepening_worker", "desks/mt5/research/deepening_worker.py",
         writes=("desks/mt5/data/hypotheses/deepening_worked.jsonl",
                 "desks/mt5/data/hypotheses/deepened_candidates.json"),
         reads=("desks/mt5/data/hypotheses/miner_deepening_queue.json",
                "desks/mt5/data/hypothesis_graph.jsonl")),
    Node("factor_residual_engine", "desks/mt5/research/factor_residual_engine.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/factor_residual.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("plumbing_miner", "desks/mt5/research/plumbing_miner.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/plumbing_miner.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("transition_alpha", "desks/mt5/research/transition_alpha.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/transition_alpha.json"),
         reads=("desks/mt5/data/universe/",)),
    Node("weak_signal_compiler", "desks/mt5/research/weak_signal_compiler.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/weak_signal_compiler.json"),
         reads=("desks/mt5/reports/universal_gates_external.json", "desks/mt5/data/universe/")),
    Node("fund_playbook", "desks/mt5/research/fund_playbook.py",
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/FUND_PLAYBOOK.json",
                 "desks/mt5/data/hypothesis_graph.jsonl")),
    Node("external_gauntlet", "desks/mt5/scripts/external_gauntlet.py",
         writes=("desks/mt5/reports/universal_gates_external.json",),
         reads=("desks/mt5/data/hypotheses/miner_candidates.json", "desks/mt5/data/universe/"),
         authority=("certificate",)),
    Node("universal_gate", "desks/mt5/research/universal_gate.py",
         writes=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         reads=("desks/mt5/data/universe/",), authority=("certificate",)),
    Node("shadow_forward", "desks/mt5/research/shadow_forward.py",
         writes=("desks/mt5/reports/shadow/",),
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json", "desks/mt5/data/universe/")),
    Node("promoter", "desks/mt5/research/promoter.py",
         writes=("desks/mt5/data/sleeve_registry.json",),
         reads=("desks/mt5/reports/shadow/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         authority=("promotion",)),
    Node("state_vector_build", "desks/mt5/research/state_vector_build.py",
         writes=("desks/mt5/data/state_vector.json", "desks/mt5/data/state_fits.json"),
         reads=("desks/mt5/data/universe/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/intelligence/ff_calendar_vintage",
                "desks/mt5/data/state_fits.json")),
    Node("state_admission_run", "desks/mt5/research/state_admission_run.py",
         writes=("desks/mt5/reports/STATE_ADMISSION.json",),
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/live_ledger.jsonl"),
         authority=("conditioning",)),
    Node("pf_allocator", "desks/mt5/research/pf_allocator.py",
         writes=("desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/pf_forecast_log.jsonl",
                 "desks/mt5/reports/pf_allocator.json", "desks/mt5/reports/pf_allocation.json",
                 "desks/mt5/data/capital_modifier_ledger.jsonl"),
         reads=("desks/mt5/data/state_vector.json", "desks/mt5/reports/STATE_ADMISSION.json",
                "backups/moat/shadow_ledgers/", "desks/mt5/data/universe/",
                "desks/mt5/reports/hunt12_partial.json", "desks/mt5/data/rail_calibration.json"),
         authority=("sizing",),
         freshness_s={"desks/mt5/data/state_vector.json": 2 * 3600,
                      "desks/mt5/reports/STATE_ADMISSION.json": 3 * 24 * 3600},
         conditions_on=("session", "event", "weekday")),
    Node("gateway", "desks/mt5/mt5desk/gateway.py",
         writes=("desks/mt5/data/gateway_state.json", "desks/mt5/data/order_intents.jsonl",
                 "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/decision_ledger.jsonl",
                 # via research.session_phase._record_broker_clock, from the live terminal
                 "desks/mt5/data/broker_clock.json"),
         reads=("desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/sleeve_registry.json",
                "desks/mt5/data/state_vector.json", "desks/mt5/data/regime_state.json",
                "desks/mt5/reports/pf_allocation.json", "desks/mt5/data/RELEASE.json"),
         authority=("position", "size"),
         freshness_s={"desks/mt5/reports/ALLOCATOR_PROOF.json": 26 * 3600}),
    # THE GROWTH GOVERNANCE LOOP: every rail billed daily, tunable rails calibrated toward
    # growth, the AI capital modifier's categories scored against what they claimed.
    Node("missed_growth", "desks/mt5/research/missed_growth.py",
         reads=("desks/mt5/reports/pf_allocation.json", "desks/mt5/reports/FILTER_VALUE.json",
                "desks/mt5/reports/STATE_ADMISSION.json"),
         writes=("desks/mt5/reports/MISSED_GROWTH.json", "desks/mt5/data/missed_growth.jsonl",
                 "desks/mt5/data/rail_calibration.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("capital_modifier_score", "desks/mt5/research/capital_modifier_score.py",
         reads=("desks/mt5/data/capital_modifier_ledger.jsonl", "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/CAPITAL_MODIFIERS.json",)),
    # EXECUTION INTELLIGENCE AND THE RELEASE: the learned fill/slip surface every cost consumer
    # shares, the netting measurement, and the one live SHA every decision is stamped with.
    Node("fill_surface", "desks/mt5/mt5desk/fill_surface.py",
         reads=("desks/mt5/data/order_intents.jsonl", "desks/mt5/reports/markout.json"),
         writes=("desks/mt5/reports/FILL_SURFACE.json",)),
    Node("netting", "desks/mt5/mt5desk/netting.py",
         reads=("desks/mt5/data/order_intents.jsonl",),
         writes=("desks/mt5/reports/NETTING.json",)),
    Node("release", "libs/ops/release.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         writes=("desks/mt5/data/RELEASE.json",)),
    # THE PROPRIETARY-DATA FLYWHEEL: every decision the desk made, taken or not, priced after the
    # fact and fed back as research targets. None of these nodes has authority; each feeds one.
    Node("counterfactual_markout", "desks/mt5/research/counterfactual_markout.py",
         reads=("desks/mt5/data/decision_ledger.jsonl", "desks/mt5/data/universe/"),
         writes=("desks/mt5/data/counterfactuals.jsonl", "desks/mt5/reports/FILTER_VALUE.json")),
    Node("excursions", "desks/mt5/research/excursions.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/universe/"),
         writes=("desks/mt5/data/excursions.jsonl", "desks/mt5/reports/EXCURSIONS.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("alpha_genome", "desks/mt5/research/alpha_genome.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",),
         writes=("desks/mt5/reports/ALPHA_GENOME.json",)),
    Node("opportunity_curve", "desks/mt5/research/opportunity_curve.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/broker_clock.json"),
         writes=("desks/mt5/reports/OPPORTUNITY_CURVE.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("microstructure_miner", "desks/mt5/research/microstructure_miner.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/data/intelligence/", "desks/mt5/reports/MICROSTRUCTURE_SURFACES.json",
                 "desks/mt5/reports/microstructure_miner.json")),
    Node("markout", "desks/mt5/mt5desk/markout.py",
         reads=("desks/mt5/data/order_intents.jsonl", "desks/mt5/data/live_ledger.jsonl"),
         writes=("desks/mt5/reports/markout.json",)),
    Node("allocator_attribution", "desks/mt5/research/allocator_attribution.py",
         reads=("desks/mt5/data/pf_forecast_log.jsonl", "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/order_intents.jsonl",
                # the growth decomposition (2026-09-04) reads every term's own ledger
                "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/reports/pf_allocation.json",
                "desks/mt5/reports/EXIT_ACCOUNTS.json", "desks/mt5/reports/FILL_SURFACE.json",
                "desks/mt5/reports/FILTER_VALUE.json", "desks/mt5/reports/MISSED_GROWTH.json"),
         writes=("desks/mt5/reports/allocator_attribution.json",)),
    Node("regime_monitor", "desks/mt5/research/regime_monitor.py",
         reads=("desks/mt5/data/live_ledger.jsonl", "desks/mt5/reports/shadow/",
                "desks/mt5/reports/FILTER_VALUE.json"),
         writes=("desks/mt5/data/regime_state.json",), authority=("hibernate",)),
    Node("regime_coverage", "desks/mt5/research/regime_coverage.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/reports/ALPHA_GENOME.json"),
         writes=("desks/mt5/reports/REGIME_COVERAGE.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("resurrection", "desks/mt5/research/resurrection.py",
         reads=("desks/mt5/data/regime_state.json", "desks/mt5/data/state_vector.json",
                "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/RESURRECTION.json",)),
    Node("data_prospector", "desks/mt5/research/data_prospector.py",
         reads=("desks/mt5/reports/REGIME_COVERAGE.json", "desks/mt5/data/state_vector.json"),
         writes=("desks/mt5/reports/DATA_PROSPECTOR.json",
                 "desks/mt5/data/prospector_targets.json")),
    Node("research_productivity", "desks/mt5/research/research_productivity.py",
         reads=("desks/mt5/data/hypotheses/deepening_worked.jsonl",
                "desks/mt5/data/hypotheses/miner_candidates.json",
                "desks/mt5/data/hypotheses/miner_deepening_queue.json",
                "desks/mt5/reports/universal_gates_external.json",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",)),
    Node("live_manifest", "desks/mt5/research/live_manifest.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/reports/ALLOCATOR_PROOF.json", "desks/mt5/data/gateway_state.json",
                "desks/mt5/data/state_vector.json", "desks/mt5/reports/STATE_ADMISSION.json",
                "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/data/LIVE_MANIFEST.jsonl",)),
    # ---- THE DISCOVERY LOOP (2026-09-04): proposers, miners, feedback engines -----------------
    # Every proposer donates through proposer_common.donate into the intelligence intake the
    # compiler merges; every miner writes deepening tasks; every feedback engine writes a report
    # a person reads AND a queue row the worker reads. Declared so a producer nobody consumes
    # shows up red rather than looking busy.
    Node("alpha_evolution", "desks/mt5/research/alpha_evolution.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                "desks/mt5/data/generator_weights.json"),
         writes=("desks/mt5/reports/alpha_evolution.json",
                 "desks/mt5/data/intelligence/alpha_evolution/")),
    Node("style_premia_sweep", "desks/mt5/research/style_premia_sweep.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/reports/style_premia_sweep.json",
                 "desks/mt5/data/intelligence/style_premia/")),
    Node("cross_asset_graph", "desks/mt5/research/cross_asset_graph.py",
         reads=("desks/mt5/data/universe/",),
         writes=("desks/mt5/reports/CROSS_ASSET_GRAPH.json",
                 "desks/mt5/data/intelligence/cross_asset_graph/")),
    Node("tail_alpha_search", "desks/mt5/research/tail_alpha_search.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/"),
         writes=("desks/mt5/reports/tail_alpha_search.json",
                 "desks/mt5/data/intelligence/tail_alpha/")),
    Node("anomaly_factory", "desks/mt5/research/anomaly_factory.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/intelligence/anomalies/",
                "desks/mt5/data/intelligence/anomaly_cursor.json", "desks/mt5/data/acquired/"),
         writes=("desks/mt5/reports/ANOMALY_FACTORY.json",
                 "desks/mt5/data/intelligence/anomaly_factory/",
                 "desks/mt5/data/intelligence/anomalies/",
                 "desks/mt5/data/intelligence/anomaly_cursor.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("survivor_distiller", "desks/mt5/research/survivor_distiller.py",
         reads=("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/mutation_operator_weights.json"),
         writes=("desks/mt5/reports/SURVIVOR_DISTILLER.json",
                 "desks/mt5/data/intelligence/survivor_distiller/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("factor_model_coevolution", "desks/mt5/research/factor_model_coevolution.py",
         reads=("desks/mt5/data/universe/", "desks/mt5/data/features/",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/COEVOLUTION.json", "desks/mt5/data/coevolution_trials.jsonl",
                 "desks/mt5/data/features/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("repo_miner", "desks/mt5/research/repo_miner.py",
         reads=("desks/mt5/data/repo_watchlist.json", "desks/mt5/data/repo_cache/"),
         writes=("desks/mt5/reports/REPO_MINER.json", "desks/mt5/data/repo_cache/",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("deep_forest_miner", "desks/mt5/research/deep_forest_miner.py",
         reads=("desks/mt5/data/deep_forest_sources.json",
                "desks/mt5/data/deep_forest_claims.jsonl",
                "desks/mt5/data/deep_forest_seen.json", "desks/mt5/data/universe/universe.json",
                "desks/mt5/data/hypotheses/deepening_worked.jsonl"),
         writes=("desks/mt5/reports/DEEP_FOREST.json", "desks/mt5/data/deep_forest_claims.jsonl",
                 "desks/mt5/data/deep_forest_seen.json",
                 "desks/mt5/data/intelligence/world/frontier.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("revival_engine", "desks/mt5/research/revival_engine.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl", "desks/mt5/reports/DRIFT.json",
                "desks/mt5/reports/REGIME_COVERAGE.json", "desks/mt5/reports/FILL_SURFACE.json"),
         writes=("desks/mt5/reports/REVIVAL.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("drift_monitor", "desks/mt5/research/drift_monitor.py",
         reads=("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                "desks/mt5/reports/shadow/", "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"),
         writes=("desks/mt5/reports/DRIFT.json",)),
    Node("exit_accounts", "desks/mt5/research/exit_accounts.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/excursions.jsonl",
                "desks/mt5/data/live_ledger.jsonl", "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/reports/EXIT_ACCOUNTS.json",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("action_counterfactuals", "desks/mt5/research/action_counterfactuals.py",
         reads=("backups/moat/shadow_ledgers/", "desks/mt5/data/live_ledger.jsonl",
                "desks/mt5/data/pf_forecast_log.jsonl", "desks/mt5/data/universe/"),
         writes=("desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
                 "desks/mt5/data/action_counterfactuals.jsonl",
                 "desks/mt5/data/hypotheses/miner_deepening_queue.json")),
    Node("research_pnl", "desks/mt5/research/research_pnl.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/data/pf_forecast_log.jsonl"),
         writes=("desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/data/research_marginal.json")),
    Node("mutation_yield", "desks/mt5/research/mutation_yield.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/intelligence/survivor_distiller/"),
         writes=("desks/mt5/reports/MUTATION_YIELD.json",
                 "desks/mt5/data/mutation_operator_weights.json",
                 "desks/mt5/data/generator_weights.json")),
    Node("research_memory", "libs/research/memory.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl",
                "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
                "desks/mt5/reports/FILL_SURFACE.json", "desks/mt5/reports/NETTING.json",
                "desks/mt5/reports/REGIME_COVERAGE.json", "docs/graveyard.md",
                "docs/research/search_operator_library.md", "docs/GROWTH_GOVERNANCE.md"),
         writes=("desks/mt5/data/memory/",)),
    Node("research_bandit", "desks/mt5/research/research_bandit.py",
         reads=("desks/mt5/data/hypothesis_graph.jsonl", "desks/mt5/data/research_marginal.json"),
         writes=("desks/mt5/data/research_budget.json",
                 "desks/mt5/reports/RESEARCH_BANDIT.json")),
)

#: Artifacts a person is expected to read. Being the ONLY reader of a node's output makes that
#: node advisory. Listed so the check has a definition rather than an opinion.
HUMAN_READ = frozenset({
    "desks/mt5/reports/markout.json", "desks/mt5/reports/allocator_attribution.json",
    "desks/mt5/reports/RESURRECTION.json", "desks/mt5/reports/DATA_PROSPECTOR.json",
    "desks/mt5/data/LIVE_MANIFEST.jsonl", "desks/mt5/reports/factor_residual.json",
    "desks/mt5/reports/plumbing_miner.json", "desks/mt5/reports/transition_alpha.json",
    "desks/mt5/reports/weak_signal_compiler.json", "desks/mt5/reports/FUND_PLAYBOOK.json",
    "desks/mt5/reports/pf_allocator.json", "desks/mt5/reports/REGIME_COVERAGE.json",
    "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json", "desks/mt5/reports/FILTER_VALUE.json",
    "desks/mt5/reports/EXCURSIONS.json", "desks/mt5/reports/ALPHA_GENOME.json",
    "desks/mt5/reports/OPPORTUNITY_CURVE.json", "desks/mt5/reports/MICROSTRUCTURE_SURFACES.json",
    "desks/mt5/reports/microstructure_miner.json", "desks/mt5/reports/MISSED_GROWTH.json",
    "desks/mt5/reports/CAPITAL_MODIFIERS.json", "desks/mt5/reports/FILL_SURFACE.json",
    "desks/mt5/reports/NETTING.json",
    "desks/mt5/reports/alpha_evolution.json", "desks/mt5/reports/style_premia_sweep.json",
    "desks/mt5/reports/CROSS_ASSET_GRAPH.json", "desks/mt5/reports/tail_alpha_search.json",
    "desks/mt5/reports/ANOMALY_FACTORY.json", "desks/mt5/reports/SURVIVOR_DISTILLER.json",
    "desks/mt5/reports/COEVOLUTION.json", "desks/mt5/reports/REPO_MINER.json",
    "desks/mt5/reports/DEEP_FOREST.json", "desks/mt5/reports/REVIVAL.json",
    "desks/mt5/reports/EXIT_ACCOUNTS.json", "desks/mt5/reports/ACTION_COUNTERFACTUALS.json",
    "desks/mt5/reports/RESEARCH_PNL.json", "desks/mt5/reports/MUTATION_YIELD.json",
    "desks/mt5/reports/RESEARCH_BANDIT.json",
})

#: Consumers outside this graph that are known to read an artifact -- the crawler reads the
#: prospector's targets, the box's PowerShell reads the manifest. DECLARED, so a DEAD_PRODUCER
#: verdict cannot be silenced by an unnamed "something reads it".
EXTERNAL_READERS = {
    "desks/mt5/data/prospector_targets.json": "world_crawler (side_channels)",
    "desks/mt5/data/hypotheses/deepened_candidates.json": "external_gauntlet via compiler merge",
    "desks/mt5/data/state_fits.json": "state_vector_build (its own cache)",
    # Append-only ledgers that are their own memory: each engine reads back what it wrote so
    # a decision is priced exactly once. Self-reads are not counted as readers by `check`.
    "desks/mt5/data/counterfactuals.jsonl": "counterfactual_markout (its own append-only memory)",
    "desks/mt5/data/excursions.jsonl": "excursions (its own append-only memory)",
    "desks/mt5/data/missed_growth.jsonl": "missed_growth (its own append-only memory)",
    "desks/mt5/data/action_counterfactuals.jsonl": "action_counterfactuals (its own memory)",
    "desks/mt5/data/deep_forest_claims.jsonl": "deep_forest_miner (its own append-only memory)",
    "desks/mt5/data/deep_forest_seen.json": "deep_forest_miner (its own seen-ledger)",
    "desks/mt5/data/intelligence/anomaly_cursor.json": "anomaly_miner (its own rotation cursor)",
    "desks/mt5/data/memory/": "deepening_worker.task_text (memory.prompt_context on every prompt)",
    "desks/mt5/data/research_budget.json": ("daily_cycle proposer budgets and deepening_worker "
                                            "voi_order, through bandit.arm_weight"),
    "desks/mt5/data/coevolution_trials.jsonl": "experiment_ledger (lifetime multiplicity)",
    "desks/mt5/data/intelligence/world/frontier.json": "world_crawler (side_channels)",
    "desks/mt5/data/repo_cache/": "repo_miner (its own cache)",
    "desks/mt5/data/intelligence/alpha_evolution/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/style_premia/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/cross_asset_graph/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/tail_alpha/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/anomaly_factory/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/intelligence/survivor_distiller/": "miner_candidate_compiler intake glob",
    "desks/mt5/data/features/": "feature_store (content-addressed cache)",
}

_PATH_RE = re.compile(r"[\"']((?:desks/mt5/|backups/|reports/|data/)[A-Za-z0-9_./-]+)[\"']")


def _covers(declared: str, path: str) -> bool:
    return path == declared or (declared.endswith("/") and path.startswith(declared))


#: Hand-maintained inputs: written by a person (or by the box's universe fetch), read by nodes.
#: Declared so a DEAD_CONSUMER verdict cannot be silenced by an unnamed "somebody writes it".
CONFIG_INPUTS = frozenset({
    "desks/mt5/data/repo_watchlist.json", "desks/mt5/data/deep_forest_sources.json",
    "desks/mt5/data/universe/universe.json",
    # Box-produced inputs: acquire_datasets fills this from the prospector's targets.
    "desks/mt5/data/acquired/",
    # Hand-written doctrine the research memory ingests as method and failure memories.
    "docs/graveyard.md", "docs/research/search_operator_library.md", "docs/GROWTH_GOVERNANCE.md",
})

MAX_DECISION_DEPTH = 5


def _decision_paths(start: Node, nodes: tuple[Node, ...],
                    read_by: Any) -> set[str]:
    """Chains from `start`'s outputs to an authority node or a declared external reader."""
    by_name = {x.name: x for x in nodes}
    found: set[str] = set()
    frontier: list[tuple[Node, str]] = [(start, start.name)]
    seen: set[str] = {start.name}
    depth = 0
    while frontier and depth < MAX_DECISION_DEPTH:
        nxt: list[tuple[Node, str]] = []
        for node, path in frontier:
            for w in node.writes:
                if w in EXTERNAL_READERS:
                    found.add(f"{path}->{EXTERNAL_READERS[w]}")
                for name in read_by(w):
                    reader = by_name.get(name)
                    if reader is None or name == node.name:
                        continue
                    if reader.authority:
                        found.add(f"{path}->{name}")
                    elif name not in seen:
                        seen.add(name)
                        nxt.append((reader, f"{path}->{name}"))
        frontier = nxt
        depth += 1
    return found


def check(nodes: tuple[Node, ...] = NODES) -> dict[str, Any]:
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for n in nodes:
        for w in n.writes:
            writers.setdefault(w, []).append(n.name)
        for r in n.reads:
            readers.setdefault(r, []).append(n.name)

    def _read_by(artifact: str) -> list[str]:
        out = []
        for r, names in readers.items():
            if _covers(r, artifact) or _covers(artifact, r):
                out.extend(names)
        return sorted(set(out))

    def _written_by(artifact: str) -> list[str]:
        out = []
        for w, names in writers.items():
            if _covers(w, artifact) or _covers(artifact, w):
                out.extend(names)
        return sorted(set(out))

    findings: list[dict[str, str]] = []
    for n in nodes:
        for w in n.writes:
            rd = [x for x in _read_by(w) if x != n.name]
            if not rd and w not in HUMAN_READ and w not in EXTERNAL_READERS:
                findings.append({"check": "DEAD_PRODUCER", "node": n.name, "artifact": w,
                                 "why": "written and read by nothing in the graph"})
        for r in n.reads:
            box_only = ("desks/mt5/data/universe/", "backups/moat/shadow_ledgers/",
                        "desks/mt5/data/intelligence/",
                        "desks/mt5/data/intelligence/ff_calendar_vintage",
                        "desks/mt5/reports/hunt12_partial.json")
            if (not _written_by(r) and not (r.endswith("/") and (ROOT / r).exists())
                    and r not in box_only and r not in CONFIG_INPUTS):
                findings.append({"check": "DEAD_CONSUMER", "node": n.name, "artifact": r,
                                 "why": "read and written by nothing in the graph"})
        if n.writes and not n.authority:
            # A producer reaches a decision when some chain of readers ends at an authority
            # node or at a declared EXTERNAL reader (regime_coverage -> deepening queue ->
            # deepening_worker -> deepened_candidates -> external_gauntlet is a real path, and
            # drift_monitor -> revival_engine -> deepening queue -> deepening_worker -> gauntlet
            # is one hop longer). Walked breadth-first over non-authority nodes to a bounded
            # depth, with the path recorded, so the verdict names the chain rather than a hop
            # count that happened to fit yesterday's graph.
            decision_readers = _decision_paths(n, nodes, _read_by)
            if not decision_readers and not all(w in HUMAN_READ for w in n.writes):
                findings.append({"check": "ADVISORY_ONLY", "node": n.name,
                                 "artifact": ", ".join(n.writes),
                                 "why": "computes artifacts that reach no decision"})

    # UNMEASURED_AUTHORITY: conditioning dimensions must be judged, and not buried.
    try:
        adm = json.loads((DESK / "reports" / "STATE_ADMISSION.json").read_text("utf-8"))
        judged = set((adm.get("verdicts") or {}).keys()) | set(adm.get("gaps") or {})
        buried = set(adm.get("graveyard") or [])
    except (OSError, ValueError):
        judged, buried = set(), set()
    for n in nodes:
        for dim in n.conditions_on:
            if dim in buried:
                findings.append({"check": "UNMEASURED_AUTHORITY", "node": n.name,
                                 "artifact": dim, "why": "conditions on a BURIED dimension"})
            elif judged and dim not in judged:
                findings.append({"check": "UNMEASURED_AUTHORITY", "node": n.name,
                                 "artifact": dim, "why": "conditions on a dimension never judged"})

    # UNDECLARED: path literals in a node's source that the graph does not know about.
    known = {p for n in nodes for p in (*n.writes, *n.reads)}
    for n in nodes:
        try:
            src = (ROOT / n.module).read_text("utf-8")
        except OSError:
            findings.append({"check": "MISSING_MODULE", "node": n.name, "artifact": n.module,
                             "why": "declared module does not exist"})
            continue
        for m in _PATH_RE.finditer(src):
            lit = m.group(1)
            if lit.endswith(".py"):
                continue                       # a module reference (release manifest), not data
            if lit.startswith("desks/mt5/") or lit.startswith("backups/"):
                full = lit
            else:
                full = f"desks/mt5/{lit}"
            if not any(_covers(k, full) or _covers(full, k) for k in known):
                findings.append({"check": "UNDECLARED", "node": n.name, "artifact": full,
                                 "why": "path literal in source not declared on any node"})

    fatal = [f for f in findings if f["check"] in
             ("DEAD_PRODUCER", "DEAD_CONSUMER", "ADVISORY_ONLY", "UNMEASURED_AUTHORITY",
              "MISSING_MODULE")]
    return {"generated_utc": datetime.now(tz=UTC).isoformat(), "nodes": len(nodes),
            "artifacts": len(set(writers) | set(readers)), "findings": findings,
            "fatal": fatal, "ok": not fatal}


def freshness(nodes: tuple[Node, ...] = NODES) -> list[dict[str, Any]]:
    """STALE_DECISION: an authority node's input older than its SLA. Runtime, not CI."""
    out = []
    now = datetime.now(tz=UTC).timestamp()
    for n in nodes:
        for art, sla in n.freshness_s.items():
            p = ROOT / art
            if not p.exists():
                out.append({"check": "STALE_DECISION", "node": n.name, "artifact": art,
                            "why": "input absent", "age_s": None, "sla_s": sla})
                continue
            age = now - p.stat().st_mtime
            if age > sla:
                out.append({"check": "STALE_DECISION", "node": n.name, "artifact": art,
                            "why": f"{age / 3600:.1f}h old, SLA {sla / 3600:.1f}h",
                            "age_s": int(age), "sla_s": sla})
    return out


def reachability(nodes: tuple[Node, ...] = NODES) -> dict[str, Any]:
    """For every artifact: which authority nodes it reaches, and through what path."""
    by_write: dict[str, list[Node]] = {}
    for n in nodes:
        for r in n.reads:
            by_write.setdefault(r, []).append(n)

    def _readers_of(art: str) -> list[Node]:
        out = []
        for r, ns in by_write.items():
            if _covers(r, art) or _covers(art, r):
                out.extend(ns)
        return out

    result: dict[str, Any] = {}
    all_arts = sorted({w for n in nodes for w in n.writes})
    for art in all_arts:
        paths: list[str] = []
        seen: set[str] = set()
        stack = [(art, [art])]
        while stack:
            cur, path = stack.pop()
            for n in _readers_of(cur):
                if n.name in seen:
                    continue
                seen.add(n.name)
                if n.authority:
                    paths.append(" -> ".join([*path, f"{n.name}[{','.join(n.authority)}]"]))
                for w in n.writes:
                    stack.append((w, [*path, n.name, w]))
        result[art] = {"reaches_authority": bool(paths), "paths": paths[:6],
                       "human_read": art in HUMAN_READ,
                       "external_reader": EXTERNAL_READERS.get(art)}
    return result


STAGES = ("CODED", "WIRED", "RUNNING", "DECISION_AFFECTING", "MEASURED")
RUNNING_WINDOW_S = 3 * 24 * 3600


def stages(nodes: tuple[Node, ...] = NODES) -> dict[str, dict[str, Any]]:
    """Per node: CODED -> WIRED -> RUNNING -> DECISION_AFFECTING -> MEASURED, each a fact.

    CODED               the module exists
    WIRED               every declared read has a producer (or is box data) and every write a
                        reader -- the check() has no fatal finding naming this node
    RUNNING             at least one of its written artifacts was refreshed inside the window
    DECISION_AFFECTING  a path from one of its writes reaches an authority node
    MEASURED            a ledger line values what it does: a rail in MISSED_GROWTH, a filter in
                        FILTER_VALUE, a term in the attribution, or its own report carrying a
                        measured verdict field
    """
    findings = check(nodes)["findings"]
    named = {f["node"] for f in findings if f["check"] in
             ("DEAD_PRODUCER", "DEAD_CONSUMER", "ADVISORY_ONLY", "UNMEASURED_AUTHORITY")}
    reach = reachability(nodes)
    measured_names: set[str] = set()
    for rel in ("reports/MISSED_GROWTH.json", "reports/FILTER_VALUE.json",
                "reports/allocator_attribution.json", "reports/CAPITAL_MODIFIERS.json",
                "reports/RESEARCH_PRODUCTIVITY.json"):
        try:
            doc = json.loads((DESK / rel).read_text("utf-8"))
            measured_names |= set(map(str, (doc.get("rails") or doc.get("filters") or
                                            doc.get("terms") or doc.get("categories") or
                                            doc.get("stages") or {}).keys()))
        except (OSError, ValueError):
            continue
    now = datetime.now(tz=UTC).timestamp()
    out: dict[str, dict[str, Any]] = {}
    for n in nodes:
        coded = (ROOT / n.module).exists()
        wired = coded and n.name not in named
        running = False
        for w in n.writes:
            p = ROOT / w
            try:
                if p.is_dir():
                    newest = max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()),
                                 default=0.0)
                else:
                    newest = p.stat().st_mtime
                if now - newest < RUNNING_WINDOW_S:
                    running = True
                    break
            except OSError:
                continue
        decision = bool(n.authority) or any(
            (reach.get(w) or {}).get("reaches_authority") for w in n.writes)
        measured = bool(n.authority) or any(
            (n.name in measured_names) or any(k.startswith(n.name) for k in measured_names)
            for _ in (0,))
        if not measured:
            for w in n.writes:
                try:
                    doc = json.loads((ROOT / w).read_text("utf-8"))
                except (OSError, ValueError, IsADirectoryError):
                    continue
                if isinstance(doc, dict) and any(k in doc for k in
                                                 ("verdict", "filters", "rails", "categories",
                                                  "unused_upside_heat", "value_logw_per_day")):
                    measured = True
                    break
        stage = "CODED" if not coded else ("WIRED" if not running else
                                           ("RUNNING" if not decision else
                                            ("DECISION_AFFECTING" if not measured else "MEASURED")))
        if not coded:
            stage = "MISSING"
        out[n.name] = {"coded": coded, "wired": wired, "running": running,
                       "decision_affecting": decision, "measured": measured, "stage": stage}
    return out


def generate_status(out_dir: Path = DESK / "reports") -> dict[str, Any]:
    status = check()
    status["stale"] = freshness()
    status["stages"] = stages()
    status["stage_counts"] = {s: sum(1 for v in status["stages"].values() if v["stage"] == s)
                              for s in ("MISSING", *STAGES)}
    reach = reachability()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "CAPABILITY_STATUS.json").write_text(json.dumps(status, indent=1), "utf-8")
    (out_dir / "LIVE_REACHABILITY.json").write_text(json.dumps(
        {"generated_utc": status["generated_utc"], "artifacts": reach}, indent=1), "utf-8")
    return status
