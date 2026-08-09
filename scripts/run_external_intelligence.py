#!/usr/bin/env python3
"""Convert elite public intelligence into measured internal frontier work.

This runner reuses the unified GPT Hunter corpus, existing hypothesis queue and generic gap
contract.  External claims enter as priors only; they cannot become survivors or capital actions.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.external_intelligence import (  # noqa: E402
    cross_universe_fusion,
    deep_forest_intelligence,
    descendant_tree,
    discovery_route_coverage,
    external_capability_graph,
    failure_harvest,
    mev_blockspace_frontier,
    mev_cex_fusion,
    microstructure_transitions,
    paper_transfer,
    portable_microstructure_representation,
    skilled_participant_sensors,
    survivor_white_space,
)
from libs.research.gap_contract import Gap, publish  # noqa: E402

OUT = ROOT / "data" / "intelligence" / "external_frontier.json"
QUEUE = ROOT / "data" / "hypothesis_queue.jsonl"


def _read(rel: str, default: Any = None) -> Any:
    try:
        return json.loads((ROOT / rel).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _rows(rel: str, key: str) -> list[dict[str, Any]]:
    doc = _read(rel, {})
    value = doc.get(key, []) if isinstance(doc, dict) else []
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _jsonl(rel: str) -> list[dict[str, Any]]:
    try:
        return [
            row
            for line in (ROOT / rel).read_text("utf-8").splitlines()
            if line.strip() and isinstance((row := json.loads(line)), dict)
        ]
    except (OSError, json.JSONDecodeError):
        return []


def _capabilities() -> list[str]:
    doc = _read("docs/research/COMPLETION_LEDGER.json", {})
    rows = doc.get("capabilities", doc) if isinstance(doc, dict) else []
    if isinstance(rows, dict):
        return [str(key) for key in rows]
    return (
        [
            str(row.get("id", row.get("capability_id")))
            for row in rows
            if isinstance(row, dict) and row.get("id", row.get("capability_id"))
        ]
        if isinstance(rows, list)
        else []
    )


def build() -> dict[str, Any]:
    items = _rows("data/intelligence/public_strategy_items.json", "items")
    papers = _rows("data/external_papers.json", "papers")
    failures = _rows("data/external_failures.json", "failures")
    participants = _rows("data/skilled_participant_events.json", "events")
    mev = _rows("data/mev_blockspace_events.json", "events")
    mev_cex = _rows("data/mev_cex_fusion_events.json", "events")
    transitions = _rows("data/microstructure_transition_events.json", "events")
    portable_doc = _read("data/portable_microstructure_events.json", {})
    portable = _rows("data/portable_microstructure_events.json", "events")
    portable_threshold = (
        portable_doc.get("max_preregistered_js") if isinstance(portable_doc, dict) else None
    )
    routes = _rows("data/discovery_route_events.json", "events")
    survivors = _rows("data/survivor_registry.json", "survivors")
    white_space = _rows("data/survivor_white_space_candidates.json", "cells")
    fusion_candidates = _rows("data/cross_universe_candidates.json", "candidates")
    deep_forest = _jsonl("data/intelligence/deep_forest_observations.jsonl")
    deep_forest.extend(
        {
            "lawfully_obtainable": True,
            "source": row.get("source", row.get("url")),
            "url": row.get("url"),
            "raw_text": row.get("text") or row.get("description") or row.get("title"),
            "translation": row.get("translation"),
            "language": row.get("language", "unknown"),
            "surface": row.get("source_kind", "public-strategy-hunter"),
            "source_timestamp": row.get("published_at"),
            "first_seen_at": row.get("first_seen_at"),
            "upstream_origin": row.get("upstream_origin", row.get("url")),
            "references": row.get("new_sources", []),
            "regional_terms": row.get("regional_terms", []),
            "economic_mechanism": row.get("mechanism"),
            "hypothesis": row.get("hypothesis"),
            "required_data": row.get("data"),
            "empirical_test": row.get("validation"),
            "falsifier": row.get("falsifier"),
            "evidence_class": row.get("evidence_class"),
            "component_assets": row.get("component_assets", []),
        }
        for row in items
    )
    deep_forest.extend(
        {
            "lawfully_obtainable": True,
            "source": row.get("source", "public-announcement"),
            "url": row.get("url"),
            "raw_text": f"{row.get('title', '')} {row.get('body', '')}".strip(),
            "surface": "public-announcement",
            "source_timestamp": row.get("published_at"),
            "first_seen_at": row.get("first_seen"),
            "uncertainty": "UNMEASURED",
        }
        for row in _jsonl("data/exchange_announcements.jsonl")
    )
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "authority": "EXTERNAL_PRIOR / RESEARCH ONLY -- ordinary internal validation mandatory",
        "capability_graph": external_capability_graph(items, _capabilities()),
        "paper_transfer": paper_transfer(papers),
        "failed_research_harvest": failure_harvest(failures),
        "skilled_participant_sensors": skilled_participant_sensors(participants),
        "mev_blockspace": mev_blockspace_frontier(mev),
        "mev_cex_fusion": mev_cex_fusion(mev_cex),
        "microstructure_transitions": microstructure_transitions(transitions),
        "portable_microstructure": portable_microstructure_representation(
            portable,
            max_preregistered_js=(
                float(portable_threshold) if isinstance(portable_threshold, (int, float)) else None
            ),
        ),
        "discovery_route_coverage": discovery_route_coverage(routes),
        "survivor_descendants": descendant_tree(survivors),
        "survivor_white_space": survivor_white_space(survivors, white_space),
        "cross_universe_fusion": cross_universe_fusion(fusion_candidates),
        "deep_forest_intelligence": deep_forest_intelligence(deep_forest),
        "prediction_market_frontier": (
            _read("reports/prediction_markets/report.json", {"status": "UNMEASURED"})
            or {"status": "UNMEASURED"}
        ),
    }


def _existing_ids() -> set[str]:
    ids = set()
    try:
        for line in QUEUE.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict) and row.get("external_candidate_id"):
                ids.add(str(row["external_candidate_id"]))
    except (OSError, json.JSONDecodeError):
        pass
    return ids


def _candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    mechanism = str(item.get("mechanism", "")).strip()
    if not mechanism or str(item.get("status", "")) != "EXTRACTED":
        return None
    hypothesis = str(item.get("hypothesis") or item.get("signal") or mechanism).strip()
    source = str(item.get("url", item.get("source", "")))
    identity = hashlib.sha256(f"{source}|{mechanism}|{hypothesis}".encode()).hexdigest()[:20]
    validation = item.get("validation")
    test = validation if isinstance(validation, str) else json.dumps(validation, default=str)
    return {
        "external_candidate_id": identity,
        "name": str(item.get("title") or mechanism)[:160],
        "hypothesis": hypothesis,
        "mechanism": mechanism,
        "data": item.get("data"),
        "test": test,
        "kill": item.get("falsifier"),
        "source": source,
        "evidence_class": item.get("evidence_class", "UNVERIFIED"),
        "status": "EXTERNAL_PRIOR",
        "search_method": "reverse_engineering",
        "contributors": {"source": item.get("source"), "mission": item.get("missions", [])},
        "authority": "CANDIDATE_ONLY -- graveyard, EV gate, multiplicity and forward validation apply",
    }


def inject_hypotheses(items: list[dict[str, Any]]) -> int:
    seen = _existing_ids()
    candidates = []
    for item in items:
        row = _candidate(item)
        if row is not None and row["external_candidate_id"] not in seen:
            seen.add(str(row["external_candidate_id"]))
            candidates.append(row)
    if not candidates:
        return 0
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE.open("a", encoding="utf-8") as handle:
        for row in candidates:
            handle.write(json.dumps(row, default=str) + "\n")
    return len(candidates)


def publish_gaps(report: dict[str, Any], injected: int) -> None:
    graph = report["capability_graph"]
    routes = report["discovery_route_coverage"]
    papers = report["paper_transfer"]
    route_rows = routes.get("routes", []) if isinstance(routes, dict) else []
    represented = routes.get("represented") if isinstance(routes, dict) else None
    total = routes.get("total") if isinstance(routes, dict) else None
    transfers = papers.get("transfers", []) if isinstance(papers, dict) else []
    completed = sum(
        row.get("first_missing_stage") is None for row in transfers if isinstance(row, dict)
    )
    gaps = [
        Gap(
            aspect="external_intelligence::discovery_route_coverage",
            source="evidence_throughput",
            current=(
                float(represented) / float(total)
                if isinstance(represented, (int, float))
                and isinstance(total, (int, float))
                and total
                else None
            ),
            ceiling=1.0,
            detail=f"represented={represented}/{total}; zero-output routes require diagnosis, not retirement",
            action="diagnose missing routes as frontier/data/miner/search-method/conversion failures",
            artifact=str(OUT.relative_to(ROOT)),
            tags=("external-intelligence", "coverage"),
        ),
        Gap(
            aspect="external_intelligence::paper_transfer",
            source="conversion_debt",
            current=(completed / len(transfers) if transfers else None),
            ceiling=1.0,
            detail=f"{completed}/{len(transfers)} papers completed all transfer stages",
            action="advance the highest-value paper's first missing replication/adversarial stage",
            artifact=str(OUT.relative_to(ROOT)),
            tags=("external-intelligence", "paper-transfer"),
        ),
        Gap(
            aspect="external_intelligence::capability_conversion",
            source="conversion_debt",
            current=(
                None
                if graph.get("status") == "UNMEASURED"
                else 1.0
                if injected or not graph.get("capability_gaps")
                else 0.0
            ),
            ceiling=1.0,
            detail=f"{len(graph.get('capability_gaps', []))} external capability gaps; {injected} hypotheses injected",
            action="replicate and adversarially test the highest-evidence external capability gap",
            artifact=str(OUT.relative_to(ROOT)),
            tags=("external-intelligence", "capability-gap"),
        ),
    ]
    missing = [
        row["route"] for row in route_rows if isinstance(row, dict) and not row.get("candidates")
    ]
    gaps[0] = Gap(**{**gaps[0].__dict__, "evidence": f"missing routes: {missing}"})
    publish("external_intelligence", gaps, directory=ROOT / "data" / "published_gaps")


def main() -> int:
    report = build()
    items = _rows("data/intelligence/public_strategy_items.json", "items")
    deep_candidates = report["deep_forest_intelligence"].get("hypothesis_candidates", [])
    injected = inject_hypotheses(items + [row for row in deep_candidates if isinstance(row, dict)])
    report["hypotheses_injected"] = injected
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    publish_gaps(report, injected)
    print(
        f"external-intelligence: {len(report['capability_graph']['nodes'])} graph nodes; "
        f"{injected} new candidates -> hypothesis queue; external claims remain priors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
