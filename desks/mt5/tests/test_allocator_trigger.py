"""The allocator trigger's three ledgers: OBSERVED, PENDING, CONSUMED.

THE DEFECT THESE PIN (2026-10-06). The first trigger kept one `seen` record per input and wrote it
BEFORE deciding to solve. A change that arrived inside the 60s debounce was logged "served by the
next pass, not dropped" and then never served, because the next pass compared against a record
that already held it. A failed solve lost its change the same way. And "landed" was a newer
`generated_utc`, which the hourly leg also produces.

EVERY INPUT IS SYNTHETIC: the module's paths are redirected into `tmp_path`, the solver is a fake
that does or does not honour the decision contract, and time is an injected clock -- so nothing
here launches `pf_allocator` or reads the box's real artifacts.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import allocator_trigger as at  # noqa: E402

MACRO = "macro_surprise:MACRO_VIEW.json"
NEWS = "news_resolve_request:allocator_resolve_request.json"


class Clock:
    def __init__(self, t: float) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reports, data = tmp_path / "reports", tmp_path / "data"
    reports.mkdir()
    data.mkdir()
    monkeypatch.setattr(at, "ROOT", tmp_path)
    monkeypatch.setattr(at, "REPORTS", reports)
    monkeypatch.setattr(at, "DATA", data)
    monkeypatch.setattr(at, "OUT", reports / "ALLOCATOR_REACTION.json")
    monkeypatch.setattr(at, "LOG", data / "allocator_reactions.jsonl")
    monkeypatch.setattr(at, "STATE", data / "allocator_trigger_state.json")
    monkeypatch.setattr(at, "LOCK", data / "allocator_trigger.lock")
    monkeypatch.setattr(at, "ALLOCATION", reports / "pf_allocation.json")
    monkeypatch.setattr(at, "RESOLVE_REQUEST", data / "allocator_resolve_request.json")
    return tmp_path


def _w(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _macro(desk: Path, label: str, at_: str | None = None) -> None:
    doc: dict[str, Any] = {"labels": {"growth": label}}
    if at_:
        doc["at"] = at_
    _w(desk / "reports" / "MACRO_VIEW.json", doc)


def honouring_solver(desk: Path, calls: list[dict[str, Any]], *, side_effect=None):
    """A solver that honours the contract: echoes request_id and input_versions."""
    def solve(budget_s: float, req: dict[str, Any]) -> dict[str, Any]:
        calls.append(req)
        if side_effect:
            side_effect()
        _w(desk / "reports" / "pf_allocation.json", {
            "generated_utc": "2026-10-06T00:00:00+00:00", "heat": {"total": 0.3},
            "decision_id": f"dec-{len(calls)}", "trigger_request_id": req["request_id"],
            "consumed_input_versions": dict(req["input_versions"])})
        return {"rc": 0, "wall_s": 1.0, "tail": ""}
    return solve


def failing_solver(calls: list[dict[str, Any]]):
    def solve(budget_s: float, req: dict[str, Any]) -> dict[str, Any]:
        calls.append(req)
        return {"rc": 1, "wall_s": 1.0, "tail": "boom"}
    return solve


def _poll(st, clock: Clock, solver=None, **kw):
    return at.poll(state=st, write=False, now=clock.t, clock=clock, solver=solver, **kw)


def test_change_during_debounce_is_not_lost(desk: Path) -> None:
    clock, calls = Clock(1_790_000_000.0), []
    solver = honouring_solver(desk, calls)
    _macro(desk, "A")
    st = _poll(None, clock, solver)["state"]                  # baseline, nothing pending
    assert not st["seen"][MACRO]["pending"] and not calls

    _macro(desk, "B")
    clock.t += 20
    st = _poll(st, clock, solver)["state"]                    # B solved and consumed
    assert len(calls) == 1 and not st["seen"][MACRO]["pending"]

    _macro(desk, "C")                                         # arrives INSIDE the 60s gap
    clock.t += 20
    res = _poll(st, clock, solver)
    st = res["state"]
    assert res["debounced"] and len(calls) == 1
    assert [p["seq"] for p in st["seen"][MACRO]["pending"]] == [3]

    clock.t += 20                                             # still inside the gap: kept
    st = _poll(st, clock, solver)["state"]
    assert [p["seq"] for p in st["seen"][MACRO]["pending"]] == [3]

    clock.t += 30                                             # gap over: served, not dropped
    st = _poll(st, clock, solver)["state"]
    assert len(calls) == 2 and not st["seen"][MACRO]["pending"]
    assert st["seen"][MACRO]["consumed"]["seq"] == 3
    assert st["seen"][MACRO]["consumed"]["decision_id"] == "dec-2"


def test_pending_survives_a_restart_through_the_state_file(desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _macro(desk, "A")
    at.poll(write=True, solve=False, now=clock.t, clock=clock)
    _macro(desk, "B")
    clock.t += 20
    at.poll(write=True, solve=False, now=clock.t, clock=clock)
    on_disk = json.loads(at.STATE.read_text("utf-8"))           # a fresh process reads this
    assert [p["seq"] for p in on_disk["seen"][MACRO]["pending"]] == [2]
    calls: list[dict[str, Any]] = []
    clock.t += 20
    res = at.poll(write=True, now=clock.t, clock=clock, solver=honouring_solver(desk, calls))
    assert len(calls) == 1 and not res["state"]["seen"][MACRO]["pending"]


def test_failed_solve_keeps_pending_and_backs_off(desk: Path) -> None:
    clock, calls = Clock(1_790_000_000.0), []
    _macro(desk, "A")
    st = _poll(None, clock, failing_solver(calls))["state"]
    _macro(desk, "B")
    clock.t += 20
    res = _poll(st, clock, failing_solver(calls))
    st = res["state"]
    assert res["attempt"]["verdict"].startswith("SOLVER_FAILED")
    assert [p["seq"] for p in st["seen"][MACRO]["pending"]] == [2]
    assert st["fail_count"] == 1 and st["last_solve_at"] == pytest.approx(clock.t)
    assert at._wait_s(1) == 60.0

    clock.t += 61                                             # second failure: 120s backoff
    st = _poll(st, clock, failing_solver(calls))["state"]
    assert st["fail_count"] == 2 and at._wait_s(2) == 120.0
    clock.t += 100
    res = _poll(st, clock, failing_solver(calls))
    assert res["debounced"] and len(calls) == 2               # backoff honoured
    st = res["state"]

    clock.t += 30                                             # retry lands and consumes
    good: list[dict[str, Any]] = []
    st = _poll(st, clock, honouring_solver(desk, good))["state"]
    assert len(good) == 1 and not st["seen"][MACRO]["pending"] and st["fail_count"] == 0


@pytest.mark.parametrize("art", [
    {"generated_utc": "2099-01-01T00:00:00+00:00"},                       # fresher stamp only
    {"generated_utc": "2099-01-01T00:00:00+00:00", "decision_id": "d1"},  # no consumed versions
    {"decision_id": "", "consumed_input_versions": {MACRO: "2:x"}},       # empty id
])
def test_landing_requires_decision_id_with_consumed_versions(desk: Path, art) -> None:
    clock, calls = Clock(1_790_000_000.0), []

    def solver(budget_s: float, req: dict[str, Any]) -> dict[str, Any]:
        calls.append(req)
        doc = dict(art)
        if "consumed_input_versions" not in doc and "decision_id" in doc:
            doc["trigger_request_id"] = req["request_id"]
        _w(desk / "reports" / "pf_allocation.json", doc)
        return {"rc": 0, "wall_s": 1.0, "tail": ""}

    _macro(desk, "A")
    st = _poll(None, clock, solver)["state"]
    _macro(desk, "B")
    clock.t += 20
    res = _poll(st, clock, solver)
    assert len(calls) == 1 and res["attempt"]["landed"] is False
    assert res["attempt"]["verdict"] == "NO_DECISION_CONTRACT"
    assert [p["seq"] for p in res["state"]["seen"][MACRO]["pending"]] == [2]
    assert res["state"]["fail_count"] == 1


def test_decision_answering_another_request_does_not_land(desk: Path) -> None:
    clock, calls = Clock(1_790_000_000.0), []

    def solver(budget_s: float, req: dict[str, Any]) -> dict[str, Any]:
        calls.append(req)
        _w(desk / "reports" / "pf_allocation.json", {
            "decision_id": "hourly-1", "trigger_request_id": "someone-else",
            "consumed_input_versions": dict(req["input_versions"])})
        return {"rc": 0, "wall_s": 1.0, "tail": ""}

    _macro(desk, "A")
    st = _poll(None, clock, solver)["state"]
    _macro(desk, "B")
    clock.t += 20
    res = _poll(st, clock, solver)
    assert res["attempt"]["verdict"] == "DECISION_ANSWERS_ANOTHER_REQUEST"
    assert res["state"]["seen"][MACRO]["pending"]


def test_version_observed_during_the_solve_stays_pending(desk: Path) -> None:
    clock, calls = Clock(1_790_000_000.0), []
    _macro(desk, "A")
    st = _poll(None, clock, honouring_solver(desk, calls))["state"]
    _macro(desk, "B")
    clock.t += 20
    # the input moves WHILE the solve runs; the solve was issued with version 2 only
    solver = honouring_solver(desk, calls, side_effect=lambda: _macro(desk, "C"))
    st = _poll(st, clock, solver)["state"]
    assert st["seen"][MACRO]["consumed"]["seq"] == 2
    clock.t += 20                                             # next look sees C: pending
    res = _poll(st, clock, honouring_solver(desk, calls))
    st = res["state"]
    assert res["settled_on_entry"] == "ALREADY_APPLIED"       # the old decision is not reused
    assert [p["seq"] for p in st["seen"][MACRO]["pending"]] == [3]


def test_stale_decision_never_clears_a_newer_pending_or_rolls_back_consumed(desk: Path) -> None:
    st = at._load_state(None)
    pend = [{"seq": s, "version": f"{s}:sig{s}", "kind": "macro_surprise",
             "observed_ts": 100.0 + s, "start_ts": 100.0 + s} for s in (2, 3)]
    st["seen"][MACRO] = {"observed": {"seq": 3, "version": "3:sig3"}, "pending": pend,
                           "consumed": {"seq": 1, "version": "1:sig1"}}
    st["issued"] = [
        {"request_id": "r0", "issued_ts": 100.0, "input_versions": {MACRO: "1:sig1"}},
        {"request_id": "r1", "issued_ts": 102.0, "input_versions": {MACRO: "2:sig2"}}]

    # an echo claiming a version the request never carried is refused outright
    v, _ = at._land(st, {"decision_id": "dx", "request_id": "r1",
                         "consumed": {MACRO: "3:sig3"}, "decided_at": None}, 200.0)
    assert v == "CONSUMED_VERSIONS_DO_NOT_ECHO_THE_REQUEST"
    assert len(st["seen"][MACRO]["pending"]) == 2

    # the older request lands late: it consumes version 2 and NOT the newer version 3
    v, samples = at._land(st, {"decision_id": "d1", "request_id": "r1",
                               "consumed": {MACRO: "2:sig2"}, "decided_at": None}, 200.0)
    assert v == "LANDED" and [s["version"] for s in samples] == ["2:sig2"]
    assert [p["seq"] for p in st["seen"][MACRO]["pending"]] == [3]
    assert st["seen"][MACRO]["consumed"]["seq"] == 2

    # an even older decision cannot roll CONSUMED back
    v, _ = at._land(st, {"decision_id": "d0", "request_id": "r0",
                         "consumed": {MACRO: "1:sig1"}, "decided_at": None}, 201.0)
    assert v == "LANDED"
    assert st["seen"][MACRO]["consumed"]["seq"] == 2
    assert [p["seq"] for p in st["seen"][MACRO]["pending"]] == [3]


def test_news_resolve_request_is_watched_and_consumed_only_by_a_landed_decision(
        desk: Path) -> None:
    import news_event_stream as nes
    assert nes.RESOLVE_REQUEST.name == at.RESOLVE_REQUEST.name
    assert nes.RESOLVE_REQUEST.parent.name == "data"
    assert any(s.path == at.RESOLVE_REQUEST for s in at.sources())

    clock, calls = Clock(1_790_000_000.0), []
    _macro(desk, "A")
    req_doc = {"at": "2026-10-06T00:00:00+00:00",
               "requests": [{"event_id": "e1", "reason": "war (T1)"}], "rule": "a REQUEST"}
    _w(at.RESOLVE_REQUEST, req_doc)
    # first sighting of a request is an UNANSWERED request, not a baseline; a failed solve
    # keeps it
    res = _poll(None, clock, failing_solver(calls))
    st = res["state"]
    assert len(calls) == 1 and [p["seq"] for p in st["seen"][NEWS]["pending"]] == [1]
    clock.t += 61
    st = _poll(st, clock, honouring_solver(desk, calls))["state"]
    assert not st["seen"][NEWS]["pending"] and st["seen"][NEWS]["consumed"]["seq"] == 1

    # the same request content at a new `at` is a NEW request
    _w(at.RESOLVE_REQUEST, {**req_doc, "at": "2026-10-06T00:05:00+00:00"})
    clock.t += 61
    st = _poll(st, clock, None, solve=False)["state"]
    assert [p["seq"] for p in st["seen"][NEWS]["pending"]] == [2]

    # an empty request list, or the file vanishing, is not a request
    st2 = at._load_state(None)
    _w(at.RESOLVE_REQUEST, {"at": "2026-10-06T00:00:00+00:00", "requests": []})
    st2 = _poll(st2, clock, None, solve=False)["state"]
    assert not st2["seen"][NEWS]["pending"]
    at.RESOLVE_REQUEST.unlink()
    clock.t += 20
    st2 = _poll(st2, clock, None, solve=False)["state"]
    assert not st2["seen"][NEWS]["pending"]


def test_latency_percentiles_and_end_to_end_sample(desk: Path) -> None:
    samples = [{"latency_s": float(i), "from_observation_s": float(i) / 2,
                "kind": "fill" if i % 2 else "macro_surprise", "decision_id": f"d{i // 10}"}
               for i in range(1, 101)]
    rep = at.latency_report(samples)
    a = rep["all_inputs"]
    assert (a["n"], a["p50_s"], a["p95_s"], a["p99_s"]) == (100, 50.0, 95.0, 99.0)
    assert a["share_within_poll_interval"] == 0.2 and a["share_within_poll_plus_gap"] == 0.8
    assert rep["per_decision_slowest_input"]["n"] == 11
    assert rep["poll_interval_s"] == 20.0 and rep["min_solve_gap_s"] == 60.0
    assert at.latency_report([])["all_inputs"]["status"] == "UNMEASURED"

    # end to end: the change carries its own stamp 15s before the trigger first saw it
    clock, calls = Clock(1_790_000_000.0), []
    _macro(desk, "A")
    st = _poll(None, clock, honouring_solver(desk, calls))["state"]
    clock.t += 20
    _macro(desk, "B", at.\
        _iso(clock.t - 15))
    res = _poll(st, clock, honouring_solver(desk, calls))
    (sample,) = [r for r in res["fired"] if r.get("event") == "consumed"]
    assert sample["latency_s"] == pytest.approx(15.0, abs=1.0)
    assert sample["from_observation_s"] == pytest.approx(0.0, abs=1.0)
    assert res["state"]["latency_samples"][-1]["decision_id"] == "dec-1"


def test_stamp_older_than_previous_look_is_clamped(desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _macro(desk, "A")
    st = _poll(None, clock, None, solve=False)["state"]
    clock.t += 20
    _macro(desk, "B", "2020-01-01T00:00:00+00:00")           # producer stamped long ago
    st = _poll(st, clock, None, solve=False)["state"]
    (p,) = st["seen"][MACRO]["pending"]
    assert p["start_ts"] == pytest.approx(clock.t - 20, abs=1.0)


def test_schema1_state_migrates_as_baseline(desk: Path) -> None:
    st = at._load_state({"seen": {MACRO: {"sig": "abc", "at": "2026-10-01T00:00:00+00:00"}},
                         "last_solve_at": 5.0})
    assert st["schema"] == 2 and st["last_solve_at"] == 5.0
    assert st["seen"][MACRO]["observed"]["version"] == "1:abc"
    assert st["seen"][MACRO]["pending"] == []


def test_atomic_write_replaces_a_read_only_file(desk: Path) -> None:
    target = desk / "data" / "ro.json"
    target.write_text("old", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
    try:
        at._atomic_write_text(target, "new")
        assert target.read_text("utf-8") == "new"
        assert not list(target.parent.glob("ro.json.*.tmp"))
    finally:
        os.chmod(target, stat.S_IREAD | stat.S_IWRITE)


def test_run_writes_report_with_contract_and_releases_lock(desk: Path) -> None:
    _macro(desk, "A")
    rep = at.run(write=True, solve=False)
    assert rep["decision_contract"]["allocation_fields"].keys() >= {
        "decision_id", "trigger_request_id", "consumed_input_versions"}
    assert at.OUT.exists() and not at.LOCK.exists()
    assert "p99_s" in rep["latency"]["all_inputs"]


def test_one_argument_solver_hook_and_reset_last_solve_forces_retry(desk: Path) -> None:
    """The `_solve(budget)` hook shape still works; resetting `last_solve_at` to 0 is past any
    backoff, because the backoff is measured from that field and nothing else."""
    clock, calls = Clock(1_790_000_000.0), []

    def solve(budget: float) -> dict[str, Any]:
        calls.append(budget)
        return {"rc": 1, "wall_s": 0.1, "tail": "boom"}

    _macro(desk, "A")
    st = _poll(None, clock, solve)["state"]
    _macro(desk, "B")
    clock.t += 1
    st = _poll(st, clock, solve)["state"]
    assert len(calls) == 1 and st["fail_count"] == 1
    st["last_solve_at"] = 0.0
    clock.t += 1
    st = _poll(st, clock, solve)["state"]
    assert len(calls) == 2 and st["seen"][MACRO]["pending"]
    assert set(st["seen"][MACRO]) >= {"observed", "pending", "consumed"}
