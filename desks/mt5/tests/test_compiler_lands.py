"""The compiler stops inside its parent's cap, reserves what its writes measured, and says so."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mcc  # noqa: E402


def _phases(**t: float) -> list[dict]:
    return [{"phase": k, "t_s": v} for k, v in t.items()]


def test_a_finished_pass_measures_its_write_phase_exactly() -> None:
    prior = {"cap_s": 720, "phases": _phases(listed=50, compile_done=300, done=480)}
    assert mcc._measured_write_s(prior) == 180


def test_a_killed_pass_teaches_at_least_the_rest_of_its_cap() -> None:
    prior = {"cap_s": 720, "phases": _phases(listed=50, compile_done=500, graph=520)}
    assert mcc._measured_write_s(prior) == 220
    assert mcc._measured_write_s({"cap_s": 720, "phases": _phases(listed=700)}) is None


def test_the_stops_sit_inside_the_parent_cap_minus_the_reserve(tmp_path: Path,
                                                               monkeypatch) -> None:
    prog = tmp_path / "progress.json"
    prog.write_text(json.dumps({"cap_s": 720, "phases": _phases(compile_done=510, graph=600)}))
    monkeypatch.setattr(mcc, "PROGRESS", prog)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "720")
    t0 = time.monotonic()
    monkeypatch.setattr(mcc, "_PROCESS_T0", t0)
    mcc._set_budget(600)
    # killed 210 s after compile_done -> reserve 1.5 x 210 = 315 s
    assert abs(mcc._CLOCK["compile_by"] - (t0 + 720 - mcc.KILL_MARGIN_S - 315)) < 1.0
    assert mcc._CLOCK["intake_by"] < mcc._CLOCK["compile_by"]
    doc = json.loads(prog.read_text())
    assert doc["write_reserve_s"] == 315 and doc["phases"][0]["phase"] == "budget_set"
    mcc._progress("compile_done")
    assert [p["phase"] for p in json.loads(prog.read_text())["phases"]] == [
        "budget_set", "compile_done"]


def test_a_reserve_larger_than_the_cap_still_compiles_a_slice(tmp_path: Path,
                                                              monkeypatch) -> None:
    prog = tmp_path / "progress.json"
    prog.write_text(json.dumps({"cap_s": 720, "phases": _phases(compile_done=10, done=900)}))
    monkeypatch.setattr(mcc, "PROGRESS", prog)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "720")
    monkeypatch.setattr(mcc, "_PROCESS_T0", time.monotonic())
    before = time.monotonic()
    mcc._set_budget(600)
    assert mcc._CLOCK["compile_by"] >= before + mcc.MIN_COMPILE_SHARE * 720 - 0.5


def test_without_a_cap_the_budget_shares_are_unchanged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mcc, "PROGRESS", tmp_path / "progress.json")
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    t0 = time.monotonic()
    monkeypatch.setattr(mcc, "_PROCESS_T0", t0)
    mcc._set_budget(600)
    assert abs(mcc._CLOCK["compile_by"] - (t0 + mcc.COMPILE_SHARE * 600)) < 1e-6
    assert abs(mcc._CLOCK["intake_by"] - (t0 + mcc.INTAKE_SHARE * 600)) < 1e-6
    mcc._CLOCK.clear()
    mcc._PROGRESS.clear()


def test_the_listing_finds_what_the_old_walk_found(tmp_path: Path) -> None:
    root = tmp_path / "intel"
    (root / "seat" / "deep").mkdir(parents=True)
    keep = [root / "seat" / "a.json", root / "seat" / "deep" / "b.JSONL", root / "c.json"]
    for p in keep:
        p.write_text("[]")
    (root / "seat" / "notes.txt").write_text("x")
    op = next(iter(mcc._OPERATIONAL_STATE))
    (root / op).write_text("{}")
    (root / "seat" / op).write_text("[]")          # inside a source dir: evidence, read
    keep.append(root / "seat" / op)
    old = {p for p in root.rglob("*")
           if p.is_file() and p.suffix.lower() in {".json", ".jsonl"}
           and not mcc._is_operational_state(p.relative_to(root))}
    got = mcc._list_artifacts(root)
    assert set(got) == old == set(keep)
    assert all(abs(got[p] - os.stat(p).st_mtime) < 1e-6 for p in got)


def teardown_function() -> None:
    mcc._CLOCK.clear()
    mcc._PROGRESS.clear()
