"""The institutional footprint's acceptance rows (IF01..IF06): they load, the audit evaluates each
one on the evidence, an absent artifact reads UNMEASURED, and a seeded violation flips its row."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("yaml")

import global_research_acceptance as A  # noqa: E402
import institutional_acceptance as IA  # noqa: E402

ADDENDUM = "docs/research/institutional_footprint_acceptance_v1.json"
NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)
AT = NOW.isoformat()


def _copy(root: Path, *rels: Path) -> None:
    for rel in rels:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, root / rel)


def _write(root: Path, rel: Path | str, doc: Any) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc) if not isinstance(doc, str) else doc, "utf-8")


def _row(rid: str, **kw: Any) -> dict[str, Any]:
    parts = rid.split(".")
    base = {"id": rid, "jurisdiction": parts[1], "publisher": parts[2], "dataset": parts[3],
            "declared_status": "DISCOVERED_NOT_INGESTED", "pit_note": "stamped at release"}
    return {**base, **kw}


def _roster(root: Path, rows: list[dict[str, Any]]) -> None:
    import yaml
    _write(root, IA.ROSTER, yaml.safe_dump({"sources": rows}))


def _frame(root: Path, sid: str, rows: list[tuple[str, str, float]], grade: str = "FIRST_RELEASE",
           col: str = "v") -> None:
    lines = [f"event_time,available_time,source_id,retrieval_time,pit_grade,{col}"]
    lines += [f"{e},{a},{sid},{AT},{grade},{v}" for e, a, v in rows]
    _write(root, IA.SERIES / f"{sid}.csv", "\n".join(lines) + "\n")


# ------------------------------------------------------------------ the rows load
def test_the_footprint_addendum_is_registered_and_every_row_is_wired() -> None:
    manifest = json.loads(A.MANIFEST.read_text("utf-8"))
    assert ADDENDUM in manifest["addenda"]
    add = json.loads((ROOT / ADDENDUM).read_text("utf-8"))
    assert add["specification"] == "INSTITUTIONAL_FOOTPRINT_ACCEPTANCE_V1_20261111"
    rows = add["requirements"]
    assert [r["id"] for r in rows] == [f"IF{i:02d}" for i in range(1, 7)]
    for r in rows:
        assert r["evaluator"] in IA.EVALUATORS, r["id"]
        assert r["clock"] and r["runtime"] and r["anchors"], r["id"]
        for kind in ("implementation", "tests", "consumers"):
            assert r[kind], (r["id"], kind)
            for p in r[kind]:
                assert (ROOT / p).exists(), (r["id"], p)
        # Every cited line still holds the code it names.
        assert A._anchor_errors(ROOT, r["anchors"]) == [], r["id"]
        assert any(b["id"] == "not_on_live" for b in r["blockers"]), r["id"]
        for b in r["blockers"]:
            assert b["id"] and b["owner"] and b["why"], r["id"]


def test_the_audit_evaluates_every_footprint_row(tmp_path: Path) -> None:
    doc = A.audit(report=tmp_path / "out.json", now=NOW)
    assert ADDENDUM in doc["addenda"]
    rows = {r["id"]: r for r in doc["rows"] if r["id"].startswith("IF")}
    assert sorted(rows) == [f"IF{i:02d}" for i in range(1, 7)]
    for rid, r in rows.items():
        ev = r["checks"]["evaluation"]
        assert ev["verdict"] in ("PASS", "FAIL", "UNMEASURED"), rid
        assert doc["evaluations"][rid] == ev["verdict"] == r["verdict"]
        assert r["status"] == "PARTIAL"            # the open not_on_live blocker, at least
        if ev["verdict"] != "PASS":
            assert any(m.startswith("evaluation:") for m in r["missing_evidence"]), rid
    # The wiring checks of IF06 hold on this tree; only its runtime may be unmeasured.
    assert rows["IF06"]["checks"]["evaluation"]["violations"] == []


# ------------------------------------------------------------------ absence is UNMEASURED
@pytest.mark.parametrize("name", sorted(IA.EVALUATORS))
def test_an_empty_root_is_unmeasured_never_pass(tmp_path: Path, name: str) -> None:
    assert IA.EVALUATORS[name](tmp_path, NOW)["verdict"] == "UNMEASURED"


@pytest.mark.parametrize("name", ["institutional_footprint.pit", "institutional_footprint.states",
                                  "institutional_footprint.cells",
                                  "institutional_footprint.coverage"])
def test_code_without_its_artifacts_is_unmeasured(tmp_path: Path, name: str) -> None:
    _copy(tmp_path, IA.ENGINE, IA.ONTOLOGY, IA.RULINGS)
    got = IA.EVALUATORS[name](tmp_path, NOW)
    assert got["verdict"] == "UNMEASURED" and got["violations"] == [], got


def test_a_stale_artifact_is_unmeasured(tmp_path: Path) -> None:
    _copy(tmp_path, IA.ENGINE, IA.ONTOLOGY)
    old = (NOW - timedelta(hours=30)).isoformat()
    _write(tmp_path, IA.COVERAGE, {"at": old, "grid": {}, "role_gaps": {}})
    _write(tmp_path, IA.SEARCH_QUEUE, {"at": old, "queue": []})
    got = IA.if05_coverage(tmp_path, NOW)
    assert got["verdict"] == "UNMEASURED" and any("stale" in u for u in got["unmeasured"])


# ------------------------------------------------------------------ IF01 atlas
def test_a_clean_atlas_passes_and_a_duplicate_id_fails(tmp_path: Path) -> None:
    rows = [_row("institutional.us.cftc.cot"),
            _row("institutional.uk.boe.repo"),
            {**_row("institutional.us.fed.h41"), "id": "fed_h41",
             "atlas_id": "institutional.us.fed.h41", "aliases": []}]
    _roster(tmp_path, rows)
    assert IA.if01_atlas(tmp_path, NOW)["verdict"] == "PASS"
    _roster(tmp_path, [*rows, _row("institutional.uk.boe.repo")])
    got = IA.if01_atlas(tmp_path, NOW)
    assert got["verdict"] == "FAIL"
    assert any(v.startswith("duplicate atlas id") for v in got["violations"])


@pytest.mark.parametrize("bad,why", [
    ({"pit_note": ""}, "row without a pit_note"),
    ({"declared_status": "ACTIVE"}, "row without a declarable status"),
    ({"id": "institutional.us.cftc"}, "id not institutional"),
    ({"id": "lane_id_first"}, "lane-registered row without atlas_id/aliases"),
])
def test_each_atlas_violation_flips_if01(tmp_path: Path, bad: dict[str, Any], why: str) -> None:
    _roster(tmp_path, [_row("institutional.uk.boe.repo"), {**_row("institutional.us.cftc.cot"),
                                                          **bad}])
    got = IA.if01_atlas(tmp_path, NOW)
    assert got["verdict"] == "FAIL" and any(v.startswith(why) for v in got["violations"]), got


# ------------------------------------------------------------------ IF02 PIT
def _pit_root(root: Path) -> None:
    _copy(root, IA.ENGINE)
    _roster(root, [_row("institutional.us.ok.series", publication_lag_days=0),
                   _row("institutional.us.rev.series", publication_lag_days=0)])
    _frame(root, "institutional.us.ok.series",
           [("2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00", 1.0)])
    _write(root, IA.COVERAGE, {"at": AT, "pit": {"latest_revised_frames": []}})
    _write(root, IA.CULTURE_LOG, json.dumps({"cell_id": "c1",
                                             "source_id": "institutional.us.ok.series",
                                             "source_ids": ["institutional.us.ok.series"]}) + "\n")


def test_first_release_frames_feeding_cells_pass_if02(tmp_path: Path) -> None:
    _pit_root(tmp_path)
    got = IA.if02_pit(tmp_path, NOW)
    assert got["verdict"] == "PASS", got


def test_a_latest_revised_frame_reaching_a_state_fails_if02(tmp_path: Path) -> None:
    _pit_root(tmp_path)
    _frame(tmp_path, "institutional.us.rev.series",
           [("2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00", 1.0)],
           grade="LATEST_REVISED")
    _write(tmp_path, IA.CULTURE_LOG, json.dumps({
        "cell_id": "state1", "source_id": "institutional.us.ok.series",
        "source_ids": ["institutional.us.ok.series", "institutional.us.rev.series"]}) + "\n")
    got = IA.if02_pit(tmp_path, NOW)
    assert got["verdict"] == "FAIL"
    assert any(v.startswith("LATEST_REVISED frame reached") for v in got["violations"])


def test_a_frame_stamped_before_its_release_fails_if02(tmp_path: Path) -> None:
    _pit_root(tmp_path)
    _frame(tmp_path, "institutional.us.ok.series",
           [("2024-01-01T00:00:00+00:00", "2024-01-01T06:00:00+00:00", 1.0)])
    got = IA.if02_pit(tmp_path, NOW)
    assert got["verdict"] == "FAIL"
    assert any(v.startswith("frame row stamped before") for v in got["violations"])


def test_cot_not_on_the_cftc_calendar_fails_if02(tmp_path: Path) -> None:
    _pit_root(tmp_path)
    src = (tmp_path / IA.ENGINE).read_text("utf-8")
    (tmp_path / IA.ENGINE).write_text(src.replace("fs.cftc_available(", "fs.my_calendar("),
                                      "utf-8")
    got = IA.if02_pit(tmp_path, NOW)
    assert got["verdict"] == "FAIL" and any("cftc_available" in v for v in got["violations"])


# ------------------------------------------------------------------ IF03 states
def _state_root(root: Path, state: dict[str, Any]) -> None:
    _copy(root, IA.ENGINE)
    _roster(root, [_row("institutional.us.ok.series")])
    _write(root, IA.STATE_REPORT, {"at": AT, "states": {"XAUUSD": {"crowding": state}},
                                   "regimes": {"XAUUSD": {"crowding": "NEUTRAL"}}})


def test_a_measured_state_with_an_interval_passes_if03(tmp_path: Path) -> None:
    _state_root(tmp_path, {"status": "MEASURED", "p": 0.5, "lo": 0.3, "hi": 0.7,
                           "age_hours": 20})
    _write(tmp_path, IA.COVERAGE, {"at": AT, "row_status": {}})
    assert IA.if03_states(tmp_path, NOW)["verdict"] == "PASS"


@pytest.mark.parametrize("state,why", [
    ({"status": "MEASURED", "p": 0.5, "lo": 0.3, "hi": 0.7, "age_hours": 200}, "state older"),
    ({"status": "MEASURED", "p": 0.5, "lo": None, "hi": None, "age_hours": 2}, "MEASURED state"),
    ({"status": "UNMEASURED", "p": 0.5, "age_hours": 200}, "state older"),
    ({"status": "UNMEASURED", "p": None, "age_hours": 200}, "UNMEASURED state given a regime"),
])
def test_a_state_violation_flips_if03(tmp_path: Path, state: dict[str, Any], why: str) -> None:
    _state_root(tmp_path, state)
    _write(tmp_path, IA.COVERAGE, {"at": AT, "row_status": {}})
    got = IA.if03_states(tmp_path, NOW)
    assert got["verdict"] == "FAIL" and any(v.startswith(why) for v in got["violations"]), got


def test_active_without_a_fed_cell_fails_if03(tmp_path: Path) -> None:
    _state_root(tmp_path, {"status": "MEASURED", "p": 0.5, "lo": 0.3, "hi": 0.7,
                           "age_hours": 2})
    sid = "institutional.us.ok.series"
    _frame(tmp_path, sid, [("2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00", 1.0)])
    now = datetime.now(tz=UTC)                    # the frame's mtime is the wall clock
    _write(tmp_path, IA.STATE_REPORT, {"at": now.isoformat(), "states": {}, "regimes": {}})
    _write(tmp_path, IA.COVERAGE, {"at": now.isoformat(), "row_status": {sid: "ACTIVE"}})
    _write(tmp_path, IA.EMITTED, {"credited": {sid: now.isoformat()}})
    assert IA.if03_states(tmp_path, now)["verdict"] == "PASS"
    _write(tmp_path, IA.EMITTED, {"credited": {sid: (now - timedelta(days=31)).isoformat()}})
    got = IA.if03_states(tmp_path, now)
    assert got["verdict"] == "FAIL" and any(v.startswith("ACTIVE without") for v in
                                            got["violations"])


# ------------------------------------------------------------------ IF04 cells
def _cells_root(root: Path, *, sides: tuple[int, ...] = (1,), vintages: int = 60) -> None:
    _copy(root, IA.ENGINE)
    sid = "institutional.us.ok.series"
    start = datetime(2020, 1, 1, tzinfo=UTC)
    _frame(root, sid, [((start + timedelta(days=i)).isoformat(),
                        (start + timedelta(days=i + 1)).isoformat(), float(i))
                       for i in range(vintages)])
    keys = [f"{sid}|v|z|XAUUSD|H1", f"{sid}|v|z|XAUUSD|H4"]
    _write(root, IA.EMITTED, {"at": AT, "spec": "purged_trade_from/1", "keys": keys,
                              "credited": {sid: AT}})
    culture = [{"cell_id": f"c{i}", "source_id": sid, "source_ids": [sid], "claim_family": "f1",
                "side_fit": {"side": s, "train_end": "2022-01-01", "selection_trials": 2}}
               for i, s in enumerate(sides)]
    _write(root, IA.CULTURE_LOG, "".join(json.dumps(c) + "\n" for c in culture))
    _write(root, IA.DONATIONS / "discoveries_20261111_1200.json", {"candidates": [
        {"evidence": {"candidate_id": "c0"}, "claim_family": "f1",
         "claim_selection_trials": 2}]})


def test_one_side_per_family_through_the_door_passes_if04(tmp_path: Path) -> None:
    _cells_root(tmp_path)
    got = IA.if04_cells(tmp_path, NOW)
    assert got["verdict"] == "PASS", got
    assert got["measured"]["donated_through_door"] == 1


@pytest.mark.parametrize("kw,why", [
    ({"sides": (1, -1)}, "claim family carrying both sides"),
    ({"vintages": 59}, "cell minted from a column with fewer than 60"),
])
def test_a_cell_violation_flips_if04(tmp_path: Path, kw: dict[str, Any], why: str) -> None:
    _cells_root(tmp_path, **kw)
    got = IA.if04_cells(tmp_path, NOW)
    assert got["verdict"] == "FAIL" and any(v.startswith(why) for v in got["violations"]), got


def test_a_donation_that_drops_the_side_charge_fails_if04(tmp_path: Path) -> None:
    _cells_root(tmp_path)
    _write(tmp_path, IA.DONATIONS / "discoveries_20261111_1300.json", {"candidates": [
        {"evidence": {"candidate_id": "c0"}, "claim_family": "f1"}]})
    got = IA.if04_cells(tmp_path, NOW)
    assert got["verdict"] == "FAIL"
    assert any(v.startswith("donated cell lost") for v in got["violations"])


def test_cells_never_donated_are_unmeasured(tmp_path: Path) -> None:
    _cells_root(tmp_path)
    shutil.rmtree(tmp_path / IA.DONATIONS)
    assert IA.if04_cells(tmp_path, NOW)["verdict"] == "UNMEASURED"


# ------------------------------------------------------------------ IF05 coverage
def _coverage_root(root: Path, queue: list[dict[str, Any]], grid_status: str = "UNMEASURED",
                   rulings: dict[str, Any] | None = None) -> None:
    _copy(root, IA.ONTOLOGY)
    _write(root, IA.RULINGS, {"cells": rulings or {}, "roles": {}})
    _write(root, IA.COVERAGE, {"at": AT, "grid": {"uk": {"repo_funding": grid_status}},
                               "grid_sources": {}, "role_gaps": {"uk": ["central_bank"]}})
    _write(root, IA.SEARCH_QUEUE, {"at": AT, "queue": queue})


QUEUE_OK = [{"jurisdiction": "uk", "source_class": "repo_funding"},
            {"jurisdiction": "uk", "role": "central_bank"}]


def test_a_queued_gap_passes_if05(tmp_path: Path) -> None:
    _coverage_root(tmp_path, QUEUE_OK)
    assert IA.if05_coverage(tmp_path, NOW)["verdict"] == "PASS"


@pytest.mark.parametrize("queue,status,why", [
    (QUEUE_OK[1:], "UNMEASURED", "UNMEASURED cell missing from search_queue"),
    (QUEUE_OK[:1], "UNMEASURED", "role gap missing from search_queue"),
    (QUEUE_OK, "UNSEARCHED", "UNSEARCHED cell"),
])
def test_a_coverage_violation_flips_if05(tmp_path: Path, queue: list[dict[str, Any]],
                                         status: str, why: str) -> None:
    _coverage_root(tmp_path, queue, status)
    got = IA.if05_coverage(tmp_path, NOW)
    assert got["verdict"] == "FAIL" and any(v.startswith(why) for v in got["violations"]), got


def test_a_cell_closed_by_an_uncited_ruling_fails_if05(tmp_path: Path) -> None:
    _coverage_root(tmp_path, QUEUE_OK, "NOT_PUBLISHED",
                   {"uk|repo_funding": {"status": "NOT_PUBLISHED", "evidence": "well-known"}})
    got = IA.if05_coverage(tmp_path, NOW)
    assert got["verdict"] == "FAIL"
    assert any(v.startswith("cell closed by a ruling") for v in got["violations"])


# ------------------------------------------------------------------ IF06 wiring
def test_a_leg_dropped_from_core_fails_if06(tmp_path: Path) -> None:
    _copy(tmp_path, IA.HOURLY, IA.ATTESTATION)
    assert IA.if06_wiring(tmp_path, NOW)["violations"] == []
    src = (tmp_path / IA.HOURLY).read_text("utf-8")
    (tmp_path / IA.HOURLY).write_text(
        src.replace('"pack_cells", "institutional_footprint", "futures_state"',
                    '"pack_cells", "futures_state"', 1), "utf-8")
    got = IA.if06_wiring(tmp_path, NOW)
    assert got["verdict"] == "FAIL" and any("CORE_LEGS" in v for v in got["violations"])


def test_a_live_attestation_and_fresh_artifacts_pass_if06(tmp_path: Path) -> None:
    _copy(tmp_path, IA.HOURLY)
    _write(tmp_path, IA.ATTESTATION, {"organs": [{
        "organ": "leg:institutional_footprint", "clock": "hourly_cycle:institutional_footprint",
        "artifact_declared": IA.COVERAGE.as_posix(), "state": "LIVE"}]})
    for rel in (IA.COVERAGE, IA.STATE_REPORT, IA.SEARCH_QUEUE):
        _write(tmp_path, rel, {"at": AT})
    assert IA.if06_wiring(tmp_path, NOW)["verdict"] == "PASS"
    _write(tmp_path, IA.ATTESTATION, {"organs": [{
        "organ": "leg:institutional_footprint", "clock": "hourly_cycle:institutional_footprint",
        "artifact_declared": IA.COVERAGE.as_posix(), "state": "MISSING"}]})
    assert IA.if06_wiring(tmp_path, NOW)["verdict"] == "FAIL"


# ------------------------------------------------------------------ the audit hook
def _audit_one(tmp_path: Path, req: dict[str, Any]) -> dict[str, Any]:
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    for name in ("impl.py", "test_impl.py", "consumer.py"):
        (root / name).write_text("def thing():\n    pass\n", "utf-8")
    base = {"id": "IF01", "title": "x", "priority": "P0", "implementation": ["impl.py"],
            "tests": ["test_impl.py"], "consumers": ["consumer.py"], "runtime": []}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"specification": "B", "completion_rule": "strict",
                                    "frontier_rule": "open",
                                    "requirements": [{**base, **req}]}), "utf-8")
    result = A.audit(root=root, manifest=manifest, report=tmp_path / "out.json", now=NOW)
    return dict(result["rows"][0])


def test_a_failing_evaluation_keeps_the_row_partial(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _roster(root, [_row("institutional.uk.boe.repo"), _row("institutional.uk.boe.repo")])
    row = _audit_one(tmp_path, {"evaluator": "institutional_footprint.atlas"})
    assert row["status"] == "PARTIAL" and row["verdict"] == "FAIL"
    assert "evaluation:institutional_footprint.atlas:FAIL" in row["missing_evidence"]


def test_an_unregistered_evaluator_is_unmeasured(tmp_path: Path) -> None:
    row = _audit_one(tmp_path, {"evaluator": "os.system"})
    assert row["verdict"] == "UNMEASURED" and row["status"] == "PARTIAL"


def test_a_drifted_anchor_is_evidence_debt(tmp_path: Path) -> None:
    row = _audit_one(tmp_path, {"anchors": ["impl.py:1#def thing", "impl.py:2#def thing",
                                            "impl.py:99", "nope.py:1"]})
    assert "anchor:impl.py:1#def thing:DRIFTED" not in row["missing_evidence"]
    assert "anchor:impl.py:2#def thing:DRIFTED" in row["missing_evidence"]
    assert "anchor:impl.py:99:DRIFTED" in row["missing_evidence"]
    assert "anchor:nope.py:1:ABSENT" in row["missing_evidence"]
