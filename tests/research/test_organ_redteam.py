from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))

from research import organ_redteam as rt  # noqa: E402

MAIN = '\nif __name__ == "__main__":\n    main()\n'
NONE: frozenset[str] = frozenset()


def _cls(organ: str, src: str = MAIN, arts: tuple[str, ...] = (),
         **kw: object) -> dict[str, object]:
    kw.setdefault("money", NONE)
    kw.setdefault("tracked", NONE)
    return rt.classify(organ, src, arts, **kw)  # type: ignore[arg-type]


def test_denylist_reasons() -> None:
    assert _cls("desks/mt5/scripts/anything.py")["reason"] == "box_scripts_dir"
    assert _cls("desks/mt5/mt5desk/x.py")["reason"] == "gateway_package"
    assert _cls("ops/release/x.py")["reason"] == "ops_plumbing"
    assert _cls("desks/mt5/research/_retired/x.py")["reason"] == "retired"
    assert _cls("desks/mt5/research/m.py",
                money=frozenset({"desks/mt5/research/m.py"}))["reason"] == "money_path"
    assert _cls("desks/mt5/research/hourly_cycle.py")["reason"] == "orchestrator_or_release"
    assert _cls("desks/mt5/research/organ_redteam.py")["reason"] == "orchestrator_or_release"
    for tok in ("mt5.order_send(req)", "import MetaTrader5 as mt5", "TRADE_ACTION_DEAL",
                "from mt5desk.config import terminal_path", "place_order(x)"):
        assert _cls("libs/x.py", tok + MAIN)["reason"] == "broker_or_orders", tok
    for tok in ('subprocess.run(["git", "commit", "-m", m])', "os.system('git push')",
                "schtasks /Create", "systemctl --user restart x"):
        assert _cls("libs/x.py", tok + MAIN)["reason"] == "mutates_git_or_scheduler", tok
    assert _cls("libs/x.py", "def f(): pass\n")["reason"] == "no_entrypoint"
    assert _cls("libs/x.py", "x", quarantine=["libs/x.py"])["reason"] == \
        "quarantined_tracked_drift"


def test_tracked_artifact_needs_a_dry_flag() -> None:
    tracked = frozenset({"STATE.json"})
    c = _cls("libs/x.py", MAIN, ("STATE.json",), tracked=tracked)
    assert not c["run"] and c["reason"] == "writes_tracked_state"
    src = 'ap.add_argument("--check")\nap.add_argument("--dry-run", action="store_true")' + MAIN
    c = _cls("libs/x.py", src, ("STATE.json",), tracked=tracked)
    assert c["run"] and c["args"] == ["--dry-run"]
    # git unreadable: every named artifact is treated as tracked
    c = _cls("libs/x.py", MAIN, ("X.json",), tracked=None)
    assert not c["run"] and c["reason"] == "tracked_state_unknowable"
    c = _cls("libs/x.py", MAIN, ("UNTRACKED.json",), tracked=tracked)
    assert c["run"] and c["args"] == [] and c["mode"] == "plain"


def test_the_real_money_path_and_box_scripts_are_never_started() -> None:
    money = rt.money_closure()
    assert len(money) > 100
    rels = sorted(money) + sorted(p.relative_to(ROOT).as_posix()
                                  for p in (ROOT / "desks" / "mt5" / "scripts").rglob("*.py"))
    for rel in rels:
        assert not rt.classify(rel, MAIN, (), money=money, tracked=NONE)["run"], rel


def test_rotation_is_by_name_and_wraps() -> None:
    names = ["c", "a", "b", "d"]
    assert rt.next_names(names, None) == ["a", "b", "c", "d"]
    assert rt.next_names(names, "c") == ["c", "d", "a", "b"]
    assert rt.next_names(names, "bb") == ["c", "d", "a", "b"]  # cursor organ left the census
    assert rt.next_names(names, "z") == ["a", "b", "c", "d"]
    assert rt.next_names([], "a") == []


def test_exception_type_only() -> None:
    err = ('Traceback (most recent call last):\n  File "x.py", line 1\n'
           "KeyError: 'secret-ish value'\n")
    assert rt.exception_type(err) == "KeyError"
    assert rt.exception_type("pkg.mod.CustomError: boom") == "CustomError"
    assert rt.exception_type("nothing here") is None


