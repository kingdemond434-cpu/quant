from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import global_research_acceptance as A  # noqa: E402

INSTITUTION = ROOT / "docs" / "research" / "miniature_institution_acceptance_v1.json"
NOW = datetime(2026, 10, 7, tzinfo=UTC)


def _one_requirement(tmp_path: Path, req: dict, **addendum_extra) -> dict:
    """Audit a single fully-evidenced requirement (no runtime) through an addendum."""
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    for name in ("impl.py", "test_impl.py", "consumer.py"):
        (root / name).write_text("", "utf-8")
    full = {"title": "x", "priority": "P0", "lane": "production",
            "implementation": ["impl.py"], "tests": ["test_impl.py"],
            "consumers": ["consumer.py"], "runtime": [], **req}
    (root / "add.json").write_text(json.dumps({"specification": "ADD_V1",
                                               "requirements": [full], **addendum_extra}),
                                   "utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"specification": "BASE", "completion_rule": "strict",
                                    "frontier_rule": "open", "addenda": ["add.json"],
                                    "requirements": []}), "utf-8")
    return A.audit(root=root, manifest=manifest, report=tmp_path / "out.json", now=NOW)


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


def test_fresh_failed_or_wrong_release_runtime_is_not_verified(
        tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"specification": "x", "completion_rule": "strict",
                                    "frontier_rule": "open", "requirements": [{
        "id": "R01", "title": "x", "priority": "P0",
        "implementation": ["impl.py"], "tests": ["test_impl.py"],
        "consumers": ["consumer.py"], "runtime": ["runtime.json"]}]}), "utf-8")
    for rel in ("impl.py", "test_impl.py", "consumer.py"):
        (root / rel).write_text("assert False\n" if rel.startswith("test") else "", "utf-8")
    (root / "runtime.json").write_text(json.dumps({
        "status": "FAILED", "completed_work": 0, "tests_passed": False,
        "commit": "wrong-sha", "completed_at": "2026-09-27T00:00:00+00:00"}), "utf-8")
    monkeypatch.setattr(A, "_release_id", lambda _root: "right-sha")
    got = A.audit(root=root, manifest=manifest, report=tmp_path / "out.json",
                  now=datetime(2026, 9, 27, 1, tzinfo=UTC))
    assert got["all_current_verified"] is False
    errors = got["rows"][0]["checks"]["runtime"][0]["proof_errors"]
    assert any(x.startswith("failed_status") for x in errors)
    assert any(x.startswith("wrong_release") for x in errors)


def test_undeclared_evidence_cannot_pass(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"specification": "x", "completion_rule": "strict",
                                    "frontier_rule": "open", "requirements": [{
        "id": "R01", "title": "x", "priority": "P0"}]}), "utf-8")
    got = A.audit(root=root, manifest=manifest, report=tmp_path / "out.json",
                  now=datetime(2026, 9, 27, tzinfo=UTC))
    assert got["rows"][0]["status"] == "PARTIAL"
    assert "runtime:UNDECLARED" in got["rows"][0]["missing_evidence"]


@pytest.mark.parametrize("changes,error", [
    ({"completed_work": None}, "completed_work_unmeasured"),
    ({"completed_work": True}, "invalid_completed_work"),
    ({"completed_work": "nan"}, "invalid_completed_work"),
    ({"completed_work": "inf"}, "invalid_completed_work"),
    ({"completed_work": 0}, "invalid_completed_work"),
    ({"commit": "5"}, "invalid_release_identity"),
    ({"completed_at": "2027-09-27T00:00:00Z"}, "future_internal_timestamp"),
])
def test_runtime_proof_rejects_false_completion(tmp_path, changes, error) -> None:
    doc = {"status": "OK", "tests_passed": True, "completed_work": 3,
           "commit": "5" * 40, "completed_at": "2026-09-27T00:00:00Z"}
    doc.update(changes)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(doc), "utf-8")
    proof, errors = A._runtime_proof(path, instant=datetime(2026, 9, 27, tzinfo=UTC),
                                     release="5" * 40)
    assert proof["status"] == "INVALID"
    assert error in errors


def test_runtime_proof_accepts_matching_measured_receipt(tmp_path) -> None:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({"status": "OK", "tests_passed": True,
                               "completed_work": 3, "commit": "a" * 40,
                               "completed_at": "2026-09-27T00:00:00Z"}), "utf-8")
    _, errors = A._runtime_proof(path, instant=datetime(2026, 9, 27, tzinfo=UTC),
                                 release="a" * 40)
    assert errors == []


