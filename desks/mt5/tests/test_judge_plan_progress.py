"""The judge's "plan" phase names its step and its progress (judge_plan_progress, 2026-10-20).

The 10-20 plans ran 9,302 s and 9,729 s and said nothing until the pre-warm pool's last line, so a
plan two hours in could not be told from a hung one. These tests pin what the launcher now
publishes and that publishing it changes nothing it reports on.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import judge_plan_progress as jpp  # noqa: E402

#: The plan's own lines, verbatim shapes from the sealed judge (LIVE f56bc72f and stack f70c5147).
PLAN_LOG = """\
2026-10-20T21:34:50+00:00 canonical sharded judge runtime=python shards=15 shard_concurrency=2
Loaded 1612345 external survivors by streaming census
Unique cells to evaluate: 1598000
Submitted families: {'discovered': 1}
Gate 0: 1200000 advance; 398000 terminal reject (1000 untradeable symbol, 397000 no economic prior)
Build preflight: 12 incomplete input/variant(s) conserved without spending build/gate compute
CACHE PRUNE: 900000 cached cell(s) scanned, 1000 older than 3 days removed in 41s
  breadth: 40 chart x session bucket(s) judged so far; least covered M1/all (1), most H1/asia (9)
  novelty: 3 of 1500 screened cell(s) set aside as REDUNDANT (twins named) -> NOVELTY_SET_ASIDE.json
  docket order: 1000 never-judged cell(s) first, then 1199000 in symbol-rotation order
  yield allocation: 600000 of 1200000 cell(s) this sweep (strength 0.70, floor 15%)