def _fixture(tmp: Path, names: list[str]) -> Path:
    for n in names:
        p = tmp / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(MAIN, "utf-8")
    (tmp / "ops").mkdir(exist_ok=True)
    (tmp / "ops" / "money_closure.txt").write_text("libs/money.py\n", "utf-8")
    src = tmp / "dead_architecture.json"
    src.write_text(json.dumps({"at": "t", "no_clock": names,
                               "organs": {n: {"artifacts": []} for n in names}}), "utf-8")
    return src


def test_pass_rotates_records_and_skips(tmp_path: Path) -> None:
    names = ["libs/a.py", "libs/b.py", "libs/money.py", "desks/mt5/scripts/s.py", "libs/c.py"]
    src = _fixture(tmp_path, names)
    out = tmp_path / "ORGAN_REDTEAM.json"
    calls: list[str] = []

    def runner(name: str, args: list[str], arts: list[str], **_: object) -> dict[str, object]:
        calls.append(name)
        return {"outcome": rt.RAN_OK, "rc": 0}

    doc = rt.run_pass(per_pass=2, cap_s=1, budget_s=100, source=src, out=out, root=tmp_path,
                      runner=runner, hold=lambda _mb: None)
    assert calls == ["libs/a.py", "libs/b.py"]  # the scripts-dir organ sorts first, never runs
    assert doc["organs"]["desks/mt5/scripts/s.py"]["outcome"] == rt.SKIPPED
    assert doc["cursor"] == "libs/c.py"
    out.write_text(json.dumps(doc), "utf-8")
    doc2 = rt.run_pass(per_pass=2, cap_s=1, budget_s=100, source=src, out=out, root=tmp_path,
                       runner=runner, hold=lambda _mb: None)
    assert calls[2:] == ["libs/c.py", "libs/a.py"]  # money + scripts skipped, then wraps
    assert doc2["organs"]["libs/money.py"]["reason"] == "money_path"
    assert set(doc2["counts"]) <= set(rt.OUTCOMES)
    assert doc2["coverage"] == 1.0


def test_absent_census_is_unmeasured(tmp_path: Path) -> None:
    doc = rt.run_pass(source=tmp_path / "nope.json", out=tmp_path / "o.json", root=tmp_path)
    assert doc["status"] == "UNMEASURED"