def test_an_open_blocker_keeps_a_fully_evidenced_requirement_partial(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for name in ("impl.py", "test_impl.py", "consumer.py"):
        (root / name).write_text("", "utf-8")
    req = {"id": "MI01", "title": "x", "priority": "P0", "lane": "production",
           "implementation": ["impl.py"], "tests": ["test_impl.py"],
           "consumers": ["consumer.py"], "runtime": [],
           "blockers": [{"id": "open_one", "owner": "o", "why": "w"},
                        {"id": "done_one", "owner": "o", "why": "w", "status": "CLOSED",
                         "proof": {"commit": "a" * 40, "artifact": "impl.py",
                                   "after_metric": "gap 0"}}]}
    addendum = tmp_path / "root" / "add.json"
    addendum.write_text(json.dumps({"specification": "ADD_V1", "requirements": [req]}), "utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"specification": "BASE", "completion_rule": "strict",
                                    "frontier_rule": "open", "addenda": ["add.json"],
                                    "requirements": []}), "utf-8")
    result = A.audit(root=root, manifest=manifest, report=tmp_path / "out.json",
                     now=datetime(2026, 10, 6, tzinfo=UTC))
    row = result["rows"][0]
    assert row["status"] == "PARTIAL" and row["specification"] == "ADD_V1"
    assert row["lane"] == "production"
    assert "blocker:open_one" in row["missing_evidence"]
    assert "blocker:done_one" not in row["missing_evidence"]
    assert result["by_specification"] == {"ADD_V1": {"CURRENT_VERIFIED": 0, "PARTIAL": 1}}
    assert result["complete_against"] == []


def test_the_institution_addendum_is_loaded_and_names_every_function() -> None:
    doc = json.loads(A.MANIFEST.read_text("utf-8"))
    rel = "docs/research/miniature_institution_acceptance_v1.json"
    assert rel in doc["addenda"]
    add = json.loads((ROOT / rel).read_text("utf-8"))
    assert add["specification"] == "MINIATURE_INSTITUTION_ACCEPTANCE_V1_20261006"
    ids = [r["id"] for r in add["requirements"]]
    assert ids == [f"MI{i:02d}" for i in range(1, len(ids) + 1)] and len(ids) >= 12
    for r in add["requirements"]:
        assert r["lane"] in ("research", "production"), r["id"]
        for kind in ("implementation", "tests", "consumers"):
            assert r[kind], (r["id"], kind)
            for p in r[kind]:
                assert (ROOT / p).exists(), (r["id"], p)
        for b in r["blockers"]:
            assert b["id"] and b["owner"] and b["why"], r["id"]


# ---------------------------------------------------------------- fix-forward of PR #196
def test_hop4_gaps_v5_v6_are_blockers_on_mi10_and_mi11_in_the_spec() -> None:
    add = json.loads(INSTITUTION.read_text("utf-8"))
    tracked = {g["gap"]: g["requirements"] for g in add["tracked_gaps"]}
    assert tracked["function_map:V5"] == ["MI10"]
    assert tracked["function_map:V6"] == ["MI11"]
    by_id = {r["id"]: r for r in add["requirements"]}
    gaps = {rid: {b.get("gap"): b for b in by_id[rid]["blockers"]} for rid in ("MI10", "MI11")}
    assert gaps["MI10"]["function_map:V5"]["status"] == "OPEN"
    assert gaps["MI11"]["function_map:V6"]["status"] == "OPEN"


def test_mi10_and_mi11_cannot_score_green_while_their_hop4_gaps_are_open(
        tmp_path: Path) -> None:
    """The live spec, scored: MI10/MI11 stay PARTIAL and name the V5/V6 blockers."""
    got = A.audit(report=tmp_path / "out.json", now=NOW)
    rows = {r["id"]: r for r in got["rows"]}
    assert rows["MI10"]["status"] == "PARTIAL"
    assert "blocker:cert_drift_blocks_nothing" in rows["MI10"]["missing_evidence"]
    assert rows["MI11"]["status"] == "PARTIAL"
    assert "blocker:gold_sleeves_uncertified" in rows["MI11"]["missing_evidence"]
    assert "MINIATURE_INSTITUTION_ACCEPTANCE_V1_20261006" not in got["complete_against"]


def test_deleting_a_tracked_gap_blocker_does_not_turn_the_requirement_green(
        tmp_path: Path) -> None:
    tracked = {"tracked_gaps": [{"gap": "function_map:V5", "requirements": ["MI10"]}]}
    bare = _one_requirement(tmp_path / "a", {"id": "MI10", "blockers": []}, **tracked)
    assert bare["rows"][0]["status"] == "PARTIAL"
    assert "untracked_gap:function_map:V5" in bare["rows"][0]["missing_evidence"]
    proven = _one_requirement(tmp_path / "b", {"id": "MI10", "blockers": [{
        "id": "v5", "gap": "function_map:V5", "owner": "lane: production", "why": "w",
        "status": "CLOSED", "proof": {"commit": "b" * 40, "artifact": "impl.py",
                                      "after_metric": {"drift_blocked": 1}}}]}, **tracked)
    assert proven["rows"][0]["status"] == "CURRENT_VERIFIED"
    assert proven["complete_against"] == ["ADD_V1"]


