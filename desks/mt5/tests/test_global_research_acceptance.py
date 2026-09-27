from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import global_research_acceptance as A  # noqa: E402


def test_manifest_has_exactly_r01_to_r30_and_no_evidence_free_requirement() -> None:
    doc = json.loads(A.MANIFEST.read_text("utf-8"))
    assert doc["specification"] == "GLOBAL_RESEARCH_MAXIMUM_V1_20260927"
    assert [r["id"] for r in doc["requirements"]] == [f"R{i:02d}" for i in range(1, 31)]
    for row in doc["requirements"]:
        assert row["implementation"] and row["tests"] and row["consumers"] and row["runtime"]


def test_acceptance_never_calls_module_existence_complete(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"specification": "x", "completion_rule": "strict",
                                    "frontier_rule": "open", "requirements": [{
        "id": "R01", "title": "x", "priority": "P0",
        "implementation": ["impl.py"], "tests": ["test_impl.py"],
        "consumers": ["consumer.py"], "runtime": ["runtime.json"]}]}), "utf-8")
    (root / "impl.py").write_text("", "utf-8")
    result = A.audit(root=root, manifest=manifest, report=tmp_path / "out.json",
                     now=datetime(2026, 9, 27, tzinfo=UTC))
    assert result["rows"][0]["status"] == "PARTIAL"
    assert any(x.startswith("tests:") for x in result["rows"][0]["missing_evidence"])
    assert any(x.startswith("consumer") for x in result["rows"][0]["missing_evidence"])
    assert any(x.startswith("runtime") for x in result["rows"][0]["missing_evidence"])
