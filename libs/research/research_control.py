"""Economic control plane for continuous discovery, conversion and self-improvement.

The unit of output is never a page, prompt, formula, worker-hour or model call.  It is useful
downstream information: a distinct testable mechanism, a properly dispositioned failure, a
validated survivor, a deployable improvement, or a newly measured blind spot.  This keeps maximum
breadth and zero-idleness compatible with the desk's multiplicity and survival laws.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from itertools import pairwise

import numpy as np

from libs.core.coerce import finite_float, integer, object_sequence

__all__ = [
    "actor_graph",
    "causal_structure",
    "compile_public_strategy",
    "completion_supervisor",
    "concurrency_economics",
    "context_packet",
    "creator_change_intelligence",
    "dependency_aware_evidence",
    "distill_doctrine",
    "distill_workflow",
    "ephemeral_specialist",
    "frontier_health",
    "lawful_disclosure_record",
    "missed_opportunity_tests",
    "model_router",
    "open_world_coverage",
    "operator_surface",
    "prequential_score",
    "research_dag_schedule",
    "resolve_instruction_conflict",
    "source_information_economics",
]


def _iso(value: str | datetime) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def lawful_disclosure_record(
    *,
    source: str,
    published_at: str | datetime,
    first_seen_at: str | datetime,
    parsed_at: str | datetime,
    content_hash: str,
    claim: str,
) -> dict[str, object]:
    """Causal disclosure provenance and the delay that any claimed edge must survive."""
    published, seen, parsed = map(_iso, (published_at, first_seen_at, parsed_at))
    if not published <= seen <= parsed:
        raise ValueError("timestamps must follow published <= first_seen <= parsed")
    return {
        "source": source,
        "published_at": published.isoformat(),
        "first_seen_at": seen.isoformat(),
        "parsed_at": parsed.isoformat(),
        "source_latency_seconds": (seen - published).total_seconds(),
        "parse_latency_seconds": (parsed - seen).total_seconds(),
        "content_hash": content_hash,
        "claim": claim,
        "authority": "PUBLIC_DISCLOSURE_ONLY -- latency-adjust before testing",
    }


def actor_graph(
    events: Sequence[Mapping[str, object]], *, min_identity_confidence: float = 0.8
) -> dict[str, object]:
    """Behavioural action graph; uncertain identity never becomes a fact by repetition."""
    nodes: dict[str, dict[str, object]] = {}
    edges = []
    for i, event in enumerate(events):
        actor = str(event.get("actor") or f"UNKNOWN:{i}")
        confidence = max(0.0, min(1.0, finite_float(event.get("identity_confidence"))))
        canonical = actor if confidence >= min_identity_confidence else f"UNKNOWN:{i}"
        nodes.setdefault(
            canonical,
            {
                "identity": canonical,
                "confidence": confidence,
                "resolved": confidence >= min_identity_confidence,
            },
        )
        edges.append(
            {
                "actor": canonical,
                "action": str(event.get("action", "UNKNOWN")),
                "asset": str(event.get("asset", "UNKNOWN")),
                "as_of": event.get("as_of"),
                "source": event.get("source"),
            }
        )
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "unknown_count": sum(not bool(n["resolved"]) for n in nodes.values()),
    }


def dependency_aware_evidence(
    values: Sequence[float], correlation: Sequence[Sequence[float]], *, prior_precision: float = 0.0
) -> dict[str, object]:
    """Generalized least-squares evidence fusion and effective independent count."""
    y, c = np.asarray(values, dtype="float64"), np.asarray(correlation, dtype="float64")
    if y.ndim != 1 or c.shape != (len(y), len(y)) or len(y) == 0:
        return {"status": "UNMEASURED"}
    c = (c + c.T) / 2
    inv = np.linalg.pinv(c)
    one = np.ones(len(y))
    precision = float(one @ inv @ one)
    weights = inv @ one / max(precision, 1e-12)
    fused = float(weights @ y)
    return {
        "status": "MEASURED",
        "nominal_evidence": len(y),
        "effective_evidence": max(0.0, precision),
        "fused_value": fused,
        "weights": weights.tolist(),
        "posterior_precision": precision + prior_precision,
        "note": "correlated scouts are evidence once, not one vote each",
    }


def creator_change_intelligence(claims: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Time-version public claims; rank changes rather than static opinions."""
    by_creator: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in claims:
        by_creator[str(row.get("creator", "UNKNOWN"))].append(row)
    changes = []
    for creator, rows in by_creator.items():
        rows.sort(key=lambda r: str(r.get("as_of", "")))
        for before, after in pairwise(rows):
            if before.get("claim") != after.get("claim"):
                changes.append(
                    {
                        "creator": creator,
                        "before": before.get("claim"),
                        "after": after.get("claim"),
                        "as_of": after.get("as_of"),
                        "source": after.get("source"),
                    }
                )
    return {"claims": len(claims), "changes": changes, "change_count": len(changes)}


