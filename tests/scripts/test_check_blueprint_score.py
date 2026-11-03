"""The blueprint re-score: a row's state is derived from evidence on this host, never raised above
its claim; a DONE claim without proof is a lie; absent inputs read UNMEASURED; a fall in a DONE
count turns the fence RED; and the leg, fence, board row, layer and attestation are all wired."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "repo_check_blueprint_score", ROOT / "scripts" / "check_blueprint_score.py")
assert _SPEC is not None and _SPEC.loader is not None
bs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bs)

NOW = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
ALL_TRUE = dict.fromkeys("IWATRDC", True)


def _repo(tmp_path: Path, *, artifact_age_h: float | None = 1.0) -> Path:
    (tmp_path / "ops").mkdir()
    (tmp_path / "desks" / "mt5" / "ops").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "ops" / "box_tasks.manifest").write_text(
        'TASK name="MT5-Hourly" trigger="hourly" runs="x"\n', "utf-8")
    research = tmp_path / "desks" / "mt5" / "research"
    research.mkdir()
    (research / "hourly_cycle.py").write_text(
        'organ = _costed("organ", lambda: _producer("organ", "research/organ.py"))\n', "utf-8")
    (research / "organ.py").write_text("def run():\n    return 1\n", "utf-8")
    (research / "library.py").write_text("X = 1\n", "utf-8")
    tests = tmp_path / "desks" / "mt5" / "tests"
    tests.mkdir()
    (tests / "test_organ.py").write_text("from research import organ\n", "utf-8")
    reports = tmp_path / "desks" / "mt5" / "reports"
    reports.mkdir()
    if artifact_age_h is not None:
        (reports / "ORGAN.json").write_text(json.dumps(
            {"generated_at": (NOW - timedelta(hours=artifact_age_h)).isoformat()}), "utf-8")
    (tmp_path / "docs" / "research").mkdir(parents=True)
    return tmp_path


def _row(rid: str = "X1", *, claim: str = "PARTIAL", status: str = "PARTIAL",
         marks: dict[str, bool | None] | None = None, reviewed_at: str = "2026-11-01",
         code: list[str] | None = None, artifacts: list[str] | None = None,
         mark_evidence: dict[str, str] | None = None, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": rid, "item": "an organ that sizes capital", "phase": "A1", "status": status,
        "gate": "none", "claim": claim, "marks": marks or dict(ALL_TRUE),
        "reviewed_at": reviewed_at, "evidence": ["desks/mt5/research/organ.py:1 runs"],
        "gap": "box evidence", "code": ["desks/mt5/research/organ.py"] if code is None else code,
        "artifacts": ["ORGAN.json"] if artifacts is None else artifacts,
        "mark_evidence": ({"A": "desks/mt5/research/organ.py:1", "C": "desks/mt5/research/organ.py"}
                          if mark_evidence is None else mark_evidence)}
    if status == "EXISTS-LIT":
        row.update(scheduled_by="hourly_cycle:organ", artifact="desks/mt5/reports/ORGAN.json")
    row.update(extra)
    return row


def _ledger(root: Path, rows: list[dict[str, Any]], **extra: Any) -> Path:
    doc = {"version": 1, "mark_ttl_days": 14,
           "expected_counts": {"A1": sum(1 for r in rows if r["phase"] == "A1")},
           "items": rows, **extra}
    p = root / "docs" / "research" / "blueprint_ledger.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def _tier5(root: Path, sections: list[dict[str, Any]]) -> Path:
    p = root / "docs" / "research" / "tier5_audit.json"
    p.write_text(json.dumps({"sections": sections, "expected_counts": {}}), "utf-8")
    return p


def _score(root: Path, **kw: Any) -> dict[str, Any]:
    return bs.score(root, now=NOW, branch=kw.pop("branch", bs.LIVE_BRANCH), **kw)


def _row_of(doc: dict[str, Any], rid: str) -> dict[str, Any]:
    return next(r for r in doc["rows"] if r["id"] == rid)


# ------------------------------------------------------------------------------- the scoring
def test_all_seven_marks_proven_on_live_is_done(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(claim="DONE", status="EXISTS-LIT")])
    _tier5(root, [])
    doc = _score(root)
    assert _row_of(doc, "X1")["state"] == "DONE"
    assert _row_of(doc, "X1")["marks"] == "✓✓✓✓✓✓✓"
    assert doc["lies"] == [] and doc["verdict"] == "GREEN"
    assert doc["ledgers"]["blueprint"]["counts"]["DONE"] == 1


def test_state_never_rises_above_the_claim_and_is_reported_promotable(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(claim="PARTIAL"), _row("X2", claim="OPEN", status="MISSING")])
    _tier5(root, [])
    doc = _score(root)
    assert _row_of(doc, "X1")["state"] == "PARTIAL" and _row_of(doc, "X1")["promotable"]
    assert _row_of(doc, "X2")["state"] == "OPEN"
    assert doc["ledgers"]["blueprint"]["counts"]["DONE"] == 0


def test_off_live_checkout_cannot_prove_deployed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row()])
    _tier5(root, [])
    doc = _score(root, branch="claude/some-feature")
    assert _row_of(doc, "X1")["marks"][5] == "?"
    assert _row_of(doc, "X1")["state"] == "PARTIAL"


def test_a_stale_recorded_judgement_reads_unmeasured(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(reviewed_at="2026-09-30")])
    _tier5(root, [])
    doc = _score(root)
    row = _row_of(doc, "X1")
    assert row["marks"][2] == "?" and row["marks"][6] == "?"   # A and C
    assert row["state"] == "PARTIAL" and not row["promotable"]


def test_absent_cited_code_reads_open(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(code=["desks/mt5/research/gone.py"])])
    _tier5(root, [])
    assert _row_of(_score(root), "X1")["state"] == "OPEN"


def test_a_stale_artifact_is_not_evidence(tmp_path: Path) -> None:
    root = _repo(tmp_path, artifact_age_h=200.0)
    _ledger(root, [_row(claim="DONE", status="EXISTS-LIT")])
    _tier5(root, [])
    doc = _score(root)
    assert _row_of(doc, "X1")["marks"][4] == "✗"
    assert doc["verdict"] == "RED"


# ------------------------------------------------------------------------------- lies
def test_a_done_claim_without_its_artifact_is_a_lie(tmp_path: Path) -> None:
    root = _repo(tmp_path, artifact_age_h=None)
    _ledger(root, [_row(claim="DONE", status="EXISTS-LIT")])
    _tier5(root, [])
    doc = _score(root)
    assert _row_of(doc, "X1")["state"] == "PARTIAL"
    assert any("claims DONE" in lie for lie in doc["lies"])
    assert doc["verdict"] == "RED"
    assert bs.main(["--root", str(root)]) == 1


def test_a_fresh_recorded_tick_with_no_evidence_is_a_lie(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(mark_evidence={"A": "desks/mt5/research/nowhere.py:3"})])
    _tier5(root, [])
    doc = _score(root)
    assert any("recorded A=✓ without mark_evidence" in lie for lie in doc["lies"])
    assert doc["verdict"] == "RED"


def test_the_tier1_verifier_judges_the_blueprint_ledger(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(status="PARTIAL", gap="")])          # PARTIAL must name its gap
    _tier5(root, [])
    doc = _score(root)
    assert any("PARTIAL must say which part" in lie for lie in doc["lies"])


def test_a_short_phase_is_a_lie(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    p = _ledger(root, [_row()])
    doc = json.loads(p.read_text("utf-8"))
    doc["expected_counts"] = {"A1": 2}
    p.write_text(json.dumps(doc), "utf-8")
    _tier5(root, [])
    assert any("1 rows, 2 expected" in lie for lie in _score(root)["lies"])


# ------------------------------------------------------------------------------- UNMEASURED
def test_missing_ledgers_read_unmeasured_never_green(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    doc = _score(root)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["ledgers"]["blueprint"]["measured"] is False
    assert doc["ledgers"]["tier5_partials_52"]["measured"] is False
    assert bs.main(["--root", str(root)]) == 2


def test_a_row_with_nothing_measurable_is_unmeasured(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(code=[], artifacts=[], reviewed_at="2026-09-30")])
    _tier5(root, [])
    assert _row_of(_score(root), "X1")["state"] == "UNMEASURED"


def test_tier5_partial_with_its_declared_artifact_absent_is_unmeasured(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row()])
    _tier5(root, [
        {"source": "S", "id": "1", "title": "lab", "status": "PARTIAL",
         "files": ["desks/mt5/research/organ.py"], "clock": "hourly_cycle:organ",
         "gap": "it DECLARES desks/mt5/reports/ABSENT.json, which is ABSENT on this tree"},
        {"source": "S", "id": "2", "title": "lab", "status": "PARTIAL",
         "files": ["desks/mt5/research/organ.py"], "clock": "hourly_cycle:organ",
         "gap": "it DECLARES desks/mt5/reports/ORGAN.json, which is ABSENT on this tree"},
        {"source": "S", "id": "3", "title": "lab", "status": "EXISTS+WIRED+LIVE",
         "files": ["desks/mt5/research/organ.py"], "clock": "hourly_cycle:organ",
         "artifact": "desks/mt5/reports/ORGAN.json"},
        {"source": "S", "id": "4", "title": "lab", "status": "REFUSED_CONSERVATIVE",
         "files": ["desks/mt5/research/organ.py"], "why": "would reduce aggressiveness"}])
    doc = _score(root)
    assert _row_of(doc, "S:1")["state"] == "UNMEASURED"
    two = _row_of(doc, "S:2")
    assert two["state"] == "PARTIAL" and two["promotable"]
    assert _row_of(doc, "S:3")["state"] == "DONE"
    assert _row_of(doc, "S:4")["state"] == "EXCLUDED"
    assert doc["ledgers"]["tier5_partials_52"]["n"] == 2
    assert doc["ledgers"]["tier5_partials_52"]["promotable"] == ["S:2"]


# ------------------------------------------------------------------------------- the fence
def test_a_fall_in_the_done_count_is_red(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row(claim="PARTIAL")])
    _tier5(root, [])
    prev = {"ledgers": {"blueprint": {"measured": True, "counts": {"DONE": 1}}}}
    doc = _score(root, previous=prev)
    assert doc["done_drops"] == ["blueprint: DONE fell 1 -> 0"]
    assert doc["verdict"] == "RED"


def test_write_then_require_state(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _ledger(root, [_row()])
    _tier5(root, [])
    out = tmp_path / "BLUEPRINT_SCORE.json"
    assert bs.require_state(out, NOW)[0] == 1                       # never written
    assert bs.main(["--root", str(root), "--write", "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert bs.require_state(out, datetime.fromisoformat(doc["generated_at"]))[0] == 0
    assert bs.require_state(out, datetime.fromisoformat(doc["generated_at"])
                            + timedelta(hours=4))[0] == 1          # stale
    doc["verdict"] = "RED"
    out.write_text(json.dumps(doc), "utf-8")
    assert bs.require_state(out, datetime.fromisoformat(doc["generated_at"]))[0] == 1


def test_open_rows_are_ranked_by_weight_then_nearness(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    low = _row("X2", item="lint the docs")
    low["item"] = "lint the docs"
    _ledger(root, [low, _row("X1")])
    _tier5(root, [])
    ranked = _score(root)["open_ranked"]
    assert [r["id"] for r in ranked] == ["X1", "X2"]
    assert ranked[0]["weight"] == 5


# ------------------------------------------------------------------------------- this repo
def test_the_committed_ledgers_tell_no_lie_and_carry_the_named_subsets() -> None:
    doc = bs.score(ROOT)
    assert doc["lies"] == [], doc["lies"][:5]
    assert doc["ledgers"]["blueprint"]["n"] == 138
    assert doc["ledgers"]["audit_items_20"]["n"] == 20
    assert doc["ledgers"]["tier5_partials_52"]["n"] == 52
    led = json.loads((ROOT / "docs" / "research" / "blueprint_ledger.json").read_text("utf-8"))
    assert led["expected_counts"] == {"A1": 43, "A2": 21, "B1": 30, "B2": 16, "C": 28}
    assert not any(it.get("claim") == "DONE" for it in led["items"])


def test_wired_as_an_hourly_leg_with_board_row_layer_fences_and_attestation() -> None:
    hc = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert re.search(r'_costed\("blueprint_score", lambda: _producer\(\s*"blueprint_score", '
                     r'"scripts/check_blueprint_score.py", "--write"\)\)', hc)
    assert '"blueprint_score": bps' in hc
    from desks.mt5.research import hourly_cycle, issue_board

    from libs.research import layers
    assert "blueprint_score" in hourly_cycle.CORE_LEGS
    assert hourly_cycle.LEG_DEPARTMENT.get("blueprint_score") == "meta"
    assert layers.LEG_LAYER["blueprint_score"] == "meta"
    assert ("blueprint_score", "desks/mt5/reports/BLUEPRINT_SCORE.json", 3600, None) \
        in issue_board.CADENCE
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text("utf-8")
    assert '("check_blueprint_score.py", ()),' in gate
    assert '("check_blueprint_score.py", ("--require-state",)),' in gate
    t1 = json.loads((ROOT / "docs" / "research" / "tier1_program.json").read_text("utf-8"))
    row = next(i for i in t1["items"] if "hourly_cycle:blueprint_score" in
               str(i.get("scheduled_by")))
    assert row["artifact"] == "desks/mt5/reports/BLUEPRINT_SCORE.json"
    state = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    assert any(r.get("organ") == "leg:blueprint_score" for r in state["organs"])


@pytest.mark.parametrize("text,w", [("allocator sovereignty", 5), ("lockbox re-cert", 4),
                                    ("world data OS", 3), ("ruff over desks", 1),
                                    ("something else", 2)])
def test_weight_table(text: str, w: int) -> None:
    assert bs.weight(text) == w
