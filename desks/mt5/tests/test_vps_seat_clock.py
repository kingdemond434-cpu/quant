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
    monkeypatch.setattr(vsc, "vps_shipped_ts", lambda *a, **k: ({}, "test: no transport ref"))
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


# ------------------------------------------------------------- PR #524 audit (2026-10-29)

def test_a_killed_unit_gets_a_longer_bound_next_time_capped(desk):
    base = vsc.bound_s("seed:darwinex", {})
    assert base == vsc.SEED_BOUND_S
    grown = vsc.bound_s("seed:darwinex", {"killed_at_bound_s": base})
    assert grown == vsc.BOUND_GROWTH * base
    assert vsc.bound_s("seed:darwinex", {"killed_at_bound_s": 10 * base}) == vsc.BOUND_CAP_S
    assert vsc.bound_s("external:cot", {"killed_at_bound_s": vsc.EXTERNAL_BOUND_S}) == \
        vsc.BOUND_GROWTH * vsc.EXTERNAL_BOUND_S


def test_run_pass_records_the_killed_bound_and_clears_it_on_success(desk):
    def killer(cmd, timeout_s):
        unit = cmd[cmd.index("--unit") + 1]
        if unit == "seed:global_frontier":
            return None, ""
        return 0, vsc.RESULT_PREFIX + json.dumps({"status": "OK", "rows": 1})

    vsc.run_pass(5000.0, runner=killer, now=NOW)
    st = json.loads(vsc.STATE.read_text("utf-8"))
    assert st["seed:global_frontier"]["killed_at_bound_s"] == vsc.SEED_BOUND_S
    assert vsc.bound_s("seed:global_frontier", st["seed:global_frontier"]) > vsc.SEED_BOUND_S
    assert "killed_at_bound_s" not in st["seed:darwinex"]

    def ok(cmd, timeout_s):
        return 0, vsc.RESULT_PREFIX + json.dumps({"status": "OK", "rows": 1})

    vsc.STATE.write_text(json.dumps({"seed:global_frontier": st["seed:global_frontier"] | {
        "last_started_at": None}}), "utf-8")
    vsc.run_pass(5000.0, runner=ok, now=NOW)
    st2 = json.loads(vsc.STATE.read_text("utf-8"))
    assert "killed_at_bound_s" not in st2["seed:global_frontier"]


def test_the_box_stands_down_when_the_vps_transport_shows_it_fetched(desk):
    # nothing on disk for darwinex or cot (adoption broken) -- but the VPS shipped both
    shipped = {"darwinex": NOW - 1800, "cot": NOW - 4 * 3600}
    p = vsc.plan({}, NOW, desk, shipped=shipped)
    assert "seed:darwinex" in p["fresh"] and "seed:darwinex" in p["vps_fetched"]
    assert "external:cot" in p["due"]          # the VPS shipped it outside the cadence
    assert "seed:fxblue" in p["due"] and "seed:fxblue" not in p["vps_fetched"]
    # regional_survivors stands down on ANY of its platform seats
    p2 = vsc.plan({}, NOW, desk, shipped={"amarkets": NOW - 60})
    assert "seed:regional_survivors" in p2["vps_fetched"]


def test_run_pass_reports_a_vps_fetched_unit_and_does_not_run_it(desk, monkeypatch):
    monkeypatch.setattr(vsc, "vps_shipped_ts", lambda *a, **k: (
        {"darwinex": NOW - 600}, "test ref"))
    calls: list[str] = []

    def runner(cmd, timeout_s):
        calls.append(cmd[cmd.index("--unit") + 1])
        return 0, vsc.RESULT_PREFIX + json.dumps({"status": "OK", "rows": 1})

    rep = vsc.run_pass(5000.0, runner=runner, now=NOW)
    assert rep["units"]["seed:darwinex"]["status"] == "VPS_FETCHED"
    assert "seed:darwinex" not in calls
    doc = json.loads(vsc.REPORT.read_text("utf-8"))
    assert doc["vps_fetched"] == ["seed:darwinex"]
    assert doc["vps_shipped"]["basis"] == "test ref"
    assert "github.com/kingdemond434-cpu/quant" in doc["rails"]["user_agent"]


def test_vps_shipped_ts_reads_the_transport_ref_and_says_when_it_cannot():
    class R:
        returncode = 0
        stderr = ""
        stdout = ("@1800000000\n\ndesks/mt5/data/intelligence/darwinex/discoveries_x.json\n"
                  "@1799990000\n\ndesks/mt5/data/intelligence/darwinex/discoveries_y.json\n"
                  "data/intelligence/cot/discoveries_z.json\n"
                  "desks/mt5/data/intelligence/latest_discoveries.json\n")

    got, basis = vsc.vps_shipped_ts(runner=lambda *a, **k: R())
    assert got == {"darwinex": 1_800_000_000.0, "cot": 1_799_990_000.0}
    assert "intel-ship/send" in basis

    class Bad:
        returncode = 128
        stdout = ""
        stderr = "fatal: bad revision"

    got, basis = vsc.vps_shipped_ts(runner=lambda *a, **k: Bad())
    assert got == {} and basis.startswith("UNMEASURED")

    def boom(*a, **k):
        raise FileNotFoundError("git")

    got, basis = vsc.vps_shipped_ts(runner=boom)
    assert got == {} and basis.startswith("UNMEASURED")


