"""live_priority: live runs at ABOVE_NORMAL; raise only, never past it, never non-live."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import judge_priority as jp
from scripts import live_priority as lp

BN, N, AN, HI = jp.BELOW_NORMAL, jp.NORMAL, jp.ABOVE_NORMAL, jp.HIGH


def _row(pid, name, cmd, nice, ppid=1, t=1.0):
    return {"pid": pid, "ppid": ppid, "name": name, "cmdline": cmd, "nice": nice,
            "create_time": t}


ROWS = [
    _row(10, "terminal64.exe", ["terminal64.exe"], BN),
    _row(11, "python.exe", ["python.exe", "C:/q/prop/e8_executor.py"], N),
    _row(12, "python.exe", ["python.exe", "C:/q/prop/ftmo_follower.py"], N),
    _row(13, "python.exe", ["python.exe", "C:/q/scripts/gateway_resident.py"], AN),
    _row(14, "terminal64.exe", ["terminal64.exe"], HI),
    _row(20, "python.exe", ["python.exe", "C:/q/research/some_miner.py"], BN),
    _row(21, "python.exe", ["python.exe", "C:/q/scripts/external_gauntlet.py"], BN),
    _row(22, "notepad.exe", ["notepad.exe"], BN),
]


def test_only_live_rows_are_planned_and_only_below_target_are_raised() -> None:
    items = {i["pid"]: i["action"] for i in lp.plan(ROWS)}
    assert items == {10: "raise", 11: "raise", 12: "raise", 13: "keep", 14: "keep"}


def test_apply_sets_exactly_above_normal_and_never_lowers_or_touches_others() -> None:
    calls = []
    done = lp.apply(lp.plan(ROWS), setter=lambda pid, cls, row: calls.append((pid, cls)))
    assert sorted(calls) == [(10, AN), (11, AN), (12, AN)]
    assert all(cls == AN for _, cls in calls)  # never HIGH or REALTIME
    s = lp.summarise(done)
    assert s["verdict"] == "OK" and s["raised"] == 3 and s["already_at_or_above"] == 2


def test_a_refused_raise_is_reported_partial() -> None:
    def deny(pid, cls, row):
        raise PermissionError("AccessDenied")
    s = lp.summarise(lp.apply(lp.plan(ROWS[:1]), setter=deny))
    assert s["verdict"] == "PARTIAL" and s["failed"] == 1


def test_no_live_process_is_unmeasured_not_ok() -> None:
    assert lp.summarise(lp.apply(lp.plan(ROWS[5:]), setter=lambda *a: None))["verdict"] \
        == jp.UNMEASURED


def test_the_switch_defaults_on_and_only_explicit_false_turns_it_off(tmp_path: Path) -> None:
    p = tmp_path / "LIVE_PRIORITY.json"
    assert lp.enabled(p)["enabled"] is True
    p.write_text("{not json", "utf-8")
    assert lp.enabled(p)["enabled"] is True
    p.write_text(json.dumps({"enabled": False}), "utf-8")
    assert lp.enabled(p)["enabled"] is False


def test_ftmo_lanes_are_live_not_miners() -> None:
    for s in ("ftmo_executor.py", "ftmo_follower.py", "ftmo_venue_reader.py"):
        assert jp.own_class("python.exe", ["python.exe", f"C:/q/prop/{s}"]) == "live"


def test_raised_live_lets_the_judge_take_its_reserved_cores() -> None:
    res = {"enabled": True, "cpus": [8, 9, 10, 11, 12, 13], "why": "t"}
    r = jp.CLASS_RANK
    before = jp.judge_target([r[BN]], [r[BN], r[N]], registered_live=r[N], reserved=res)
    after = jp.judge_target([r[BN]], [r[AN], r[AN]], registered_live=r[N], reserved=res)
    assert "cpus" not in before and after["rank"] == jp.CLASS_RANK[N] and after["cpus"]


def test_the_installer_registers_one_minute_task_running_this_script() -> None:
    ps = (Path(lp.__file__).parent / "install_live_priority_task.ps1").read_text("utf-8")
    assert "scripts\\live_priority.py" in ps and "-Minutes 1" in ps
    assert "MT5-LivePriority" in ps


def test_live_recorders_are_live_and_raised_never_lowered() -> None:
    """Audit 2026-11-25 13:09Z: the tick tape (a MODULE), the E8 spread sampler and the moat
    recorder sit strictly above every research class. Box 11-25: at BELOW_NORMAL beside a
    BELOW_NORMAL test suite, the tick_recorder heartbeat gap reached 474 s."""
    rec = [
        _row(30, "python.exe", ["python.exe", "-u", "-m", "recorders.tick_recorder"], BN),
        _row(31, "python.exe", ["python.exe", "C:\\q\\desks\\mt5\\prop\\e8_spread_sampler.py"], BN),
        _row(32, "py.exe", ["py.exe", "-3", "C:\\q\\desks\\mt5\\moat\\moat_recorder.py"], N),
        _row(33, "python.exe", ["python.exe", "-m", "recorders.tick_integrity", "--days", "1"], BN),
        _row(34, "python.exe", ["python.exe", "-c", "import recorders.tick_recorder"], BN),
        _row(35, "notepad.exe", ["notepad.exe", "tick_recorder.py"], BN),
    ]
    assert [jp.own_class(r["name"], r["cmdline"]) for r in rec] == [
        "live", "live", "live", None, None, None]
    items = {i["pid"]: i["action"] for i in lp.plan(rec)}
    assert items == {30: "raise", 31: "raise", 32: "raise"}
    calls = []
    lp.apply(lp.plan(rec), setter=lambda pid, cls, row: calls.append((pid, cls)))
    assert sorted(calls) == [(30, AN), (31, AN), (32, AN)]
