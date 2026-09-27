"""One read-only mission-control view over the quantitative institution.

This is the useful public organisational lesson from Bracket22: one place can answer what the
firm did, what is blocked, which sources convert, and what the institutional graph knows.  It is
an interface over canonical organs, never a second registry and never a capital authority.
Missing inputs remain UNMEASURED.  No count is reconstructed from prose.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORTS = DESK / "reports"
OUT = REPORTS / "MISSION_CONTROL.json"

INPUTS: dict[str, tuple[Path, float]] = {
    "knowledge_graph": (REPORTS / "KNOWLEDGE_GRAPH.json", 2.5),
    "conversion": (REPORTS / "CONVERSION_MAXIMISER.json", 2.5),
    "certificates": (REPORTS / "UNIVERSAL_SURVIVORS.json", 2.5),
    "forward": (REPORTS / "FORWARD_CALIBRATION.json", 2.5),
    "breadth": (REPORTS / "EFFECTIVE_BREADTH.json", 26.0),
    "execution": (REPORTS / "execution_quality.json", 26.0),
    "allocation": (REPORTS / "pf_allocation.json", 2.5),
    "plumbing": (REPORTS / "PLUMBING_INVARIANTS.json", 2.5),
    "self_heal": (REPORTS / "DESK_SELF_HEAL.json", 2.5),
    "tier5": (REPORTS / "TIER5_ACCEPTANCE.json", 26.0),
}

BRACKET22_DISPOSITION: tuple[dict[str, str], ...] = (
    {"claim": "one chief-of-staff interface over a persistent AI firm",
     "disposition": "IMPLEMENTED", "canonical": "research/mission_control.py"},
    {"claim": "persistent corporate brain linking research and outcomes",
     "disposition": "DEDUPLICATED", "canonical": "research/knowledge_graph.py"},
    {"claim": "independent red-team researcher attacks each thesis",
     "disposition": "DEDUPLICATED", "canonical": "research/adversary.py + mathlab/institution.py"},
    {"claim": "asynchronous 24/7 specialist research",
     "disposition": "DEDUPLICATED", "canonical": "hourly_cycle.py + box_tasks.manifest"},
    {"claim": "reported cost/productivity and trading performance",
     "disposition": "REFUSED_AS_EVIDENCE",
     "canonical": "unaudited claims create no AlphaCell and grant no capital"},
)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _atomic(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=1, default=str)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _nested(doc: Mapping[str, Any] | None, *keys: str) -> Any:
    value: Any = doc
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _number(doc: Mapping[str, Any] | None,
            paths: tuple[tuple[str, ...], ...]) -> int | float | None:
    for path in paths:
        value = _nested(doc, *path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, list):
            return len(value)
    return None


def build(*, now: datetime | None = None,
          inputs: Mapping[str, tuple[Path, float]] | None = None,
          previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    specs = dict(inputs or INPUTS)
    docs: dict[str, dict[str, Any] | None] = {}
    health: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    for name, (path, max_age_h) in specs.items():
        doc = _read(path)
        docs[name] = doc
        try:
            age_h = max(0.0, (now.timestamp() - path.stat().st_mtime) / 3600.0)
        except OSError:
            age_h = None
        status = ("MISSING" if doc is None else
                  "STALE" if age_h is None or age_h > max_age_h else "CURRENT")
        health[name] = {"status": status, "path": str(path),
                        "age_h": round(age_h, 3) if age_h is not None else None,
                        "max_age_h": max_age_h}
        if status != "CURRENT":
            issues.append({"kind": "producer_health", "organ": name, "status": status,
                           "owner": str(path), "action": "run or repair the canonical producer"})

    counters = {
        "knowledge_nodes": _number(docs.get("knowledge_graph"), (("n_nodes",),)),
        "knowledge_edges": _number(docs.get("knowledge_graph"), (("n_edges",),)),
        "unconverted_leads": _number(
            docs.get("knowledge_graph"), (("unconverted_testable_leads",),)),
        "conversion_debt": _number(
            docs.get("conversion"), (("debt_after", "total_debt"),)),
        "new_gauntlet_cells": _number(docs.get("conversion"), (("new_cells",),)),
        "certificates": _number(
            docs.get("certificates"), (("certified",), ("certificates",), ("rows",))),
        "forward_with_evidence": _number(
            docs.get("forward"), (("with_trades",), ("measured",), ("trades",))),
        "effective_breadth": _number(
            docs.get("breadth"), (("effective_breadth",), ("n_eff",))),
    }
    old = previous.get("counters", {}) if isinstance(previous, Mapping) else {}
    deltas: dict[str, int | float | None] = {}
    for name, value in counters.items():
        prior = old.get(name) if isinstance(old, Mapping) else None
        deltas[name] = value - prior if isinstance(value, (int, float)) and isinstance(
            prior, (int, float)) else None

    blocker = _nested(docs.get("conversion"), "largest_blocker")
    if isinstance(blocker, Mapping) and blocker.get("status") == "MEASURED":
        issues.append({"kind": "conversion", "organ": blocker.get("owner"),
                       "status": blocker.get("blocker"), "rows": blocker.get("rows"),
                       "action": blocker.get("attack")})
    unrepaired = _nested(docs.get("self_heal"), "unrepaired")
    if isinstance(unrepaired, list):
        issues.extend({"kind": "self_heal", **row} for row in unrepaired
                      if isinstance(row, dict))

    graph = docs.get("knowledge_graph") or {}
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "CURRENT" if not issues else "ATTENTION",
        "authority": "READ_AND_ROUTE_RESEARCH_ONLY",
        "capital_authority": False,
        "counters": counters,
        "since_previous_snapshot": deltas,
        "overnight": {
            "what_changed": {k: v for k, v in deltas.items() if v not in (None, 0)},
            "unmeasured": [k for k, v in deltas.items() if v is None],
            "note": "deltas compare durable mission-control snapshots; first run is UNMEASURED",
        },
        "blocked": issues,
        "research_productivity": graph.get("top_sources_by_yield", []),
        "under_researched": {
            "mechanisms_with_leads_but_no_cells": graph.get(
                "mechanisms_with_leads_but_no_cells", []),
            "unconverted_testable_leads": graph.get("unconverted_testable_leads"),
        },
        "source_health": health,
        "question_contract": ["what happened overnight", "what is blocked",
                              "which researchers are productive", "what is under-researched",
                              "what do we know about <term>"],
        "external_system_disposition": {
            "system": "Bracket22",
            "source_status": "USER_PROVIDED_SECONDARY_SUMMARY_UNVERIFIED",
            "claims": list(BRACKET22_DISPOSITION),
            "silent_drops": 0,
        },
        "boundary": ("no promotion, sizing, allocation, risk-limit, gate, arming or order "
                     "authority; every answer cites canonical state"),
    }


def answer(question: str, snapshot: Mapping[str, Any], *, term: str = "") -> dict[str, Any]:
    q = question.lower().strip()
    if "overnight" in q or "while i" in q:
        return {"question": question, "answer": snapshot.get("overnight"),
                "source": str(OUT)}
    if "block" in q or "wrong" in q or "failed" in q:
        return {"question": question, "answer": snapshot.get("blocked"),
                "source": str(OUT)}
    if "productive" in q or "researcher" in q or "scientist" in q:
        return {"question": question, "answer": snapshot.get("research_productivity"),
                "source": "KNOWLEDGE_GRAPH.json::top_sources_by_yield"}
    if "under-research" in q or "coverage" in q or "missing" in q:
        return {"question": question, "answer": snapshot.get("under_researched"),
                "source": "KNOWLEDGE_GRAPH.json"}
    if term:
        try:
            import knowledge_graph
            result = knowledge_graph.what_do_we_know(term)
        except Exception as exc:
            result = {"term": term,
                      "unmeasured": [f"graph query failed: {type(exc).__name__}: {exc}"]}
        return {"question": question, "answer": result,
                "source": "knowledge_graph.what_do_we_know"}
    return {"question": question, "answer": None,
            "unmeasured": ("question not in the deterministic contract; provide --term for "
                           "graph lookup")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--question", default="")
    parser.add_argument("--term", default="")
    args = parser.parse_args(argv)
    previous = _read(args.out)
    snapshot = build(previous=previous)
    _atomic(args.out, snapshot)
    if args.question:
        print(json.dumps(answer(args.question, snapshot, term=args.term), indent=1, default=str))
    else:
        print(f"mission control: {snapshot['status']} issues={len(snapshot['blocked'])} "
              f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