def test_the_child_installs_the_rails_before_any_miner_runs(monkeypatch):
    import box_rails
    import seed_miners
    seen: dict[str, object] = {}

    def fake_run_and_save(only=None, tail=True):
        seen["installed"] = box_rails._STATE["installed"]
        seen["env"] = os.environ.get(box_rails.ENV)
        return {}

    monkeypatch.setattr(seed_miners, "run_and_save", fake_run_and_save)
    monkeypatch.setattr(box_rails, "install", lambda walled=None: box_rails._STATE.update(
        {"installed": True}))
    monkeypatch.delenv(box_rails.ENV, raising=False)
    try:
        assert vsc.run_unit("seed:darwinex")["status"] == "OK"
    finally:
        box_rails._STATE["installed"] = False
        os.environ.pop(box_rails.ENV, None)
    assert seen == {"installed": True, "env": "1"}


def test_spawned_external_miner_children_reinstall_the_rails(monkeypatch):
    import box_rails
    import run_all_miners
    calls: list[str] = []
    monkeypatch.setattr(box_rails, "install", lambda walled=None: calls.append("install"))

    class Q:
        def __init__(self):
            self.items = []

        def put(self, x):
            self.items.append(x)

    monkeypatch.setenv("QUANT_BOX_RAILS", "1")
    q = Q()
    run_all_miners._run_miner_inner("x", lambda: calls.append("mine") or [], q)
    assert calls == ["install", "mine"] and q.items == [("ok", [])]
    monkeypatch.delenv("QUANT_BOX_RAILS")
    calls.clear()
    run_all_miners._run_miner_inner("x", lambda: calls.append("mine") or [], Q())
    assert calls == ["mine"]                    # the VPS path is untouched


def test_an_unreadable_roster_is_unmeasured_never_an_empty_pass(tmp_path):
    desk = tmp_path / "desks" / "mt5"
    (desk / "research").mkdir(parents=True)
    with pytest.raises(seat_clocks.Unmeasured, match="cannot parse"):
        seat_clocks._daily_proposers(desk)          # file absent
    with pytest.raises(seat_clocks.Unmeasured, match="cannot parse"):
        seat_clocks._daily_steps(desk)
    (desk / "research" / "daily_cycle.py").write_text("def broken(:\n", "utf-8")
    with pytest.raises(seat_clocks.Unmeasured):
        seat_clocks._daily_proposers(desk)
    (desk / "research" / "daily_cycle.py").write_text(
        "PROPOSERS: tuple[str, ...] = ()\nSTEPS = ()\n", "utf-8")
    with pytest.raises(seat_clocks.Unmeasured, match="empty"):
        seat_clocks._daily_proposers(desk)
    with pytest.raises(seat_clocks.Unmeasured):
        seat_clocks._daily_steps(desk)
    (desk / "research" / "daily_cycle.py").write_text("X = 1\n", "utf-8")
    with pytest.raises(seat_clocks.Unmeasured, match="no annotated"):
        seat_clocks._daily_proposers(desk)
    with pytest.raises(seat_clocks.Unmeasured, match="no tuple"):
        seat_clocks._daily_steps(desk)
    # the real file still reads
    assert len(seat_clocks._daily_proposers(_DESK)) >= 10


def test_report_is_unmeasured_with_its_cause_when_a_roster_cannot_be_read(tmp_path,
                                                                           monkeypatch):
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    monkeypatch.setattr(seat_clocks, "red_seats", lambda now=None, desk=None: [])
    rep = seat_clocks.report(NOW, desk)
    assert rep["status"] == "UNMEASURED" and rep["red"] == []
    checks = {u["check"]: u["error"] for u in rep["unmeasured"]}
    assert set(checks) == {"proposers", "daily_steps"}
    assert all("cannot parse" in e for e in checks.values())


def test_never_stale_does_not_read_an_unmeasured_seat_check_as_ok(tmp_path, monkeypatch):
    sys.path.insert(0, str(_ROOT / "ops"))
    import never_stale
    health = tmp_path / "process_health.json"
    health.write_text(json.dumps({"processes": []}), "utf-8")
    monkeypatch.setattr(never_stale, "HEALTH", health)
    monkeypatch.setattr(never_stale, "_capital_faults", lambda: [])
    monkeypatch.setattr(seat_clocks, "report", lambda: {
        "status": "UNMEASURED", "red": [],
        "unmeasured": [{"check": "proposers", "error": "Unmeasured: cannot parse"}]})
    assert never_stale.run(apply=False)["status"] == "NEEDS_HUMAN"

    def boom():
        raise ImportError("no seat_clocks")

    monkeypatch.setattr(seat_clocks, "report", boom)
    doc = never_stale.run(apply=False)
    assert doc["status"] == "NEEDS_HUMAN"
    assert doc["seat_clocks"]["status"] == "UNMEASURED"
    assert "ImportError" in doc["seat_clocks"]["error"]
    monkeypatch.setattr(seat_clocks, "report", lambda: {"status": "OK", "red": []})
    assert never_stale.run(apply=False)["status"] == "OK"
