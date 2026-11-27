"""Boot r24 phase A: the run-as probe is read-only on the account (Audit Q1 bound 4)."""

from __future__ import annotations

from types import SimpleNamespace

from ops.box_git import runas_probe as P

ALLOWED = {"initialize", "account_info", "terminal_info", "shutdown", "last_error"}


class Recorder:
    def __init__(self, *, init=True, login=12345611, connected=True):
        self.calls: list[str] = []
        self._init, self._login, self._conn = init, login, connected

    def __getattr__(self, name):
        def call(*a, **k):
            self.calls.append(name)
            if name == "initialize":
                return self._init
            if name == "account_info":
                return SimpleNamespace(login=self._login)
            if name == "terminal_info":
                return SimpleNamespace(connected=self._conn, trade_allowed=True)
            if name == "last_error":
                return (-10003, "IPC")
            return None

        return call


def test_a_pass_needs_connected_and_the_expected_suffix() -> None:
    m = Recorder()
    r = P.probe(m, "x.exe", "11")
    assert r["ok"] and r["login_suffix"] == "11" and "12345611" not in str(r)
    assert set(m.calls) <= ALLOWED and m.calls[-1] == "shutdown"


def test_the_probe_never_calls_anything_but_the_four_reads() -> None:
    for m in (Recorder(), Recorder(init=False), Recorder(connected=False), Recorder(login=99)):
        P.probe(m, "x.exe", "11")
        assert set(m.calls) <= ALLOWED, m.calls
        assert "shutdown" in m.calls


def test_failures_are_named() -> None:
    assert "initialize failed" in P.probe(Recorder(init=False), "x", "11")["why"]
    assert P.probe(Recorder(connected=False), "x", "11")["why"] == "not connected"
    assert P.probe(Recorder(login=99), "x", "11")["why"] == "login suffix differs"
    assert not P.probe(Recorder(), "x", "")["ok"]  # no expectation is never a pass


def test_only_this_accounts_terminals_are_counted() -> None:
    class Proc:
        def __init__(self, pid, name, user):
            self.pid, self._n, self._u = pid, name, user

        def name(self):
            return self._n

        def username(self):
            if self._u is None:
                raise PermissionError
            return self._u

    procs = [
        Proc(1, "terminal64.exe", "BOX\\quantrun"),
        Proc(2, "terminal64.exe", "BOX\\Administrator"),
        Proc(3, "terminal64.exe", None),
        Proc(4, "python.exe", "BOX\\quantrun"),
    ]
    assert P._own_terminals(procs, "quantrun") == {1}


def test_the_probe_source_names_no_order_call() -> None:
    from pathlib import Path

    src = Path(P.__file__).read_text(encoding="utf-8")
    for banned in ("order_send", "order_check", "positions_get", "symbol_select", "orders_get"):
        assert banned not in src


# ------------------------------------------------------------------ the migrator's plan
from datetime import UTC, datetime, timedelta  # noqa: E402

from ops.box_git import runas_plan as R  # noqa: E402


def _t(name, user, exe="cmd.exe", args=r"/c C:\opt\quant\x.cmd", rl="Limited"):
    return {
        "name": name,
        "principal": {"user": user, "runlevel": rl},
        "actions": [{"execute": exe, "arguments": args, "workdir": ""}],
    }


TASKS = [
    _t("MT5-Gateway", "Administrator", rl="Highest"),
    _t("MT5-Hourly", "SYSTEM"),
    _t("MT5-AdoptRelease", "SYSTEM"),
    _t("Other", "SYSTEM", args="/c C:\\elsewhere\\y"),
    _t("Done", "quantrun"),
    {"name": "Hidden", "principal": {}, "actions": None},
]


def test_only_live_tree_principals_move_and_only_to_quantrun() -> None:
    assert R.to_move(TASKS) == ["MT5-Gateway", "MT5-Hourly"]  # never the adopter
    now = datetime(2026, 11, 28, 12, tzinfo=UTC)
    adopter_still_runs_head_code = R.proof([_t("MT5-AdoptRelease", "SYSTEM")], {"g": True}, {}, now)
    assert adopter_still_runs_head_code["elevated_live_tree"] == ["MT5-AdoptRelease"]
    assert R.new_principal() == {"user": "quantrun", "logon": "S4U", "runlevel": "Limited"}
    snap = R.snapshot(TASKS, R.to_move(TASKS))
    assert snap == {
        "MT5-Gateway": {"user": "Administrator", "runlevel": "Highest"},
        "MT5-Hourly": {"user": "SYSTEM", "runlevel": "Limited"},
    }


