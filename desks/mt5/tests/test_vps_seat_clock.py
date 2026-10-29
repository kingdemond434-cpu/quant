"""The VPS-only seats get a box-side clock, idempotent with the VPS path (2026-10-29).

Thirty-three seats were written only by VPS timers and reached the box only through
intel-ship/send, silent since 2026-10-14. These pin: the box clock's unit lists match the
runners it stands in for; a unit whose seats any clock (the VPS's shipped files included) fed
inside the cadence is not run again; a unit is never attempted more often than its cadence;
stalest first; a unit that does not fit is deferred, not cut, and a killed one blocks no other;
the census counts two sweeps of one seat in one hour once; and the RED check names every seat
silent past two cadences of its slowest clock, in never_stale's output.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "side_channels"), str(_ROOT), str(_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import vps_seat_clock as vsc  # noqa: E402

from libs.ops import seat_clocks  # noqa: E402

NOW = 1_800_000_000.0


def _module_names(path: Path, var: str) -> list[str]:
    tree = ast.parse(path.read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == var for t in node.targets):
            v = node.value
            if isinstance(v, ast.Dict):
                return [k.value for k in v.keys if isinstance(k, ast.Constant)]
            return [e.elts[0].value for e in v.elts]  # type: ignore[attr-defined]
    raise AssertionError(f"{var} not found in {path}")


def test_the_unit_lists_are_the_runners_own():
    sc = _DESK / "side_channels"
    assert list(seat_clocks.SEED_UNITS) == _module_names(sc / "seed_miners.py", "MINERS")
    assert list(seat_clocks.EXTERNAL_UNITS) == _module_names(sc / "run_all_miners.py",
                                                             "ALL_MINERS")


def test_all_thirty_three_vps_only_seats_have_a_box_unit():
    assert len(seat_clocks.VPS_ONLY_SEATS) == 33
    units = set(seat_clocks.units())
    for seat, unit in seat_clocks.VPS_ONLY_SEATS.items():
        assert unit in units, seat
        assert seat in seat_clocks.unit_seats(unit), seat
        assert any(c[0].startswith("box:") for c in seat_clocks.unit_clocks(unit))


@pytest.fixture
def desk(tmp_path, monkeypatch):
    d = tmp_path / "desks" / "mt5"
    (d / "data" / "intelligence").mkdir(parents=True)
    monkeypatch.setattr(vsc, "BASE", d)
    monkeypatch.setattr(vsc, "STATE", d / "data" / "vps_seat_clock_state.json")
    monkeypatch.setattr(vsc, "REPORT", d / "reports" / "VPS_SEAT_CLOCK.json")
    return d


def _sweep(desk: Path, seat: str, age_h: float, now: float = NOW, hhmm: str = "0805") -> Path:
    f = desk / "data" / "intelligence" / seat / f"discoveries_20271015_{hhmm}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("[\n{}\n]\n", "utf-8")
    os.utime(f, (now - age_h * 3600, now - age_h * 3600))
    return f


def test_a_unit_the_vps_already_fed_is_not_run_again(desk):
    _sweep(desk, "cot", 0.5)                     # the VPS shipped cot half an hour ago
    _sweep(desk, "darwinex", 7.0)                # nobody has fed darwinex for 7 h
    p = vsc.plan({}, NOW, desk)
    assert "external:cot" in p["fresh"]
    assert "seed:darwinex" in p["due"]


def test_a_unit_is_never_attempted_more_often_than_its_cadence(desk):
    started = {"seed:darwinex": {"last_started_at": "2027-01-15T08:00:00+00:00"}}
    now = seat_clocks._iso_ts("2027-01-15T09:00:00+00:00")
    assert "seed:darwinex" in vsc.plan(started, now, desk)["fresh"]
    later = seat_clocks._iso_ts("2027-01-15T11:30:00+00:00")
    assert "seed:darwinex" in vsc.plan(started, later, desk)["due"]


def test_stalest_first_and_the_never_fed_lead(desk):
    _sweep(desk, "darwinex", 30.0)
    _sweep(desk, "fxblue", 10.0)
    due = vsc.plan({}, NOW, desk)["due"]
    assert due.index("seed:global_frontier") < due.index("seed:darwinex") < due.index(
        "seed:fxblue")


def test_a_pass_defers_what_does_not_fit_and_a_kill_blocks_nothing(desk, monkeypatch):
    calls: list[str] = []

    def runner(cmd, timeout_s):
        unit = cmd[cmd.index("--unit") + 1]
        calls.append(unit)
        if unit == "seed:global_frontier":
            return None, ""                      # killed at its bound
        return 0, vsc.RESULT_PREFIX + json.dumps({"status": "OK", "rows": 3})

    rep = vsc.run_pass(1000.0, runner=runner, now=NOW)
    units = rep["units"]
    assert units["seed:global_frontier"]["status"] == "KILLED_AT_BOUND"
    assert units["seed:regional_survivors"]["status"] == "DEFERRED"   # 1,200 s bound > 1,000 s
    assert units["seed:darwinex"]["status"] == "OK"
    assert units["external:korea"]["status"] == "OK"
    assert "seed:regional_survivors" not in calls
    assert "join:seed" in calls                  # the once-per-pass join still runs
    st = json.loads(vsc.STATE.read_text("utf-8"))
    assert "last_started_at" not in st.get("seed:regional_survivors", {})
    assert st["seed:global_frontier"]["last_status"] == "KILLED_AT_BOUND"
    assert json.loads(vsc.REPORT.read_text("utf-8"))["deferred"] == ["seed:regional_survivors"]
    # next hour: the killed unit is inside its cadence (not hammered); the deferred one leads
    nxt = vsc.plan(st, time.time() + 3600, desk)["due"]
    assert nxt[0] == "seed:regional_survivors"
    assert "seed:global_frontier" not in nxt


def test_seed_only_runs_the_named_source_and_keeps_its_wall(tmp_path, monkeypatch):
    import seed_miners
    hits: list[str] = []
    monkeypatch.setattr(seed_miners, "INTEL", tmp_path)
    monkeypatch.setattr(seed_miners, "STATE", tmp_path / "seed_miners_state.json")
    monkeypatch.setattr(seed_miners, "MINERS", {
        "a_src": lambda: hits.append("a") or [seed_miners.row("a_src", "k", "t", "u")],
        "b_src": lambda: hits.append("b") or [],
        "walled_src": lambda: hits.append("walled") or []})
    monkeypatch.setattr(seed_miners, "SOURCE_WALLS", {"walled_src": {
        "verdict": "ROBOTS_DISALLOW", "host": "example.invalid", "since": "2026-01-01",
        "evidence": "robots.txt"}})
    monkeypatch.setattr(seed_miners, "_wall_due", lambda name, st: False)
    import discovery_io
    monkeypatch.setattr(discovery_io, "write_discoveries", lambda path, rows: (
        path.parent.mkdir(parents=True, exist_ok=True),
        path.write_text(json.dumps(rows), "utf-8"), rows)[2])
    res = seed_miners.run_and_save(only={"a_src", "walled_src"}, tail=False)
    assert hits == ["a"]                         # the walled source was NOT fetched
    assert set(res) == {"a_src", "walled_src"}
    assert res["walled_src"]["discoveries"][0]["kind"] == "walled"


def test_two_sweeps_of_one_seat_in_one_hour_count_once(tmp_path, monkeypatch):
    import check_producer_yield as cpy
    desk = tmp_path / "desks" / "mt5"
    monkeypatch.setattr(cpy, "DESK", desk)
    monkeypatch.setattr(cpy, "ROOT", tmp_path)
    now = time.time()
    _sweep(desk, "cot", 0.1, now, hhmm="0805")    # VPS sweep, shipped
    _sweep(desk, "cot", 0.1, now, hhmm="0840")    # box sweep, same hour
    _sweep(desk, "cot", 0.1, now, hhmm="0905")    # next hour
    out = cpy._seat_output(3.0)
    assert out["cot"] == 2 * 3                     # two hours, three lines each, once per hour


def test_red_names_every_seat_silent_past_two_cadences(tmp_path):
    desk = tmp_path / "desks" / "mt5"
    for seat in seat_clocks.VPS_ONLY_SEATS:
        _sweep(desk, seat, 1.0)
    _sweep(desk, "cot", 7.0)                      # silent for 7 h > 2 x 3 h
    for f in (desk / "data" / "intelligence" / "amarkets").iterdir():
        f.unlink()
    red = {r["seat"]: r for r in seat_clocks.red_seats(NOW, desk)}
    assert set(red) == {"cot", "amarkets"}
    assert red["cot"]["threshold_h"] == 2 * seat_clocks.BOX_CADENCE_H
    assert red["amarkets"]["age_h"] is None and "never run" in red["amarkets"]["why"]


def test_red_names_a_proposer_with_no_completed_run_in_two_days(tmp_path):
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    old = "2027-01-10T00:00:00+00:00"
    fresh = "2027-01-15T00:00:00+00:00"
    (desk / "data" / "daily_proposers_state.json").write_text(json.dumps({
        "anomaly_factory": {"last_ok_at": old, "last_status": "KILLED_AT_BOUND"},
        "plumbing_miner": {"last_ok_at": fresh, "last_status": "OK"},
        "gone": {"last_status": "ABSENT"}}), "utf-8")
    now = seat_clocks._iso_ts("2027-01-15T12:00:00+00:00")
    red = seat_clocks.red_proposers(now, desk, ["anomaly_factory", "plumbing_miner", "gone",
                                                "tail_alpha_search"])
    assert [r["seat"] for r in red] == ["anomaly_factory", "tail_alpha_search"]


def test_never_stale_publishes_the_red_seats(tmp_path, monkeypatch):
    sys.path.insert(0, str(_ROOT / "ops"))
    import never_stale
    health = tmp_path / "process_health.json"
    health.write_text(json.dumps({"processes": []}), "utf-8")
    monkeypatch.setattr(never_stale, "HEALTH", health)
    monkeypatch.setattr(never_stale, "_capital_faults", lambda: [])
    monkeypatch.setattr(seat_clocks, "report", lambda: {
        "status": "RED", "n_red": 1, "red": [{"seat": "cot", "why": "silent 7h"}]})
    doc = never_stale.run(apply=False)
    assert doc["status"] == "NEEDS_HUMAN"
    assert doc["seat_clocks"]["red"][0]["seat"] == "cot"


def test_the_leg_is_on_the_hourly_roster():
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"vps_seat_clock", "side_channels/vps_seat_clock.py"' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["vps_seat_clock"] == "information"