PRE-WARM START: 600000 cell(s) in docket order, 15 worker(s), build budget ends in 8100s
PRE-WARM: 15 worker(s) warmed 9000 cell(s) in 8100s (500000 already cached, 3 failed, 90000 not reached)
SHARDED SWEEP: 600000 planned cell(s) across 15 shard(s)
"""


class _Clock:
    def __init__(self) -> None:
        self.t = 1_000.0

    def __call__(self) -> float:
        self.t += 10.0
        return self.t


def _tracker(tmp_path: Path, phase: str = "plan") -> tuple[jpp.PlanTracker, dict, Path]:
    doc = {"pid": 1, "phase": phase, "phases": {}, "_t": 0.0}
    path = tmp_path / "JUDGE_SWEEP_PHASE.json"
    return jpp.PlanTracker(doc, path, clock=_Clock()), doc, path


def test_the_judges_own_lines_name_each_plan_step_and_its_counts(tmp_path) -> None:
    tr, doc, path = _tracker(tmp_path)
    tr.step("lane_and_docket")
    out = io.StringIO()
    tee = tr.tee(out)
    seen = []
    for ln in PLAN_LOG.splitlines(keepends=True):
        tee.write(ln)
        seen.append(doc["plan_step"])
    assert out.getvalue() == PLAN_LOG                    # the log itself is untouched
    assert seen[1:4] == ["docket_grouping", "gate0", "gate0"]
    assert "preflight" in seen and "cache_prune" in seen and "order" in seen
    assert seen[-4:] == ["prewarm", "prewarm", "plan_handoff", "dispatch"]
    assert doc["plan_counts"] == {"docket_rows": 1612345, "unique_cells": 1598000,
                                  "gate0_advance": 1200000, "prewarm_cells": 600000,
                                  "planned_cells": 600000}
    on_disk = json.loads(path.read_text("utf-8"))
    assert on_disk["plan_step"] == "dispatch" and "_t" not in on_disk
    assert set(on_disk["plan_steps"]) >= {"lane_and_docket", "gate0", "prewarm"}
    assert all(v > 0 for v in on_disk["plan_steps"].values())


def test_a_line_split_across_writes_is_still_one_marker(tmp_path) -> None:
    tr, doc, _ = _tracker(tmp_path)
    tee = tr.tee(io.StringIO())
    tee.write("Gate 0: 5 adv")
    assert doc.get("plan_step") is None
    tee.write("ance; 2 terminal reject\n")
    assert doc["plan_step"] == "preflight" and doc["plan_counts"]["gate0_advance"] == 5


def test_nothing_is_tracked_outside_the_plan_phase(tmp_path) -> None:
    tr, doc, path = _tracker(tmp_path, phase="build_shards")
    tee = tr.tee(io.StringIO())
    tee.write(PLAN_LOG)
    tr.progress("prewarm", warmed=1)
    assert "plan_step" not in doc and "plan_progress" not in doc and not path.exists()


def test_the_hook_reports_counts_and_is_throttled(tmp_path) -> None:
    now = [1_000.0]
    doc = {"phase": "plan"}
    path = tmp_path / "JUDGE_SWEEP_PHASE.json"
    tr = jpp.PlanTracker(doc, path, clock=lambda: now[0])
    tr.progress("prewarm", total=10, warmed=1, oldest_in_flight_s=3.5)   # a step change: written
    assert doc["plan_step"] == "prewarm"
    first = json.loads(path.read_text("utf-8"))["plan_progress"]
    assert first["warmed"] == 1 and first["total"] == 10 and first["step"] == "prewarm"
    now[0] += jpp.WRITE_EVERY_S / 2
    tr.progress("prewarm", total=10, warmed=2)                           # held in memory
    assert doc["plan_progress"]["warmed"] == 2
    assert json.loads(path.read_text("utf-8"))["plan_progress"]["warmed"] == 1
    now[0] += jpp.WRITE_EVERY_S
    tr.progress("prewarm", total=10, warmed=3)                           # written
    assert json.loads(path.read_text("utf-8"))["plan_progress"]["warmed"] == 3


def test_attach_only_where_the_sealed_image_declares_the_hook(tmp_path) -> None:
    tr, _, _ = _tracker(tmp_path)

    class Old:
        pass

    class New:
        PLAN_PROGRESS_HOOK = None

    assert tr.attach(Old) is False and not hasattr(Old, "PLAN_PROGRESS_HOOK")
    assert tr.attach(New) is True and New.PLAN_PROGRESS_HOOK == tr.progress


def test_a_broken_tracker_never_breaks_the_log(tmp_path) -> None:
    tr, _, _ = _tracker(tmp_path)

    def boom(_text: str) -> None:
        raise RuntimeError("report failure")

    tr.line = boom  # type: ignore[method-assign]
    out = io.StringIO()
    tee = tr.tee(out)
    assert tee.write("Gate 0: 1 advance; 0 terminal\n") == len("Gate 0: 1 advance; 0 terminal\n")
    assert out.getvalue().startswith("Gate 0:")


def test_the_launcher_wires_the_tee_and_the_hook() -> None:
    src = (Path(__file__).resolve().parents[1] / "scripts" / "run_sharded_gauntlet.py").read_text(
        "utf-8")
    assert "PlanTracker(_PHASE_DOC, SWEEP_PHASE)" in src
    assert "sys.stdout = sys.stderr = plan.tee(log)" in src
    assert "plan.attach(judge)" in src


# ------------------------------------------------------------- the sealed half (patch present)
eg = pytest.importorskip("scripts.external_gauntlet")
sealed = pytest.mark.skipif(not hasattr(eg, "PLAN_PROGRESS_HOOK"),
                            reason="judge_plan_phase sealed patch not applied")


@sealed
def test_gate0_reads_a_charts_presence_from_its_index_not_its_frame(tmp_path, monkeypatch):
    import pandas as pd

    idx = pd.date_range("2026-10-01", periods=50, freq="5min", tz="UTC")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx).to_parquet(
        tmp_path / "EURUSD_M5.parquet")
    monkeypatch.setattr(eg, "UNI", tmp_path)
    eg._LAST_DAY.clear()
    eg._FRAME_CACHE.clear()

    def no_frames(*_a, **_k):
        raise AssertionError("gate 0 loaded a whole frame for a chart on disk")

    monkeypatch.setattr(eg, "_bars_for", no_frames)
    assert eg._chart_present("EURUSD", "M5") is True
    # No parquet: the terminal route is asked exactly as before (here: nothing).
    monkeypatch.setattr(eg, "_bars_for", lambda *_a, **_k: None)
    assert eg._chart_present("EURUSD", "M15") is False
    eg._LAST_DAY.clear()


@sealed
def test_the_hook_is_report_only_and_swallows_its_own_failure(monkeypatch) -> None:
    got = []
    monkeypatch.setattr(eg, "PLAN_PROGRESS_HOOK", lambda step, **kw: got.append((step, kw)))
    eg._plan_progress("gate0", force=True, done=1, total=2)
    assert got == [("gate0", {"done": 1, "total": 2})]

    def boom(*_a, **_k):
        raise RuntimeError("hook failed")

    monkeypatch.setattr(eg, "PLAN_PROGRESS_HOOK", boom)
    eg._plan_progress("gate0", force=True, done=2, total=2)      # no raise
    monkeypatch.setattr(eg, "PLAN_PROGRESS_HOOK", None)
    eg._plan_progress("gate0", force=True)                      # no hook: a no-op


@sealed
def test_gate0_partition_is_unchanged_by_the_hook(monkeypatch) -> None:
    specs = [{"sym": "NOSUCH", "family": "carry", "params": {}},
             {"sym": "NOSUCH2", "family": "carry", "params": {"timeframe": "M5"}}]
    meta: dict = {}
    base = eg.partition_at_economic_prior([dict(s) for s in specs], meta)
    seen = []
    monkeypatch.setattr(eg, "PLAN_PROGRESS_HOOK", lambda step, **kw: seen.append(step))
    with_hook = eg.partition_at_economic_prior([dict(s) for s in specs], meta)
    assert with_hook == base and seen and set(seen) == {"gate0"}
