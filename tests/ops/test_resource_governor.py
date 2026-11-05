"""Box resource governor: release and risk get CPU first, research is never lowered, money and
the judge are never touched."""

from __future__ import annotations

import json
import runpy
from datetime import UTC, datetime
from pathlib import Path

RG = runpy.run_path(str(Path(__file__).resolve().parents[2] / "ops" / "resource_governor.py"))
Proc, plan, tick, classify = RG["Proc"], RG["plan"], RG["tick"], RG["classify"]
IDLE, BELOW, NORMAL, HIGH = RG["IDLE"], RG["BELOW_NORMAL"], RG["NORMAL"], RG["HIGH"]
UNKNOWN = RG["UNKNOWN"]

GATE = r"powershell.exe -File C:\ProgramData\QuantBox\bin\workflow_gate.ps1"
ADOPT = r"powershell.exe -File C:\opt\quant\desks\mt5\scripts\Adopt-And-Seal.ps1"
MINER = r"python.exe C:\opt\quant\desks\mt5\research\department_resident.py"
E8 = r"python.exe C:\opt\quant\desks\mt5\prop\e8_executor.py"
TERM = r"C:\MT5\terminal64.exe /portable"
JUDGE = r"python.exe C:\opt\quant\scripts\run_sharded_gauntlet.py --shards 8"


def _p(pid: int, cmd: str, prio: int = BELOW, ppid: int = 0, started: float = 0.0,
       name: str = "") -> object:  # fmt: skip
    return Proc(pid, ppid, cmd, prio, started, name)


def test_money_is_never_touched_at_any_load() -> None:
    procs = [_p(10, TERM, prio=BELOW), _p(11, E8, prio=NORMAL), _p(12, "python.exe x", ppid=11)]
    for mode in ("NORMAL", "THROTTLE"):
        out = plan(procs, mode)
        assert not set(out.set_to) & {10, 11, 12}, mode  # the executor's child too
    assert classify(TERM) == classify(E8) == "LIVE"


def test_the_gate_and_adoption_trees_are_reserved_above_research_but_never_above_normal() -> None:
    procs = [_p(1, GATE), _p(2, "gh.exe api repos/o/r/pulls", ppid=1),
             _p(3, "git.exe fetch", ppid=1),
             _p(4, ADOPT), _p(5, "git.exe fetch origin", ppid=4), _p(6, MINER),
             _p(7, r"python audit_gate.py --sweep --box", prio=HIGH)]  # fmt: skip
    out = plan(procs, "NORMAL")
    assert set(out.set_to) == {1, 2, 3, 4, 5}
    assert all(v == NORMAL for v in out.set_to.values())
    assert 7 not in out.set_to  # already above NORMAL: never touched, never raised further


def test_research_is_never_lowered_under_overload_or_fan_out() -> None:
    """Auditor MF1 (never-throttle-mining, zuck 2026-09-29): an overload or a fan-out is
    reported, never acted on. No research pid is set below the class it started at."""
    n = RG["MAX_RESEARCH_PROCS"]
    procs = [_p(100 + i, MINER, prio=(BELOW, NORMAL)[i % 2], started=float(i))
             for i in range(n + 5)] + [_p(1, GATE)]  # fmt: skip
    for mode in ("NORMAL", "THROTTLE"):
        out = plan(procs, mode)
        assert set(out.set_to) == {1}, mode
    assert plan(procs, "THROTTLE").would_yield == n + 5
    assert plan(procs, "NORMAL").would_yield == 5


def test_unclassified_processes_are_never_touched() -> None:
    procs = [_p(1, "svchost.exe -k netsvcs"), _p(2, "python.exe C:\\tools\\other.py")]
    for mode in ("NORMAL", "THROTTLE"):
        assert not plan(procs, mode).set_to


def test_tick_reports_overload_and_writes_only_raises(tmp_path: Path) -> None:
    state, report = tmp_path / "s.json", tmp_path / "r.json"
    procs = [_p(6, MINER), _p(1, GATE)]
    calls: list[tuple[int, int]] = []

    def setter(pid: int, prio: int) -> None:
        calls.append((pid, prio))

    def run(cpu: float) -> dict:
        return tick(lambda: (list(procs), cpu, 40.0), setter, state, report,
                    now=lambda: datetime(2026, 11, 4, tzinfo=UTC))  # fmt: skip

    run(99), run(99)
    doc = run(99)
    assert doc["mode"] == "THROTTLE" and doc["report_only"]["overload"]
    assert doc["report_only"]["would_yield"] == 1
    assert "NOT applied" in doc["report_only"]["missed_growth"]
    assert calls and all(c == (1, NORMAL) for c in calls)  # the miner was never written
    run(50), run(50)
    assert run(50)["mode"] == "NORMAL"
    assert json.loads(report.read_text())["cpu_pct"] == 50.0


