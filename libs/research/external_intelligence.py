"""External capability transfer and renewable survivor-frontier intelligence.

Everything here is research-state transformation.  Public claims remain priors, participant
behaviour remains a sensor, empty white-space remains a question, and no output can promote a
strategy or direct a trade.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from libs.core.coerce import finite_float, integer, object_sequence

DISCOVERY_ROUTES = (
    "external_research",
    "internal_mechanism_generation",
    "data_first_mining",
    "anomaly_mining",
    "failure_mining",
    "near_survivor_recovery",
    "live_discrepancy_mining",
    "skilled_participant_behavior",
    "execution_anomalies",
    "mev_blockspace",
    "state_transition_models",
    "prediction_markets",
    "cross_domain_fusion",
    "multilingual_communities",
    "obscure_open_source",
    "open_research_questions",
    "new_search_methods",
)

PAPER_STAGES = (
    "mechanism_extracted",
    "code_data_located",
    "method_inspected",
    "timestamps_universe_reconstructed",
    "independently_reproduced",
    "adversarially_tested",
    "costs_tested",
    "transport_tested",
    "portfolio_independence_tested",
    "descendants_generated",
    "proprietary_state_combination_tested",
)


def external_capability_graph(
    items: Sequence[Mapping[str, object]], internal_capabilities: Sequence[str] = ()
) -> dict[str, object]:
    known = {str(value).casefold() for value in internal_capabilities}
    nodes: dict[tuple[str, str], dict[str, object]] = {}
    edges: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    for item in items:
        source = str(item.get("url", item.get("source", "")))
        evidence = str(item.get("evidence_class", "UNVERIFIED")).upper()
        entities = item.get("entities", [])
        if isinstance(entities, list):
            for entity in entities:
                if not isinstance(entity, Mapping) or not entity.get("name"):
                    continue
                kind, name = str(entity.get("type", "unknown")), str(entity["name"])
                key = (kind, name.casefold())
                node = nodes.setdefault(
                    key,
                    {
                        "type": kind,
                        "name": name,
                        "sources": [],
                        "reproducible_outputs": 0,
                        "internal_replications": 0,
                        "independent_survivors": 0,
                        "marketing_or_unreproducible": 0,
                    },
                )
                sources = node.get("sources")
                if isinstance(sources, list):
                    sources.append(source)
                node["reproducible_outputs"] = integer(node.get("reproducible_outputs")) + int(
                    bool(item.get("reproducible"))
                )
                node["internal_replications"] = integer(node.get("internal_replications")) + int(
                    bool(item.get("internal_replication"))
                )
                node["independent_survivors"] = integer(node.get("independent_survivors")) + int(
                    bool(item.get("independent_survivor"))
                )
                node["marketing_or_unreproducible"] = integer(
                    node.get("marketing_or_unreproducible")
                ) + int(bool(item.get("marketing")) or evidence in {"UNVERIFIED", "CLAIM_ONLY"})
        raw_edges = item.get("relationships", [])
        if isinstance(raw_edges, list):
            edges.extend(
                {**dict(edge), "source": source} for edge in raw_edges if isinstance(edge, Mapping)
            )
        raw_gaps = item.get("capability_gaps", [])
        if isinstance(raw_gaps, list):
            for gap in raw_gaps:
                row = dict(gap) if isinstance(gap, Mapping) else {"capability": str(gap)}
                capability = str(row.get("capability", "")).strip()
                if not capability or capability.casefold() in known:
                    continue
                gaps.append(
                    {
                        **row,
                        "capability": capability,
                        "source": source,
                        "evidence_class": evidence,
                        "status": "GAP_CANDIDATE",
                        "next": (
                            "replicate -> adversarial test -> adapt -> integrate -> "
                            "ordinary validation"
                        ),
                    }
                )
    ranked_nodes = sorted(
        nodes.values(),
        key=lambda row: (
            -integer(row.get("independent_survivors")),
            -integer(row.get("internal_replications")),
            -integer(row.get("reproducible_outputs")),
            integer(row.get("marketing_or_unreproducible")),
            str(row["name"]),
        ),
    )
    return {
        "status": "MEASURED" if items else "UNMEASURED",
        "nodes": ranked_nodes,
        "edges": edges,
        "capability_gaps": gaps,
        "ranking_law": "demonstrated downstream information value, never fame",
    }


def paper_transfer(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    transfers = []
    for row in rows:
        completed = row.get("stages", {})
        completed = completed if isinstance(completed, Mapping) else {}
        first_missing = next((stage for stage in PAPER_STAGES if not completed.get(stage)), None)
        replication = str(row.get("replication_result", "UNMEASURED")).upper()
        status = (
            "REPLICATION_FAILED_INFORMATION_BANKED"
            if replication in {"FAILED", "REFUTED"}
            else "READY_FOR_INTERNAL_VALIDATION"
            if first_missing is None
            else "IN_PROGRESS"
        )
        transfers.append(
            {
                "id": row.get("id", row.get("url")),
                "status": status,
                "completed_stages": sum(bool(completed.get(stage)) for stage in PAPER_STAGES),
                "total_stages": len(PAPER_STAGES),
                "first_missing_stage": first_missing,
                "replication_result": replication,
                "descendant_hypotheses": row.get("descendant_hypotheses", []),
                "authority": "successful replication is not survivor promotion",
            }
        )
    return {"status": "MEASURED" if rows else "UNMEASURED", "transfers": transfers}


def failure_harvest(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    out = []
    for row in rows:
        assets: list[dict[str, object]] = []
        for key in (
            "datasets",
            "infrastructure",
            "negative_knowledge",
            "conditional_effects",
            "alternate_targets",
            "alternate_horizons",
            "execution_uses",
            "adjacent_mechanisms",
        ):
            value = row.get(key, [])
            if isinstance(value, list):
                assets.extend({"type": key, "value": item} for item in value)
        out.append(
            {
                "failure_id": row.get("id"),
                "cause": row.get("failure_cause", "UNMEASURED"),
                "harvested_assets": assets,
                "information_banked": bool(assets),
                "status": "HARVESTED" if assets else "UNMEASURED",
            }
        )
    return {"status": "MEASURED" if rows else "UNMEASURED", "failures": out}


def skilled_participant_sensors(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_actor: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for event in events:
        by_actor[str(event.get("actor", "UNKNOWN"))].append(event)
    sensors = []
    for actor, rows in by_actor.items():
        rows.sort(key=lambda row: str(row.get("as_of", "")))
        outcomes = [
            finite_float(row.get("outcome"))
            for row in rows
            if isinstance(row.get("outcome"), (int, float))
        ]
        calibrated = [
            (finite_float(row.get("probability")), finite_float(row.get("outcome")))
            for row in rows
            if isinstance(row.get("probability"), (int, float))
            and isinstance(row.get("outcome"), (int, float))
        ]
        brier = (
            sum((probability - outcome) ** 2 for probability, outcome in calibrated)
            / len(calibrated)
            if calibrated
            else None
        )
        sensors.append(
            {
                "actor": actor,
                "observations": len(rows),
                "mean_outcome": sum(outcomes) / len(outcomes) if outcomes else None,
                "brier": round(brier, 12) if brier is not None else None,
                "reaction_latency_median": _median(
                    [
                        finite_float(row.get("reaction_latency_seconds"))
                        for row in rows
                        if isinstance(row.get("reaction_latency_seconds"), (int, float))
                    ]
                ),
                "regimes": sorted({str(row.get("regime")) for row in rows if row.get("regime")}),
                "authority": (
                    "INFORMATION_SENSOR_ONLY -- never copy trades or infer private identity"
                ),
            }
        )
    return {"status": "MEASURED" if events else "UNMEASURED", "sensors": sensors}


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def mev_blockspace_frontier(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    dimensions = ("cex", "dex", "mempool", "oracle", "builder")
    interactions: Counter[str] = Counter()
    inclusion: list[float] = []
    latency: list[float] = []
    for event in events:
        active = tuple(name for name in dimensions if event.get(name) is not None)
        if len(active) >= 2:
            interactions["x".join(active)] += 1
        included = event.get("included")
        if isinstance(included, bool):
            inclusion.append(float(included))
        inclusion_latency = event.get("inclusion_latency_seconds")
        if isinstance(inclusion_latency, (int, float)):
            latency.append(float(inclusion_latency))
    return {
        "status": "MEASURED" if events else "UNMEASURED",
        "events": len(events),
        "interaction_coverage": dict(interactions),
        "inclusion_probability": sum(inclusion) / len(inclusion) if inclusion else None,
        "median_inclusion_latency_seconds": _median(latency),
        "missing_domains": [
            name for name in dimensions if not any(row.get(name) is not None for row in events)
        ],
        "note": "blockspace state is independent microstructure, not generic wallet analytics",
    }


def microstructure_transitions(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    venue_counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        current, future = row.get("current_state"), row.get("future_state")
        if current is None or future is None:
            continue
        counts[str(current)][str(future)] += 1
        venue_counts[str(row.get("venue", "UNKNOWN"))][str(current)][str(future)] += 1

    def posterior(table: Mapping[str, Counter[str]]) -> dict[str, dict[str, float]]:
        states = sorted(set(table) | {future for values in table.values() for future in values})
        return {
            current: {
                future: (table.get(current, Counter()).get(future, 0) + 1)
                / (sum(table.get(current, Counter()).values()) + len(states))
                for future in states
            }
            for current in states
        }

    return {
        "status": "MEASURED" if counts else "UNMEASURED",
        "posterior": posterior(counts) if counts else {},
        "by_venue": {venue: posterior(table) for venue, table in venue_counts.items()},
        "uses": [
            "direction",
            "execution",
            "maker_taker",
            "risk",
            "liquidation",
            "volatility",
            "activation",
        ],
        "guard": "states must be observable at decision time; selection trials remain counted",
    }


def discovery_route_coverage(events: Sequence[Mapping[str, object]]) -> dict[str, object]:
    counts = Counter(str(event.get("route", "UNATTRIBUTED")) for event in events)
    rows: list[dict[str, object]] = []
    for route in DISCOVERY_ROUTES:
        n = counts.get(route, 0)
        rows.append(
            {
                "route": route,
                "candidates": n,
                "status": "ACTIVE" if n else "DIAGNOSIS_REQUIRED",
                "zero_output_diagnosis": None
                if n
                else [
                    "low frontier value",
                    "weak miner",
                    "missing data",
                    "inadequate search method",
                    "broken conversion pipeline",
                ],
            }
        )
    return {
        "status": "MEASURED" if events else "UNMEASURED",
        "routes": rows,
        "represented": sum(integer(row.get("candidates")) > 0 for row in rows),
        "total": len(rows),
        "unattributed": counts.get("UNATTRIBUTED", 0),
        "law": "zero output is never automatically zero opportunity",
    }


def descendant_tree(survivors: Sequence[Mapping[str, object]]) -> dict[str, object]:
    branches = []
    for survivor in survivors:
        descendants = survivor.get("descendant_candidates")
        for child in descendants if isinstance(descendants, list) else []:
            if not isinstance(child, Mapping):
                continue
            value, cost = child.get("expected_information_value"), child.get("cost")
            marginal = (
                float(value) - float(cost)
                if isinstance(value, (int, float)) and isinstance(cost, (int, float))
                else None
            )
            branches.append(
                {
                    "parent_survivor": survivor.get("id"),
                    "hypothesis": child.get("hypothesis"),
                    "axis": child.get("axis"),
                    "marginal_information_value": marginal,
                    "status": "PREREGISTRATION_REQUIRED"
                    if marginal is not None and marginal > 0
                    else "STOP_OR_UNMEASURED",
                }
            )
    return {"status": "MEASURED" if survivors else "UNMEASURED", "branches": branches}


def survivor_white_space(
    survivors: Sequence[Mapping[str, object]], candidate_cells: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    dimensions = (
        "asset",
        "venue",
        "instrument",
        "participant",
        "geography",
        "language",
        "horizon",
        "regime",
        "data_modality",
        "mechanism",
        "execution_style",
    )
    occupied = {tuple(str(row.get(name, "UNKNOWN")) for name in dimensions) for row in survivors}
    cells = []
    for cell in candidate_cells:
        key = tuple(str(cell.get(name, "UNKNOWN")) for name in dimensions)
        empty = key not in occupied
        plausible = bool(cell.get("economic_plausibility"))
        components = [
            cell.get(name)
            for name in (
                "independence",
                "crisis_diversification",
                "capacity",
                "persistence",
                "complementarity",
            )
        ]
        measured = all(isinstance(value, (int, float)) for value in components)
        cost = cell.get("cost")
        score = (
            sum(finite_float(value) for value in components) / max(finite_float(cost), 1e-12)
            if measured and isinstance(cost, (int, float)) and float(cost) > 0
            else None
        )
        cells.append(
            {
                "cell": dict(zip(dimensions, key, strict=True)),
                "empty": empty,
                "economic_plausibility": plausible,
                "priority_score": score if empty and plausible else None,
                "status": "TARGET_CANDIDATE" if empty and plausible else "NOT_AN_OPPORTUNITY",
            }
        )
    cells.sort(
        key=lambda row: (
            -finite_float(row.get("priority_score"))
            if isinstance(row.get("priority_score"), (int, float))
            else math.inf
        )
    )
    return {
        "status": "MEASURED" if survivors or candidate_cells else "UNMEASURED",
        "dimensions": list(dimensions),
        "occupied_cells": len(occupied),
        "candidate_cells": cells,
        "guard": "an empty cell is not evidence of an opportunity",
    }


__all__ = [
    "DISCOVERY_ROUTES",
    "FUSION_VALUE_DIMENSIONS",
    "PAPER_STAGES",
    "cross_universe_fusion",
    "deep_forest_intelligence",
    "descendant_tree",
    "discovery_route_coverage",
    "external_capability_graph",
    "failure_harvest",
    "mev_blockspace_frontier",
    "mev_cex_fusion",
    "microstructure_transitions",
    "paper_transfer",
    "portable_microstructure_representation",
    "skilled_participant_sensors",
    "survivor_white_space",
]


def mev_cex_fusion(
    events: Sequence[Mapping[str, object]], *, min_cell_n: int = 30
) -> dict[str, object]:
    """Screen CEX state x blockspace state without treating thin conditional cells as evidence."""
    if min_cell_n < 2:
        raise ValueError("min_cell_n must be at least 2")
    cells: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for event in events:
        key = (
            str(event.get("cex_state", "UNKNOWN")),
            str(event.get("blockspace_state", "UNKNOWN")),
            str(event.get("liquidation_state", "UNKNOWN")),
        )
        cells[key].append(event)
    rows: list[dict[str, object]] = []
    for key, observations in cells.items():
        metrics = {}
        for name in (
            "future_return",
            "future_volatility",
            "execution_cost_bps",
            "inclusion_latency_seconds",
        ):
            values = [
                finite_float(row.get(name))
                for row in observations
                if isinstance(row.get(name), (int, float))
            ]
            metrics[name] = sum(values) / len(values) if values else None
        rows.append(
            {
                "cex_state": key[0],
                "blockspace_state": key[1],
                "liquidation_state": key[2],
                "n": len(observations),
                "status": "SCREEN_READY" if len(observations) >= min_cell_n else "UNDERPOWERED",
                "conditional_means": metrics,
            }
        )
    return {
        "status": "MEASURED" if events else "UNMEASURED",
        "cells": rows,
        "effective_trials": len(rows),
        "min_cell_n": min_cell_n,
        "authority": (
            "SCREEN_ONLY -- family multiplicity, costs and untouched forward evidence apply"
        ),
    }


def portable_microstructure_representation(
    events: Sequence[Mapping[str, object]], *, max_preregistered_js: float | None = None
) -> dict[str, object]:
    """Measure whether discrete LOB-state transitions transport across assets.

    No portability threshold is inferred from these results.  Transfer candidates are emitted only
    when the caller supplies a threshold declared before inspecting this evidence.
    """
    if max_preregistered_js is not None and not 0 <= max_preregistered_js <= math.log(2):
        raise ValueError("max_preregistered_js must lie in [0, log(2)]")
    tables: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for event in events:
        asset, state, future = (
            event.get("asset"),
            event.get("representation"),
            event.get("future_state"),
        )
        if asset is None or state is None or future is None:
            continue
        tables[str(asset)][str(state)][str(future)] += 1
    assets = sorted(tables)
    pairs = []

    def js(left: Counter[str], right: Counter[str]) -> float:
        outcomes = sorted(set(left) | set(right))
        lp = [(left.get(value, 0) + 1) / (sum(left.values()) + len(outcomes)) for value in outcomes]
        rp = [
            (right.get(value, 0) + 1) / (sum(right.values()) + len(outcomes)) for value in outcomes
        ]
        mid = [(a + b) / 2 for a, b in zip(lp, rp, strict=True)]
        return 0.5 * sum(a * math.log(a / m) for a, m in zip(lp, mid, strict=True)) + 0.5 * sum(
            b * math.log(b / m) for b, m in zip(rp, mid, strict=True)
        )

    for i, left_asset in enumerate(assets):
        for right_asset in assets[i + 1 :]:
            common = sorted(set(tables[left_asset]) & set(tables[right_asset]))
            divergences = [
                js(tables[left_asset][state], tables[right_asset][state]) for state in common
            ]
            mean_js = sum(divergences) / len(divergences) if divergences else None
            pairs.append(
                {
                    "left_asset": left_asset,
                    "right_asset": right_asset,
                    "common_representations": len(common),
                    "mean_js_divergence": mean_js,
                    "transfer_candidate": (
                        mean_js is not None
                        and max_preregistered_js is not None
                        and mean_js <= max_preregistered_js
                    ),
                }
            )
    return {
        "status": "MEASURED" if tables else "UNMEASURED",
        "assets": assets,
        "pairwise_transport": pairs,
        "preregistered_js_threshold": max_preregistered_js,
        "authority": "REPRESENTATION SCREEN ONLY -- leave-one-asset/venue-out validation required",
    }


FUSION_VALUE_DIMENSIONS = (
    "expected_information_gain",
    "survivor_generation_potential",
    "independence",
    "capacity",
    "persistence",
    "asymmetry",
    "option_value",
)


def cross_universe_fusion(
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Rank hypotheses whose state exists only through a join of distinct universes."""
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        universes = candidate.get("universes", [])
        universes = (
            list(dict.fromkeys(str(value) for value in universes))
            if isinstance(universes, list)
            else []
        )
        row = {
            "id": candidate.get("id", candidate.get("hypothesis")),
            "universes": universes,
            "hidden_state": candidate.get("hidden_state"),
            "hypothesis": candidate.get("hypothesis"),
        }
        if candidate.get("lawfully_obtainable") is not True:
            rows.append({**row, "status": "INELIGIBLE_OR_LEGAL_REVIEW_REQUIRED"})
            continue
        if len(universes) < 2 or not candidate.get("hypothesis"):
            rows.append({**row, "status": "INVALID_FUSION", "priority_score": None})
            continue
        values = [candidate.get(name) for name in FUSION_VALUE_DIMENSIONS]
        cost = candidate.get("acquisition_research_cost")
        measured = all(isinstance(value, (int, float)) for value in values)
        score = (
            sum(finite_float(value) for value in values) / finite_float(cost)
            if measured and isinstance(cost, (int, float)) and float(cost) > 0
            else None
        )
        rows.append(
            {
                **row,
                "status": "TESTABLE_CANDIDATE" if score is not None else "UNMEASURED",
                "value_components": dict(zip(FUSION_VALUE_DIMENSIONS, values, strict=True)),
                "acquisition_research_cost": cost,
                "priority_score": score,
                "disposition_required": "TEST_NOW | TEST_LATER_WITH_BLOCKER | REJECT_BEFORE_TEST",
                "authority": "HYPOTHESIS ONLY -- multiplicity and untouched evidence apply",
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("priority_score") is None,
            -finite_float(row.get("priority_score")),
            str(row.get("id")),
        )
    )
    represented = sorted(
        {str(universe) for row in rows for universe in object_sequence(row.get("universes"))}
    )
    return {
        "status": "MEASURED" if candidates else "UNMEASURED",
        "candidates": rows,
        "represented_universes": represented,
        "value_dimensions": list(FUSION_VALUE_DIMENSIONS),
        "law": "one universe should reveal hidden state driving another",
    }