def test_the_weekend_window() -> None:
    fri = datetime(2026, 11, 27, 21, 59, tzinfo=UTC)
    assert not R.in_window(fri) and R.in_window(fri + timedelta(minutes=1))
    assert R.in_window(datetime(2026, 11, 28, 12, tzinfo=UTC))
    assert not R.in_window(datetime(2026, 11, 29, 21, 0, tzinfo=UTC))


def test_the_state_machine_never_reregisters_after_a_move() -> None:
    now = datetime(2026, 11, 28, 12, tzinfo=UTC)
    assert R.step({}, now, probes={}) == ("PROBE", "probe")
    assert R.step({}, now, probes={"attach": {"ok": True}}) == ("WAIT_WINDOW", "wait:attach")
    assert (
        R.step({}, now, probes={"attach": {"ok": False}, "portable": {"ok": True}})[1]
        == "wait:portable"
    )
    assert R.step({}, now, probes={"attach": {"ok": False}}) == ("BLOCKED", "alarm")
    assert R.step({"state": "WAIT_WINDOW", "mode": "attach"}, now, probes={}, window=False) == (
        "WAIT_WINDOW",
        "wait",
    )
    assert R.step({"state": "WAIT_WINDOW", "mode": "attach"}, now, probes={}, window=True) == (
        "MOVED",
        "move:attach",
    )
    for s in ("MOVED", "WATCH", "DONE", "BLOCKED", "ROLLED_BACK"):
        assert not R.step({"state": s}, now, probes={"attach": {"ok": True}}, window=True)[
            1
        ].startswith("move")


def test_the_monday_watch() -> None:
    moved = datetime(2026, 11, 28, 12, tzinfo=UTC)
    opened = datetime(2026, 11, 29, 22, tzinfo=UTC)
    now = opened + timedelta(hours=1)
    kw = {"market_open_since": opened, "consecutive_rejects": 0}
    assert R.watch_verdict(moved, now, heartbeat_at=now, **kw) == "ok"
    assert R.watch_verdict(moved, now, heartbeat_at=now - timedelta(minutes=16), **kw) == "rollback"
    assert (
        R.watch_verdict(
            moved, now, heartbeat_at=now, market_open_since=opened, consecutive_rejects=3
        )
        == "rollback"
    )
    assert R.watch_verdict(moved, opened + timedelta(hours=7), heartbeat_at=None, **kw) == "done"
    assert (
        R.watch_verdict(
            moved, now, heartbeat_at=None, market_open_since=None, consecutive_rejects=9
        )
        == "ok"
    )  # closed market: nothing to judge


def test_proof_and_the_guards_reading_of_it() -> None:
    now = datetime(2026, 11, 28, 12, tzinfo=UTC)
    moved = [_t("MT5-Gateway", "quantrun"), _t("QuantForge-BootMove", "SYSTEM")]
    good = R.proof(moved, {"guard": True, "trust": True}, {"no_ea": True}, now, [])
    assert good["independent"] and R.proof_holds(good, now) == (True, "independent")
    assert not R.proof_holds(good, now + timedelta(minutes=16))[0]
    assert not R.proof(TASKS, {"guard": True}, {}, now)["independent"]  # elevated + unreadable
    assert not R.proof(moved, {"guard": False}, {}, now, [])["independent"]
    assert not R.proof(moved, {}, {}, now, [])["independent"]  # no write probe ran
    assert not R.proof(moved, {"guard": True}, {"dll_off": False}, now, [])["independent"]
    assert R.proof_holds(None, now) == (False, "RUN_AS.json missing")


