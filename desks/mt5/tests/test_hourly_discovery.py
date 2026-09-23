"""The hourly discovery pass: every organ gets an hourly turn, on a budget, with its failures named.

Pinned here: the plan never overspends the hour and never starves an organ below the floor;
the organ that waited longest runs first; a subprocess exit is classified honestly (OK,
DEFERRED_MEMORY on the memory guard's EX_TEMPFAIL, FAILED, KILLED_AT_BUDGET); state and report
are written where the fence and the next pass read them; and child mode calls an organ by its
declared convention with the budget it was given.
"""
from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_discovery as hd  # noqa: E402


def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hd, "STATE", tmp_path / "data" / "hourly_discovery_state.json")
    monkeypatch.setattr(hd, "REPORT", tmp_path / "reports" / "HOURLY_DISCOVERY.json")
    monkeypatch.setattr(hd, "_weight", lambda name: 1.0)


def test_the_plan_shares_the_hour_between_floor_and_cap(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    p = hd.plan({}, total_s=2700.0)
    assert {n for n, _ in p} == set(hd.ORGANS)
    assert sum(b for _, b in p) <= 2700.0 + 1e-6
    assert all(hd.MIN_ORGAN_S <= b <= hd.MAX_ORGAN_S for _, b in p)
    # a short hour still gives every organ its floor and never overspends
    short = hd.plan({}, total_s=len(hd.ORGANS) * hd.MIN_ORGAN_S)
    assert all(b == hd.MIN_ORGAN_S for _, b in short)


def test_the_organ_that_waited_longest_runs_first(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    state = {n: {"last_ok_at": "2026-09-05T03:00:00+00:00"} for n in hd.ORGANS}
    state["tail_alpha_search"] = {"last_ok_at": "2026-09-01T00:00:00+00:00"}
    state.pop("anomaly_factory")                       # never ran: stalest of all
    order = [n for n, _ in hd.plan(state, total_s=2700.0)]
    assert order[0] == "anomaly_factory"
    assert order[1] == "tail_alpha_search"


def test_a_pass_classifies_every_exit_and_writes_state_and_report(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(hd, "ORGANS", {"a_ok": "run", "b_mem": "run", "c_fail": "run",
                                       "d_slow": "run"})
    seen: list[list[str]] = []

    def runner(cmd: list[str], timeout_s: float) -> tuple[int | None, str]:
        seen.append(cmd)
        name = cmd[cmd.index("--organ") + 1]
        if name == "a_ok":
            return 0, "a_ok: {}\n" + hd.YIELD_PREFIX + '{"cells_proposed": 4, "claims_new": 2}'
        if name == "b_mem":
            return hd.EX_TEMPFAIL, "memory_guard: no headroom"
        if name == "d_slow":
            raise subprocess.TimeoutExpired(cmd, timeout_s)
        return 1, "Traceback"

    rep = hd.run_pass(total_s=1200.0, runner=runner)
    rows = rep["organs"]
    assert rows["a_ok"]["status"] == "OK"
    assert rows["b_mem"]["status"] == "DEFERRED_MEMORY"
    assert rows["c_fail"]["status"] == "FAILED"
    assert rows["d_slow"]["status"] == "KILLED_AT_BUDGET"
    assert (rep["ok"], rep["deferred"], rep["failed"]) == (1, 1, 1)
    # every child was launched with its own budget and, when the guard exists, behind it
    for cmd in seen:
        assert "--budget-s" in cmd
        assert (str(hd.MEMORY_GUARD) in cmd) == hd.MEMORY_GUARD.exists()
    state = json.loads(hd.STATE.read_text("utf-8"))
    assert state["a_ok"]["last_ok_at"] and state["a_ok"]["runs"] == 1
    assert "last_ok_at" not in state["c_fail"] and state["c_fail"]["last_status"] == "FAILED"
    written = json.loads(hd.REPORT.read_text("utf-8"))
    assert written["organs"]["b_mem"]["rc"] == hd.EX_TEMPFAIL
    # what the hour PRODUCED is on the report, by organ and in total; a run that produced
    # nothing is named as such rather than counted as a success
    assert written["organs"]["a_ok"]["yield"] == {"cells_proposed": 4, "claims_new": 2}
    assert written["yield"] == {"cells_proposed": 4, "claims_new": 2}
    assert state["a_ok"]["yield_total"] == {"cells_proposed": 4, "claims_new": 2}
    assert written["organs_with_zero_yield"] == []


def test_yield_is_read_from_the_organs_own_counters() -> None:
    assert hd.yield_of({"cells_proposed": 3, "proposals": [1, 2], "note": "x", "ok": True}) == {
        "cells_proposed": 3, "proposals": 2}
    assert hd.yield_of(None) == {}
    assert hd.parse_yield("junk\n" + hd.YIELD_PREFIX + '{"tasks": 7}\n') == {"tasks": 7}
    assert hd.parse_yield("no yield line") == {}


def test_an_hour_that_runs_out_skips_the_rest_by_name(tmp_path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(hd, "ORGANS", {"x": "run", "y": "run", "z": "run"})
    clock = {"t": 0.0}
    monkeypatch.setattr(hd.time, "monotonic", lambda: clock["t"])

    def runner(cmd: list[str], timeout_s: float) -> tuple[int | None, str]:
        clock["t"] += 100.0                           # each organ eats 100s of a 180s hour
        return 0, ""

    rep = hd.run_pass(total_s=180.0, runner=runner)
    statuses = [rep["organs"][n]["status"] for n in ("x", "y", "z")]
    assert statuses.count("OK") >= 1
    assert "SKIPPED_NO_TIME" in statuses


def test_child_mode_calls_each_convention_with_its_budget(monkeypatch) -> None:
    calls: dict[str, object] = {}
    budgeted = types.ModuleType("fake_budgeted")

    def run(symbols=None, budget_s: float = 999.0) -> dict:   # noqa: ARG001
        calls["budget"] = budget_s
        return {"cells_proposed": 3}

    budgeted.run = run                                          # type: ignore[attr-defined]
    plain = types.ModuleType("fake_plain")
    plain.run = lambda: {"n": 1}                                # type: ignore[attr-defined]
    crawler = types.ModuleType("fake_crawler")
    crawler.crawl = lambda run_budget_s: {"planned": run_budget_s}   # type: ignore[attr-defined]
    mainer = types.ModuleType("fake_main")
    mainer.main = lambda: 0                                     # type: ignore[attr-defined]
    for m in (budgeted, plain, crawler, mainer):
        monkeypatch.setitem(sys.modules, m.__name__, m)
    monkeypatch.setattr(hd, "ORGANS", {"fake_budgeted": "run_budget", "fake_plain": "run",
                                       "fake_crawler": "crawl_budget", "fake_main": "main"})
    assert hd.run_organ("fake_budgeted", 240.0)["result"] == {"cells_proposed": 3}
    assert calls["budget"] == 240.0
    assert hd.run_organ("fake_plain", 240.0)["result"] == {"n": 1}
    assert hd.run_organ("fake_crawler", 240.0)["result"] == {"planned": 240}
    assert hd.run_organ("fake_main", 240.0)["rc"] == 0


def test_every_declared_organ_exists_on_this_tree() -> None:
    """A name here that no module answers to is an hourly failure nobody asked for."""
    missing = []
    for name in hd.ORGANS:
        found = any((_DESK / sub / f"{name}.py").exists() for sub in ("research", "side_channels"))
        if not found:
            missing.append(name)
    assert not missing, missing