_DEEP_FOREST_INJECTION = re.compile(
    r"(?:ignore (?:all |any )?(?:previous|system)|reveal (?:the )?system prompt|"
    r"execute (?:this |the )?command|send (?:me )?(?:credentials|keys|secrets))",
    re.IGNORECASE,
)
_DEEP_FOREST_PROMOTION = re.compile(
    r"(?:guaranteed returns?|risk[- ]free|limited time|referral|affiliate|pump now)",
    re.IGNORECASE,
)


def _utc(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def deep_forest_intelligence(
    records: Sequence[Mapping[str, object]],
    *,
    known_vocabulary: Sequence[str] = (),
) -> dict[str, object]:
    """Convert lawful raw multilingual evidence into durable, skeptical research records.

    This is an ingestion boundary for public or explicitly authorized exports. Collected text is
    always untrusted data; it has no instruction, validation, promotion, execution or capital
    authority. Corroboration is counted by upstream origin, not repost count.
    """
    known = {str(term).casefold() for term in known_vocabulary}
    fingerprints: dict[str, list[dict[str, object]]] = defaultdict(list)
    source_edges: set[tuple[str, str]] = set()
    vocabulary: set[str] = set()
    rejected = []
    normalized = []
    hypotheses = []
    for record in records:
        source = str(record.get("source", record.get("url", "UNKNOWN")))
        if record.get("lawfully_obtainable") is not True:
            rejected.append(
                {
                    "source": source,
                    "status": "ACCESS_BOUNDARY_REJECTED",
                    "reason": "public or explicitly authorized access was not established",
                }
            )
            continue
        raw = str(record.get("original_text") or record.get("raw_text") or record.get("text") or "")
        translated = str(record.get("translation") or "")
        compact = re.sub(r"\s+", " ", raw).strip()
        fingerprint = hashlib.sha256(compact.casefold().encode()).hexdigest()[:20]
        upstream = str(record.get("upstream_origin") or record.get("origin") or source)
        published = _utc(record.get("source_timestamp") or record.get("published_at"))
        first_seen = _utc(record.get("first_seen_at") or record.get("ingested_at"))
        mainstream = _utc(record.get("mainstream_publication_at"))
        reaction = _utc(record.get("market_reaction_at"))
        lead_seconds = (
            (first_seen - published).total_seconds()
            if published is not None and first_seen
            else None
        )
        mainstream_lead = (
            (mainstream - first_seen).total_seconds()
            if mainstream is not None and first_seen is not None
            else None
        )
        reaction_lead = (
            (reaction - first_seen).total_seconds()
            if reaction is not None and first_seen is not None
            else None
        )
        terms = record.get("regional_terms", [])
        if isinstance(terms, list):
            vocabulary.update(str(term) for term in terms if str(term).casefold() not in known)
        references = record.get("references", record.get("new_sources", []))
        if isinstance(references, list):
            source_edges.update((source, str(target)) for target in references if target)
        poison_flags = []
        if _DEEP_FOREST_INJECTION.search(raw):
            poison_flags.append("PROMPT_INJECTION_TEXT")
        if _DEEP_FOREST_PROMOTION.search(raw):
            poison_flags.append("PROMOTIONAL_OR_MANIPULATIVE_LANGUAGE")
        row = {
            "source": source,
            "language": record.get("language", "unknown"),
            "surface": record.get("surface", "unknown"),
            "original_text": raw,
            "translation": translated or None,
            "semantic_fingerprint": fingerprint,
            "upstream_origin": upstream,
            "source_timestamp": published.isoformat() if published else None,
            "first_seen_at": first_seen.isoformat() if first_seen else None,
            "collection_latency_seconds": lead_seconds,
            "lead_to_mainstream_seconds": mainstream_lead,
            "lead_to_market_reaction_seconds": reaction_lead,
            "information_half_life_seconds": record.get("information_half_life_seconds"),
            "poison_flags": poison_flags,
            "uncertainty": record.get("uncertainty", "UNMEASURED"),
            "untrusted_external_content": True,
            "authority": "RAW_EVIDENCE_ONLY",
        }
        fingerprints[fingerprint].append({"source": source, "upstream_origin": upstream})
        normalized.append(row)
        mechanism = str(record.get("economic_mechanism") or record.get("mechanism") or "").strip()
        hypothesis = str(record.get("hypothesis") or "").strip()
        required_data = record.get("required_data") or record.get("data")
        empirical_test = record.get("empirical_test") or record.get("validation")
        if mechanism and hypothesis and required_data and empirical_test:
            hypotheses.append(
                {
                    "status": "EXTRACTED",
                    "source": source,
                    "url": record.get("url", source),
                    "title": record.get("title", mechanism),
                    "mechanism": mechanism,
                    "hypothesis": hypothesis,
                    "data": required_data,
                    "validation": empirical_test,
                    "falsifier": record.get("falsifier"),
                    "evidence_class": record.get("evidence_class", "UNVERIFIED_CHATTER"),
                    "component_assets": record.get("component_assets", []),
                    "authority": "EXTERNAL_PRIOR_ONLY",
                }
            )
    independence = []
    for fingerprint, mentions in fingerprints.items():
        origins = sorted({str(row["upstream_origin"]) for row in mentions})
        independence.append(
            {
                "semantic_fingerprint": fingerprint,
                "mentions": len(mentions),
                "independent_origins": len(origins),
                "origins": origins,
            }
        )
    return {
        "status": "MEASURED" if records else "UNMEASURED",
        "accepted": len(normalized),
        "access_rejected": rejected,
        "normalized_records": normalized,
        "source_graph_edges": [
            {"from": left, "to": right, "type": "REFERENCES"}
            for left, right in sorted(source_edges)
        ],
        "source_independence": independence,
        "new_regional_vocabulary": sorted(vocabulary),
        "hypothesis_candidates": hypotheses,
        "raw_to_research_conversion_rate": len(hypotheses) / len(normalized)
        if normalized
        else None,
        "access_law": "public or explicitly authorized only; never bypass access controls",
        "validation_law": "external content and model opinion never establish alpha",
    }
