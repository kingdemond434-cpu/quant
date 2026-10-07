"""THE REGIONAL PARITY ORGAN -- the table is written, the digest is small, the queue becomes work.

    python -m pytest desks/mt5/tests/test_regional_parity_pass.py -q -p no:cacheprovider

What is fenced here:

  * ONE PASS WRITES FIVE THINGS, all gitignored box state: reports/REGIONAL_PARITY.json, the
    digest under data/digests/, the candidate-class ledger, the dataset hunter's parity targets,
    and a `discoveries_parity_<date>.json` in the exact shape `acquire_datasets._endpoints` reads
    (rows with `endpoints`, `host` and the parity `lane` marker);
  * AN UNMATCHED DECLARATION IS A PERSISTED CANDIDATE CLASS, never dropped, even once absent;
  * EVERY UNMEASURED CELL REACHES THE DATASET HUNTER as a parity target;
  * --dry-run WRITES NO BYTE;
  * WITH NO LEDGER ON DISK NOTHING IS COVERED and the absence is named UNMEASURED;
  * THE DIGEST IS SMALL AND CARRIES ITS SHAPE (totals, by_group, by_region, queue head);
  * IT IS WIRED: an hourly leg, a results-dict entry, a department, a layer, a budget, and an
    artifact the component registry resolves from the organ's own `OUT`.

The real country packs are read (they are code in this tree); every output goes to tmp.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import equivalence_ontology as EQ  # noqa: E402
from libs.research import layers as LY  # noqa: E402
from research import regional_parity_pass as RPP  # noqa: E402


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reports, data = tmp_path / "reports", tmp_path / "data"
    monkeypatch.setattr(RPP, "REPORTS", reports)
    monkeypatch.setattr(RPP, "DATA", data)
    monkeypatch.setattr(RPP, "TENSOR", reports / "COVERAGE_TENSOR.json")
    monkeypatch.setattr(RPP, "INGESTION", reports / "INGESTION_EXPLOITATION.json")
    monkeypatch.setattr(RPP, "INGESTION_LEDGER", data / "ingestion_ledger.jsonl")
    monkeypatch.setattr(RPP, "DEPTH_REPORT", reports / "regional_parity.json")
    monkeypatch.setattr(RPP, "WORLD", data / "intelligence" / "world")
    monkeypatch.setattr(RPP, "DIGEST", data / "digests" / "regional_parity_digest.json")
    monkeypatch.setattr(RPP, "OUT", reports / "REGIONAL_PARITY.json")
    monkeypatch.setattr(RPP, "CANDIDATES", data / "equivalence_candidates.json")
    monkeypatch.setattr(RPP, "HUNT_TARGETS", data / "parity_hunt_targets.json")
    monkeypatch.setattr(RPP, "BASE", tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def doc_and_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp = tmp_path_factory.mktemp("rpp")
    mp = pytest.MonkeyPatch()
    try:
        for name, value in (("REPORTS", tmp / "reports"), ("DATA", tmp / "data"),
                            ("TENSOR", tmp / "reports" / "COVERAGE_TENSOR.json"),
                            ("INGESTION", tmp / "reports" / "INGESTION_EXPLOITATION.json"),
                            ("INGESTION_LEDGER", tmp / "data" / "ingestion_ledger.jsonl"),
                            ("DEPTH_REPORT", tmp / "reports" / "regional_parity.json"),
                            ("WORLD", tmp / "data" / "intelligence" / "world"),
                            ("DIGEST", tmp / "data" / "digests" / "regional_parity_digest.json"),
                            ("OUT", tmp / "reports" / "REGIONAL_PARITY.json"),
                            ("CANDIDATES", tmp / "data" / "equivalence_candidates.json"),
                            ("HUNT_TARGETS", tmp / "data" / "parity_hunt_targets.json"),
                            ("BASE", tmp)):
            mp.setattr(RPP, name, value)
        doc = RPP.build()
    finally:
        mp.undo()
    return {"doc": doc, "tmp": tmp}


def test_one_pass_writes_report_digest_and_discoveries(doc_and_files: dict[str, Any]) -> None:
    tmp: Path = doc_and_files["tmp"]
    out = json.loads((tmp / "reports" / "REGIONAL_PARITY.json").read_text("utf-8"))
    assert out["n_cells"] == out["n_countries"] * len(EQ.CLASSES)
    assert out["n_countries"] >= 135
    files = sorted((tmp / "data" / "intelligence" / "world").glob("discoveries_parity_*.json"))
    assert len(files) == 1
    rows = json.loads(files[0].read_text("utf-8"))
    assert isinstance(rows, list) and rows
    for r in rows:
        assert r["kind"] == "dataset" and r["url"].startswith(("http://", "https://"))
        assert isinstance(r["endpoints"], list) and r["host"]
        assert r["parity"]["countries"] and r["parity"]["classes"]
        assert r["lane"] == RPP.PARITY_LANE
        assert all(EQ.terms_verdict(u) == EQ.PERMITTED for u in r["endpoints"])
    assert any(r["endpoints"] for r in rows), "known endpoints reach the acquirer"
    assert rows[0]["endpoints"], "rows with an endpoint are ranked first"


def test_no_ledger_means_nothing_is_covered(doc_and_files: dict[str, Any]) -> None:
    doc = doc_and_files["doc"]
    assert doc["totals"]["counts"]["COVERED"] == 0
    assert doc["proof"]["readable"] is False
    assert any("ingestion ledger" in u for u in doc["unmeasured"])
    assert any("COVERAGE_TENSOR" in u for u in doc["unmeasured"])
    assert doc["totals"]["counts"][EQ.UNMEASURED] > 0
    assert doc["totals"]["counts"]["DECLARED"] > 0, "the real packs declare classes"


def test_digest_is_small_and_shaped(doc_and_files: dict[str, Any]) -> None:
    path = doc_and_files["tmp"] / "data" / "digests" / "regional_parity_digest.json"
    raw = path.read_text("utf-8")
    assert len(raw.encode("utf-8")) < 64_000
    d = json.loads(raw)
    for key in ("at", "totals", "by_group", "by_region", "parity_spread", "work_queue_head",
                "discoveries_file", "unmeasured", "class_source"):
        assert key in d, key
    assert set(d["totals"]["counts"]) == set(EQ.DISPOSITIONS)
    assert len(d["work_queue_head"]) <= RPP.DIGEST_QUEUE
    assert "cells" not in d


def test_dry_run_writes_nothing(desk: Path) -> None:
    doc = RPP.build(dry_run=True)
    assert doc["dry_run"] is True
    assert not any(desk.rglob("*.json"))


def test_a_ledger_on_disk_can_cover_a_declared_cell(desk: Path) -> None:
    (desk / "data").mkdir(parents=True)
    row = {"kind": "release", "unit_id": "kr_cpi", "downstream_state": "CANDIDATE_INPUT"}
    (desk / "data" / "ingestion_ledger.jsonl").write_text(json.dumps(row) + "\n", "utf-8")
    doc = RPP.build(dry_run=True)
    cell = next(c for c in doc["cells"] if c["country"] == "kr" and c["class"] == "Inflation:CPI")
    assert cell["disposition"] == "COVERED"
    assert doc["totals"]["counts"]["COVERED"] >= 1


def test_the_leg_is_wired() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/regional_parity_pass.py"' in src
    assert '"regional_parity": rpp' in src
    assert '"coverage_tensor", "regional_parity",' in src
    assert '"regional_parity": 400' in src
    assert LY.LEG_LAYER["regional_parity"] == "information"
    from desks.mt5.ops import components
    assert components.own_artifact("desks/mt5/research/regional_parity_pass.py") == (
        "desks/mt5/reports/REGIONAL_PARITY.json",)


def test_unmeasured_cells_reach_the_hunter_and_candidates_persist(
        doc_and_files: dict[str, Any]) -> None:
    tmp: Path = doc_and_files["tmp"]
    doc = doc_and_files["doc"]
    targets = json.loads((tmp / "data" / "parity_hunt_targets.json").read_text("utf-8"))
    assert targets["n_cells"] == doc["totals"]["counts"][EQ.UNMEASURED]
    assert all(v["terms"] and v["countries"] for v in targets["classes"].values())
    ledger = json.loads((tmp / "data" / "equivalence_candidates.json").read_text("utf-8"))
    assert ledger["n"] == ledger["n_present"] == len(
        {c["candidate_id"] for c in doc["candidate_classes"]})
    assert doc["totals"]["parity"] == EQ.UNMEASURED, "nothing measured -> headline UNMEASURED"


def test_candidate_ledger_never_drops_a_row() -> None:
    row = {"candidate_id": "a" * 16, "pack": "kr", "kind": "release", "id": "x", "text": "x"}
    first = RPP.merge_candidates(None, [row], "2026-10-06T00:00:00+00:00")
    second = RPP.merge_candidates(first, [], "2026-10-07T00:00:00+00:00")
    kept = second["rows"]["a" * 16]
    assert second["n"] == 1 and second["n_present"] == 0
    assert kept["present"] is False and kept["first_seen"] == "2026-10-06T00:00:00+00:00"
    assert kept["last_seen"] == "2026-10-06T00:00:00+00:00"