def _organs(tmp_path: Path, organs: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    (repo / "reports").mkdir(parents=True)
    (repo / "data").mkdir()
    for n, src in organs.items():
        (repo / n).write_text(src, "utf-8")
    return repo


def _go(repo: Path, n: str, cap: float = 20.0,
        tracked: tuple[str, ...] = ()) -> dict[str, object]:
    # `systemp` is pinned to a directory the organs never write, so "outside the repository"
    # below really is outside every allowed place (pytest's tmp_path lives in the real temp dir).
    return rt.run_one(n, [], [], cap_s=cap, mem_mb=1024, root=repo, tracked_reports=tracked,
                      systemp=str(repo.parent / "systemp"))


def test_run_one_outcomes(tmp_path: Path) -> None:
    repo = _organs(tmp_path, {
        "ok.py": "print('hello')",
        "boom.py": "raise ValueError('a message that must not be recorded')",
        "slow.py": "import time\ntime.sleep(30)",
        "quiet.py": "x = 1",
        "temp_ok.py": ("import tempfile, os\n"
                       "open(os.path.join(tempfile.gettempdir(), 'x'), 'w').write('1')"),
    })
    assert _go(repo, "ok.py")["outcome"] == rt.RAN_OK
    boom = _go(repo, "boom.py")
    assert boom["outcome"] == rt.CRASHED and boom["exception"] == "ValueError"
    assert "message" not in json.dumps(boom)
    assert _go(repo, "slow.py", cap=1.0)["outcome"] == rt.TIMEOUT
    assert _go(repo, "quiet.py")["outcome"] == rt.NO_OUTPUT
    # the organ's own temp dir is the sandbox, which is writable
    assert _go(repo, "temp_ok.py")["outcome"] == rt.RAN_OK


def test_mf3_writes_inside_the_repo_are_refused_except_untracked_reports(tmp_path: Path) -> None:
    repo = _organs(tmp_path, {
        "writer.py": ("from pathlib import Path\nr = Path(__file__).parent\n"
                      "(r / 'reports' / 'r.json').write_text('{}')\n"
                      "(r / 'data' / 'state.json').write_text('{}')\n"),
        "tracked_report.py": ("from pathlib import Path\n"
                              "(Path(__file__).parent / 'reports' / 't.json').write_text('{}')"),
    })
    w = _go(repo, "writer.py")
    assert w["outcome"] == rt.CRASHED and w["exception"] == "WriteRefused"
    assert (repo / "reports" / "r.json").exists()
    assert not (repo / "data" / "state.json").exists()
    assert w["refused"] == [f"write: {os.path.join('data', 'state.json')}"]
    t = _go(repo, "tracked_report.py", tracked=("reports/t.json",))
    assert t["exception"] == "WriteRefused"
    assert not (repo / "reports" / "t.json").exists()


def test_mf3_a_write_outside_the_repository_is_refused(tmp_path: Path) -> None:
    tape = tmp_path / "tick_tape"
    tape.mkdir()
    repo = _organs(tmp_path, {
        # swallows the refusal and exits 0: it is still classified from the refusal record
        "outside.py": (f"try:\n    open({str(tape / 'XAUUSD.bin')!r}, 'wb').write(b'x')\n"
                       "except PermissionError:\n    pass\nprint('done')"),
        "rename.py": (f"import os\nos.replace({str(tape / 'a')!r}, {str(tape / 'b')!r})"),
        "mkdir.py": f"import os\nos.mkdir({str(tape / 'new')!r})",
    })
    o = _go(repo, "outside.py")
    assert o["outcome"] == rt.CRASHED and o["exception"] == "WriteRefused", o
    assert not (tape / "XAUUSD.bin").exists()
    for n in ("rename.py", "mkdir.py"):
        r = _go(repo, n)
        assert r["outcome"] == rt.CRASHED and r["exception"] == "WriteRefused", (n, r)
    assert not (tape / "new").exists()


def test_mf1_network_is_refused_loopback_included(tmp_path: Path) -> None:
    repo = _organs(tmp_path, {
        "connect.py": ("import socket\ns = socket.socket()\n"
                       "s.connect(('127.0.0.1', 1))"),
        "resolve.py": "import socket\nsocket.getaddrinfo('localhost', 80)",
        "byname.py": ("import socket\ntry:\n    socket.gethostbyname('example.com')\n"
                      "except OSError:\n    pass"),
    })
    for n in ("connect.py", "resolve.py", "byname.py"):
        r = _go(repo, n)
        assert r["outcome"] == rt.NETWORK_REFUSED, (n, r)
        assert any(str(x).startswith("network: socket.") for x in r["refused"])  # type: ignore[attr-defined]


def test_mf2_child_processes_are_refused(tmp_path: Path) -> None:
    marker = tmp_path / "child_ran"
    child = f"open({str(marker)!r}, 'w').write('1')"
    repo = _organs(tmp_path, {
        "popen.py": f"import subprocess, sys\nsubprocess.run([sys.executable, '-c', {child!r}])",
        "system.py": "import os\nos.system('echo hi')",
        "execv.py": "import os, sys\nos.execv(sys.executable, [sys.executable, '-c', 'pass'])",
    })
    for n in ("popen.py", "system.py", "execv.py"):
        r = _go(repo, n)
        assert r["outcome"] == rt.CRASHED and r["exception"] == "SpawnRefused", (n, r)
    assert not marker.exists()


def test_sf1_the_environment_is_an_allowlist(tmp_path: Path) -> None:
    env = rt.organ_env(str(tmp_path), tmp_path, base={
        "PATH": "/bin", "SystemRoot": "C:\\Windows", "PYTHONHASHSEED": "0",
        "QUANT_REDTEAM_X": "1", "OPENAI_API_KEY": "k", "AWS_SECRET_ACCESS_KEY": "k",
        "HOME": "/root", "GITHUB_TOKEN": "k", "QUANT_ALLOW_SSH_PY": "1"})
    assert {"PATH", "SystemRoot", "PYTHONHASHSEED", "QUANT_REDTEAM_X"} <= set(env)
    for k in ("OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "HOME", "GITHUB_TOKEN",
              "QUANT_ALLOW_SSH_PY"):
        assert k not in env
    assert env["TEMP"] == env["TMP"] == str(tmp_path)


def test_sf2_placing_windows_are_read_and_honoured() -> None:
    from datetime import UTC, datetime
    gold = rt.gold_signal_hours()
    assert gold and ("asia", 7) in gold  # read from decision_core, not typed here
    assert rt.scalp_windows() is not None
    off = lambda _now: 2  # noqa: E731  -- winter broker clock

    def at(h: int, m: int) -> datetime:
        return datetime(2026, 11, 18, h, m, tzinfo=UTC)

    # 05:00Z = 07:00 broker in winter: the asia placement
    assert "gold asia" in str(rt.placing_window(at(5, 0), lead_min=4, offset_h=off, gold=gold,
                                                scalp=[]))
    # well clear of every window
    assert rt.placing_window(at(1, 0), lead_min=4, offset_h=off, gold=gold, scalp=[]) is None
    # a pass that would still be running when the window opens is refused too
    assert rt.placing_window(at(4, 25), lead_min=10, offset_h=off, gold=gold, scalp=[])
    # a LIVE scalp row trading 15-17 broker, and one whose session is unresolvable
    assert "scalp" in str(rt.placing_window(at(13, 30), lead_min=4, offset_h=off, gold=[],
                                            scalp=[("s", 15, 17)]))
    assert rt.placing_window(at(1, 0), lead_min=4, offset_h=off, gold=[],
                             scalp=[("s", 0, 24)])
    # unreadable windows and an unreadable clock fail closed
    assert rt.placing_window(at(1, 0), lead_min=4, offset_h=off, gold=None, scalp=[],
                             read=False)
    assert rt.placing_window(at(1, 0), lead_min=4, offset_h=lambda _n: 1 / 0, gold=gold,
                             scalp=[])


def test_sf2_scalp_rows_resolve_their_session_hours(tmp_path: Path) -> None:
    sl = tmp_path / "sleeves.json"
    sl.write_text(json.dumps({"sleeves": [
        {"name": "a", "status": "LIVE", "session": "overlap"},
        {"name": "b", "status": "LIVE", "session": "all"},
        {"name": "c", "status": "RETIRED", "session": "overlap"}]}), "utf-8")
    assert rt.scalp_windows(sl) == [("a", 15, 17), ("b", 0, 24)]


def test_sf2_stall_watch_pressure(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    now = datetime(2026, 11, 18, 5, 0, tzinfo=UTC)
    p = tmp_path / "stall_watch.json"
    p.write_text(json.dumps({"checked_at": "2026-11-18T04:55:00+00:00",
                             "memory": {"free_phys_mb": 600, "total_phys_mb": 8186}}), "utf-8")
    assert rt.stall_pressure(512, now=now, paths=[p])
    p.write_text(json.dumps({"checked_at": "2026-11-18T04:55:00+00:00",
                             "memory": {"free_phys_mb": 6000, "total_phys_mb": 8186}}), "utf-8")
    assert rt.stall_pressure(512, now=now, paths=[p]) is None
    p.write_text(json.dumps({"checked_at": "2026-11-17T00:00:00+00:00",
                             "memory": {"free_phys_mb": 10, "total_phys_mb": 8186}}), "utf-8")
    assert rt.stall_pressure(512, now=now, paths=[p]) is None  # stale: psutil stands alone


def test_a_hold_stands_the_pass_down(tmp_path: Path) -> None:
    src = _fixture(tmp_path, ["libs/a.py"])
    calls: list[str] = []

    def runner(name: str, *_a: object, **_k: object) -> dict[str, object]:
        calls.append(name)
        return {"outcome": rt.RAN_OK}

    doc = rt.run_pass(source=src, out=tmp_path / "o.json", root=tmp_path, runner=runner,
                      hold=lambda _mb: "gold asia placing window")
    assert not calls and doc["status"] == "STOOD_DOWN"
    assert doc["stood_down_because"] == "gold asia placing window"
    assert doc["cursor"] == "libs/a.py"


def test_hold2_mf1_a_helper_that_imports_metatrader5_is_refused(tmp_path: Path) -> None:
    stub = tmp_path / "stub"
    (stub / "MetaTrader5").mkdir(parents=True)
    marker = tmp_path / "terminal_reached"
    (stub / "MetaTrader5" / "__init__.py").write_text(
        f"open({str(marker)!r}, 'w').write('1')\ndef initialize():\n    return True\n", "utf-8")
    repo = _organs(tmp_path, {
        "helper.py": "import MetaTrader5 as mt5\ndef up():\n    return mt5.initialize()\n",
        "organ.py": f"import sys\nsys.path.insert(0, {str(stub)!r})\nimport helper\nhelper.up()",
        # an organ that treats the broker as optional and carries on is still classified
        "optional.py": (f"import sys\nsys.path.insert(0, {str(stub)!r})\n"
                        "try:\n    import helper\nexcept ImportError:\n    helper = None\n"
                        "print('carried on')"),
    })
    for n in ("organ.py", "optional.py"):
        r = _go(repo, n)
        assert r["outcome"] == rt.BROKER_REFUSED and r["exception"] == "BrokerRefused", (n, r)
        assert "broker: import MetaTrader5" in r["refused"]  # type: ignore[operator]
    assert not marker.exists()


def test_hold2_mf2_a_multiprocessing_child_is_refused(tmp_path: Path) -> None:
    marker = tmp_path / "mp_child_ran"
    repo = _organs(tmp_path, {
        "mp.py": ("import multiprocessing as mp\n"
                  f"def child():\n    open({str(marker)!r}, 'w').write('1')\n"
                  "if __name__ == '__main__':\n"
                  "    p = mp.Process(target=child)\n    p.start()\n    p.join()\n"),
        "mp_spawn.py": ("import multiprocessing as mp\n"
                        f"def child():\n    open({str(marker)!r}, 'w').write('1')\n"
                        "if __name__ == '__main__':\n"
                        "    p = mp.get_context('spawn').Process(target=child)\n"
                        "    p.start()\n    p.join()\n"),
    })
    for n in ("mp.py", "mp_spawn.py"):
        r = _go(repo, n)
        assert r["outcome"] == rt.CRASHED and r["exception"] == "SpawnRefused", (n, r)
    assert not marker.exists()


def test_hold2_sf_native_calls_are_refused_and_plain_ctypes_imports(tmp_path: Path) -> None:
    import pytest
    if sys.platform == "win32":
        pytest.skip("the libc names below are POSIX")
    repo = _organs(tmp_path, {
        "plain.py": "import ctypes, numpy, pandas\nprint(ctypes.sizeof(ctypes.c_int))",
        "call.py": "import ctypes\nctypes.CDLL(None).getpid()",
        "load.py": "import ctypes\nctypes.CDLL('libc.so.6')",
        # the one path that raises ctypes.call_function: the _ctypes helper on a live pointer
        "helper_call.py": ("import ctypes, _ctypes\n"
                           "cb = ctypes.CFUNCTYPE(ctypes.c_int)(lambda: 7)\n"
                           "_ctypes.call_function(ctypes.cast(cb, ctypes.c_void_p).value, ())"),
    })
    assert _go(repo, "plain.py")["outcome"] == rt.RAN_OK
    for n in ("call.py", "load.py", "helper_call.py"):
        r = _go(repo, n)
        assert r["outcome"] == rt.NATIVE_REFUSED and r["exception"] == "NativeRefused", (n, r)


def test_hold2_sf_the_guard_state_is_not_reachable_by_name() -> None:
    import ast
    tree = ast.parse(rt.BOOTSTRAP)
    names = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
             if isinstance(t, ast.Name)}
    names |= {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    # `_install` (deleted after use) and `_organ` (the path) are the only module-scope names
    assert names == {"_install", "_organ"}, names
    assert "busy" not in {t.id for n in tree.body if isinstance(n, ast.Assign)
                          for t in n.targets if isinstance(t, ast.Name)}
