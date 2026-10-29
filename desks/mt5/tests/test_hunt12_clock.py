"""The growth sizer refused on every pass for want of an input nothing produced.

`pf_allocator` solves posterior E[log W] for the per-sleeve heat every sleeve on this desk should
risk. `data/PF_ALLOCATOR_ARMED` has been present since 2026-09-04, the hourly cycle carries a
`pf_allocator` leg, `decision_core.allocator_heat` reads its artifact and
`promoted_lot(from_book=True)` sizes from its fractions -- and `reports/pf_allocation.json` HAS
NEVER EXISTED. Measured 2026-09-10 on a checkout of the same code the box runs:

    $ python desks/mt5/research/pf_allocator.py --mode normal
    [..] assembling evidence (backtest daily-R over gold book + hunt survivors)
    REFUSING to project a portfolio without .../reports/hunt12_partial.json
    exit 1

The allocator assembles evidence through `portfolio_projection`, which refuses without the hunt12
survivor report. That report had exactly ONE scheduler -- `research_supervisor`, keyed on a
one-shot `reports/DONE_hunt12` marker, on the worker the cycle's own comments record as dead or
stalled. One-shot means produced once ever, or never; it was never. So "the allocator is armed and
wired" was true and worthless at the same time, and every sleeve fell back to `ramped_fraction`:
the authority ramp, a count of closed trades that contains no estimate of growth at all.

WHAT THESE TESTS PIN, and why each is a defect this fix could reintroduce:

    THE SWEEP IS ROUTED BY LANE. The principal's 2026-09-06 standing order says single-name
    equities are never hunted for statistical hypotheses. Routing is also what lets the sweep hold
    a clock at all: 251 symbols do not fit an hourly budget and 145 do, which is why it was
    one-shot in the first place.

    E_MAX IS SIZED TO THE ROUTED GRID, NOT SHRUNK TO FIND SURVIVORS. The correction must count
    the cells actually looked at -- this module's own stated rule -- and 4,016 -> 2,320 moves the
    bar by 0.145 of a t. The test pins the direction AND that the move is small, because a large
    move would mean somebody had reached for the denominator to manufacture passes.

    AN UNFINISHED SWEEP IS REFUSED, NOT LOADED. A resumable sweep read by a portfolio builder is
    the GOLD-ONLY truncation wearing a new hat: 85 symbols of 145 loaded as the whole book is the
    same defect with a different number of sleeves in it.

    AND A REPORT FROM BEFORE `complete` EXISTED IS STILL ACCEPTED. Refusing on a missing key would
    reject every artifact already on the box -- a regression dressed as a safety check.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import run_hunt12 as h12  # noqa: E402
from research import universe_policy  # noqa: E402

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- routing


def test_the_sweep_is_routed_by_lane_and_names_what_it_set_aside():
    """A cell that vanishes between the universe and the sweep is indistinguishable from one
    that was tested and failed."""
    meta = {"EURUSD": {}, "XAUUSD": {}, "Apple": {}, "3M": {}, "NOTREAL": {}}
    routed, split = h12.routed_universe(meta)
    assert "EURUSD" in routed
    assert "Apple" not in routed and "3M" not in routed
    assert split[universe_policy.EVENT], "the split does not name the event-lane symbols"
    assert "NOTREAL" in split[universe_policy.UNCLASSIFIED]
    assert "NOTREAL" not in routed, "an unregistered string reached hypothesis discovery"


def test_routing_is_the_mandate_and_not_a_speed_trick_on_the_real_registry():
    """145 of 251 today. If this ever routes everything, the order has been quietly undone."""
    meta = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    routed, split = h12.routed_universe(meta)
    assert 0 < len(routed) < len(meta), "the whole registry reached the hypothesis lane"
    assert len(split[universe_policy.EVENT]) > 50, "no equities were set aside"


# --------------------------------------------------------------- the multiplicity denominator


def test_e_max_is_sized_to_the_routed_grid_and_the_move_is_small():
    """THE DIRECTION AND THE MAGNITUDE BOTH MATTER. Counting cells nobody looks at charges every
    FX and metals cell for equity columns that should never have been tested -- but a correction
    that fell a long way would mean the denominator had been reached for to manufacture passes.
    Measured: 4,016 cells -> 2,320, E[max t] 3.621 -> 3.476."""
    from mt5desk.multiplicity import deflation, sweep_size

    full = deflation(sweep_size(251, len(h12.WINDOWS), len(h12.STATES)))
    routed = deflation(sweep_size(145, len(h12.WINDOWS), len(h12.STATES)))
    assert routed < full, "routing did not reduce the grid it corrects for"
    assert full - routed < 0.25, (
        f"E_MAX fell by {full - routed:.3f}; a move that size is not a repaired denominator")


def test_the_gate_itself_is_untouched():
    """Cheaper multiplicity is not a lower bar. `defl > 2` and every other threshold stand."""
    src = (_DESK / "research" / "run_hunt12.py").read_text("utf-8")
    assert "defl > 2" in src
    assert 'r["profit_factor"] > 1.05' in src
    assert 'r["max_dd_r"] > -30' in src
    assert 'r2["t_stat"] > 1.5' in src


# --------------------------------------------------------------------------- resume


def _partial(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "hunt12_partial.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_an_absent_sweep_starts_fresh(tmp_path):
    done, results, why = h12._carried(tmp_path / "nope.json", ["EURUSD"], NOW, 168.0)
    assert (done, results) == ([], [])
    assert "no carried sweep" in why


def test_a_sweep_from_before_routing_is_not_merged_into_a_routed_one(tmp_path):
    """Its cells were judged at the unrouted E_MAX. Carrying them forward produces one artifact
    holding two different multiplicity corrections, which is worse than either."""
    p = _partial(tmp_path, {"done": ["EURUSD"], "all": [{"sym": "EURUSD"}],
                            "started_at": NOW.isoformat()})
    done, results, why = h12._carried(p, ["EURUSD"], NOW, 168.0)
    assert done == [] and results == []
    assert "predates lane routing" in why


def test_a_routed_sweep_resumes_where_it_stopped(tmp_path):
    p = _partial(tmp_path, {"done": ["EURUSD"], "all": [{"sym": "EURUSD", "gate": False}],
                            "routed": ["EURUSD", "AUDCAD"], "started_at": NOW.isoformat()})
    done, results, why = h12._carried(p, ["EURUSD", "AUDCAD"], NOW, 168.0)
    assert done == ["EURUSD"] and len(results) == 1
    assert "resumed at 1/2" in why


def test_a_stale_sweep_restarts_rather_than_resuming(tmp_path):
    old = (NOW - timedelta(hours=200)).isoformat()
    p = _partial(tmp_path, {"done": ["EURUSD"], "all": [], "routed": ["EURUSD"],
                            "started_at": old})
    done, _, why = h12._carried(p, ["EURUSD"], NOW, 168.0)
    assert done == [] and "200h old" in why


def test_a_changed_universe_restarts_rather_than_resuming(tmp_path):
    p = _partial(tmp_path, {"done": ["EURUSD"], "all": [], "routed": ["EURUSD"],
                            "started_at": NOW.isoformat()})
    done, _, why = h12._carried(p, ["EURUSD", "AUDCAD"], NOW, 168.0)
    assert done == [] and "routed universe changed" in why


def test_an_unreadable_sweep_is_a_fresh_start_never_a_silent_empty_book(tmp_path):
    p = tmp_path / "hunt12_partial.json"
    p.write_text("{ truncated", encoding="utf-8")
    done, results, why = h12._carried(p, ["EURUSD"], NOW, 168.0)
    assert (done, results) == ([], []) and "unreadable" in why


def test_the_artifact_is_replaced_never_truncated_in_place(tmp_path):
    """The sweep is stopped by a deadline between symbols now, so an interrupted write is a
    routine event. A half-written report reaches the loader as a JSONDecodeError from inside a
    portfolio builder -- the one shape the careful refusal there exists to prevent."""
    p = tmp_path / "a.json"
    h12._write_atomic(p, {"x": 1})
    assert json.loads(p.read_text("utf-8")) == {"x": 1}
    assert not list(tmp_path.glob("*.tmp")), "the temp file was left behind"


# --------------------------------------------------------------- the loader's refusals


def _projection():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_pp_hunt12_clock", _DESK / "research" / "portfolio_projection.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_PP = _projection()


def _reports(tmp_path: Path, monkeypatch, doc) -> None:
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    body = doc if isinstance(doc, str) else json.dumps(doc)
    (tmp_path / "reports" / "hunt12_partial.json").write_text(body, encoding="utf-8")
    monkeypatch.setattr(_PP, "BASE", tmp_path)


def test_an_unfinished_sweep_is_refused_and_the_refusal_says_how_far_it_got(
        tmp_path, monkeypatch):
    _reports(tmp_path, monkeypatch,
             {"complete": False, "done": ["A"] * 85, "n_routed": 145,
              "all": [{"gate": True, "sym": "A"}], "resume": "resumed at 85/145"})
    with pytest.raises(SystemExit) as e:
        _PP.load_h12_survivors()
    msg = str(e.value)
    assert "REFUSING" in msg and "85 of 145" in msg
    assert "resumes on the next hourly pass" in msg, (
        "the refusal does not say it heals itself, so a reader will go fix it by hand")


def test_a_finished_sweep_loads_its_survivors(tmp_path, monkeypatch):
    _reports(tmp_path, monkeypatch,
             {"complete": True, "done": ["A"], "n_routed": 1,
              "all": [{"gate": True, "sym": "A"}, {"gate": False, "sym": "B"}]})
    got = _PP.load_h12_survivors()
    assert [c["sym"] for c in got] == ["A"]


def test_a_report_from_before_complete_existed_is_still_accepted(tmp_path, monkeypatch):
    """Refusing on a MISSING key rejects every artifact already on the box. Only an explicit
    False is an unfinished sweep."""
    _reports(tmp_path, monkeypatch, {"done": ["A"], "all": [{"gate": True, "sym": "A"}]})
    assert [c["sym"] for c in _PP.load_h12_survivors()] == ["A"]


def test_a_corrupt_report_is_a_refusal_not_a_traceback(tmp_path, monkeypatch):
    _reports(tmp_path, monkeypatch, "{ truncated")
    with pytest.raises(SystemExit) as e:
        _PP.load_h12_survivors()
    assert "unreadable" in str(e.value)


def _complete_snapshot(tmp_path, monkeypatch, **changes):
    _reports(tmp_path, monkeypatch,
             {"complete": False, "done": ["EURUSD"], "n_routed": 2,
              "all": [{"gate": True, "sym": "EURUSD", "partial_only": True}]})
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text(
        json.dumps({"EURUSD": {}, "XAUUSD": {}}), "utf-8")
    doc = {"complete": True, "done": ["EURUSD", "XAUUSD"],
           "routed": ["EURUSD", "XAUUSD"], "n_routed": 2,
           "started_at": (datetime.now(UTC) - timedelta(hours=12)).isoformat(),
           "swept_at": datetime.now(UTC).isoformat(),
           "all": [{"gate": True, "sym": "XAUUSD"},
                   {"gate": False, "sym": "EURUSD"}]}
    doc.update(changes)
    p = tmp_path / "reports" / "hunt12.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


@pytest.mark.parametrize("partial", ["incomplete", "absent", "corrupt"])
def test_refresh_keeps_the_verified_complete_book(tmp_path, monkeypatch, partial):
    _complete_snapshot(tmp_path, monkeypatch)
    p = tmp_path / "reports" / "hunt12_partial.json"
    if partial == "absent":
        p.unlink()
    elif partial == "corrupt":
        p.write_text("{ interrupted", "utf-8")
    before = p.read_bytes() if p.exists() else None
    assert [row["sym"] for row in _PP.load_h12_survivors()] == ["XAUUSD"]
    assert (p.read_bytes() if p.exists() else None) == before


@pytest.mark.parametrize("changes", [
    {"started_at": (datetime.now(UTC) - timedelta(days=8)).isoformat()},
    {"started_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    {"started_at": None},
    {"complete": False},
    {"done": ["EURUSD", "EURUSD"]},
    {"routed": ["EURUSD", "USDJPY"]},
    {"n_routed": 1},
    {"all": [{"sym": "USDJPY", "gate": True}]},
])
def test_publication_time_never_rescues_invalid_completed_evidence(
        tmp_path, monkeypatch, changes):
    _complete_snapshot(tmp_path, monkeypatch, **changes)
    with pytest.raises(SystemExit, match="unfinished sweep"):
        _PP.load_h12_survivors()


def test_legacy_full_report_cannot_claim_a_fresh_evaluation_age(tmp_path, monkeypatch):
    p = _complete_snapshot(tmp_path, monkeypatch)
    doc = json.loads(p.read_text("utf-8"))
    del doc["started_at"]
    p.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(SystemExit, match="unfinished sweep"):
        _PP.load_h12_survivors()


def test_completed_publication_preserves_evaluation_age_on_no_work_pass(tmp_path, monkeypatch):
    uni = tmp_path / "data" / "universe"
    uni.mkdir(parents=True)
    (uni / "universe.json").write_text(json.dumps({"EURUSD": {}}), "utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    started = (datetime.now(UTC) - timedelta(hours=12)).isoformat()
    (reports / "hunt12_partial.json").write_text(json.dumps({
        "started_at": started, "done": ["EURUSD"], "routed": ["EURUSD"],
        "all": [{"sym": "EURUSD", "gate": True}], "complete": True,
    }), "utf-8")
    monkeypatch.setattr(h12, "BASE", tmp_path)
    monkeypatch.setattr(h12, "UNI", uni)
    assert h12._run([]) == 0
    complete = json.loads((reports / "hunt12.json").read_text("utf-8"))
    assert complete["complete"] is True
    assert complete["started_at"] == started
    assert complete["done"] == complete["routed"] == ["EURUSD"]


def test_hunt12_overlapping_writer_cannot_enter_sweep(monkeypatch):
    from contextlib import contextmanager

    from research import job_lock

    @contextmanager
    def held(name, **kwargs):
        assert name == "hunt12"
        yield False

    monkeypatch.setattr(job_lock, "exclusive_job", held)
    monkeypatch.setattr(h12, "_run", lambda args: pytest.fail("entered occupied sweep"))
    assert h12.main([]) == 0


# --------------------------------------------------------------- the hourly clock


@pytest.fixture()
def cycle():
    return pytest.importorskip("research.hourly_cycle")


def test_the_leg_runs_when_the_report_is_absent(cycle, tmp_path):
    run, why = cycle._hunt12_state(tmp_path / "nope.json", NOW)
    assert run and "absent" in why
    assert "allocator refuses" in why, "the reason does not name what the absence costs"


def test_the_leg_runs_when_the_sweep_is_unfinished(cycle, tmp_path):
    p = _partial(tmp_path, {"complete": False, "done": ["A"] * 30, "n_routed": 145,
                            "started_at": NOW.isoformat()})
    run, why = cycle._hunt12_state(p, NOW)
    assert run and "30 of 145" in why


def test_the_leg_runs_when_the_sweep_is_a_week_old(cycle, tmp_path):
    p = _partial(tmp_path, {"complete": True, "done": ["A"], "n_routed": 1,
                            "started_at": (NOW - timedelta(hours=200)).isoformat()})
    run, why = cycle._hunt12_state(p, NOW)
    assert run and "200h old" in why


def test_refresh_begins_while_the_last_complete_sweep_is_still_valid(cycle, tmp_path):
    p = _partial(tmp_path, {"complete": True,
                            "started_at": (NOW - timedelta(days=6)).isoformat()})
    run, why = cycle._hunt12_state(p, NOW)
    assert run and "refresh 120h; evidence expiry 168h" in why
    assert cycle.HUNT12_MAX_AGE_S - cycle.HUNT12_REFRESH_AGE_S == 48 * 3600


def test_refresh_threshold_reaches_the_producer_and_honors_hold(cycle, tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "BASE", tmp_path)
    monkeypatch.setattr(cycle, "_hunt12_state", lambda: (True, "refresh due"))
    calls = []
    monkeypatch.setattr(cycle, "_producer", lambda *args: calls.append(args) or {"status": "OK"})
    assert cycle.hunt12()["status"] == "OK"
    assert calls[0][-2:] == ("--max-age-h", "120.0")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "HOLD_hunt12").touch()
    assert cycle.hunt12()["status"] == "SKIPPED"
    assert len(calls) == 1


def test_future_complete_sweep_requires_repair(cycle, tmp_path):
    p = _partial(tmp_path, {"complete": True,
                            "started_at": (NOW + timedelta(hours=1)).isoformat()})
    run, why = cycle._hunt12_state(p, NOW)
    assert run and "future timestamp" in why


@pytest.fixture()
def resident(cycle, tmp_path, monkeypatch):
    import psutil
    from types import SimpleNamespace

    monkeypatch.setattr(cycle, "BASE", tmp_path)
    monkeypatch.setattr(cycle.time, "time", lambda: 1000)
    (tmp_path / "data").mkdir()

    class Process:
        pid = 42
        info = {"cmdline": ["pythonw.exe", "research/run_hunt12.py"]}
        state = psutil.STATUS_STOPPED
        started = 0
        cpu = 0
        child = []
        files = []
        resumes = 0

        def cwd(self):
            return str(tmp_path)

        def status(self):
            return self.state

        def cpu_times(self):
            return SimpleNamespace(user=self.cpu, system=0)

        def create_time(self):
            return self.started

        def children(self):
            return self.child

        def open_files(self):
            return self.files

        def resume(self):
            self.resumes += 1
            self.state = psutil.STATUS_RUNNING

    proc = Process()
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([proc]))
    return proc


def test_unused_stopped_canonical_writer_is_resumed_without_a_second_writer(cycle, resident):
    receipt = cycle._hunt12_resident_health()
    assert receipt["alive"] and receipt["resumed"] and receipt["pid"] == 42
    assert resident.resumes == 1


@pytest.mark.parametrize("reason", ["hold", "cpu", "child", "file", "recent", "other_cwd"])
def test_stopped_worker_with_existing_ownership_or_hold_is_preserved(
        cycle, resident, tmp_path, reason, monkeypatch):
    if reason == "hold":
        (tmp_path / "data" / "HOLD_hunt12").touch()
    elif reason == "cpu":
        resident.cpu = 0.01
    elif reason == "child":
        resident.child = [object()]
    elif reason == "file":
        resident.files = [object()]
    elif reason == "recent":
        resident.started = 900
    else:
        monkeypatch.setattr(resident, "cwd", lambda: str(tmp_path.parent))
    receipt = cycle._hunt12_resident_health()
    assert receipt["alive"] is not True
    assert resident.resumes == 0


def test_ambiguous_residents_and_denied_status_never_resume(cycle, resident, monkeypatch):
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([resident, resident]))
    assert cycle._hunt12_resident_health()["resident_count"] == 2
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([resident]))

    def denied():
        raise psutil.AccessDenied(resident.pid)

    monkeypatch.setattr(resident, "status", denied)
    assert cycle._hunt12_resident_health()["alive"] is None
    assert resident.resumes == 0


def test_health_does_not_duplicate_a_stopped_writer(cycle, resident, monkeypatch):
    import psutil

    resident.cpu = 1
    resident.state = psutil.STATUS_STOPPED
    monkeypatch.setattr(cycle, "EXPECTED", {"hunt12": ("pythonw.exe", "run_hunt12.py")})
    monkeypatch.setattr(cycle, "procs", lambda: "run_hunt12.py")
    monkeypatch.setattr(cycle, "_cmd_lines", lambda: "")
    monkeypatch.setattr(cycle, "start", lambda script: pytest.fail("duplicate writer launched"))
    assert cycle.health()["hunt12"]["alive"] is False


def test_health_does_not_start_an_absent_held_writer(cycle, tmp_path, monkeypatch):
    monkeypatch.setattr(cycle, "BASE", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "HOLD_hunt12").touch()
    monkeypatch.setattr(cycle, "EXPECTED", {"hunt12": ("pythonw.exe", "run_hunt12.py")})
    monkeypatch.setattr(cycle, "procs", lambda: "")
    monkeypatch.setattr(cycle, "_cmd_lines", lambda: "")
    monkeypatch.setattr(cycle, "start", lambda script: pytest.fail("held writer launched"))
    assert "no launch attempted" in cycle.health()["hunt12"]["note"]


def test_a_fresh_complete_sweep_is_skipped_with_a_reason(cycle, tmp_path):
    """A leg that reports SKIPPED with a reason is not an idle leg (III.16): the artifact it
    exists to keep current is current, and that is the measurement."""
    p = _partial(tmp_path, {"complete": True, "done": ["A"], "n_routed": 1,
                            "started_at": (NOW - timedelta(hours=3)).isoformat()})
    run, why = cycle._hunt12_state(p, NOW)
    assert not run and "complete and 3h old" in why


def test_the_leg_stops_inside_the_legs_own_budget(cycle):
    """It stops BETWEEN symbols. Being SIGKILLed by the leg timeout loses that symbol's work and
    can land mid-write, which is what makes a resume untrustworthy."""
    assert cycle.HUNT12_DEADLINE_S < cycle.SEARCH_BUDGET_SEC
    assert cycle.SEARCH_BUDGET_SEC - cycle.HUNT12_DEADLINE_S >= 30


def test_the_sweep_runs_before_the_allocator_that_needs_it(cycle):
    """Ordering is the whole point: an allocator solving before its input exists refuses, and
    the next hour it refuses again."""
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert src.index('_costed("hunt12"') < src.index('_costed("pf_allocator"'), (
        "hunt12 runs after the allocator that refuses without it")


def test_the_leg_reaches_the_cycles_report(cycle):
    """A leg absent from the report is a leg nobody can tell ran."""
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"hunt12": h12' in src
