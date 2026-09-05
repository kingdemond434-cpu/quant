"""A FIXER MUST BE JUDGED BY THE ARTIFACT, NEVER BY ITS LAUNCH (gap-fixer 2026-08-29).

`fix_sweep` runs `ssh ... 'cmd /c "... start /b py -3 orthogonal_sweep.py"'` and returned
`rc == 0`. `start /b` returns the moment the LAUNCH is accepted, so that rc reports that cmd.exe
parsed a command line -- not that python was found, not that the script ran, not that a byte was
written. MEASURED: `orthogonal_candidates.json` last advanced 2026-08-28T20:05; SWEEP was "fixed"
at 01:33, 02:33 and 03:13 on 08-29, each journaled `ATTEMPTED  lock cleared; direct_rc=0`, and the
artifact never moved. The vocabulary was ATTEMPTED / FAILED / COOLDOWN, so a fixer that repairs
nothing looked exactly like one that works -- while the breach it was fixing printed beside it
every five minutes.
"""
from __future__ import annotations

import json

import pytest

from scripts import auto_fixers


@pytest.fixture
def rig(tmp_path, monkeypatch):
    art = tmp_path / "orthogonal_candidates.json"
    art.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(auto_fixers, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(auto_fixers, "WITNESS", {"SWEEP": art})
    monkeypatch.setattr(auto_fixers, "FIX_COOLDOWN_MIN", 0)
    monkeypatch.setitem(auto_fixers.FIXERS, "SWEEP", lambda: (True, "lock cleared; direct_rc=0"))
    return art


def _outcomes(tmp_path) -> list[str]:
    return [r["outcome"] for r in
            json.loads((tmp_path / "state.json").read_text("utf-8"))["journal"]]


def test_a_launch_that_moves_nothing_is_reported_INEFFECTIVE(rig, tmp_path):
    """THE DEFECT. Three green launches, artifact frozen, journal all-clear."""
    auto_fixers.apply(["SWEEP: stale"])            # first attempt: nothing to compare against yet
    auto_fixers.apply(["SWEEP: stale"])            # artifact never moved
    auto_fixers.apply(["SWEEP: stale"])
    outcomes = _outcomes(tmp_path)
    assert outcomes[0] == "ATTEMPTED"
    assert outcomes[1:] == ["INEFFECTIVE", "INEFFECTIVE"], outcomes
    detail = json.loads((tmp_path / "state.json").read_text("utf-8"))["journal"][-1]["detail"]
    assert "has not advanced across 2 consecutive attempt(s)" in detail
    assert "deep repair" in detail


def test_a_launch_that_moves_the_artifact_stays_ATTEMPTED(rig, tmp_path):
    """The other half: a fixer that works must not be slandered by its own verifier."""
    auto_fixers.apply(["SWEEP: stale"])
    import os
    st = rig.stat()
    os.utime(rig, (st.st_atime + 600, st.st_mtime + 600))   # the remote job landed
    auto_fixers.apply(["SWEEP: stale"])
    assert _outcomes(tmp_path) == ["ATTEMPTED", "ATTEMPTED"]


def test_the_ineffective_counter_resets_once_the_artifact_moves(rig, tmp_path):
    """A class that recovers must not stay branded, or the signal decays into noise."""
    import os
    auto_fixers.apply(["SWEEP: stale"])
    auto_fixers.apply(["SWEEP: stale"])
    assert _outcomes(tmp_path)[-1] == "INEFFECTIVE"
    st = rig.stat()
    os.utime(rig, (st.st_atime + 600, st.st_mtime + 600))
    auto_fixers.apply(["SWEEP: stale"])
    assert _outcomes(tmp_path)[-1] == "ATTEMPTED"


def test_a_class_with_no_witness_is_UNWITNESSED_never_silently_successful(tmp_path, monkeypatch):
    """UNMEASURED IS A REAL ANSWER (L1.28a). Not knowing whether a repair landed is a different
    fact from knowing it did, and rendering them identically is the defect one level up."""
    monkeypatch.setattr(auto_fixers, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(auto_fixers, "WITNESS", {})
    monkeypatch.setattr(auto_fixers, "FIX_COOLDOWN_MIN", 0)
    monkeypatch.setitem(auto_fixers.FIXERS, "SWEEP", lambda: (True, "launched"))
    auto_fixers.apply(["SWEEP: stale"])
    row = json.loads((tmp_path / "state.json").read_text("utf-8"))["journal"][-1]
    assert row["outcome"] == "ATTEMPTED"
    assert "UNWITNESSED" in row["detail"] and "UNMEASURED" in row["detail"]


def test_the_real_sweep_witness_is_the_artifact_the_breach_names():
    """The mapping is only useful if it names the file check_research_health actually watches."""
    assert auto_fixers.WITNESS["SWEEP"].name == "orthogonal_candidates.json"
    assert "hypotheses" in str(auto_fixers.WITNESS["SWEEP"])