def test_low_ram_is_overload_too_and_a_refused_change_is_reported(tmp_path: Path) -> None:
    procs = [_p(1, GATE)]
    for _ in range(3):
        doc = tick(lambda: (procs, 10.0, 1.0), lambda pid, prio: "AccessDenied: no",
                   tmp_path / "s.json", tmp_path / "r.json")  # fmt: skip
    assert doc["mode"] == "THROTTLE" and doc["errors"] == {"1": "AccessDenied: no"}


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    def boom(pid: int, prio: int) -> None:
        raise AssertionError("dry run touched a process")

    doc = tick(lambda: ([_p(1, GATE)], 99.0, 40.0), boom, tmp_path / "s.json", tmp_path / "r.json",
               dry=True)  # fmt: skip
    assert doc["dry_run"] and doc["actions"] and not (tmp_path / "s.json").exists()


def test_a_recycled_pid_is_not_a_parent() -> None:
    """Windows reuses pids: a gate that started AFTER a process whose old parent pid it took
    never lends that process its reserved class."""
    procs = [_p(1, GATE, started=100.0), _p(6, "python.exe other.py", ppid=1, started=50.0)]
    assert 6 not in plan(procs, "NORMAL").set_to


def test_the_judge_and_its_workers_are_never_touched() -> None:
    """zuck 10-29 reserved the judge 8 cores; judge_priority.py owns its class, not this."""
    procs = [_p(20, JUDGE), _p(21, "python.exe -c from multiprocessing.spawn import spawn_main",
                               ppid=20, started=1.0)]  # fmt: skip
    for mode in ("NORMAL", "THROTTLE"):
        assert not plan(procs, mode).set_to
    assert plan(procs, "NORMAL").classes["JUDGE"] == 2


def test_an_unreadable_parent_shields_its_tree_and_is_counted() -> None:
    """An Administrator token cannot read SYSTEM command lines: an unreadable SYSTEM python
    could be the gate, so nothing under it counts as research. svchost shields nothing."""
    procs = [_p(30, "", prio=UNKNOWN, name="python.exe"),
             _p(31, MINER, ppid=30, started=1.0),
             _p(40, "", prio=UNKNOWN, name="svchost.exe"),
             _p(41, MINER, ppid=40, started=1.0)]  # fmt: skip
    out = plan(procs, "THROTTLE")
    assert out.classes["UNREADABLE"] == 2 and out.classes["SHIELDED"] == 1
    assert out.classes["RESEARCH"] == 1 and not out.set_to
    assert classify("") == "UNREADABLE"


def test_an_unknown_class_is_never_written() -> None:
    assert not plan([_p(1, GATE, prio=UNKNOWN)], "NORMAL").set_to


# ------------------------------------------------------------------ judge cores (rule 4)
ALL = tuple(range(18))
JUDGE_CORES, RESEARCH_CORES = RG["JUDGE_CORES"], RG["RESEARCH_CORES"]


def _a(pid: int, cmd: str, aff: tuple[int, ...] | None = ALL, **kw: object) -> object:
    p = _p(pid, cmd, **kw)  # type: ignore[arg-type]
    p.affinity = aff
    return p


def test_the_split_is_zucks_8_for_the_judge_and_10_for_research() -> None:
    assert len(JUDGE_CORES) == 8 and len(RESEARCH_CORES) == 10
    assert not set(JUDGE_CORES) & set(RESEARCH_CORES)
    assert set(JUDGE_CORES) | set(RESEARCH_CORES) == set(ALL)
    assert {16, 17} <= set(RESEARCH_CORES) and set(range(8)) <= set(RESEARCH_CORES)


