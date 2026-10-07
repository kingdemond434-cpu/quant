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
import math
import os
import stat
import statistics
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


# --------------------------------------------------------------------------- event-driven sources
EQUITY = "equity_move:gateway_state.json"
COST = "cost_regime:cost_truth_quotes.json"
DRIFT = "drift_health:DRIFT.json"


def _pending(st: dict[str, Any], key: str) -> list[int]:
    return [p["seq"] for p in st["seen"][key]["pending"]]


def _equity(desk: Path, eq: float, **extra: Any) -> None:
    _w(desk / "data" / "gateway_state.json", {"equity": eq, **extra})


def _assert_consumed_only_by_landing(desk: Path, st: dict[str, Any], key: str,
                                     clock: Clock) -> dict[str, Any]:
    """A failed solve keeps the version pending; only a landed decision consumes it."""
    calls: list[dict[str, Any]] = []
    seq = _pending(st, key)[-1]
    st = _poll(st, clock, failing_solver(calls))["state"]
    assert calls and _pending(st, key)[-1] == seq
    assert (st["seen"][key].get("consumed") or {}).get("seq") != seq
    clock.t += 61
    res = _poll(st, clock, honouring_solver(desk, calls))
    st = res["state"]
    assert not st["seen"][key]["pending"] and st["seen"][key]["consumed"]["seq"] == seq
    assert st["seen"][key]["consumed"]["decision_id"]
    kind = key.split(":", 1)[0]
    assert any(s.get("kind") == kind for s in res["fired"] if s.get("event") == "consumed")
    assert at.latency_report(st["latency_samples"])["by_kind"][kind]["status"] == "MEASURED"
    return st


def test_equity_move_fires_on_material_move_not_noise_and_accumulates_drift(desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _equity(desk, 1000.0)
    st = _poll(None, clock, None, solve=False)["state"]
    assert not st["seen"][EQUITY]["pending"]                  # first sight is the baseline
    assert st["seen"][EQUITY]["observed"]["anchor"] == {"equity": 1000.0}

    for eq in (1004.0, 1004.0, 996.0):                        # inside the band, and a rewrite
        _equity(desk, eq, lot=0.01)
        clock.t += 20
        res = _poll(st, clock, None, solve=False)
        st = res["state"]
        assert not st["seen"][EQUITY]["pending"]
    (row,) = [w for w in res["watch"] if w["key"] == EQUITY]
    assert row["materiality"]["basis"].startswith("DEFAULT")  # no history: the stated prior
    assert row["materiality"]["threshold_log"] == pytest.approx(at.EQUITY_DEFAULT_DAILY_VOL)

    _equity(desk, 1006.0)                                     # 0.6% vs anchor: still noise
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert not st["seen"][EQUITY]["pending"]
    _equity(desk, 1012.0)                                     # slow drift reaches 1.19%: fires
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, EQUITY) == [2]
    assert st["seen"][EQUITY]["observed"]["anchor"] == {"equity": 1012.0}
    _equity(desk, 1013.0)                                     # noise against the NEW anchor
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, EQUITY) == [2]
    _assert_consumed_only_by_landing(desk, st, EQUITY, clock)


def test_equity_unreadable_is_not_an_observation_and_falls_back_to_account_state(
        desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _equity(desk, 1000.0)
    st = _poll(None, clock, None, solve=False)["state"]
    _w(desk / "data" / "gateway_state.json", {"lot": 0.01})   # no equity, no account_state
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert not st["seen"][EQUITY]["pending"]
    _w(desk / "data" / "account_state.json", {"equity": 1100.0})
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, EQUITY) == [2]


