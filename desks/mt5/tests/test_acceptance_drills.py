"""ARCH-18: the eight acceptance drills are graded from the recovery scorecard (PASS only when every
proving row passed on a fresh scorecard), published with the six publication fields, written as
runtime proofs the acceptance audit reads, and never claim tests they did not run."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import acceptance_drills as ad  # noqa: E402
from research import recovery_drills as rd  # noqa: E402

NOW = datetime(2026, 11, 10, 12, tzinfo=UTC)
NAMED = {"replay", "information_freshness", "model_to_decision", "no_duplicate_execution",
         "reconciliation", "rollback_restore", "research_under_load",
         "latency_without_excess_trading"}


def _card(tmp: Path, verdicts: dict[str, str], at: datetime = NOW) -> Path:
    p = tmp / "RECOVERY_DRILLS.json"
    p.write_text(json.dumps({"generated_utc": at.isoformat(), "drills": [
        {"drill": k, "verdict": v, "why": f"{k} said {v}"} for k, v in verdicts.items()]}))
    return p


def _all(verdict: str) -> dict[str, str]:
    return {r: verdict for spec in ad.DRILLS.values() for r in spec["rows"]}


def test_the_eight_named_drills_are_all_here() -> None:
    assert set(ad.DRILLS) == NAMED


def test_every_proving_row_is_a_scorecard_row_or_lands_with_a_sibling() -> None:
    have = {d for d, _, _ in rd.DRILLS}
    pending = {"reconciliation", "load", "workload_separation"}   # ARCH-06 / ARCH-07 rows
    for spec in ad.DRILLS.values():
        for r in spec["rows"]:
            assert r in have or r in pending, r


def test_implementation_paths_exist_or_are_named_pending() -> None:
    for spec in ad.DRILLS.values():
        for f in spec["implementation"]:
            assert (_ROOT / f).exists() or f in ad.PENDING_ON, f


def test_all_rows_passing_passes_with_publication_fields(tmp_path: Path) -> None:
    doc = ad.grade(NOW, scorecard=_card(tmp_path, _all("PASS")), release="a" * 40)
    assert doc["verdict"] == "PASS" and doc["counts"]["PASS"] == 8
    row = doc["drills"][0]
    for k in ("implementation_path", "runtime_identity", "tested_behaviour",
              "evidence_timestamp", "remaining_blocker", "impact"):
        assert k in row
    assert row["remaining_blocker"] is None and row["runtime_identity"]["release"] == "a" * 40


def test_one_failing_row_fails_its_drill_and_names_it(tmp_path: Path) -> None:
    v = _all("PASS") | {"rollback": "FAIL"}
    doc = ad.grade(NOW, scorecard=_card(tmp_path, v), release="a" * 40)
    by = {r["drill"]: r for r in doc["drills"]}
    assert by["rollback_restore"]["verdict"] == "FAIL"
    assert "rollback said FAIL" in by["rollback_restore"]["remaining_blocker"]
    assert by["replay"]["verdict"] == "PASS"


def test_absent_rows_and_stale_scorecards_are_unmeasured_never_pass(tmp_path: Path) -> None:
    v = _all("PASS")
    v.pop("load")
    doc = ad.grade(NOW, scorecard=_card(tmp_path, v), release="a" * 40)
    by = {r["drill"]: r for r in doc["drills"]}
    assert by["research_under_load"]["verdict"] == "UNMEASURED"
    assert "load=ABSENT" in by["research_under_load"]["why"]
    stale = ad.grade(NOW, scorecard=_card(tmp_path, _all("PASS"), NOW - timedelta(hours=9)))
    assert stale["counts"]["UNMEASURED"] == 8
    absent = ad.grade(NOW, scorecard=tmp_path / "nope.json")
    assert absent["counts"]["UNMEASURED"] == 8


def test_proofs_never_claim_tests_and_the_audit_reads_them(tmp_path: Path) -> None:
    import global_research_acceptance as gra
    doc = ad.grade(NOW, scorecard=_card(tmp_path, _all("PASS")), release="b" * 40)
    pr = ad.proof(doc["drills"][0], doc)
    assert pr["tests_passed"] is None and pr["status"] == "PASS" and pr["completed_work"] >= 1
    p = tmp_path / "replay.json"
    p.write_text(json.dumps(pr))
    got, errs = gra._runtime_proof(p, instant=NOW, release="b" * 40)
    assert errs == ["tests_not_attested"], errs


def test_the_addendum_is_loaded_and_publishes_per_requirement(tmp_path: Path) -> None:
    import global_research_acceptance as gra
    spec = json.loads((_ROOT / "docs/research/global_research_maximum_v1.json").read_text())
    assert "docs/research/acceptance_drills_v1.json" in spec["addenda"]
    add = json.loads((_ROOT / "docs/research/acceptance_drills_v1.json").read_text())
    assert len(add["requirements"]) == 8
    doc = gra.audit(report=tmp_path / "GRA.json", now=NOW)
    rows = [r for r in doc["rows"] if r["id"].startswith("AD")]
    assert len(rows) == 8
    for r in rows:
        pub = r["publication"]
        assert pub["impact"] in ("production", "research")
        assert pub["implementation_path"] and pub["tested_behaviour"]
        assert r["status"] == "PARTIAL"     # no fresh proof in a test tree: never verified


@pytest.mark.parametrize("did", sorted(NAMED))
def test_each_drill_maps_to_at_least_one_row(did: str) -> None:
    assert ad.DRILLS[did]["rows"]
