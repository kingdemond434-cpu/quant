"""Box resource governor: release and risk get CPU, research yields, money is never touched."""

from __future__ import annotations

import json
import runpy
from datetime import UTC, datetime
from pathlib import Path

RG = runpy.run_path(str(Path(__file__).resolve().parents[2] / "ops" / "resource_governor.py"))
Proc, plan, tick, classify = RG["Proc"], RG["plan"], RG["tick"], RG["classify"]
IDLE, BELOW, NORMAL, HIGH = RG["IDLE"], RG["BELOW_NORMAL"], RG["NORMAL"], RG["HIGH"]

GATE = r"powershell.exe -File C:\ProgramData\QuantBox\bin\workflow_gate.ps1"
ADOPT = r"powershell.exe -File C:\opt\quant\desks\mt5\scripts\Adopt-And-Seal.ps1"
MINER = r"python.exe C:\opt\quant\desks\mt5\research\department_resident.py"
E8 = r"python.exe C:\opt\quant\desks\mt5\prop\e8_executor.py"
TERM = r"C:\MT5\terminal64.exe /portable"


def _p(pid: int, cmd: str, prio: int = BELOW, ppid: int = 0, started: float = 0.0,
       name: str = "") -> object:  # fmt: skip
    return Proc(pid, ppid, cmd, prio, started, name)


def test_money_is_never_touched_at_any_load() -> None:
    procs = [_p(10, TERM, prio=BELOW), _p(11, E8, prio=NORMAL), _p(12, "python.exe x", ppid=11)]
    for mode in ("NORMAL", "THROTTLE"):
        out = plan(procs, mode, {})
        assert not set(out.set_to) & {10, 11, 12}, mode  # the executor's child too
    assert classify(TERM) == classify(E8) == "LIVE"


def test_the_gate_and_adoption_trees_are_reserved_above_research_but_never_above_normal() -> None:
    procs = [_p(1, GATE), _p(2, "gh.exe api repos/o/r/pulls", ppid=1),
             _p(3, "git.exe fetch", ppid=1),
             _p(4, ADOPT), _p(5, "git.exe fetch origin", ppid=4), _p(6, MINER),
             _p(7, r"python audit_gate.py --sweep --box", prio=HIGH)]  # fmt: skip
    out = plan(procs, "NORMAL", {})
    assert {1, 2, 3, 4, 5} <= set(out.set_to) and all(
        out.set_to[p] == NORMAL for p in (1, 2, 3, 4, 5)
    )
    assert 6 not in out.set_to  # research below the bound keeps its class
    assert 7 not in out.set_to  # already above NORMAL: never touched, never raised further


def test_overload_sends_research_to_idle_and_recovery_restores_its_own_class() -> None:
    deep = MINER.replace("department_resident", "deepening_worker")
    procs = [_p(6, MINER, prio=BELOW), _p(8, deep,
                                         prio=NORMAL), _p(1, GATE)]  # fmt: skip
    out = plan(procs, "THROTTLE", {})
    assert out.set_to[6] == IDLE and out.set_to[8] == IDLE and out.set_to[1] == NORMAL
    lowered = {6: BELOW, 8: NORMAL}
    idle_now = [_p(6, MINER, prio=IDLE), _p(8, procs[1].cmd, prio=IDLE)]
    back = plan(idle_now, "NORMAL", lowered)
    assert back.restore == {6: BELOW, 8: NORMAL} and not back.set_to


def test_fan_out_beyond_the_bound_yields_newest_first() -> None:
    n = RG["MAX_RESEARCH_PROCS"]
    procs = [_p(100 + i, MINER, started=float(i)) for i in range(n + 5)]
    out = plan(procs, "NORMAL", {})
    assert sorted(out.set_to) == [100 + i for i in range(n, n + 5)]
    assert all(v == IDLE for v in out.set_to.values())


def test_unclassified_processes_are_never_touched() -> None:
    procs = [_p(1, "svchost.exe -k netsvcs"), _p(2, "python.exe C:\\tools\\other.py")]
    for mode in ("NORMAL", "THROTTLE"):
        assert not plan(procs, mode, {}).set_to