def test_equity_band_is_derived_from_the_deal_ledger(desk: Path) -> None:
    """Realised daily returns rebuilt from cost_truth_quotes.json deals: the deposit is balance,
    never a return, and the threshold is k x the measured sigma."""
    base = 1_788_134_400                                      # a Monday 00:00 UTC
    deals: list[dict[str, Any]] = [{"epoch": base - 86_400, "type": 2, "profit": 1000.0}]
    bal, rets = 1000.0, []
    for i in range(12):                                       # 12 weekdays, alternating +/- 2%
        day = base + 86_400 * (i + 2 * (i // 5))
        pnl = bal * (0.02 if i % 2 == 0 else -0.02)
        deals.append({"epoch": day + 3600, "type": 0, "entry": 1, "profit": pnl,
                      "swap": 0.0, "comm": 0.0, "fee": 0.0})
        rets.append(math.log((bal + pnl) / bal))
        bal += pnl
    _w(desk / "data" / "cost_truth_quotes.json", {"deals": deals, "symbols": {}})
    quotes = at._read(desk / "data" / "cost_truth_quotes.json")
    sigma, n = at._deals_sigma(quotes)
    assert n == 12 and sigma == pytest.approx(statistics.stdev(rets), rel=1e-9)
    band = at._equity_band({}, quotes)
    assert band["basis"].startswith("MEASURED")
    assert band["threshold_log"] == pytest.approx(at.EQUITY_K_SIGMA * sigma, abs=1e-6)


def _quotes(desk: Path, spread: float, swap_long: float = -5.0, swap_short: float = 1.0,
            stamp: str = "2026-10-06T00:00:00+00:00", ask: float = 1.1) -> None:
    _w(desk / "data" / "cost_truth_quotes.json", {"at": stamp, "symbols": {
        "EURUSD": {"at": stamp, "ask": ask, "bid": 1.0, "live_spread_pts": spread,
                   "swap_long": swap_long, "swap_short": swap_short},
        "NOTHELD": {"live_spread_pts": 999.0 if ask > 1.1 else 1.0}}})


def _roster(desk: Path) -> None:
    _w(desk / "data" / "sleeve_registry.json", {"sleeves": {"EURUSD.x.asia": {
        "status": "LIVE", "identity": {"symbol": "EURUSD"}}}})


def test_cost_regime_fires_beyond_the_band_not_on_noise_or_rewrite(desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _roster(desk)
    _quotes(desk, 2.0)
    st = _poll(None, clock, None, solve=False)["state"]
    assert not st["seen"][COST]["pending"]
    assert set(st["seen"][COST]["observed"]["anchor"]) == {"EURUSD"}  # sleeve symbols only

    # a rewrite with new prices and stamps, a one-point spread tick, a swap that moved < 2x and
    # a non-sleeve symbol blowing out: none of them is a regime change
    for i, (spread, sl) in enumerate(((2.0, -5.0), (3.0, -5.0), (2.0, -8.0))):
        _quotes(desk, spread, sl, stamp=f"2026-10-06T00:0{i + 1}:00+00:00", ask=1.2)
        clock.t += 20
        st = _poll(st, clock, None, solve=False)["state"]
        assert not st["seen"][COST]["pending"]

    _quotes(desk, 7.0)                                        # (7+1)/(2+1): 1.4 doublings
    clock.t += 20
    res = _poll(st, clock, None, solve=False)
    st = res["state"]
    assert _pending(st, COST) == [2]
    (row,) = [w for w in res["watch"] if w["key"] == COST]
    assert row["materiality"]["moved"] == {"EURUSD": ["spread"]}

    _quotes(desk, 7.0, swap_short=-0.5)                       # swap sign flip: a new regime
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, COST) == [2, 3]
    _assert_consumed_only_by_landing(desk, st, COST, clock)


def test_cost_band_widens_to_the_symbols_measured_dispersion(desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _roster(desk)
    _w(desk / "data" / "cost_surface.json",
       {"symbols": {"EURUSD": {"stress_p90_over_p50": 8.0}}})  # log2 = 3 doublings
    _quotes(desk, 2.0)
    st = _poll(None, clock, None, solve=False)["state"]
    _quotes(desk, 7.0)                                        # 1.4 doublings: inside 3
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert not st["seen"][COST]["pending"]
    _quotes(desk, 40.0)                                       # 41/3: 3.8 doublings
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, COST) == [2]


def _drift(desk: Path, hazards: dict[str, tuple[str, float | None]], verdict: str = "STABLE",
           stamp: str = "2026-10-06T00:00:00+00:00", z: float = 0.1) -> None:
    _w(desk / "reports" / "DRIFT.json", {
        "generated_utc": stamp, "verdict": verdict, "structure_verdict": "STABLE",
        "hazard_max": z, "what_changed": [f"z={z}"],
        "hazard_by_sleeve": {k: {"verdict": v, "hazard": h, "components": {"z": z}}
                             for k, (v, h) in hazards.items()}})


def test_drift_health_fires_on_verdict_or_band_not_on_rewrite(desk: Path) -> None:
    clock = Clock(1_790_000_000.0)
    _drift(desk, {"s1": ("HOLDING", 0.05), "s2": ("HOLDING", None)})
    st = _poll(None, clock, None, solve=False)["state"]
    assert not st["seen"][DRIFT]["pending"]
    # the unchanged observation rewritten; hazard moving INSIDE its band; z, prose, stamp moving
    for i, h in enumerate((0.05, 0.10, 0.14)):
        _drift(desk, {"s1": ("HOLDING", h), "s2": ("HOLDING", None)},
               stamp=f"2026-10-06T0{i + 1}:00:00+00:00", z=0.1 + i)
        clock.t += 20
        st = _poll(st, clock, None, solve=False)["state"]
        assert not st["seen"][DRIFT]["pending"]

    _drift(desk, {"s1": ("HOLDING", 0.20), "s2": ("HOLDING", None)})  # crosses AT_RISK band
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, DRIFT) == [2]
    _drift(desk, {"s1": ("HOLDING", 0.20), "s2": ("BREAKING", None)})  # a verdict changed
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, DRIFT) == [2, 3]
    _drift(desk, {"s1": ("HOLDING", 0.20), "s2": ("BREAKING", None)}, verdict="DRIFT_AHEAD")
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, DRIFT) == [2, 3, 4]
    (desk / "reports" / "DRIFT.json").unlink()               # a missing report is not a verdict
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, DRIFT) == [2, 3, 4]
    _drift(desk, {"s1": ("HOLDING", 0.20), "s2": ("BREAKING", None)}, verdict="DRIFT_AHEAD")
    clock.t += 20
    st = _poll(st, clock, None, solve=False)["state"]
    assert _pending(st, DRIFT) == [2, 3, 4]
    _assert_consumed_only_by_landing(desk, st, DRIFT, clock)


def test_report_publishes_latency_per_new_kind_and_keeps_foreign_state(desk: Path) -> None:
    _w(at.STATE, {"schema": 2, "seen": {}, "book": {"owner": "book_trigger", "v": 7}})
    _equity(desk, 1000.0)
    rep = at.run(write=True, solve=False)
    assert {"equity_move", "cost_regime", "drift_health"} <= set(rep["latency"]["by_kind"])
    assert rep["latency"]["by_kind"]["drift_health"]["status"] == "UNMEASURED"
    assert json.loads(at.STATE.read_text("utf-8"))["book"] == {"owner": "book_trigger", "v": 7}
    keys = {s.key for s in at.sources()}
    assert {EQUITY, "equity_move:E8_GOLD.json", COST, DRIFT} <= keys
