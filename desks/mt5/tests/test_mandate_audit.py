"""The mandate audit moves a row only on evidence about that row: file presence never promotes,
a vanished module or leg demotes, a fresh stamped artifact turns an audited SCHEDULED row
RUNNING, a checkout's mtime is not a run, evidence stages are kept and flagged stale, and a claim
moves a row only as far as it verifies."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import mandate_audit as ma  # noqa: E402

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
CYCLE = 'x = _costed("fx_leg", lambda: _producer("fx_leg", "research/fx.py"))\n'


def _tree(tmp: Path, files: dict[str, str], tracked: set[str] | None = None) -> ma.Tree:
    for rel, body in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    cyc = tmp / "desks/mt5/research/hourly_cycle.py"
    cyc.parent.mkdir(parents=True, exist_ok=True)
    if not cyc.exists():
        cyc.write_text(CYCLE)
    return ma.Tree(root=tmp, tracked=tracked if tracked is not None else set())


def _row(rid: str = "ROMAN-0001", state: str = "CODED", **kw) -> dict:
    return {"id": rid, "state": state, "owner_thread": "World sensor", "module": [],
            "scheduler": "NONE", "output_artifacts": [], "audit_legs": [], **kw}


def _run(tree: ma.Tree, rows: list[dict], claims: dict | None = None) -> dict:
    base = {"generated_at": "2026-10-06T16:20:52Z", "live_sha": "x", "requirements": rows}
    return ma.build(now=NOW, baseline=base, tree=tree, claims=claims or {})


def _stamped(at: datetime) -> str:
    return json.dumps({"generated_utc": at.isoformat()})


def test_file_presence_never_promotes_a_coded_row(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def f(): pass\n",
                         "desks/mt5/reports/FX.json": _stamped(NOW)})
    row = _row(module=["libs/fx.py:1"], scheduler="hourly leg fx_leg",
               output_artifacts=["desks/mt5/reports/FX.json"], audit_legs=["fx_leg"])
    r = _run(t, [row])["rows"][0]
    assert r["state"] == "CODED" and not r["changed"]


def test_vanished_module_regresses_to_absent(tmp_path: Path) -> None:
    t = _tree(tmp_path, {})
    r = _run(t, [_row(state="SCHEDULED", module=["libs/gone.py:10"])])["rows"][0]
    assert r["state"] == "ABSENT" and r["why"].startswith("regressed")


def test_vanished_leg_regresses_scheduled_to_coded(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def f(): pass\n"})
    row = _row(state="SCHEDULED", module=["libs/fx.py"], audit_legs=["removed_leg"])
    assert _run(t, [row])["rows"][0]["state"] == "CODED"


def test_fresh_stamped_artifact_makes_audited_scheduled_running(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def f(): pass\n",
                         "desks/mt5/reports/FX.json": _stamped(NOW - timedelta(hours=2))})
    row = _row(state="SCHEDULED", module=["libs/fx.py"], audit_legs=["fx_leg"],
               output_artifacts=["desks/mt5/reports/FX.json"])
    doc = _run(t, [row])
    assert doc["rows"][0]["state"] == "RUNNING" and doc["running"] == 1


def test_stale_stamp_stays_scheduled(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def f(): pass\n",
                         "desks/mt5/reports/FX.json": _stamped(NOW - timedelta(hours=40))})
    row = _row(state="SCHEDULED", module=["libs/fx.py"], audit_legs=["fx_leg"],
               output_artifacts=["desks/mt5/reports/FX.json"])
    assert _run(t, [row])["rows"][0]["state"] == "SCHEDULED"


def test_tracked_file_mtime_is_not_a_run(tmp_path: Path) -> None:
    rel = "desks/mt5/data/intelligence/korea/a.csv"
    t = _tree(tmp_path, {"libs/fx.py": "def f(): pass\n", rel: "x\n"}, tracked={rel})
    row = _row(state="SCHEDULED", module=["libs/fx.py"], audit_legs=["fx_leg"],
               output_artifacts=["desks/mt5/data/intelligence/korea/"])
    assert _run(t, [row])["rows"][0]["state"] == "SCHEDULED"


def test_evidence_stage_kept_and_flagged_stale(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def f(): pass\n"})
    row = _row(state="LIVE", module=["libs/fx.py"],
               output_artifacts=["desks/mt5/reports/FX.json"])
    doc = _run(t, [row])
    assert doc["rows"][0]["state"] == "LIVE" and doc["rows"][0]["evidence_stale"]


def test_row_without_module_keeps_audit(tmp_path: Path) -> None:
    t = _tree(tmp_path, {})
    assert _run(t, [_row(state="BLOCKED")])["rows"][0]["state"] == "BLOCKED"


def test_claim_moves_row_only_as_far_as_it_verifies(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def build():\n    pass\n",
                         "tests/test_fx.py": "from libs import fx\n",
                         "desks/mt5/reports/FX.json": _stamped(NOW)})
    claim = {"code": ["libs/fx.py::build"], "tests": ["tests/test_fx.py"], "leg": "fx_leg",
             "artifacts": ["desks/mt5/reports/FX.json"]}
    doc = _run(t, [_row(state="ABSENT")], {"ROMAN-0001": claim})
    assert doc["rows"][0]["state"] == "RUNNING" and doc["claims"]["verified"] == 1
    no_leg = {**claim, "leg": "not_a_leg"}
    assert _run(t, [_row(state="ABSENT")], {"ROMAN-0001": no_leg})["rows"][0]["state"] == "CODED"


def test_failing_claim_changes_nothing(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def other():\n    pass\n",
                         "tests/test_fx.py": "from libs import fx\n"})
    claim = {"code": ["libs/fx.py::build"], "tests": ["tests/test_fx.py"], "leg": "fx_leg"}
    doc = _run(t, [_row(state="ABSENT")], {"ROMAN-0001": claim})
    assert doc["rows"][0]["state"] == "ABSENT"
    assert doc["claims"]["rows"][0]["proves"] is None
    assert "not defined" in doc["claims"]["rows"][0]["why"]


def test_claim_never_lowers_or_overrides_evidence(tmp_path: Path) -> None:
    t = _tree(tmp_path, {"libs/fx.py": "def build():\n    pass\n",
                         "tests/test_fx.py": "from libs import fx\n"})
    claim = {"code": ["libs/fx.py::build"], "tests": ["tests/test_fx.py"]}
    row = _row(state="PROVEN", module=["libs/fx.py"])
    assert _run(t, [row], {"ROMAN-0001": claim})["rows"][0]["state"] == "PROVEN"


def test_committed_baseline_matches_the_audit_and_has_no_unowned_rows() -> None:
    base = ma.load_baseline()
    rows = base["requirements"]
    assert len(rows) == 3601
    assert not [r for r in rows if r["owner_thread"] == "UNOWNED"]
    assert {r["state"] for r in rows} <= set(ma.STATES)


def test_committed_claims_verify_against_this_tree() -> None:
    tree = ma.Tree()
    for rid, claim in ma.load_claims().items():
        stage, why = ma.verify_claim(claim, tree, NOW)
        assert stage in ma.CODE_STAGES, f"{rid}: {why}"


def test_leg_is_wired_into_the_hourly_cycle() -> None:
    assert "mandate_audit" in ma.Tree().legs