def compile_public_strategy(rule: Mapping[str, object]) -> dict[str, object]:
    """Compile ambiguity into a preregistered interpretation lattice, never one lucky encoding."""
    required = ("signal", "universe", "entry", "exit")
    missing = [k for k in required if not rule.get(k)]
    if missing:
        return {"status": "REFUSED", "missing": missing}
    raw_horizons = object_sequence(rule.get("horizons"))
    raw_thresholds = object_sequence(rule.get("thresholds"))
    horizons = list(raw_horizons) if raw_horizons else [rule.get("horizon", "1d")]
    thresholds = list(raw_thresholds) if raw_thresholds else [rule.get("threshold", 0.0)]
    interpretations = [
        {"horizon": h, "threshold": t, "direction": d}
        for h in horizons
        for t in thresholds
        for d in ("literal", "inverted_control")
    ]
    family_hash = hashlib.sha256(
        repr(
            (rule["signal"], rule["universe"], rule["entry"], rule["exit"], interpretations)
        ).encode()
    ).hexdigest()[:16]
    return {
        "status": "COMPILED",
        "family_id": family_hash,
        "interpretations": interpretations,
        "effective_trials": len(interpretations),
        "authority": "CANDIDATES_ONLY -- ordinary family-wise validation applies",
    }


def research_dag_schedule(
    nodes: Sequence[Mapping[str, object]], completed: Sequence[str] = ()
) -> dict[str, object]:
    """Dependency-aware, expected-value-per-cost research schedule."""
    done = set(map(str, completed))
    rows = []
    for node in nodes:
        node_id = str(node["id"])
        deps = {str(value) for value in object_sequence(node.get("depends_on"))}
        eligible = deps <= done
        ev = finite_float(node.get("expected_elog_gain"))
        cost = max(finite_float(node.get("cost"), 1.0), 1e-12)
        rows.append(
            {
                "id": node_id,
                "eligible": eligible,
                "blocked_by": sorted(deps - done),
                "score": ev / cost,
                "artifact": node.get("artifact"),
            }
        )
    rows.sort(
        key=lambda r: (not bool(r.get("eligible")), -finite_float(r.get("score")), str(r.get("id")))
    )
    return {"schedule": rows, "next": next((r["id"] for r in rows if r["eligible"]), None)}


def concurrency_economics(
    samples: Sequence[Mapping[str, float]], *, work_waiting: int, available_slots: int
) -> dict[str, object]:
    """Choose concurrency while marginal *useful* throughput remains positive."""
    rows = []
    for sample in samples:
        workers = int(sample["workers"])
        useful = float(sample.get("useful_outputs", 0.0))
        hours = max(float(sample.get("hours", 0.0)), 1e-12)
        cost = max(float(sample.get("cost", workers * hours)), 1e-12)
        rows.append(
            {
                "workers": workers,
                "useful_per_hour": useful / hours,
                "useful_per_cost": useful / cost,
            }
        )
    rows.sort(key=lambda r: int(r["workers"]))
    best = max(
        rows,
        key=lambda r: (float(r["useful_per_cost"]), float(r["useful_per_hour"])),
        default={"workers": 0, "useful_per_hour": 0.0, "useful_per_cost": 0.0},
    )
    target = min(available_slots, work_waiting, int(best["workers"])) if work_waiting > 0 else 0
    return {
        "benchmarks": rows,
        "target_workers": target,
        "idle_defect": bool(
            work_waiting > target
            and available_slots > target
            and float(best["useful_per_hour"]) > 0
        ),
        "guard": "trial volume and duplicate outputs are not useful throughput",
    }


