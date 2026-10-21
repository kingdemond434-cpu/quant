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
from scripts import judge_plan_progress as jpp

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
PRE-WARM: 15 worker(s) warmed 9000 cell(s) in 8100s (500000 already cached, 3 failed, 9 not)
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


def test_the_prewarm_pool_is_published_as_its_own_phase(tmp_path, monkeypatch) -> None:
    """Desk health 2026-10-21: the pool was 8,640 s of a 9,729 s "plan"; it is now phase prewarm,
    and the launcher's own phase clock times it."""
    from scripts import run_sharded_gauntlet as runner

    monkeypatch.setattr(runner, "SWEEP_PHASE", tmp_path / "JUDGE_SWEEP_PHASE.json")
    monkeypatch.setattr(runner, "_PHASE_DOC", {})
    clock = iter(float(t) for t in range(100, 10_000, 50))
    monkeypatch.setattr(runner.time, "time", lambda: next(clock))
    runner._phase("plan")
    tr = jpp.PlanTracker(runner._PHASE_DOC, runner.SWEEP_PHASE, on_phase=runner._phase,
                         clock=lambda: 0.0)
    tee = tr.tee(io.StringIO())
    tee.write(PLAN_LOG)
    runner._phase("build_shards")                  # what `_timed_dispatch` does next
    doc = json.loads(runner.SWEEP_PHASE.read_text("utf-8"))
    assert list(doc["phases"]) == ["plan", "prewarm", "plan_handoff"]
    assert doc["phase"] == "build_shards" and doc["plan_step"] == "dispatch"


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
    assert tr.attach(New) is True
    assert New.PLAN_PROGRESS_HOOK == tr.progress  # noqa: SIM300


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
    assert "PlanTracker(_PHASE_DOC, SWEEP_PHASE, on_phase=_phase)" in src
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


# ------------------------------------------- the pre-warm pool deals a chart's run to one worker
chunked = pytest.mark.skipif(not hasattr(eg, "PREWARM_CHUNK"),
                             reason="judge_plan_phase sealed patch not applied")


def _fake_warm_one(spec, meta):                      # module level: picklable for the pool
    import os as _os
    st = {"w": "WARMED", "h": "HIT", "f": "NOT_RUN_BUILD_FAILED"}[spec["params"]["k"][0]]
    return {"sym": spec["sym"], "family": spec["family"], "tf": "M5", "status": st,
            "why": "fake" if st.startswith("NOT_RUN") else "", "pid": _os.getpid()}


def _docket():
    kinds = "wwhwfwwhww" * 4
    return [{"sym": f"S{(i // 6) % 3}", "family": "fam",
             "params": {"timeframe": "M5", "k": f"{kinds[i]}{i}"}} for i in range(len(kinds))]


@chunked
@pytest.mark.parametrize("chunk", [1, 3, 8])
def test_the_chunked_pool_gives_every_cell_the_same_outcome(monkeypatch, chunk) -> None:
    import multiprocessing as mp
    if mp.get_start_method(allow_none=True) not in (None, "fork") or sys.platform == "win32":
        pytest.skip("the fake worker is installed by fork")
    monkeypatch.setattr(eg, "_warm_one", _fake_warm_one)
    monkeypatch.setattr(eg, "WORKERS", 2)
    monkeypatch.setattr(eg, "PREWARM_CHUNK", 1)
    base = eg._prewarm_cache(_docket(), {}, __import__("time").time() + 600)
    monkeypatch.setattr(eg, "PREWARM_CHUNK", chunk)
    got = eg._prewarm_cache(_docket(), {}, __import__("time").time() + 600)
    for k in ("submitted", "warmed", "hit", "failed", "unreached", "failures",
              "failure_reasons", "built_symbols", "failed_cells"):
        assert got[k] == base[k], k
    assert got["submitted"] == len(_docket()) and got["unreached"] == 0


@chunked
def test_a_run_never_crosses_a_chart_or_the_chunk_size() -> None:
    specs = _docket()
    runs: list[list] = []
    for sp in specs:                                   # the rule `_submit_next` applies
        if runs and len(runs[-1]) < eg.PREWARM_CHUNK and eg._chart_of(runs[-1][0]) == \
                eg._chart_of(sp):
            runs[-1].append(sp)
        else:
            runs.append([sp])
    assert [sp for r in runs for sp in r] == specs     # order kept, nothing dropped
    assert all(len({eg._chart_of(s) for s in r}) == 1 for r in runs)