def test_the_seat_switches_off_only_after_7_days_of_unbroken_proof(tmp_path) -> None:
    import json
    from types import SimpleNamespace as NS

    from ops.box_git import box_loop as L

    cfg = NS(guard_dir=tmp_path)
    now = datetime(2026, 12, 6, 12, tzinfo=UTC)
    assert L.seat_required(cfg, now) == (True, "RUN_AS.json missing")
    d = tmp_path / "runas"
    d.mkdir()
    good = R.proof([_t("MT5-Gateway", "quantrun")], {"guard": True}, {}, now, [])
    (tmp_path / L.RUN_AS_PROOF).write_text(json.dumps(good), encoding="utf-8")

    def hist(days, gap_at=None, bad_at=None):
        rows, t = [], now - timedelta(days=days)
        while t <= now:
            if gap_at is None or not (gap_at <= t < gap_at + timedelta(minutes=30)):
                rows.append(json.dumps({"at": t.isoformat(), "independent": t != bad_at}))
            t += timedelta(minutes=5)
        (d / "RUN_AS_HISTORY.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")

    hist(6)
    assert L.seat_required(cfg, now)[0]
    hist(8)
    assert L.seat_required(cfg, now)[0] is False
    hist(8, gap_at=now - timedelta(days=2))
    assert L.seat_required(cfg, now)[0]  # a gap restarts the clock
    hist(8, bad_at=(now - timedelta(days=1)).replace(minute=0))
    assert L.seat_required(cfg, now)[0]  # one bad proof restarts it
    bad = dict(good, independent=False, elevated_processes=["7 python.exe (SYSTEM)"])
    (tmp_path / L.RUN_AS_PROOF).write_text(json.dumps(bad), encoding="utf-8")
    hist(8)
    assert L.seat_required(cfg, now)[0]  # fails back at once


def test_process_proof() -> None:
    procs = [
        {"pid": 1, "name": "python.exe", "cmdline": r"py C:\opt\quant\x.py", "user": "SYSTEM"},
        {
            "pid": 2,
            "name": "python.exe",
            "cmdline": "py x.py",
            "user": "BOX\\Administrator",
            "cwd": r"C:\opt\quant\desks\mt5",
        },
        {
            "pid": 3,
            "name": "python.exe",
            "cmdline": r"py C:\opt\quant\x.py",
            "user": "BOX\\quantrun",
        },
        {"pid": 4, "name": "terminal64.exe", "cmdline": r"C:\opt\quant", "user": "SYSTEM"},
        {
            "pid": 5,
            "name": "powershell.exe",
            "cmdline": r"-File C:\ProgramData\QuantBox\guard\adopt\a.ps1 C:\opt\quant",
            "user": "SYSTEM",
        },
    ]
    assert R.elevated_processes(procs) == ["1 python.exe (SYSTEM)", "2 python.exe (ADMINISTRATOR)"]
    now = datetime(2026, 11, 28, 12, tzinfo=UTC)
    assert not R.proof([], {"g": True}, {}, now)["independent"]  # processes unmeasured


def test_uncleared_head_code_never_runs_while_the_seat_is_required(monkeypatch) -> None:
    """Audit MF1 (r24 a9a46e82d): quantci may reach the terminals like any account, so a PR's own
    code runs before a CLEAR only once the seat is no longer required."""
    from ops.box_git import box_loop as L

    class F:
        def gh(self, path, *a, **k):
            if path.endswith("/check-runs"):
                return {"check_runs": []}
            return []  # no CLEAR on the PR

    pr = {"number": 1, "head": {"sha": "b" * 40}}
    assert L._eligible(F(), [pr], set(), need_clear=True) == []
    assert L._eligible(F(), [pr], set(), need_clear=False) == [pr]
    assert L.seat_required(object())[0]  # r24 ships with the seat required


def test_kill_old_matches_full_paths_only(monkeypatch) -> None:
    import sys
    import types

    psutil = types.ModuleType("psutil")
    monkeypatch.setitem(sys.modules, "psutil", psutil)

    class P:
        def __init__(self, pid, name, cmd, user, cwd):
            self.info = {"pid": pid, "name": name, "cmdline": cmd, "username": user}
            self._cwd, self.killed = cwd, False

        def cwd(self):
            return self._cwd

        def kill(self):
            self.killed = True

    procs = [
        P(
            1,
            "python.exe",
            ["py", "research\\hourly_cycle.py"],
            "SYSTEM",
            "C:\\opt\\quant\\desks\\mt5",
        ),
        P(
            2,
            "python.exe",
            ["py", "research\\hourly_cycle_extra.py"],
            "SYSTEM",
            "C:\\opt\\quant\\desks\\mt5",
        ),
        P(
            3,
            "python.exe",
            ["py", "research\\hourly_cycle.py"],
            "BOX\\quantrun",
            "C:\\opt\\quant\\desks\\mt5",
        ),
        P(
            4,
            "terminal64.exe",
            ["t", "research\\hourly_cycle.py"],
            "SYSTEM",
            "C:\\opt\\quant\\desks\\mt5",
        ),
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda *a: procs, raising=False)
    import ntpath
    import os

    monkeypatch.setattr(os, "path", ntpath)
    assert R.kill_old(["C:\\opt\\quant\\desks\\mt5\\research\\hourly_cycle.py"]) == [1]