def test_while_the_judge_runs_research_is_held_off_its_cores_and_nothing_else_moves() -> None:
    procs = [_a(20, JUDGE), _a(21, "python.exe -c spawn_main", ppid=20, started=1.0),
             _a(6, MINER, prio=NORMAL), _a(7, MINER, aff=(16, 17)), _a(8, MINER, aff=(9, 10)),
             _a(1, GATE), _a(11, E8), _a(12, "svchost.exe -k netsvcs"),
             _a(13, MINER, aff=None)]  # fmt: skip
    out = plan(procs, "NORMAL")
    assert out.reserve.startswith("on")
    assert out.pin == {6: RESEARCH_CORES, 8: RESEARCH_CORES}  # 7 already inside: left alone
    assert not set(out.pin) & {20, 21, 1, 11, 12, 13}  # judge, gate, money, other, unreadable
    assert all(set(c) <= set(RESEARCH_CORES) for c in out.pin.values())
    assert 6 not in out.set_to  # research keeps its priority


def test_no_judge_gives_each_narrowed_process_its_own_affinity_back(tmp_path: Path) -> None:
    state, report = tmp_path / "s.json", tmp_path / "r.json"
    pins: list[tuple[int, tuple[int, ...]]] = []
    procs = [_a(20, JUDGE), _a(6, MINER, started=5.0), _a(7, MINER, started=6.0)]

    def pinner(pid: int, cores: tuple[int, ...]) -> None:
        pins.append((pid, cores))
        next(p for p in procs if p.pid == pid).affinity = cores

    def run() -> dict:
        return tick(lambda: (list(procs), 50.0, 40.0), lambda *_: None, state, report,
                    pinner=pinner, ncpu=18)  # fmt: skip

    doc = run()
    assert sorted(pins) == [(6, RESEARCH_CORES), (7, RESEARCH_CORES)]
    assert doc["judge_cores"]["narrowed"] == 2
    pins.clear()
    assert run()["affinity"] == [] and not pins  # already held: nothing rewritten
    procs.pop(0)  # the judge finished
    procs[1].affinity = (0, 1)  # something else re-pinned 7 since: no longer ours
    doc = run()
    assert pins == [(6, ALL)] and doc["judge_cores"]["state"].startswith("off")
    assert json.loads(state.read_text())["narrowed"] == {}


def test_a_recycled_pid_never_gets_someone_elses_affinity_back(tmp_path: Path) -> None:
    state = tmp_path / "s.json"
    state.write_text(
        json.dumps({"narrowed": {"6:5.000": {"orig": list(ALL), "set": list(RESEARCH_CORES)}}})
    )
    procs = [_a(6, MINER, aff=RESEARCH_CORES, started=99.0)]  # same pid, a new process
    doc = tick(lambda: (procs, 10.0, 40.0), lambda *_: None, state, tmp_path / "r.json",
               pinner=lambda *_: None, ncpu=18)  # fmt: skip
    assert doc["affinity"] == []


def test_another_core_count_pins_nothing() -> None:
    procs = [_a(20, JUDGE, aff=tuple(range(36))), _a(6, MINER, aff=tuple(range(36)))]
    out = plan(procs, "NORMAL", ncpu=36)
    assert not out.pin and out.reserve.startswith("off: 36 cores")


def test_dry_run_pins_nothing_and_a_refused_pin_is_reported(tmp_path: Path) -> None:
    procs = [_a(20, JUDGE), _a(6, MINER)]

    def boom(pid: int, cores: tuple[int, ...]) -> None:
        raise AssertionError("dry run pinned a process")

    doc = tick(lambda: (procs, 10.0, 40.0), lambda *_: None, tmp_path / "s.json",
               tmp_path / "r.json", dry=True, pinner=boom, ncpu=18)  # fmt: skip
    assert doc["affinity"] and doc["dry_run"]
    doc = tick(lambda: (procs, 10.0, 40.0), lambda *_: None, tmp_path / "s.json",
               tmp_path / "r.json", pinner=lambda *_: "AccessDenied: no", ncpu=18)  # fmt: skip
    assert doc["errors"] == {"6": "AccessDenied: no"} and doc["judge_cores"]["narrowed"] == 0


def test_research_at_normal_is_named_with_its_parent() -> None:
    """Hourly pass P78: installers register miners at Priority 7 (BELOW_NORMAL), so research at
    NORMAL came from somewhere else. The report names it and who started it."""
    procs = [
        _a(5, r"powershell.exe -File C:\opt\quant\run_research.ps1", prio=NORMAL),
        _a(6, MINER, prio=NORMAL, ppid=5, started=1.0),
        _a(7, MINER),
    ]
    out = plan(procs, "NORMAL")
    assert out.research_by_class == {"NORMAL": 1, "BELOW_NORMAL": 1}
    assert out.research_high == [{"pid": 6, "class": "NORMAL", "cmd": MINER,
                                  "parent": procs[0].cmd}]  # fmt: skip
