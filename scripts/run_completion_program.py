#!/usr/bin/env python3
"""Run the integrated completion capabilities against current desk evidence.

No synthetic success values are inserted.  A missing input produces ``UNMEASURED`` and names the
input contract; the report is then consumed by max-push so absence becomes ranked work.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.asymmetry import (  # noqa: E402
    information_advantage_frontier,
    self_footprint_coverage,
)
from libs.ops.production_contract import (  # noqa: E402
    accounting_from_execution_tape,
    autonomous_recovery_plan,
    counterfactual_reality_gap,
    decision_record,
    deterministic_hot_path,
    latency_metrics,
    preflight_contract,
    reality_gap,
    strategy_manifest,
    venue_eligibility,
)
from libs.portfolio.decision_intelligence import (  # noqa: E402
    alpha_retention,
    capital_inventory_policy,
    capital_topology,
    dependence_preserving_monte_carlo,
    effective_breadth,
    execution_opportunity,
    exit_reallocation_decision,
    momentum_rebound_surface,
    monetisation_latency,
    path_drawdown_state,
    regime_conditional_allocation,
    regime_model_selection,
    return_attribution,
    transition_posterior,
    transition_surprise,
    trigger_collision_control,
    venue_stress_state,
    volatility_manifold_state,
    xsec_momentum_book,
)
from libs.research.funnel import meaningful_research_throughput  # noqa: E402
from libs.research.research_control import (  # noqa: E402
    actor_graph,
    causal_structure,
    compile_public_strategy,
    completion_supervisor,
    concurrency_economics,
    context_packet,
    creator_change_intelligence,
    dependency_aware_evidence,
    distill_doctrine,
    distill_workflow,
    ephemeral_specialist,
    frontier_health,
    lawful_disclosure_record,
    missed_opportunity_tests,
    model_router,
    open_world_coverage,
    operator_surface,
    prequential_score,
    research_dag_schedule,
    resolve_instruction_conflict,
    source_information_economics,
)
from libs.validation.research_diagnostics import (  # noqa: E402
    ConditionalClaim,
    ablate_gates,
    cluster_failures,
    conditional_validation,
    semantic_label_integrity,
    sequential_experiment_design,
    threshold_sensitivity,
)

OUT = ROOT / "data" / "completion_program.json"


def _read(rel: str, default: Any = None) -> Any:
    try:
        return json.loads((ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _rows(doc: Any, *keys: str) -> list[dict[str, Any]]:
    value = doc
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def _jsonl(rel: str) -> list[dict[str, Any]]:
    try:
        return [
            row
            for line in (ROOT / rel).read_text("utf-8").splitlines()
            if line.strip()
            for row in [json.loads(line)]
            if isinstance(row, dict)
        ]
    except (OSError, json.JSONDecodeError):
        return []


def _numeric_series(doc: Any, *keys: str) -> list[float]:
    if not isinstance(doc, dict):
        return []
    for key in keys:
        value = doc.get(key)
        if isinstance(value, list):
            clean = [float(x) for x in value if isinstance(x, (int, float)) and np.isfinite(x)]
            if len(clean) >= 2:
                return clean
    return []


def _validation() -> dict[str, Any]:
    review = _read("data/research_review.json", {})
    sweep = _read("data/full_sweep_report.json", {})
    killed = _rows(sweep, "killed_cells") or _rows(review, "kill_audit", "rows")
    statistics = [
        float(r["statistic"]) for r in killed if isinstance(r.get("statistic"), (int, float))
    ]
    threshold = (
        review.get("gate_power", {}).get("f3_threshold") if isinstance(review, dict) else None
    )
    sensitivity = (
        threshold_sensitivity(statistics, float(threshold))
        if isinstance(threshold, (int, float))
        else {"status": "UNMEASURED", "reason": "F3 threshold/statistics absent"}
    )
    gate_vectors: dict[str, list[bool]] = {}
    for row in killed:
        results = row.get("gate_results")
        if isinstance(results, dict):
            for gate, verdict in results.items():
                gate_vectors.setdefault(str(gate), []).append(bool(verdict))
    ablation = (
        ablate_gates(gate_vectors)
        if gate_vectors
        else {"status": "UNMEASURED", "reason": "per-cell gate vectors absent"}
    )
    conditional_rows = _rows(_read("data/conditional_claims.json", {}), "claims")
    conditional = []
    for row in conditional_rows:
        try:
            conditional.append(
                conditional_validation(
                    ConditionalClaim(
                        claim_id=str(row["claim_id"]),
                        state_name=str(row["state_name"]),
                        state_declared_before_results=bool(
                            row.get("state_declared_before_results")
                        ),
                        state_observable_at_decision=bool(row.get("state_observable_at_decision")),
                        untouched_oos=bool(row.get("untouched_oos")),
                        ancestry_trials=int(row.get("ancestry_trials", 1)),
                        returns=tuple(float(x) for x in row.get("returns", [])),
                        state_mask=tuple(bool(x) for x in row.get("state_mask", [])),
                    )
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            conditional.append({"status": "INVALID_INPUT", "reason": str(exc)})
    design_rows = _rows(_read("data/experiment_designs.json", {}), "experiments")
    sequential = []
    for row in design_rows:
        try:
            sequential.append(
                sequential_experiment_design(
                    minimum_effect=float(row["minimum_effect"]),
                    noise_sd=float(row["noise_sd"]),
                    available_n=int(row.get("available_n", 0)),
                    alpha=float(row.get("alpha", 0.05)),
                    power=float(row.get("power", 0.8)),
                    planned_looks=int(row.get("planned_looks", 1)),
                    observed_effect=(
                        float(row["observed_effect"])
                        if isinstance(row.get("observed_effect"), (int, float))
                        else None
                    ),
                    standard_error=(
                        float(row["standard_error"])
                        if isinstance(row.get("standard_error"), (int, float))
                        else None
                    ),
                    additional_information_value=(
                        float(row["additional_information_value"])
                        if isinstance(row.get("additional_information_value"), (int, float))
                        else None
                    ),
                    additional_cost=(
                        float(row["additional_cost"])
                        if isinstance(row.get("additional_cost"), (int, float))
                        else None
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            sequential.append({"status": "INVALID_INPUT", "reason": str(exc)})
    semantic_rows = _rows(_read("data/semantic_label_audits.json", {}), "audits")
    semantic = []
    for row in semantic_rows:
        records = row.get("records", [])
        try:
            semantic.append(
                semantic_label_integrity(
                    records if isinstance(records, list) else [],
                    inferred_field=str(row.get("inferred_field", "inferred")),
                    authoritative_field=str(row.get("authoritative_field", "authoritative")),
                    authoritative_source=str(row.get("authoritative_source", "")),
                    outcome_field=(str(row["outcome_field"]) if row.get("outcome_field") else None),
                    min_ground_truth=int(row.get("min_ground_truth", 30)),
                    min_preregistered_kappa=(
                        float(row["min_preregistered_kappa"])
                        if isinstance(row.get("min_preregistered_kappa"), (int, float))
                        else None
                    ),
                )
            )
        except (TypeError, ValueError) as exc:
            semantic.append({"status": "INVALID_INPUT", "reason": str(exc)})
    return {
        "threshold_sensitivity": sensitivity,
        "gate_ablation": ablation,
        "failure_clustering": cluster_failures(killed),
        "conditional_validation": conditional or [{"status": "UNMEASURED"}],
        "sequential_experiment_design": sequential or [{"status": "UNMEASURED"}],
        "semantic_label_integrity": semantic or [{"status": "UNMEASURED"}],
    }


def _portfolio() -> dict[str, Any]:
    live = _read("web/cashcarry_live.json", {})
    shadow = _read("web/cashcarry_shadow.json", {})
    portfolio = _read("data/portfolio_admission.json", {})
    series = _numeric_series(shadow, "returns", "daily_returns", "pnl_series")
    sleeve_map = shadow.get("sleeve_returns", {}) if isinstance(shadow, dict) else {}
    sleeve_series = (
        [v for v in sleeve_map.values() if isinstance(v, list)]
        if isinstance(sleeve_map, dict)
        else []
    )
    matrix = None
    if sleeve_series and len({len(v) for v in sleeve_series}) == 1 and len(sleeve_series[0]) >= 2:
        matrix = np.asarray(sleeve_series, dtype="float64").T
    elif len(series) >= 2:
        matrix = np.asarray(series, dtype="float64")[:, None]
    weights = portfolio.get("weights") if isinstance(portfolio, dict) else None
    if isinstance(weights, dict) and matrix is not None:
        w = [float(weights.get(name, 0.0)) for name in sleeve_map] if sleeve_map else [1.0]
    else:
        w = [1.0] if matrix is not None else []

    regime = _read("web/regime.json", {})
    states = regime.get("history", []) if isinstance(regime, dict) else []
    states = [str(x.get("state", x)) if isinstance(x, dict) else str(x) for x in states]
    transitions = transition_posterior(states)
    surprise = (
        {"status": "UNMEASURED"}
        if transitions.get("status") != "MEASURED"
        else transition_surprise(str(states[-2]), str(states[-1]), transitions["posterior"])
    )
    trigger_history = _read("data/trigger_history.json", {}).get("matrix", [])
    prices = _read("data/xsec_prices.json", {}).get("prices", [])
    intended = float(live.get("intended_pnl", 0.0)) if isinstance(live, dict) else 0.0
    realised = (
        float(live.get("realised_pnl", live.get("pnl", 0.0))) if isinstance(live, dict) else 0.0
    )
    stage_times = live.get("stage_times", {}) if isinstance(live, dict) else {}
    half_life = float(live.get("half_life_seconds", 0.0)) if isinstance(live, dict) else 0.0
    edge_bps = float(live.get("edge_bps", 0.0)) if isinstance(live, dict) else 0.0
    topology_doc = _read("data/capital_topology.json", {})
    topology_rows = _rows(topology_doc, "accounts")
    topology_limits = topology_doc.get("limits", {}) if isinstance(topology_doc, dict) else {}
    volatility_doc = _read("data/volatility_surfaces.json", {})
    surfaces = volatility_doc.get("surfaces", []) if isinstance(volatility_doc, dict) else []
    manifold = {"status": "UNMEASURED"}
    if isinstance(surfaces, list) and surfaces:
        try:
            manifold = volatility_manifold_state(
                surfaces,
                train_rows=int(volatility_doc.get("train_rows", 0)),
                rank=int(volatility_doc.get("rank", 0)),
                anomaly_quantile=float(volatility_doc.get("anomaly_quantile", 0.99)),
                asset_labels=(
                    volatility_doc.get("asset_labels")
                    if isinstance(volatility_doc.get("asset_labels"), list)
                    else None
                ),
            )
        except (TypeError, ValueError, np.linalg.LinAlgError) as exc:
            manifold = {"status": "INVALID_INPUT", "reason": str(exc)}
    venue_doc = _read("data/venue_stress_history.json", {})
    venue_history = _rows(venue_doc, "history")
    venue_state = venue_stress_state(
        venue_history,
        components=(
            venue_doc.get("components")
            if isinstance(venue_doc, dict) and isinstance(venue_doc.get("components"), list)
            else (
                "liquidations",
                "open_interest_change_abs",
                "funding_abs",
                "basis_abs",
                "depth_drop",
                "insurance_fund_drawdown",
                "collateral_haircut",
                "adl_level",
                "withdrawal_constraint",
            )
        ),
        alert_z=(
            float(venue_doc["alert_z"])
            if isinstance(venue_doc, dict) and isinstance(venue_doc.get("alert_z"), (int, float))
            else None
        ),
    )
    return {
        "volatility_manifold": manifold,
        "venue_stress_state": venue_state,
        "capital_topology": capital_topology(
            topology_rows,
            max_venue_fraction=float(topology_limits.get("max_venue_fraction", 1.0)),
            max_collateral_fraction=float(topology_limits.get("max_collateral_fraction", 1.0)),
        ),
        "portfolio_monte_carlo": (
            dependence_preserving_monte_carlo(matrix, w, n_paths=500)
            if matrix is not None
            else {"status": "UNMEASURED"}
        ),
        "effective_breadth": (
            effective_breadth(matrix) if matrix is not None else {"status": "UNMEASURED"}
        ),
        "regime_transition_posterior": transitions,
        "transition_surprise": surprise,
        "path_drawdown": path_drawdown_state(series),
        "capital_inventory": capital_inventory_policy(
            deployable=max(0.0, float(live.get("deployable", 0.0))),
            dry_powder=max(0.0, float(live.get("dry_powder", 0.0))),
            opportunity_score=float(live.get("opportunity_score", 0.0)),
            future_option_score=float(live.get("future_option_score", 0.0)),
        ),
        "trigger_collision": (
            trigger_collision_control(trigger_history)
            if isinstance(trigger_history, list) and len(trigger_history) >= 2
            else {"status": "UNMEASURED"}
        ),
        "xsec_momentum": (
            xsec_momentum_book(prices)
            if isinstance(prices, list) and len(prices) >= 2
            else {"status": "UNMEASURED"}
        ),
        "momentum_rebound": momentum_rebound_surface([], [], []),
        "exit_engine": exit_reallocation_decision(
            live.get("hold_scenarios", []), live.get("alternative_scenarios", [])
        ),
        "execution_surface": (
            execution_opportunity(
                gross_edge_bps=edge_bps,
                order_size=float(live["order_size"]),
                queue_ahead=float(live["queue_ahead"]),
                through_volume=float(live["through_volume"]),
                taker_cost_bps=float(live.get("taker_cost_bps", 0.0)),
                adverse_selection_bps=float(live.get("adverse_selection_bps", 0.0)),
            )
            if isinstance(live, dict)
            and all(k in live for k in ("order_size", "queue_ahead", "through_volume"))
            else {"status": "UNMEASURED"}
        ),
        "alpha_retention": alpha_retention(
            intended_pnl=intended, realised_pnl=realised, leaks=live.get("leaks", {})
        ),
        "return_attribution": return_attribution(series, _numeric_series(live, "market_returns")),
        "monetisation_latency": monetisation_latency(
            stage_times, edge_bps=edge_bps, half_life_seconds=half_life
        ),
        "regime_allocation": regime_conditional_allocation(
            regime.get("posterior", {}), portfolio.get("state_elog", {})
        ),
        "regime_model_selection": regime_model_selection(
            regime.get("model_oos", {}) if isinstance(regime, dict) else {}
        ),
    }


def _research() -> dict[str, Any]:
    ledger = _read("data/decision_ledger.json", {})
    decisions = _rows(ledger, "decisions")
    source = _read("data/source_production.json", {})
    sources = _rows(source, "sources")
    claims = _rows(_read("data/public_claims.json", {}), "claims")
    evidence = _read("data/evidence_fusion.json", {})
    values, corr = evidence.get("values", []), evidence.get("correlation", [])
    tasks = _rows(_read("data/research_tasks.json", {}), "tasks")
    model_history = _rows(_read("data/model_attribution.json", {}), "events")
    traces = _read("data/workflow_traces.json", {}).get("traces", [])
    lessons = _rows(_read("data/lessons.json", {}), "lessons")
    forecasts = _rows(_read("data/forecasts.json", {}), "forecasts")
    completion = _rows(_read("data/completion_ledger_status.json", {}), "rows")
    queue = _rows(_read("data/max_push_queue.json", {}), "queue")
    live_ladder = _read("data/live_ladder.json", {})
    live = _rows(live_ladder, "rows")
    intelligence_cycle = _read("web/intelligence_cycle.json", {})
    study_status = _read("data/study_status.json", {})
    research_review = _read("data/research_review.json", {})
    completion_status = _read("data/completion_ledger_status.json", {})
    blocked = [r for r in completion if r.get("status") == "EXTERNALLY_BLOCKED"]
    status_counts = Counter(str(r.get("status")) for r in decisions)
    discovered = sum(int(r.get("found", 0) or 0) for r in sources)
    distinct = sum(int(r.get("novel", 0) or 0) for r in sources)
    tested = sum(int(r.get("tested", 0) or 0) for r in sources)
    survivors = sum(int(r.get("independent", r.get("survivors", 0)) or 0) for r in sources)
    workers = _read("data/concurrency_benchmarks.json", {})
    worker_rows = _rows(workers, "samples")
    disclosures = _rows(_read("data/disclosure_events.json", {}), "events")
    disclosure_rows = []
    for row in disclosures:
        try:
            disclosure_rows.append(
                lawful_disclosure_record(
                    source=str(row["source"]),
                    published_at=row["published_at"],
                    first_seen_at=row["first_seen_at"],
                    parsed_at=row["parsed_at"],
                    content_hash=str(row["content_hash"]),
                    claim=str(row["claim"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            disclosure_rows.append({"status": "INVALID_INPUT", "reason": str(exc)})
    specialist_events = _rows(_read("data/specialist_history.json", {}), "events")
    causal_rows = _rows(_read("data/causal_mechanisms.json", {}), "mechanisms")
    source_economics_rows = _rows(_read("data/source_economics.json", {}), "sources")
    conflict_rows = _rows(_read("data/instruction_conflicts.json", {}), "conflicts")
    context_doc = _read("data/context_tasks.json", {})
    context_tasks = _rows(context_doc, "tasks")
    context_core = context_doc.get("core", []) if isinstance(context_doc, dict) else []
    doctrine_modules = (
        context_doc.get("doctrine_modules", {}) if isinstance(context_doc, dict) else {}
    )
    method_optimizer = _read("data/research_alpha_optimizer.json", {})
    external_frontier = _read("data/intelligence/external_frontier.json", {})
    proprietary_candidates = _rows(_read("data/proprietary_information.json", {}), "candidates")
    throughput_events = _jsonl("data/research_throughput_events.jsonl")
    coverage_cells = _rows(_read("data/open_world_coverage.json", {}), "cells")
    taxonomy_challenges = _rows(_read("data/coverage_taxonomy_challenges.json", {}), "challenges")
    return {
        "disclosure_intelligence": disclosure_rows or [{"status": "UNMEASURED"}],
        "proprietary_information_frontier": information_advantage_frontier(proprietary_candidates),
        "meaningful_research_throughput": meaningful_research_throughput(throughput_events),
        "open_world_coverage": open_world_coverage(coverage_cells, taxonomy_challenges),
        "external_intelligence": (
            external_frontier
            if isinstance(external_frontier, dict) and external_frontier
            else {"status": "UNMEASURED"}
        ),
        "search_strategy_evolution": (
            method_optimizer.get("search_strategy_evolution", {"status": "UNMEASURED"})
            if isinstance(method_optimizer, dict)
            else {"status": "UNMEASURED"}
        ),
        "causal_structures": [
            causal_structure(row.get("nodes", {}), row.get("links", []))
            for row in causal_rows
            if isinstance(row.get("nodes", {}), dict) and isinstance(row.get("links", []), list)
        ]
        or [{"status": "UNMEASURED"}],
        "source_information_economics": source_information_economics(source_economics_rows),
        "instruction_conflicts": [
            resolve_instruction_conflict(row.get("rules", []))
            for row in conflict_rows
            if isinstance(row.get("rules", []), list)
        ]
        or [{"status": "UNMEASURED"}],
        "context_packets": [
            context_packet(
                core=context_core if isinstance(context_core, list) else [],
                doctrine_modules=doctrine_modules if isinstance(doctrine_modules, dict) else {},
                domain=str(row.get("domain", "")),
                dynamic_state=row.get("dynamic_state", row),
            )
            for row in context_tasks
        ]
        or [{"status": "UNMEASURED"}],
        "ephemeral_specialists": [
            ephemeral_specialist(
                specialist_id=str(row.get("specialist_id", "UNKNOWN")),
                task_id=str(row.get("task_id", "UNKNOWN")),
                artifact=str(row.get("artifact", "")),
                useful_value=float(row.get("useful_value", 0.0)),
                cost=float(row.get("cost", 0.0)),
                completed=bool(row.get("completed")),
            )
            for row in specialist_events
        ],
        "input_health": {
            "study_status": study_status or {"status": "UNMEASURED"},
            "intelligence_cycle": intelligence_cycle or {"status": "UNMEASURED"},
            "research_review": research_review or {"status": "UNMEASURED"},
            "live_ladder": live_ladder or {"status": "UNMEASURED"},
            "completion_ledger": completion_status or {"status": "UNMEASURED"},
        },
        "actor_graph": actor_graph(_rows(_read("data/actor_events.json", {}), "events")),
        "evidence_fusion": (
            dependency_aware_evidence(values, corr) if values and corr else {"status": "UNMEASURED"}
        ),
        "creator_changes": creator_change_intelligence(claims),
        "semantic_compiler": (
            compile_public_strategy(claims[0].get("strategy", {}))
            if claims
            else {"status": "UNMEASURED"}
        ),
        "research_dag": research_dag_schedule(tasks),
        "concurrency_economics": concurrency_economics(
            worker_rows,
            work_waiting=len(tasks),
            available_slots=int(workers.get("available_slots", 0) or 0),
        ),
        "model_router": model_router(model_history, "research"),
        "workflow_distillation": distill_workflow(traces if isinstance(traces, list) else []),
        "doctrine_distillation": distill_doctrine(lessons),
        "missed_opportunity": missed_opportunity_tests(decisions),
        "prequential": prequential_score(forecasts),
        "operator_surface": operator_surface(live=live, blocked=blocked, queue=queue),
        "completion_supervisor": completion_supervisor(completion),
        "frontier_health": frontier_health(
            discovered=discovered,
            distinct_mechanisms=distinct,
            tested=tested,
            dispositioned=sum(status_counts.values()),
            survivors=survivors,
            portfolio_tested=sum(int(r.get("portfolio_positive", 0) or 0) for r in sources),
            deployed=sum(int(r.get("live_descendants", 0) or 0) for r in sources),
            queue_waiting=len(queue),
            eligible_capacity_idle=int(workers.get("eligible_idle", 0) or 0),
            blind_spots_open=sum(r.get("status") != "VERIFIED_COMPLETE" for r in completion),
            blind_spots_new=int(source.get("blind_spots_new", 0) or 0),
        ),
    }


def _production() -> dict[str, Any]:
    decisions = []
    execution_decisions = ROOT / "data" / "execution_decisions.jsonl"
    try:
        decisions = [
            json.loads(line)
            for line in execution_decisions.read_text("utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        decisions = []
    if not decisions:
        decisions = _rows(_read("data/decision_ledger.json", {}), "decisions")
    tape = []
    tape_path = ROOT / "data" / "moat" / "execution_tape" / "cashcarry_trades.jsonl"
    with contextlib.suppress(OSError, json.JSONDecodeError):
        tape = [
            json.loads(line) for line in tape_path.read_text("utf-8").splitlines() if line.strip()
        ]
    replay = _read("data/hot_path_replay.json", {})
    raw_manifest = _read("data/strategy_manifest.json", {}) or (
        replay.get("manifest", {}) if isinstance(replay, dict) else {}
    )
    manifest_spec = (
        raw_manifest.get("specification", raw_manifest) if isinstance(raw_manifest, dict) else {}
    )
    required = {"strategy_id", "signal", "allocator", "risk_policy", "execution_policy"}
    manifest = (
        strategy_manifest(
            manifest_spec,
            version=str(raw_manifest.get("version", "1")),
            parent_hash=raw_manifest.get("parent_hash"),
        )
        if required <= set(manifest_spec)
        else {"status": "UNMEASURED"}
    )
    venue = _read("data/venue_capabilities.json", {})
    requirements = (
        manifest_spec.get("venue_requirements", {}) if isinstance(manifest_spec, dict) else {}
    )
    preflight = _read("data/preflight_checks.json", {})
    modes = _read("data/reality_parity.json", {})
    timestamps = decisions[-1].get("timestamps", {}) if decisions else {}
    known_decisions = {
        "EXECUTED",
        "SIGNAL_REJECTED",
        "RISK_REJECTED",
        "COST_REJECTED",
        "CAPACITY_REJECTED",
        "EXECUTION_REJECTED",
        "VENUE_UNAVAILABLE",
        "MISSED_LATENCY",
    }
    latest_decision = str(decisions[-1].get("decision", "")) if decisions else ""
    hot_path = {"status": "UNMEASURED"}
    if isinstance(replay, dict) and replay.get("manifest") and replay.get("observation"):
        try:
            hot_path = deterministic_hot_path(
                replay["manifest"],
                replay["observation"],
                lambda observation, manifest: replay.get("signal", {}),
                lambda signal, manifest: replay.get("desired_order", {}),
                lambda desired, manifest: replay.get("risk_output", {}),
                lambda approved, manifest: replay.get("adapter_order", {}),
            )
            hot_path["status"] = "MEASURED"
        except (TypeError, ValueError) as exc:
            hot_path = {"status": "INVALID_INPUT", "reason": str(exc)}
    sample_decision = (
        decision_record(
            decision_id=str(decisions[-1].get("id", decisions[-1].get("decision_id", "unknown"))),
            decision=latest_decision,
            strategy_version=str(decisions[-1].get("strategy_version", "unknown")),
            state_snapshot=decisions[-1].get("state_snapshot") or {"legacy_record": True},
            rationale=str(decisions[-1].get("rationale", decisions[-1].get("reason", "legacy"))),
            desired_order=decisions[-1].get("desired_order"),
        )
        if decisions and latest_decision in known_decisions
        else {"status": "UNMEASURED"}
    )
    counterfactual_doc = _read("data/counterfactual_worlds.json", {})
    counterfactual = counterfactual_reality_gap(
        _rows(counterfactual_doc, "real"),
        _rows(counterfactual_doc, "synthetic"),
        features=(
            counterfactual_doc.get("features", [])
            if isinstance(counterfactual_doc, dict)
            and isinstance(counterfactual_doc.get("features"), list)
            else []
        ),
        max_preregistered_gap=(
            float(counterfactual_doc["max_preregistered_gap"])
            if isinstance(counterfactual_doc, dict)
            and isinstance(counterfactual_doc.get("max_preregistered_gap"), (int, float))
            else None
        ),
    )
    return {
        "deterministic_hot_path": hot_path,
        "decision_ledger": sample_decision,
        "strategy_manifest": manifest,
        "counterfactual_reality_gap": counterfactual,
        "self_footprint_moat": self_footprint_coverage([*decisions, *tape]),
        "controller_continuity": _read("data/controller_lease.json", {"status": "UNMEASURED"}),
        "reality_gap": reality_gap(
            modes.get("paper", []), modes.get("canary", []), modes.get("live", [])
        ),
        "preflight": preflight_contract(
            preflight.get("checks", preflight) if isinstance(preflight, dict) else {}
        ),
        "venue_capability": venue_eligibility(venue.get("capabilities", venue), requirements),
        "execution_tape_accounting": accounting_from_execution_tape(tape),
        "latency_metrics": latency_metrics(
            timestamps,
            half_life_seconds=float(decisions[-1].get("half_life_seconds", 0.0))
            if decisions
            else 0.0,
            edge_bps=float(decisions[-1].get("edge_bps", 0.0)) if decisions else 0.0,
        ),
        "autonomous_recovery": autonomous_recovery_plan(
            component="completion_program",
            failure_class="input_missing",
            capital_critical=False,
            legal_fallback="emit UNMEASURED and continue",
            attempts=0,
        ),
    }


def build() -> dict[str, Any]:
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "authority": "MEASUREMENT_ONLY -- no orders, promotions or threshold changes",
        "validation": _validation(),
        "portfolio": _portfolio(),
        "research": _research(),
        "production": _production(),
    }


def main() -> int:
    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    print(f"completion-program: wrote {OUT.relative_to(ROOT)}; missing inputs remain UNMEASURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
