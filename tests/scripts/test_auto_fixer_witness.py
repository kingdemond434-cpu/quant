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
from pathlib import Path

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


#: Fixer classes whose repair is provable by an artifact. A RATCHET: it may rise, never fall.
#: Measured 2026-09-05 at 14 of 21, up from 1. It was 15 for a moment, until
#: `test_every_witness_is_the_artifact_its_own_breach_names` rejected a QUEUES entry:
#: check_research_health raises no QUEUES breach at all, so there was no
#: complaint for that witness to correspond to. The gap was costing exactly what the WITNESS
#: docstring predicted: SEARCH sat 35.2h stale and GAUNTLET 58.3h on the live dashboard, both with
#: a fixer wired and running on the 30-minute health timer, neither repairing anything, and
#: nothing in the desk able to tell that from a repair that worked.
MIN_WITNESSED = 14


def test_witness_coverage_only_ever_improves() -> None:
    """A fixer with no witness can report ATTEMPTED forever. That is honest -- UNWITNESSED is a
    real answer -- but it is not a state to drift back into: every class that CAN be proved should
    be, and the six that remain (BREADTH, FAMILIES, FORWARD, ROI, SEATS, STALL-WATCH) are analyses
    with no single producing artifact rather than gaps anyone chose to leave."""
    assert len(auto_fixers.WITNESS) >= MIN_WITNESSED, (
        f"witness coverage fell to {len(auto_fixers.WITNESS)} of {len(auto_fixers.FIXERS)}; a "
        f"repair that stops being provable is a repair that can silently stop working"
    )


def test_no_witness_names_a_class_that_has_no_fixer() -> None:
    """Dead config in the other direction: a witness for a class nothing repairs would never be
    consulted, and would read as coverage the desk does not have."""
    orphan = sorted(set(auto_fixers.WITNESS) - set(auto_fixers.FIXERS))
    assert not orphan, f"witness entries with no fixer: {orphan}"


def test_every_witness_is_the_artifact_its_own_breach_names() -> None:
    """The witness and the complaint must not drift apart. `check_research_health` is the only
    thing that raises these classes, so if it does not mention the file, proving that file moved
    proves nothing about the breach that was raised."""
    health = (Path(auto_fixers.__file__).parent / "check_research_health.py").read_text("utf-8")
    for cls, path in sorted(auto_fixers.WITNESS.items()):
        assert path.name in health, (
            f"WITNESS[{cls!r}] points at {path.name}, which check_research_health never reads -- "
            f"so a fix could be 'proved' by a file unrelated to the breach it answered"
        )
