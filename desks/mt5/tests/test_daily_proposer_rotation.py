"""No daily proposer can be silenced by another's runtime (2026-10-29).

MT5-Daily was terminated at its Task Scheduler limit (0x41306) inside the `proposers` step, which
ran eighteen proposers in one fixed order and was stamped only when it ended. Every later pass
began again at `plumbing_miner` and died early, so the tail (anomaly_factory, tail_alpha_search,
survivor_distiller, ...) never ran on any clock. These pin the structure that replaced it: one
bounded child per proposer, least-recently-started first, deferral (never a cut) when a proposer
does not fit the pass's deadline, progress published after every proposer, and a chain that
stops starting steps at its deadline instead of being killed by the task.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402

TODAY = "2026-10-29"


@pytest.fixture
def dc(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "PROPOSER_STATE", tmp_path / "state.json")
    monkeypatch.setattr(daily_cycle, "PROPOSER_REPORT", tmp_path / "report.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "_utc_today", lambda: TODAY)
    monkeypatch.setattr(daily_cycle, "_proposer_budget", lambda name: 300.0)
    monkeypatch.setitem(daily_cycle._DEADLINE, "seconds", None)
    monkeypatch.setitem(daily_cycle._DEADLINE, "t0", None)
    return tmp_path


def _state(dc) -> dict:
    return json.loads((dc / "state.json").read_text("utf-8"))


def test_the_order_is_least_recently_started_first_and_skips_the_finished():
    st = {"plumbing_miner": {"last_started_at": "2026-10-28T23:00:00+00:00"},
          "transition_alpha": {"last_started_at": "2026-10-27T23:00:00+00:00"},
          "anomaly_factory": {"done_day": TODAY}}
    order = daily_cycle.proposer_order(st, TODAY)
    assert "anomaly_factory" not in order
    # never-started proposers lead in declared order, then the oldest start, then the newest
    assert order[0] == "weak_signal_compiler"
    assert order[-2:] == ["transition_alpha", "plumbing_miner"]


def test_a_proposer_killed_at_its_bound_does_not_cost_the_others_their_run(dc, monkeypatch):
    ran: list[str] = []

    def fake(name, budget, bound):
        ran.append(name)
        return {"status": "KILLED_AT_BOUND" if name == "plumbing_miner" else "OK", "wall_s": 1}

    monkeypatch.setattr(daily_cycle, "_run_proposer", fake)
    daily_cycle._proposers()
    assert ran == list(daily_cycle.PROPOSERS)
    st = _state(dc)
    assert st["plumbing_miner"]["last_status"] == "KILLED_AT_BOUND"
    assert "done_day" not in st["plumbing_miner"]
    assert st["book_forensics"]["done_day"] == TODAY
    rep = json.loads((dc / "report.json").read_text("utf-8"))
    assert rep["killed"] == ["plumbing_miner"]
    assert len(rep["done"]) == len(daily_cycle.PROPOSERS) - 1


def test_the_tail_is_reached_even_when_the_first_proposer_always_hangs(dc, monkeypatch):
    """The 2026-10-28 shape: each pass gets room for ONE proposer, and plumbing_miner (first in
    the declared order) never finishes. The old loop restarted at plumbing_miner every pass, so
    the tail never ran. Now every proposer is started within len(PROPOSERS) passes."""
    started: list[str] = []
    clock = {"t": 0.0}
    monkeypatch.setattr(daily_cycle.time, "monotonic", lambda: clock["t"])

    def one_then_out(name, budget, bound):
        started.append(name)
        clock["t"] += 10_000.0          # the pass's whole deadline spent on this one
        return {"status": "KILLED_AT_BOUND" if name == "plumbing_miner" else "OK", "wall_s": 1}

    monkeypatch.setattr(daily_cycle, "_run_proposer", one_then_out)
    for day in range(1, len(daily_cycle.PROPOSERS) + 1):
        monkeypatch.setattr(daily_cycle, "_utc_today", lambda d=day: f"2026-11-{d:02d}")
        clock["t"] = 0.0
        daily_cycle._DEADLINE.update({"t0": 0.0, "seconds": 1000.0, "basis": "test"})
        daily_cycle._proposers()
    assert set(started) == set(daily_cycle.PROPOSERS)
    assert started.count("plumbing_miner") == 1


def test_a_proposer_that_does_not_fit_is_deferred_not_started(dc, monkeypatch):
    ran: list[str] = []
    monkeypatch.setattr(daily_cycle, "_run_proposer",
                        lambda n, b, bd: ran.append(n) or {"status": "OK", "wall_s": 1})
    daily_cycle._DEADLINE.update({"t0": daily_cycle.time.monotonic(), "seconds": 100.0,
                                  "basis": "test"})
    daily_cycle._proposers()            # bound of a 300 s proposer is 600 s > 100 s left
    assert ran == []
    st = _state(dc)
    assert all("last_started_at" not in st[n] for n in daily_cycle.PROPOSERS)
    rep = json.loads((dc / "report.json").read_text("utf-8"))
    assert len(rep["deferred"]) == len(daily_cycle.PROPOSERS)
    # the budget handed over is unchanged; only the start was deferred
    assert rep["proposers"]["plumbing_miner"]["bound_s"] == 600


def test_budgets_are_not_cut_and_the_bound_sits_above_them():
    assert daily_cycle.proposer_bound(300.0) == 600.0
    assert daily_cycle.proposer_bound(3600.0) == 5400.0
    assert daily_cycle.proposer_bound(None, {"last_ok_wall_s": 8000}) == 12000.0
    assert daily_cycle.proposer_bound(None) == daily_cycle.UNBUDGETED_BOUND_S


def test_the_deadline_comes_from_the_caller(monkeypatch):
    monkeypatch.delenv("DAILY_CYCLE_DEADLINE_S", raising=False)
    monkeypatch.setenv("HOURLY_PLAN", "dept:forward")
    monkeypatch.setenv("DAILY_CYCLE_HOURLY_BUDGET_SEC", "900")
    assert daily_cycle._resolve_deadline() == (840.0, "hourly daily leg budget")
    monkeypatch.setenv("DAILY_CYCLE_DEADLINE_S", "7200")
    assert daily_cycle._resolve_deadline()[0] == 7200.0
    monkeypatch.delenv("DAILY_CYCLE_DEADLINE_S")
    monkeypatch.delenv("HOURLY_PLAN")
    monkeypatch.setattr(daily_cycle, "_task_limit_s", lambda task="MT5-Daily": 10800.0)
    secs, basis = daily_cycle._resolve_deadline()
    assert secs == 10800.0 - 900.0 and "ExecutionTimeLimit" in basis


def test_iso_durations():
    assert daily_cycle.parse_iso_duration("PT72H") == 259200.0
    assert daily_cycle.parse_iso_duration("P1DT2H30M") == 95400.0
    assert daily_cycle.parse_iso_duration("PT0S") is None
    assert daily_cycle.parse_iso_duration("") is None


def test_the_chain_stops_starting_steps_at_its_deadline_and_resumes(dc, monkeypatch):
    calls: list[str] = []
    steps = tuple((n, (lambda n=n: calls.append(n))) for n in ("a", "b", "c"))
    monkeypatch.setattr(daily_cycle, "STEPS", steps)
    clock = {"t": 0.0}
    monkeypatch.setattr(daily_cycle.time, "monotonic", lambda: clock["t"])

    def step_a():
        calls.append("a")
        clock["t"] = 50.0               # step a spends the whole deadline
    monkeypatch.setattr(daily_cycle, "STEPS", (("a", step_a), *steps[1:]))
    daily_cycle._DEADLINE.update({"t0": 0.0, "seconds": 40.0, "basis": "test"})
    assert daily_cycle._run_chain(force=False) == 0
    assert calls == ["a"]
    stamp = json.loads((dc / "daily_cycle_state.json").read_text("utf-8"))
    assert set(stamp["steps"]) == {"a"}
    daily_cycle._DEADLINE.update({"t0": 50.0, "seconds": 1000.0})
    daily_cycle._run_chain(force=False)
    assert calls == ["a", "b", "c"]


def test_the_child_runs_one_proposer_and_a_hung_one_is_killed(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "fake_prop_ok.py").write_text(textwrap.dedent("""
        def run(budget_s=600.0):
            return {"tests_run": 4, "cells_proposed": 2, "budget": budget_s}
    """), "utf-8")
    (mods / "fake_prop_hang.py").write_text(textwrap.dedent("""
        import time
        def run():
            time.sleep(60)
    """), "utf-8")
    monkeypatch.setenv("PYTHONPATH", str(mods))
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    ok = daily_cycle._run_proposer("fake_prop_ok", 300.0, 120.0)
    assert ok["status"] == "OK" and ok["cells_proposed"] == 2 and ok["tests_run"] == 4
    hung = daily_cycle._run_proposer("fake_prop_hang", None, 3.0)
    assert hung["status"] == "KILLED_AT_BOUND"
    gone = daily_cycle._run_proposer("no_such_proposer_xyz", None, 60.0)
    assert gone["status"] == "ABSENT"


def test_the_census_and_the_liveness_check_read_the_same_list():
    sys.path.insert(0, str(_ROOT / "scripts"))
    import check_producer_yield

    from libs.ops import seat_clocks
    assert check_producer_yield._daily_proposers() == list(daily_cycle.PROPOSERS)
    assert seat_clocks._daily_proposers(_DESK) == list(daily_cycle.PROPOSERS)
    for name in ("anomaly_factory", "microstructure_miner", "plumbing_miner",
                 "style_premia_sweep", "survivor_distiller", "tail_alpha_search"):
        assert name in daily_cycle.PROPOSERS


# ------------------------------------------------------------- PR #524 audit (2026-10-29)

def test_a_proposer_killed_at_its_bound_gets_a_longer_bound_capped():
    budgeted = daily_cycle.proposer_bound(1200.0, {})
    assert budgeted == 1800.0
    assert daily_cycle.proposer_bound(1200.0, {"killed_at_bound_s": 1800}) == 2700.0
    unb = daily_cycle.proposer_bound(None, {"killed_at_bound_s": daily_cycle.UNBUDGETED_BOUND_S})
    assert unb == daily_cycle.PROPOSER_BOUND_GROWTH * daily_cycle.UNBUDGETED_BOUND_S
    assert daily_cycle.proposer_bound(None, {"killed_at_bound_s": 10 ** 6}) == \
        daily_cycle.PROPOSER_BOUND_CAP_S


def test_the_killed_bound_is_recorded_and_cleared_on_success(dc, monkeypatch):
    bounds: dict[str, list[float]] = {}
    outcome = {"v": "KILLED_AT_BOUND"}

    def fake(name, budget, bound):
        bounds.setdefault(name, []).append(bound)
        st = outcome["v"] if name == "fund_playbook" else "OK"
        return {"status": st, "wall_s": 1}

    monkeypatch.setattr(daily_cycle, "_run_proposer", fake)
    daily_cycle._proposers()
    st = _state(dc)
    first = bounds["fund_playbook"][0]
    assert st["fund_playbook"]["killed_at_bound_s"] == round(first)
    daily_cycle._proposers()                           # same day: only the killed one is owed
    assert bounds["fund_playbook"][1] == daily_cycle.PROPOSER_BOUND_GROWTH * round(first)
    outcome["v"] = "OK"
    st = _state(dc)
    st["fund_playbook"].pop("done_day", None)
    (dc / "state.json").write_text(json.dumps(st), "utf-8")
    daily_cycle._proposers()
    assert "killed_at_bound_s" not in _state(dc)["fund_playbook"]


def test_task_limit_decodes_utf16_and_never_raises(dc, monkeypatch):
    xml = ("<?xml version=\"1.0\" encoding=\"UTF-16\"?><Task><Settings>"
           "<ExecutionTimeLimit>PT3H</ExecutionTimeLimit></Settings></Task>")

    class R:
        returncode = 0

        def __init__(self, out):
            self.stdout = out

    for raw in (b"\xff\xfe" + xml.encode("utf-16-le"), xml.encode("utf-16-le"),
                xml.encode("utf-8")):
        assert daily_cycle._task_limit_s(runner=lambda *a, _r=raw, **k: R(_r)) == 10800.0

    def boom(*a, **k):
        raise ValueError("weird schtasks failure")

    assert daily_cycle._task_limit_s(runner=boom) is None
    assert "weird schtasks failure" in (dc / "daily_cycle.log").read_text("utf-8")
    assert daily_cycle._task_limit_s(runner=lambda *a, **k: R(b"garbage")) is None


# ------------------------------------- PR #524 audit v3: a missing DEPENDENCY is not ABSENT


def test_a_proposer_with_a_missing_dependency_is_failed_not_absent(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "fake_prop_needs_dep.py").write_text(
        "import no_such_dependency_xyz  # noqa: F401\ndef run():\n    return {}\n", "utf-8")
    monkeypatch.setenv("PYTHONPATH", str(mods))
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    broken = daily_cycle._run_proposer("fake_prop_needs_dep", None, 60.0)
    assert broken["status"] == "FAILED"
    assert "no_such_dependency_xyz" in broken["error"]
    assert daily_cycle._run_proposer("no_such_proposer_xyz", None, 60.0)["status"] == "ABSENT"


def test_absent_is_only_the_proposer_module_itself():
    own = ModuleNotFoundError("No module named 'p'", name="p")
    dep = ModuleNotFoundError("No module named 'scipy'", name="scipy")
    assert daily_cycle._proposer_absent("p", own) is True
    assert daily_cycle._proposer_absent("p", dep) is False


def test_the_pass_books_a_broken_import_failed_and_the_liveness_check_names_it(dc,
                                                                                monkeypatch):
    victim = daily_cycle.PROPOSERS[0]

    def budget(name):
        if name == victim:
            raise ModuleNotFoundError("No module named 'scipy'", name="scipy")
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(daily_cycle, "_proposer_budget", budget)
    monkeypatch.setattr(daily_cycle, "_run_proposer", lambda *a: pytest.fail("ran"))
    daily_cycle._proposers()
    st = _state(dc)
    assert st[victim]["last_status"] == "FAILED" and "scipy" in st[victim]["last_error"]
    assert all(st[n]["last_status"] == "ABSENT" for n in daily_cycle.PROPOSERS if n != victim)
    from libs.ops import seat_clocks
    (dc / "data").mkdir()
    (dc / "data" / seat_clocks.PROPOSER_STATE.name).write_text(json.dumps(st), "utf-8")
    red = seat_clocks.red_proposers(desk=dc, names=list(daily_cycle.PROPOSERS))
    assert [r["seat"] for r in red] == [victim]
