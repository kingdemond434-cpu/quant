from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1] / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import mission_control as mc  # noqa: E402


def _write(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc), "utf-8")
    return path


def test_snapshot_is_one_read_only_truthful_interface(tmp_path: Path) -> None:
    now = datetime.now(tz=UTC)
    inputs = {
        "knowledge_graph": (_write(tmp_path / "kg.json", {
            "n_nodes": 12, "n_edges": 20, "unconverted_testable_leads": 3,
            "top_sources_by_yield": [{"source_id": "x", "n_certified": 1}],
            "mechanisms_with_leads_but_no_cells": ["fixing_flow"],
        }), 2.5),
        "conversion": (_write(tmp_path / "conv.json", {
            "debt_after": {"total_debt": 7}, "new_cells": 4,
            "largest_blocker": {"status": "MEASURED", "blocker": "NO_DATA", "rows": 2,
                                "owner": "acquirer", "attack": "fetch"},
        }), 2.5),
        "certificates": (_write(tmp_path / "certs.json", {
            "n": 823, "survivors": {"a": {}, "b": {}},
        }), 2.5),
        "forward": (_write(tmp_path / "forward.json", {
            "lane": {"n_clocks": 577, "n_active": 576, "n_eligible": 0},
        }), 2.5),
        "breadth": (_write(tmp_path / "breadth.json", {
            "effective": {"effective_breadth": 2.483},
        }), 26.0),
    }
    snap = mc.build(now=now, inputs=inputs,
                    previous={"counters": {"knowledge_nodes": 10,
                                            "new_gauntlet_cells": 1}})
    assert snap["capital_authority"] is False
    assert snap["counters"]["knowledge_nodes"] == 12
    assert snap["since_previous_snapshot"]["knowledge_nodes"] == 2
    assert snap["since_previous_snapshot"]["new_gauntlet_cells"] == 3
    assert snap["counters"]["certificates"] == 823
    assert snap["counters"]["forward_clocks"] == 577
    assert snap["counters"]["forward_active"] == 576
    assert snap["counters"]["forward_eligible"] == 0
    assert snap["counters"]["forward_with_evidence"] is None
    assert snap["counters"]["effective_breadth"] == 2.483
    assert snap["blocked"][0]["status"] == "NO_DATA"
    disposition = snap["external_system_disposition"]
    assert disposition["silent_drops"] == 0
    assert {row["disposition"] for row in disposition["claims"]} == {
        "IMPLEMENTED", "DEDUPLICATED", "REFUSED_AS_EVIDENCE"}
    assert mc.answer("what happened overnight", snap)["answer"] == snap["overnight"]
    assert mc.answer("which researchers are productive", snap)["answer"][0]["source_id"] == "x"


def test_missing_input_is_attention_not_zero(tmp_path: Path) -> None:
    snap = mc.build(inputs={"forward": (tmp_path / "missing.json", 1.0)})
    assert snap["status"] == "ATTENTION"
    assert snap["source_health"]["forward"]["status"] == "MISSING"
    assert snap["counters"]["forward_with_evidence"] is None