def model_router(history: Sequence[Mapping[str, object]], task_class: str) -> dict[str, object]:
    """Route to observed downstream value per cost, retaining exploration."""
    rows = []
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for event in history:
        if str(event.get("task_class")) == task_class:
            grouped[str(event.get("model"))].append(event)
    total = sum(map(len, grouped.values()))
    for model, events in grouped.items():
        reward = sum(finite_float(e.get("downstream_value")) for e in events)
        cost = sum(max(finite_float(e.get("cost")), 0.0) for e in events)
        exploit = reward / max(cost, 1e-12)
        explore = math.sqrt(2 * math.log(max(total, 2)) / len(events))
        rows.append(
            {
                "model": model,
                "calls": len(events),
                "value_per_cost": exploit,
                "routing_score": exploit + explore,
            }
        )
    rows.sort(key=lambda r: (-finite_float(r.get("routing_score")), str(r.get("model"))))
    return {
        "task_class": task_class,
        "ranking": rows,
        "selected": rows[0]["model"] if rows else None,
        "reward": "downstream value, never prompt volume",
    }


def ephemeral_specialist(
    *,
    specialist_id: str,
    task_id: str,
    artifact: str,
    useful_value: float,
    cost: float,
    completed: bool,
) -> dict[str, object]:
    return {
        "specialist_id": specialist_id,
        "task_id": task_id,
        "lifecycle": ["INSTANTIATED", "EXECUTED", "RECORDED", "TERMINATED"]
        if completed
        else ["INSTANTIATED", "EXECUTED", "FAILED", "TERMINATED"],
        "artifact": artifact,
        "useful_value": useful_value,
        "cost": cost,
        "value_per_cost": useful_value / max(cost, 1e-12),
        "persistent_worker_created": False,
    }


def distill_workflow(traces: Sequence[Sequence[str]], *, min_repeats: int = 3) -> dict[str, object]:
    counts = Counter(tuple(trace) for trace in traces if trace)
    candidates = [
        {"trace": list(trace), "repeats": n, "estimated_steps_saved": (len(trace) - 1) * n}
        for trace, n in counts.items()
        if n >= min_repeats
    ]
    candidates.sort(key=lambda r: (-integer(r.get("estimated_steps_saved")), str(r.get("trace"))))
    return {"candidates": candidates, "distillable": len(candidates)}


def distill_doctrine(
    lessons: Sequence[Mapping[str, object]], *, min_recurrence: int = 2
) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for lesson in lessons:
        grouped[str(lesson.get("mechanism", "UNKNOWN"))].append(lesson)
    proposals = []
    for mechanism, rows in grouped.items():
        if len(rows) >= min_recurrence:
            strongest = "test" if any(r.get("automatable") for r in rows) else "checklist"
            proposals.append(
                {
                    "mechanism": mechanism,
                    "recurrences": len(rows),
                    "strongest_justified_form": strongest,
                    "success_metric": "recurrence rate falls on forward incidents",
                }
            )
    return {"proposals": proposals}


