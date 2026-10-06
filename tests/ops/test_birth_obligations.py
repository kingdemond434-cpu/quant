"""EVERY OBLIGATION IS INHERITED, NOT REMEMBERED: plant five incomplete arrivals, catch five.

The fence's whole claim is that a thing created NEXT MONTH inherits its obligations without a
session remembering them. The only way to test that claim is to create such a thing -- one per
axis -- after the floor has been recorded, and require the fence to name each of them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_birth_obligations as birth  # noqa: E402


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _baseline_tree(root: Path) -> None:
    """A small tree where every axis measures and every object HAS its obligation."""
    _write(root / "scripts" / "old_tool.py", "if __name__ == '__main__':\n    pass\n")
    _write(root / "desks" / "mt5" / "research" / "hourly_cycle.py",
           '_costed("old_tool", lambda: None)\n')
    _write(root / "docs" / "research" / "runtime_state.json",
           json.dumps({"organs": [{"organ": "leg:old_tool", "artifact": "scripts/old_tool.py"}]}))
    _write(root / "desks" / "mt5" / "data" / "deep_forest_sources.json",
           json.dumps({"cn": [{"id": "old_source"}]}))
    _write(root / "desks" / "mt5" / "reports" / "SOURCE_DRAIN.json",
           json.dumps({"rows": [{"source": "old_source", "stage": "cells_judged"}]}))
    _write(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json",
           json.dumps({"families": {"old_family": {"judged": 12}}}))
    _write(root / "desks" / "mt5" / "reports" / "regional_parity.json",
           json.dumps({"regions": {"old_region": {"depth": 3}}, "flagged": []}))
    _write(root / "libs" / "old_deleter.py",
           "import shutil\n\n\ndef go(p):\n    if p.exists():\n        shutil.rmtree(p)\n")
    # 6. the SIXTH AXIS (attribution, 2026-09-23): a registry whose cells and discoveries born
    # since the obligation date all carry their producer stamp.
    import sqlite3
    db = root / "data" / "alpha_registry.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.execute("create table research_candidates (id text, created_at text, producer text)")
    con.execute("create table discoveries (discovery_id text, created_at text, producer text)")
    con.execute("insert into research_candidates values ('c1', '2026-09-24T01:00:00', 'miner')")
    con.execute("insert into discoveries values ('d1', '2026-09-24T01:00:00', 'miner')")
    con.commit()
    con.close()
    # 7. the SEVENTH AXIS (certificate birth, 2026-09-24): every certificate the canon holds has
    # a row in the birth record, naming its producer.
    _write(root / "desks" / "mt5" / "data" / "UNIVERSAL_SURVIVORS.canon.json",
           json.dumps({"survivors": {"external.OLD.cell": {"hunt": "external",
                                                           "cell": "OLD.cell"}}}))
    _write(root / "desks" / "mt5" / "data" / "certificate_provenance.json",
           json.dumps({"records": {"OLD.cell": {"verdict": "ATTRIBUTED",
                                                "producer": "miner"}}}))


def _plant_five(root: Path) -> None:
    """One new object per axis, each arriving WITHOUT the obligation of its class."""
    # 1. a new executable with no clock and no attested row
    _write(root / "scripts" / "new_tool.py", "if __name__ == '__main__':\n    pass\n")
    # 2. a new source with no position in the collection chain
    _write(root / "desks" / "mt5" / "data" / "deep_forest_sources.json",
           json.dumps({"cn": [{"id": "old_source"}, {"id": "new_source"}]}))
    # 3. a new family the judge never reaches
    _write(root / "desks" / "mt5" / "reports" / "JUDGE_COVERAGE.json",
           json.dumps({"families": {"old_family": {"judged": 12},
                                    "new_family": {"judged": 0}}}))
    # 4. a new country arriving below the standing floors
    _write(root / "desks" / "mt5" / "reports" / "regional_parity.json",
           json.dumps({"regions": {"old_region": {"depth": 3}, "new_country": {"depth": 0}},
                       "flagged": ["new_country"]}))
    # 5. a new destructive path that acts without looking
    _write(root / "libs" / "new_deleter.py",
           "import shutil\n\n\ndef go(p):\n    shutil.rmtree(p)\n")


def test_the_baseline_tree_is_complete_on_every_axis(tmp_path: Path) -> None:
    _baseline_tree(tmp_path)
    doc = birth.measure(tmp_path)
    for name, ax in doc["axes"].items():
        assert ax["verdict"] == "measured", f"{name} could not be measured: {ax['why']}"
        assert ax["incomplete"] == 0, f"{name} starts incomplete: {ax['names']}"
    assert doc["failures"] == []


def test_five_arrivals_without_their_obligations_are_all_caught(tmp_path: Path) -> None:
    _baseline_tree(tmp_path)
    assert birth.main(["--root", str(tmp_path), "--update"]) == 0
    _plant_five(tmp_path)

    doc = birth.measure(tmp_path)
    arrived = {k: v["arrived_without_obligation"] for k, v in doc["axes"].items()}
    assert arrived["executable"] == ["scripts/new_tool.py"]
    assert arrived["source"] == ["new_source"]
    assert arrived["family"] == ["new_family"]
    assert arrived["region"] == ["new_country"]
    assert arrived["destructive"] == ["libs/new_deleter.py"]
    assert len(doc["failures"]) == 5
    assert birth.main(["--root", str(tmp_path)]) == 2


def test_an_arrival_that_acquires_its_obligation_leaves_the_floor(tmp_path: Path) -> None:
    """The ratchet falls by itself: no human edits a number to record the repair."""
    _baseline_tree(tmp_path)
    birth.main(["--root", str(tmp_path), "--update"])
    _write(tmp_path / "libs" / "new_deleter.py",
           "import shutil\n\n\ndef go(p):\n    shutil.rmtree(p)\n")
    assert birth.measure(tmp_path)["axes"]["destructive"]["arrived_without_obligation"] == [
        "libs/new_deleter.py"]
    birth.main(["--root", str(tmp_path), "--update"])          # accept the debt
    ax = birth.measure(tmp_path)["axes"]["destructive"]
    assert ax["arrived_without_obligation"] == [] and ax["incomplete"] == 1
    _write(tmp_path / "libs" / "new_deleter.py",
           "import shutil\n\n\ndef go(p):\n    if p.exists():\n        shutil.rmtree(p)\n")
    ax = birth.measure(tmp_path)["axes"]["destructive"]
    assert ax["incomplete"] == 0 and ax["healed"] == 1


def test_an_axis_with_no_declaring_artifact_is_unmeasured_not_zero(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    doc = birth.measure(tmp_path)
    for name, ax in doc["axes"].items():
        assert ax["verdict"] == birth.UNMEASURED, name
        assert ax["why"].startswith(birth.UNMEASURED)
    assert doc["failures"] == [], "an unmeasured axis must never manufacture a failure"


def test_every_axis_names_the_fence_that_already_owns_it() -> None:
    """The point is ONE place that answers 'did anything arrive incomplete', not five more
    checkers: each axis must delegate to the fence the desk already has."""
    for ax in birth.AXES:
        assert ax.fence is not None, ax.name
        assert (ROOT / "scripts" / ax.fence[0]).is_file(), ax.fence[0]
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert "check_birth_obligations.py" in gate, "the fence must run on the law gate"


# ------------------------------- attestation rows are appended, never edited (audit 2026-10-06)

def _rs(at: str, rows: list[dict]) -> dict:
    return {"generated_at": at, "organs": rows}


def test_an_in_place_row_edit_is_named_and_an_append_is_not() -> None:
    """e499d3020 added a path to the LIVE row leg:external_gauntlet's `code` list by hand, with
    generated_at unchanged; the fence exited 0."""
    row = {"organ": "leg:external_gauntlet", "code": ["a.py"], "state": "LIVE"}
    base = _rs("2026-10-05T10:00:00+00:00", [row])
    edited = _rs("2026-10-05T10:00:00+00:00", [{**row, "code": ["a.py", "b.py"]}])
    assert birth.attestation_edits(base, edited) == [
        "leg:external_gauntlet: edited in place (code)"]
    appended = _rs("2026-10-05T10:00:00+00:00", [dict(row), {"organ": "leg:new"}])
    assert birth.attestation_edits(base, appended) == []
    removed = _rs("2026-10-05T10:00:00+00:00", [])
    assert birth.attestation_edits(base, removed) == ["leg:external_gauntlet: row removed"]
    # a full re-attestation stamps a LATER generated_at and owns every row it rewrites
    reattested = _rs("2026-10-05T11:00:00+00:00", [{**row, "state": "STALE"}])
    assert birth.attestation_edits(base, reattested) == []
    # an older stamp is not a re-attestation
    older = _rs("2026-10-05T09:00:00+00:00", [{**row, "state": "STALE"}])
    assert birth.attestation_edits(base, older) != []
    assert not birth.REATTEST_FIELDS


def _git(root: Path, *args: str) -> None:
    import subprocess
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "PATH": __import__("os").environ.get("PATH", ""),
                        "HOME": str(root)})


def test_check_against_the_merge_base_fails_a_committed_edit(tmp_path: Path, monkeypatch: Any,
                                                              capsys: Any) -> None:
    rel = tmp_path / "docs" / "research" / "runtime_state.json"
    row = {"organ": "leg:x", "code": ["x.py"]}
    _write(rel, json.dumps(_rs("2026-10-05T10:00:00+00:00", [row])))
    _git(tmp_path, "init", "-q", "-b", "live")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "live")
    _git(tmp_path, "checkout", "-q", "-b", "pr")
    ok = birth.check_attestation_rows(tmp_path, ref="live")
    assert ok["verdict"] == "measured" and ok["edits"] == []
    _write(rel, json.dumps(_rs("2026-10-05T10:00:00+00:00", [{**row, "code": ["x.py", "y.py"]}])))
    _git(tmp_path, "commit", "-q", "-am", "hand edit")
    bad = birth.check_attestation_rows(tmp_path, ref="live")
    assert bad["edits"] == ["leg:x: edited in place (code)"]
    monkeypatch.setenv("QUANT_LIVE_REF", "live")
    assert birth.main(["--root", str(tmp_path)]) == 2
    assert "rewritten without a re-attestation" in capsys.readouterr().out


def test_no_git_is_unmeasured_never_a_pass_or_a_failure(tmp_path: Path) -> None:
    r = birth.check_attestation_rows(tmp_path, ref="nope")
    assert r["verdict"] == birth.UNMEASURED and r["edits"] == []
