"""The holder an End leaves behind is reaped, and only when it is PROVEN to be the task's own
(Audit ruling 2026-11-25 12:17Z).

Box 11-24..25: MT5-MergeDocket's action is `cmd /c ... merge_hypotheses.py`. Its python (pid 16808)
sat 17.5 h at 0.01 core holding the merge_hypotheses job lock, so every next run was refused. A
`schtasks /End` ends the cmd.exe the scheduler started and can leave that python alive -- the
End+Run would cure nothing. After the End, the holder's tree is terminated only when: the task is a
research/ops lane, it declares its lock, before the End the holder was alive with the lock row's
create_time and its parent ran the task's OWN registered action, and after the End the same holder
(same pid, same create_time) still lives. Otherwise nothing is killed and Claude is alerted.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_desk_self_heal as rheal  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
TASK = "MT5-MergeDocket"
ACTION = ('cmd.exe /d /s /c "cd /d C:\\opt\\quant\\desks\\mt5 && '
          '"C:\\Program Files\\Python314\\python.exe" -u -W ignore '
          'research\\merge_hypotheses.py >> logs\\MT5-MergeDocket.log 2>&1"')
CT = 1_764_006_241.0


def _lock(root: Path, **row) -> None:
    p = root / rheal.LOCK_DIR / "merge_hypotheses.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pid": 16808, "create_time": CT, **row}), "utf-8")


def _info(ct=CT, parent=ACTION):
    return lambda pid: {"pid": pid, "create_time": ct, "ppid": 4948, "parent_cmdline": parent}


def _before(root, **kw):
    return rheal.holder_before_end(root, TASK, proc_info=kw.get("info", _info()),
                                   task_action=kw.get("action", lambda t: ACTION))


def test_a_proven_holder_that_survives_the_end_is_reaped(tmp_path):
    _lock(tmp_path)
    snap = _before(tmp_path)
    assert snap["ok"] and snap["pid"] == 16808
    killed = []
    r = rheal.reap_after_end(snap, proc_info=_info(),
                             kill_tree=lambda pid, ct: killed.append((pid, ct)) or True)
    assert killed == [(16808, CT)]
    assert r["reaped"] and r["alert"]


def test_a_holder_the_end_already_took_is_left_alone(tmp_path):
    _lock(tmp_path)
    snap = _before(tmp_path)
    killed = []
    r = rheal.reap_after_end(snap, proc_info=lambda pid: None,
                             kill_tree=lambda *a: killed.append(a) or True)
    assert killed == [] and not r["reaped"] and not r["alert"]


def test_a_reused_pid_is_never_killed(tmp_path):
    _lock(tmp_path)
    snap = _before(tmp_path, info=_info(ct=CT + 600))
    assert not snap["ok"] and snap["alert"]
    killed = []
    r = rheal.reap_after_end(snap, kill_tree=lambda *a: killed.append(a) or True)
    assert killed == [] and r["alert"] and not r["reaped"]


def test_a_pid_reused_between_the_proofs_and_the_reap_is_never_killed(tmp_path):
    _lock(tmp_path)
    snap = _before(tmp_path)
    killed = []
    r = rheal.reap_after_end(snap, proc_info=_info(ct=CT + 30),
                             kill_tree=lambda *a: killed.append(a) or True)
    assert killed == [] and r["alert"] and not r["reaped"]


def test_a_holder_from_another_task_is_never_killed(tmp_path):
    """MT5-Compiler also runs merge_hypotheses under the same lock: its python is not
    MergeDocket's, so ending MergeDocket must never kill it."""
    _lock(tmp_path)
    other = 'cmd.exe /d /s /c "... hourly_cycle.py --lane compiler"'
    snap = _before(tmp_path, info=_info(parent=other))
    assert not snap["ok"] and snap["alert"]


def test_no_action_readable_means_no_kill(tmp_path):
    _lock(tmp_path)
    snap = _before(tmp_path, action=lambda t: None)
    assert not snap["ok"]


def test_a_lock_without_create_time_cannot_prove_anything(tmp_path):
    p = tmp_path / rheal.LOCK_DIR / "merge_hypotheses.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pid": 16808}), "utf-8")
    snap = _before(tmp_path)
    assert not snap["ok"] and snap["alert"]


def test_no_lock_means_nothing_to_reap(tmp_path):
    snap = _before(tmp_path)
    assert not snap["ok"] and not snap.get("alert")


def test_live_and_undeclared_tasks_never_reach_a_kill(tmp_path, monkeypatch):
    _lock(tmp_path)
    monkeypatch.setitem(rheal.TASK_LOCKS, "MT5-FTMO-Executor", "merge_hypotheses")
    for task in ("MT5-FTMO-Executor", "MT5-Gauntlet", "MT5-E8-Live"):
        snap = rheal.holder_before_end(tmp_path, task, proc_info=_info(),
                                       task_action=lambda t: ACTION)
        assert not snap["ok"], task
    assert all(not rheal.heal._LIVE_TASK.search(t) for t in rheal.TASK_LOCKS
               if t != "MT5-FTMO-Executor")


def _write_docket(root: Path, age_h: float) -> None:
    p = root / "desks/mt5/data/hypotheses/external_survivors.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", "utf-8")
    t = (NOW - timedelta(hours=age_h)).timestamp()
    os.utime(p, (t, t))


def test_the_actuator_reaps_after_a_successful_end_and_logs_it(tmp_path):
    _write_docket(tmp_path, 22)
    calls: list[tuple[str, str]] = []
    doc = rheal.run(root=tmp_path, apply=True, out=tmp_path / "out.json",
                    ledger_path=tmp_path / "ledger.json", now=NOW,
                    measure_headroom=False, run_pass=False,
                    run_task=lambda t: calls.append(("run", t)) or True,
                    task_running=lambda t: True,
                    end_task=lambda t: calls.append(("end", t)) or True,
                    before_end=lambda t: {"task": t, "lock": "merge_hypotheses", "ok": True,
                                          "pid": 16808, "create_time": CT},
                    after_end=lambda s: calls.append(("reap", s["task"])) or
                    {**{k: s[k] for k in ("task", "lock", "pid", "create_time")},
                     "reaped": True, "alert": True, "why": "test"})
    docket = [c for c in calls if c[1] == TASK]
    assert docket == [("end", TASK), ("reap", TASK), ("run", TASK)]
    assert doc["reaped"] and doc["reaped"][0]["reaped"]
    ledger = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
    assert ledger[rheal.REAP_KEY][0]["pid"] == 16808


def test_a_failed_end_reaps_nothing(tmp_path):
    _write_docket(tmp_path, 22)
    calls: list[tuple[str, str]] = []
    rheal.run(root=tmp_path, apply=True, out=tmp_path / "out.json",
              ledger_path=tmp_path / "ledger.json", now=NOW,
              measure_headroom=False, run_pass=False,
              run_task=lambda t: calls.append(("run", t)) or True,
              task_running=lambda t: True,
              end_task=lambda t: False,
              before_end=lambda t: {"task": t, "lock": "merge_hypotheses", "ok": True,
                                    "pid": 16808, "create_time": CT},
              after_end=lambda s: calls.append(("reap", s["task"])) or {})
    assert [c for c in calls if c[1] == TASK] == []
