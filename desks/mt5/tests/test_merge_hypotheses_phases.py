"""A merge records what each of its phases cost (2026-11-05: 27 h runs nobody could apportion)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import merge_hypotheses as mh


def test_phases_time_each_step_and_publish_only_for_the_live_docket(tmp_path, monkeypatch):
    monkeypatch.setattr(mh, "PROGRESS", tmp_path / "progress.json")
    ph = mh._Phases()
    ph.mark("sources", 3)
    ph.mark("bank_read")
    rep = ph.report()
    assert list(rep["phase_seconds"]) == ["sources", "bank_read"]
    assert rep["rows"] == {"sources": 3} and rep["elapsed_s"] >= 0
    doc = json.loads((tmp_path / "progress.json").read_text("utf-8"))
    assert doc["last_phase"] == "bank_read" and doc["pid"] == rep["pid"]
    (tmp_path / "progress.json").unlink()
    monkeypatch.setattr(mh, "HYP", tmp_path / "elsewhere")
    mh._Phases().mark("sources")
    assert not (tmp_path / "progress.json").exists()


def test_every_phase_mark_in_main_is_a_distinct_name():
    import inspect
    import re
    names = re.findall(r'phases\.mark\("([a-z_]+)"', inspect.getsource(mh.main))
    assert len(names) == len(set(names)) >= 12