@pytest.mark.parametrize("owner", ["", "   ", "this thread", "TBD", "this thread (fence)"])
def test_a_blocker_without_a_durable_owner_is_flagged(tmp_path: Path, owner: str) -> None:
    got = _one_requirement(tmp_path, {"id": "MI01", "blockers": [
        {"id": "b1", "owner": owner, "why": "w"}]})
    row = got["rows"][0]
    assert "blocker_owner:b1" in row["missing_evidence"]
    assert got["ownerless_blockers"] == ["MI01:b1"]
    assert row["blockers"][0]["owner"] == owner, "the stored owner is carried, never derived"


def test_every_blocker_in_the_institution_spec_has_a_durable_owner() -> None:
    add = json.loads(INSTITUTION.read_text("utf-8"))
    for r in add["requirements"]:
        for b in r["blockers"]:
            _, problems = A.blocker_state(b, ROOT)
            assert "owner_missing" not in problems, (r["id"], b["id"], b.get("owner"))


@pytest.mark.parametrize("proof,defect", [
    (None, "proof_commit"),
    ({"artifact": "impl.py", "after_metric": "0"}, "proof_commit"),
    ({"commit": "zz", "artifact": "impl.py", "after_metric": "0"}, "proof_commit"),
    ({"commit": "c" * 40, "after_metric": "0"}, "proof_artifact"),
    ({"commit": "c" * 40, "artifact": "nope.json", "after_metric": "0"},
     "proof_artifact_absent"),
    ({"commit": "c" * 40, "artifact": "impl.py"}, "proof_after_metric"),
    ({"commit": "c" * 40, "artifact": "impl.py", "after_metric": ""}, "proof_after_metric"),
])
def test_closed_without_proof_scores_as_still_open(tmp_path: Path, proof, defect) -> None:
    blocker = {"id": "b1", "owner": "lane: research", "why": "w", "status": "CLOSED"}
    if proof is not None:
        blocker["proof"] = proof
    got = _one_requirement(tmp_path, {"id": "MI01", "blockers": [blocker]})
    row = got["rows"][0]
    assert row["status"] == "PARTIAL"
    assert row["blockers"][0]["effective_status"] == "INVALID_CLOSE"
    assert defect in row["blockers"][0]["problems"]
    assert any(m.startswith("blocker:b1:closed_without_proof:") for m in row["missing_evidence"])
    assert row["closed_blockers"] == [] and got["open_blockers"] == 1


def test_mi05_names_the_deadman_rail_by_reference_only() -> None:
    add = json.loads(INSTITUTION.read_text("utf-8"))
    rail = "scripts/run_deadman_switch.py"
    for r in add["requirements"]:
        for kind in ("implementation", "tests", "consumers", "runtime"):
            assert rail not in r.get(kind, []), (r["id"], kind)
    mi05 = next(r for r in add["requirements"] if r["id"] == "MI05")
    ref = next(x for x in mi05["reference_only"] if x["path"] == rail)
    assert "never edited" in ref["note"].lower() and "LAWS section 4" in ref["note"]
    assert rail in A.TIER3_NEVER_EDIT


def test_the_scorer_refuses_a_spec_that_declares_the_tier3_rail_as_work(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "run_deadman_switch.py").write_text("", "utf-8")
    got = _one_requirement(tmp_path, {"id": "MI05", "blockers": [],
                                      "consumers": ["consumer.py",
                                                    "scripts/run_deadman_switch.py"]})
    assert ("tier3_declared:consumers:scripts/run_deadman_switch.py"
            in got["rows"][0]["missing_evidence"])


def test_no_acceptance_organ_writes_the_deadman_rail(tmp_path: Path) -> None:
    import hashlib
    rail = ROOT / "scripts" / "run_deadman_switch.py"
    before = hashlib.sha256(rail.read_bytes()).hexdigest()
    got = A.audit(report=tmp_path / "out.json", now=NOW)
    assert hashlib.sha256(rail.read_bytes()).hexdigest() == before
    mi05 = next(r for r in got["rows"] if r["id"] == "MI05")
    assert mi05["references"][0]["path"] == "scripts/run_deadman_switch.py"
    for organ in (DESK / "research" / "global_research_acceptance.py",
                  ROOT / "scripts" / "check_acceptance_properties.py"):
        assert "run_deadman_switch" not in organ.read_text("utf-8"), organ