@chunked
def test_a_run_starts_no_cell_after_the_deadline(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(eg, "_warm_one", lambda sp, meta: calls.append(sp) or {"status": "HIT"})
    rows = eg._warm_run(_docket()[:3], {}, deadline=0.0)
    assert calls == [] and [r["status"] for r in rows] == ["UNREACHED"] * 3
    rows = eg._warm_run(_docket()[:3], {}, deadline=__import__("time").time() + 600)
    assert len(calls) == 3 and [r["status"] for r in rows] == ["HIT"] * 3


# ------------------------------------------- next seal rotation: an unreadable chart (sealed)
#: v2.1 (audit of 602887dc): a resource fault raises, and the label names WHICH input failed.
unreadable = pytest.mark.skipif(
    not hasattr(eg, "_unreadable_chart")
    or "sym" not in __import__("inspect").signature(getattr(eg, "_unreadable_why", len)).parameters,
    reason="judge_plan_phase next-rotation v2.1 patch not applied")


def _body_corrupt_parquet(path: Path) -> Path:
    """A chart whose INDEX column reads and whose body does not: the case `_chart_present` and
    `_cell_last_day` (index-only) call present and `pd.read_parquet` refuses."""
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq

    idx = pd.date_range("2026-01-01", periods=5000, freq="5min", tz="UTC")
    pd.DataFrame({"open": np.linspace(1, 2, 5000), "close": np.linspace(2, 3, 5000)},
                 index=idx).to_parquet(path)
    rg = pq.ParquetFile(path).metadata.row_group(0)
    col = next(rg.column(i) for i in range(rg.num_columns)
               if rg.column(i).path_in_schema == "close")
    start = col.dictionary_page_offset or col.data_page_offset
    raw = bytearray(path.read_bytes())
    raw[start:start + col.total_compressed_size] = b"\xff" * col.total_compressed_size
    path.write_bytes(bytes(raw))
    return path


def _good_parquet(path: Path) -> Path:
    import pandas as pd

    idx = pd.date_range("2026-01-01", periods=500, freq="5min", tz="UTC")
    pd.DataFrame({"close": range(500)}, index=idx).to_parquet(path)
    return path


def _specs():
    return [{"sym": "BAD", "family": "fam", "params": {"timeframe": "M5", "k": 1}},
            {"sym": "OK", "family": "fam", "params": {"timeframe": "M5", "k": 2}}]


@pytest.fixture
def uni(tmp_path, monkeypatch):
    import pandas as pd

    _body_corrupt_parquet(tmp_path / "BAD_M5.parquet")
    _good_parquet(tmp_path / "OK_M5.parquet")
    monkeypatch.setattr(eg, "UNI", tmp_path)
    monkeypatch.setattr(eg, "_LAST_DAY", {})
    monkeypatch.setattr(eg, "_FRAME_CACHE", eg.OrderedDict())
    monkeypatch.setattr(eg, "_cell_last_day", lambda s, tf="H1": pd.Timestamp("2026-10-20"))
    monkeypatch.setattr(eg, "cache_load", lambda key: None)
    monkeypatch.setattr(eg, "_cache_key", lambda *a, **k: "key")   # no replay identity read
    monkeypatch.setattr(eg, "_rss_mb", lambda: 0.0)
    return tmp_path


def _build(specs):
    blocked: list = []
    out = eg._build_specs(specs, {}, __import__("time").time(), {}, {}, set(), blocked)
    return out, blocked


@unreadable
def test_a_body_corrupt_chart_reads_present_and_its_read_is_named_unreadable(
        tmp_path, monkeypatch) -> None:
    _body_corrupt_parquet(tmp_path / "BAD_M5.parquet")
    monkeypatch.setattr(eg, "UNI", tmp_path)
    monkeypatch.setattr(eg, "_LAST_DAY", {})
    monkeypatch.setattr(eg, "_FRAME_CACHE", eg.OrderedDict())
    assert eg._chart_present("BAD", "M5") and eg._cell_last_day("BAD", "M5") is not None
    with pytest.raises(Exception) as caught:
        eg._bars_for("BAD", "M5")
    assert eg._unreadable_chart(caught.value)
    assert not eg._unreadable_chart(KeyError("a code defect"))


@unreadable
def test_a_resource_fault_is_never_filed_as_data() -> None:
    import pyarrow as pa

    assert not eg._unreadable_chart(MemoryError())
    assert not eg._unreadable_chart(pa.ArrowMemoryError("oom"))
    assert not eg._unreadable_chart(PermissionError(13, "locked", "X_M5.parquet"))


@unreadable
@pytest.mark.parametrize("fault", [MemoryError("oom"), PermissionError(13, "locked")])
def test_an_oom_or_a_locked_file_raises_out_of_the_build(uni, monkeypatch, fault) -> None:
    def build(sym, family, params, meta):
        raise fault

    monkeypatch.setattr(eg, "build_cell", build)
    with pytest.raises(type(fault)):
        _build(_specs())
    # the pool's worker turns any raise into ERROR -- never a terminal verdict, so the spec stays
    # in the docket and the shard builds it again; what it must NOT be is a BUILD_FAILED park
    assert eg._warm_one(_specs()[0], {})["status"] == "ERROR"


@unreadable
def test_one_unreadable_chart_blocks_its_own_cell_and_the_build_goes_on(uni, monkeypatch) -> None:
    def build(sym, family, params, meta):
        if sym == "BAD":
            return eg._bars_for(sym, "M5")             # the real read: OSError from thrift
        return None                                   # an ordinary build failure, named after

    monkeypatch.setattr(eg, "build_cell", build)
    out, blocked = _build(_specs())
    assert [b["sym"] for b in blocked] == ["BAD", "OK"], "the shard went on past the bad file"
    assert blocked[0]["downstream_status"] == "NOT_RUN_BUILD_FAILED"
    assert blocked[0]["why"].startswith("UNREADABLE_CHART: the M5 parquet BAD_M5.parquet")
    assert not blocked[1]["why"].startswith("UNREADABLE")
    assert out["cell_objs"] == [] and out["built_fresh"] == 0

    def defect(sym, family, params, meta):
        raise KeyError("a code defect is never filed as data")

    monkeypatch.setattr(eg, "build_cell", defect)
    with pytest.raises(KeyError):
        _build(_specs())


@unreadable
def test_another_inputs_failure_is_never_labelled_as_this_charts_body(uni, monkeypatch) -> None:
    """OK's own chart reads whole: an OSError from inside its build was some OTHER input."""
    monkeypatch.setattr(eg, "build_cell",
                        lambda *a: (_ for _ in ()).throw(OSError("peer chart refused")))
    _out, blocked = _build(_specs()[1:])
    assert blocked[0]["why"].startswith("UNREADABLE_INPUT: the M5 chart reads whole")
    missing = FileNotFoundError(2, "No such file", "data/cot/EUR.csv")
    monkeypatch.setattr(eg, "build_cell", lambda *a: (_ for _ in ()).throw(missing))
    _out, blocked = _build(_specs()[1:])
    assert blocked[0]["why"].startswith("INPUT_MISSING: data/cot/EUR.csv")


@unreadable
def test_the_pool_gives_an_unreadable_chart_the_loops_own_verdict(uni, monkeypatch) -> None:
    monkeypatch.setattr(eg, "build_cell", lambda *a: (_ for _ in ()).throw(OSError("torn")))
    got = eg._warm_one(_specs()[0], {})
    assert got["status"] == "NOT_RUN_BUILD_FAILED"
    assert got["why"].startswith("UNREADABLE_CHART")
    blocked: list = []
    kept = eg._apply_prewarm_failures(_specs()[:1], {eg._spec_key(_specs()[0]): got}, blocked)
    assert kept == [] and blocked[0]["why"] == got["why"]
    monkeypatch.setattr(eg, "build_cell", lambda *a: (_ for _ in ()).throw(KeyError("bug")))
    assert eg._warm_one(_specs()[0], {})["status"] == "ERROR"   # unchanged for a defect


# ------------------------------- next seal rotation v2.2: transient faults and an absent chart
#: v2.2 (audit of 25d1fd22): a timeout or a dropped connection is a passing fault, never data,
#: and a chart gone since the plan read it is INPUT_MISSING, never re-read into UNREADABLE_CHART.
unreadable_v22 = pytest.mark.skipif(
    not hasattr(eg, "_unreadable_why")
    or "pq.exists()" not in __import__("inspect").getsource(eg._unreadable_why),
    reason="judge_plan_phase next-rotation v2.2 patch not applied")


@unreadable_v22
@pytest.mark.parametrize("fault", [TimeoutError("share timed out"),
                                   ConnectionError("mount dropped"),
                                   ConnectionResetError(104, "reset")])
def test_a_transient_fault_is_never_filed_as_data(uni, monkeypatch, fault) -> None:
    assert not eg._unreadable_chart(fault)

    def build(sym, family, params, meta):
        raise fault

    monkeypatch.setattr(eg, "build_cell", build)
    with pytest.raises(type(fault)):
        _build(_specs())
    assert eg._warm_one(_specs()[0], {})["status"] == "ERROR", "transient: not terminal"


@unreadable_v22
def test_a_chart_gone_since_the_plan_is_input_missing_not_unreadable(uni, monkeypatch) -> None:
    (uni / "OK_M5.parquet").unlink()
    why = eg._unreadable_why("OK", "M5", OSError("torn read"))
    assert why.startswith("INPUT_MISSING: the M5 chart OK_M5.parquet is absent"), why
    monkeypatch.setattr(eg, "build_cell",
                        lambda *a: (_ for _ in ()).throw(OSError("torn read")))
    _out, blocked = _build(_specs()[1:])
    assert blocked[0]["why"].startswith("INPUT_MISSING: the M5 chart")


def test_a_flush_that_meets_a_concurrent_change_is_skipped_never_raised(tmp_path) -> None:
    """Audit of a971d83da, should-fix 2: `flush` walks the launcher's `_PHASE_DOC` without
    `_PHASE_LOCK`, and a dispatch thread changing it mid-walk raises RuntimeError ("dictionary
    changed size during iteration"). The stamp is a report: it is skipped, never raised."""
    class _Changing(dict):
        def items(self):  # type: ignore[override]
            raise RuntimeError("dictionary changed size during iteration")

    path = tmp_path / "JUDGE_SWEEP_PHASE.json"
    tr = jpp.PlanTracker(_Changing(pid=1, phase="plan", phases={}), path, clock=_Clock())
    tr.flush(force=True)                         # raised RuntimeError before the fix
    tr.step("lane_and_docket")                   # and through step's own forced flush
    assert not path.exists(), "nothing half-written: the next flush writes the stamp"
    assert not list(tmp_path.glob("*.tmp")), "and no tmp is left behind"
