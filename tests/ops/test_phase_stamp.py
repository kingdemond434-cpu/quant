"""A killed organ still says where it died (libs/ops/phase_stamp.py, 2026-11-03)."""

from __future__ import annotations

import json
from pathlib import Path

from libs.ops.phase_stamp import PhaseStamp


def test_the_last_phase_entered_is_on_disk_before_it_runs(tmp_path: Path) -> None:
    p = tmp_path / "reports" / "ORGAN.phase.json"
    st = PhaseStamp("organ", p)
    st.enter("read_graph")
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert (doc["phase"], doc["state"]) == ("read_graph", "RUNNING")
    st.enter("walk")
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["phase"] == "walk"
    assert doc["phases"][0]["phase"] == "read_graph" and "s" in doc["phases"][0]
    phases = st.done()
    assert json.loads(p.read_text(encoding="utf-8"))["state"] == "DONE"
    assert [ph["phase"] for ph in phases] == ["read_graph", "walk"]
    assert not list(p.parent.glob("*.tmp"))


def test_an_unwritable_stamp_never_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    st = PhaseStamp("organ", blocker / "sub" / "ORGAN.phase.json")   # parent is a file
    st.enter("anything")
    assert st.done()[0]["phase"] == "anything"