def test_tick_throttles_after_sustained_overload_and_recovers(tmp_path: Path) -> None:
    state, report = tmp_path / "s.json", tmp_path / "r.json"
    procs = [_p(6, MINER)]
    calls: list[tuple[int, int]] = []

    def setter(pid: int, prio: int) -> None:
        calls.append((pid, prio))
        procs[0] = _p(6, MINER, prio=prio)

    def run(cpu: float) -> dict:
        return tick(lambda: (list(procs), cpu, 40.0), setter, state, report,
                    now=lambda: datetime(2026, 11, 4, tzinfo=UTC))  # fmt: skip

    assert run(99)["mode"] == "NORMAL" and run(99)["mode"] == "NORMAL"
    assert run(99)["mode"] == "THROTTLE" and calls == [(6, IDLE)]
    assert run(90)["mode"] == "THROTTLE"  # between the thresholds: hold
    run(50), run(50)
    doc = run(50)
    assert doc["mode"] == "NORMAL" and calls[-1] == (6, BELOW)  # its own class back
    assert json.loads(report.read_text())["cpu_pct"] == 50.0


def test_low_ram_is_overload_too_and_a_refused_change_is_reported(tmp_path: Path) -> None:
    procs = [_p(6, MINER)]
    for _ in range(3):
        doc = tick(lambda: (procs, 10.0, 1.0), lambda pid, prio: "AccessDenied: no",
                   tmp_path / "s.json", tmp_path / "r.json")  # fmt: skip
    assert doc["mode"] == "THROTTLE" and doc["errors"] == {"6": "AccessDenied: no"}


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    def boom(pid: int, prio: int) -> None:
        raise AssertionError("dry run touched a process")

    doc = tick(lambda: ([_p(1, GATE)], 99.0, 40.0), boom, tmp_path / "s.json", tmp_path / "r.json",
               dry=True)  # fmt: skip
    assert doc["dry_run"] and doc["actions"] and not (tmp_path / "s.json").exists()


def test_a_recycled_pid_is_not_a_parent() -> None:
    """Windows reuses pids: a gate that started AFTER a miner whose old parent pid it took never
    lends that miner its reserved class."""
    procs = [_p(1, GATE, started=100.0), _p(6, MINER, ppid=1, started=50.0)]
    assert 6 not in plan(procs, "NORMAL", {}).set_to


JUDGE = r"python.exe C:\opt\quant\scripts\run_sharded_gauntlet.py --shards 8"


def test_the_judge_and_its_workers_are_never_touched() -> None:
    """zuck 10-29 reserved the judge 8 cores; judge_priority.py owns its class, not this."""
    procs = [_p(20, JUDGE), _p(21, "python.exe -c from multiprocessing.spawn import spawn_main",
                               ppid=20, started=1.0), _p(6, MINER)]  # fmt: skip
    out = plan(procs, "THROTTLE", {})
    assert 20 not in out.set_to and 21 not in out.set_to and out.set_to[6] == IDLE
    assert out.classes["JUDGE"] == 2


def test_an_unreadable_parent_shields_its_tree_and_is_counted() -> None:
    """An Administrator token cannot read SYSTEM command lines: an unreadable SYSTEM python could
    be the gate, so nothing under it is lowered. svchost (the scheduler) shields nothing."""
    procs = [_p(30, "", prio=RG["UNKNOWN"], name="python.exe"),
             _p(31, MINER, ppid=30, started=1.0),
             _p(40, "", prio=RG["UNKNOWN"], name="svchost.exe"),
             _p(41, MINER, ppid=40, started=1.0)]  # fmt: skip
    out = plan(procs, "THROTTLE", {})
    assert set(out.set_to) == {41}
    assert out.classes["UNREADABLE"] == 2 and out.classes["SHIELDED"] == 1
    assert classify("") == "UNREADABLE"


def test_an_unknown_class_is_never_written() -> None:
    procs = [_p(1, GATE, prio=RG["UNKNOWN"]), _p(6, MINER, prio=RG["UNKNOWN"])]
    assert not plan(procs, "THROTTLE", {}).set_to