def missed_opportunity_tests(decisions: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Convert non-trades into new tests without retroactively changing their verdicts."""
    tests = []
    for row in decisions:
        counterfactual = row.get("counterfactual_return")
        if row.get("decision") != "EXECUTED" and isinstance(counterfactual, (int, float)):
            tests.append(
                {
                    "parent_decision": row.get("id"),
                    "hypothesis": f"revise {row.get('reason', 'unknown')} handling",
                    "observed_counterfactual": finite_float(counterfactual),
                    "status": "PREREGISTRATION_REQUIRED",
                    "promotion_authority": False,
                }
            )
    return {"missed": len(tests), "tests": tests}


def prequential_score(forecasts: Sequence[Mapping[str, object]]) -> dict[str, object]:
    resolved = [f for f in forecasts if f.get("outcome") is not None]
    if not resolved:
        return {"status": "UNMEASURED", "unresolved": len(forecasts)}
    p = np.asarray([finite_float(f.get("probability")) for f in resolved])
    y = np.asarray([finite_float(f.get("outcome")) for f in resolved])
    if np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must lie in [0, 1]")
    bins = []
    for lo in np.arange(0, 1, 0.1):
        mask = (p >= lo) & (p < lo + 0.1 if lo < 0.9 else p <= 1)
        if mask.any():
            bins.append(
                {
                    "lower": float(lo),
                    "n": int(mask.sum()),
                    "forecast": float(p[mask].mean()),
                    "outcome": float(y[mask].mean()),
                }
            )
    return {
        "status": "MEASURED",
        "resolved": len(resolved),
        "unresolved": len(forecasts) - len(resolved),
        "brier": float(np.mean((p - y) ** 2)),
        "calibration": bins,
    }


def operator_surface(
    *,
    live: Sequence[Mapping[str, object]],
    blocked: Sequence[Mapping[str, object]],
    queue: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    making = [x for x in live if finite_float(x.get("realised_pnl")) > 0]
    ranked = sorted(queue, key=lambda x: -finite_float(x.get("score")))
    return {
        "live_count": len(live),
        "making_money_count": len(making),
        "blocked_count": len(blocked),
        "highest_value_next": ranked[0] if ranked else None,
        "live": list(live),
        "blocked": list(blocked),
    }


def completion_supervisor(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    unfinished = [
        r for r in rows if r.get("status") not in ("VERIFIED_COMPLETE", "EXTERNALLY_BLOCKED")
    ]
    unfinished.sort(
        key=lambda r: (
            -finite_float(r.get("expected_elog_gain"))
            / max(finite_float(r.get("cost"), 1.0), 1e-12),
            str(r.get("capability_id", "")),
        )
    )
    return {
        "remaining": len(unfinished),
        "next": unfinished[0] if unfinished else None,
        "loop": "measure -> select highest marginal E[log W]/cost -> execute -> verify -> repeat",
    }


def frontier_health(
    *,
    discovered: int,
    distinct_mechanisms: int,
    tested: int,
    dispositioned: int,
    survivors: int,
    portfolio_tested: int,
    deployed: int,
    queue_waiting: int,
    eligible_capacity_idle: int,
    blind_spots_open: int,
    blind_spots_new: int,
) -> dict[str, object]:
    """One control for breadth, depth, conversion, utilisation and unknown-unknown renewal."""

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    return {
        "breadth": {
            "discoveries": discovered,
            "distinct_mechanisms": distinct_mechanisms,
            "independence_ratio": ratio(distinct_mechanisms, discovered),
        },
        "conversion": {
            "tested_per_distinct": ratio(tested, distinct_mechanisms),
            "dispositioned_per_tested": ratio(dispositioned, tested),
            "survivors_per_dispositioned": ratio(survivors, dispositioned),
            "portfolio_tested_per_survivor": ratio(portfolio_tested, survivors),
            "deployed_per_portfolio_tested": ratio(deployed, portfolio_tested),
        },
        "utilisation": {
            "work_waiting": queue_waiting,
            "eligible_capacity_idle": eligible_capacity_idle,
            "idle_defect": bool(queue_waiting and eligible_capacity_idle),
        },
        "frontier": {
            "blind_spots_open": blind_spots_open,
            "blind_spots_new": blind_spots_new,
            "renewing": bool(blind_spots_new > 0),
            "escalate_measurement_set": bool(blind_spots_open == 0),
        },
        "law": (
            "maximise distinct validated mechanisms and conversion, never nominal trials "
            "or survivor count"
        ),
    }


def causal_structure(
    nodes: Mapping[str, object], links: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Audit a mechanism's causal chain and invariance predictions without claiming causality."""
    required = (
        "participant_state",
        "constraint_incentive",
        "behavior",
        "observable_data",
        "market_impact",
        "expected_response",
    )
    missing = [name for name in required if not nodes.get(name)]
    known = set(nodes)
    invalid_links = [
        dict(link)
        for link in links
        if str(link.get("from")) not in known or str(link.get("to")) not in known
    ]
    predictions = [
        dict(link) for link in links if link.get("prediction") and link.get("environment")
    ]
    diagnostics = {
        key: list(object_sequence(nodes.get(key)))
        for key in (
            "confounders",
            "mediators",
            "proxies",
            "common_causes",
            "reverse_causality",
            "selection_effects",
        )
    }
    return {
        "status": "MEASURED" if not missing and not invalid_links else "PARTIALLY_MEASURED",
        "chain": {name: nodes.get(name) for name in required},
        "missing_links": missing,
        "invalid_edges": invalid_links,
        "diagnostics": diagnostics,
        "invariance_predictions": predictions,
        "multiple_independent_predictions": len(predictions) >= 2,
        "authority": "STRUCTURAL HYPOTHESIS ONLY -- invariance tests must use untouched evidence",
    }


def source_information_economics(sources: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Price source latency against its information half-life and downstream survivor yield."""
    rows = []
    for source in sources:
        required = (
            "observation_latency_seconds",
            "publication_latency_seconds",
            "ingestion_latency_seconds",
            "market_reaction_latency_seconds",
            "information_half_life_seconds",
        )
        if any(not isinstance(source.get(key), (int, float)) for key in required):
            rows.append({"source": source.get("source"), "status": "UNMEASURED"})
            continue
        latency = sum(max(0.0, finite_float(source.get(key))) for key in required[:3])
        half_life = finite_float(source.get("information_half_life_seconds"))
        if half_life <= 0:
            rows.append({"source": source.get("source"), "status": "UNMEASURED"})
            continue
        retained = 0.5 ** (latency / half_life)
        reliability = source.get("historical_reliability")
        uniqueness = source.get("uniqueness")
        survivor_yield = source.get("downstream_survivor_yield")
        inputs_measured = all(
            isinstance(value, (int, float)) for value in (reliability, uniqueness, survivor_yield)
        )
        option_value = (
            retained
            * finite_float(reliability)
            * finite_float(uniqueness)
            * finite_float(survivor_yield)
            if inputs_measured
            else None
        )
        rows.append(
            {
                "source": source.get("source"),
                "status": "MEASURED" if inputs_measured else "PARTIALLY_MEASURED",
                "end_to_end_latency_seconds": latency,
                "market_reaction_latency_seconds": finite_float(
                    source.get("market_reaction_latency_seconds")
                ),
                "information_half_life_seconds": half_life,
                "information_retained_at_ingestion": retained,
                "revision_frequency": source.get("revision_frequency"),
                "failure_rate": source.get("failure_rate"),
                "downstream_survivor_yield": survivor_yield,
                "latency_adjusted_option_value": option_value,
                "combination_only_value": source.get("combination_only_value"),
            }
        )
    ranked = sorted(
        rows,
        key=lambda row: (
            -finite_float(row.get("latency_adjusted_option_value"))
            if isinstance(row.get("latency_adjusted_option_value"), (int, float))
            else math.inf
        ),
    )
    return {"status": "MEASURED" if rows else "UNMEASURED", "sources": ranked}


def resolve_instruction_conflict(rules: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Resolve an explicit conflict by the constitutional 1..9 precedence hierarchy."""
    valid = [
        rule
        for rule in rules
        if isinstance(rule.get("precedence"), int) and 1 <= integer(rule.get("precedence")) <= 9
    ]
    if len(valid) < 2:
        return {"status": "UNMEASURED", "reason": "fewer than two valid conflicting rules"}
    top_level = min(integer(rule.get("precedence")) for rule in valid)
    contenders = [rule for rule in valid if integer(rule.get("precedence")) == top_level]

    def score(rule: Mapping[str, object]) -> float:
        value = finite_float(rule.get("expected_elog_gain"))
        confidence = max(0.0, min(1.0, finite_float(rule.get("evidence_quality"))))
        return value * confidence

    winner = max(contenders, key=lambda rule: (score(rule), str(rule.get("id", ""))))
    return {
        "status": "RESOLVED",
        "winning_rule": winner.get("id"),
        "precedence": top_level,
        "within_level_score": score(winner),
        "overridden_rules": [rule.get("id") for rule in valid if rule is not winner],
        "record_required": True,
        "hierarchy": (
            "legal/security/survival -> valid state -> E[log W] -> evidence -> marginal EV -> "
            "discovery -> information option value -> operations -> proxies"
        ),
    }


def context_packet(
    *,
    core: Sequence[str],
    doctrine_modules: Mapping[str, Sequence[str]],
    domain: str,
    dynamic_state: Mapping[str, object],
) -> dict[str, object]:
    """Give a specialist immutable core plus relevant doctrine and state, retaining provenance."""
    selected = list(doctrine_modules.get(domain, ()))
    packet = {
        "core_constitution": list(core),
        "domain": domain,
        "doctrine": selected,
        "dynamic_state": dict(dynamic_state),
    }
    rendered = repr(packet)
    all_doctrine = sum(len(list(rows)) for rows in doctrine_modules.values())
    return {
        "status": "MEASURED" if core and selected else "PARTIALLY_MEASURED",
        "packet": packet,
        "included_doctrine_items": len(selected),
        "omitted_irrelevant_doctrine_items": max(0, all_doctrine - len(selected)),
        "estimated_tokens": math.ceil(len(rendered) / 4),
        "guard": (
            "core survival/evidence/trust rules are never omitted; controller retains global state"
        ),
    }


OPEN_WORLD_DIMENSIONS = (
    "source",
    "language",
    "geography",
    "asset",
    "venue",
    "instrument",
    "horizon",
    "regime",
    "participant",
    "mechanism",
    "data_modality",
    "research_method",
    "validation_method",
    "execution_style",
    "portfolio_role",
    "risk_layer",
    "infrastructure_layer",
    "failure_mode",
)
COVERAGE_STATES = frozenset({"COVERED", "WEAKLY_COVERED", "UNTESTED", "BLOCKED", "UNKNOWN"})


def open_world_coverage(
    cells: Sequence[Mapping[str, object]],
    taxonomy_challenges: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Map and rank known coverage gaps while forcing daily discovery beyond the taxonomy.

    The supplied cells are deliberately sparse observations, not a Cartesian product. Unknown
    categories cannot be counted honestly, so known-cell coverage and taxonomy-renewal are reported
    separately and the open-world frontier is never labelled complete.
    """
    by_dimension: dict[str, Counter[str]] = {
        dimension: Counter() for dimension in OPEN_WORLD_DIMENSIONS
    }
    white_spaces: list[dict[str, object]] = []
    invalid: list[dict[str, object]] = []
    for index, cell in enumerate(cells):
        status = str(cell.get("status", "UNKNOWN")).upper().replace(" ", "_")
        if status not in COVERAGE_STATES:
            invalid.append({"index": index, "status": status})
            status = "UNKNOWN"
        represented = {
            dimension: str(cell[dimension])
            for dimension in OPEN_WORLD_DIMENSIONS
            if cell.get(dimension) not in (None, "")
        }
        for dimension in represented:
            by_dimension[dimension][status] += 1
        if status == "COVERED":
            continue
        value = cell.get("expected_elog_gain")
        information = cell.get("expected_information_gain")
        option = cell.get("unknown_unknown_option_value")
        cost = cell.get("cost")
        components = (value, information, option, cost)
        priority = (
            (finite_float(value) + finite_float(information) + finite_float(option))
            / finite_float(cost)
            if all(isinstance(component, (int, float)) for component in components)
            and finite_float(cost) > 0
            else None
        )
        lawful = cell.get("lawfully_obtainable") is not False
        white_spaces.append(
            {
                "cell_id": cell.get("id", index),
                "dimensions": represented,
                "status": status,
                "priority_score": priority if lawful else None,
                "lawfully_obtainable": lawful,
                "blocker": cell.get("blocker"),
                "next_action": cell.get("next_action"),
                "disposition_required": (
                    "IMPLEMENT | TEST | BLOCKED | REJECT | DEFER_BY_DOMINANCE"
                ),
            }
        )
    white_spaces.sort(
        key=lambda row: (
            not bool(row["lawfully_obtainable"]),
            row["priority_score"] is None,
            -finite_float(row.get("priority_score")),
            str(row["cell_id"]),
        )
    )
    dimension_rows: list[dict[str, object]] = []
    for dimension, counts in by_dimension.items():
        total = sum(counts.values())
        dimension_rows.append(
            {
                "dimension": dimension,
                "known_cells": total,
                "states": {state: counts.get(state, 0) for state in sorted(COVERAGE_STATES)},
                "known_cell_coverage": counts.get("COVERED", 0) / total if total else None,
                "status": "UNMEASURED"
                if total == 0
                else "GAPS_PRESENT"
                if counts.get("COVERED", 0) < total
                else "KNOWN_CELLS_COVERED",
            }
        )
    known_dimensions = set(OPEN_WORLD_DIMENSIONS)
    novel_dimensions = sorted(
        {
            str(row.get("dimension"))
            for row in taxonomy_challenges
            if row.get("dimension") and str(row.get("dimension")) not in known_dimensions
        }
    )
    challenge_methods = sorted(
        {str(row.get("search_method")) for row in taxonomy_challenges if row.get("search_method")}
    )
    known_total = sum(sum(counts.values()) for counts in by_dimension.values())
    known_covered = sum(counts.get("COVERED", 0) for counts in by_dimension.values())
    return {
        "status": "MEASURED" if cells else "UNMEASURED",
        "dimensions": dimension_rows,
        "known_cell_coverage": known_covered / known_total if known_total else None,
        "white_spaces": white_spaces,
        "daily_priority": [
            row
            for row in white_spaces
            if bool(row.get("lawfully_obtainable")) and row.get("priority_score") is not None
        ][:25],
        "invalid_states": invalid,
        "taxonomy_challenge_count": len(taxonomy_challenges),
        "taxonomy_challenge_methods": challenge_methods,
        "novel_dimensions_discovered": novel_dimensions,
        "taxonomy_renewing": bool(taxonomy_challenges),
        "frontier_complete": False,
        "law": (
            "maximize useful known-cell coverage daily and continually discover dimensions the "
            "coverage map does not yet contain; never infer open-world completion"
        ),
    }
