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
    pin_args = ('-File "C:\\ProgramData\\QuantBox\\guard\\adopt\\tree\\desks\\mt5\\scripts\\'
                'Adopt-And-Seal.ps1" -RepoRoot "C:\\opt\\quant" -Pinned')
    pinned = _t("MT5-AdoptRelease", "SYSTEM", exe="powershell.exe", args=pin_args)
    assert R.proof([pinned], {"g": True}, {}, now, [])["elevated_live_tree"] == []
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


def test_the_door_needs_a_guard_verdict_or_a_seal(tmp_path) -> None:
    """Audit C3: rule 7 of protect.py."""
    import json

    from ops.box_git import protect as D
    old, mrg, head, seal = "1" * 40, "2" * 40, "3" * 40, "4" * 40
    live = f"refs/heads/{D.LIVE_BRANCH}"
    (tmp_path / "verdicts").mkdir()

    def git(*a):
        if a[0] == "rev-list":
            return {mrg: f"{mrg} {old} {head}", seal: f"{seal} {old}",
                    "5" * 40: f"{'5' * 40} {'9' * 40}"}[a[-1]]
        return {seal: D.SEAL_PATH + "\n"}.get(a[-1], "x.py\n")
    assert D.guard_refusals([(old, mrg, live)], str(tmp_path), git)  # no verdict yet
    (tmp_path / "verdicts" / f"{head}.json").write_text(
        json.dumps({"sha": head, "cls": "FAIL"}), encoding="utf-8")
    assert D.guard_refusals([(old, mrg, live)], str(tmp_path), git)
    (tmp_path / "verdicts" / f"{head}.json").write_text(
        json.dumps({"sha": head, "cls": "PASS"}), encoding="utf-8")
    assert D.guard_refusals([(old, mrg, live)], str(tmp_path), git) == []
    assert D.guard_refusals([(old, seal, live)], str(tmp_path), git) == []
    assert D.guard_refusals([(old, "5" * 40, live)], str(tmp_path), git)  # not one step
    assert D.guard_refusals([(old, mrg, "refs/heads/claude/x")], str(tmp_path), git) == []


def test_the_pinned_adopter_runs_no_tree_code(monkeypatch, tmp_path) -> None:
    """Audit C4: with QUANT_ADOPT_PINNED=1 the guard's helpers come from its own checkout and the
    smoke imports nothing from the tree it adopts."""
    from libs.ops import adopt_guard as G
    monkeypatch.setenv(G.PINNED_ENV, "1")
    assert G.code_root(tmp_path) == G.OWN_ROOT
    ran = []
    code, doc = G.smoke(tmp_path, runner=lambda *a, **k: ran.append(a))
    assert code == G.GO and doc["decision"] == "SMOKE_PINNED_SKIPPED" and ran == []
    monkeypatch.delenv(G.PINNED_ENV)
    assert G.code_root(tmp_path) == tmp_path


def test_the_adopter_script_takes_pinned() -> None:
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text(
        encoding="utf-8")
    assert "[switch] $Pinned" in src and "$env:QUANT_ADOPT_PINNED = \"1\"" in src
    assert "core.hooksPath=NUL" in src and "QUANT_LEDGER_ROOT = $RepoRoot" in src
    assert 'Join-Path $script:DeciderRoot "scripts\\migrate_live_ledger_view.py"' in src


# ---------------------------------------------------------------- r24.2: Audit C4, the hold on r4
_REPO = __import__("pathlib").Path(__file__).resolve().parents[2]


def _ps(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


def _branch(src: str, anchor: str) -> str:
    """The text of the `if ($Pinned) {...}` block that starts at the first line holding anchor."""
    i = src.index(anchor)
    j = src.index("if ($Pinned)", max(0, i - 400))
    assert j <= i, f"{anchor!r} is not inside an `if ($Pinned)` block"
    return src[j:i + len(anchor)]


def test_the_pinned_adopter_executes_nothing_from_the_tree() -> None:
    """Every step of Adopt-And-Seal that would execute or import from -RepoRoot or $desk sits
    behind `if ($Pinned)`, and every libs.ops call names the tree as root= DATA."""
    src = _ps("desks/mt5/scripts/Adopt-And-Seal.ps1")
    # the interpreter: the tree's .venv only ever in the unpinned branch
    pin = src.index("if ($Pinned) {\n    # (Audit C4, r24.2)")
    venv = src.index('Join-Path $RepoRoot ".venv\\Scripts\\python.exe"')
    assert venv > src.index("} else {", pin)
    assert '$env:PYTHONSAFEPATH = "1"' in src and "_quant_pinned_fence" in src
    # installers, selfheal, release_authority: skipped when pinned
    assert "if ($Pinned) { Log \"ensure-task:" in src
    _branch(src, ". $selfheal; Invoke-BoxSelfHeal")
    _branch(src, 'research\\release_authority.py") --once')
    assert 'if (-not $Pinned -and -not (Test-Path $adoptScript))' in src
    # every `-c "... from libs.ops ..."` passes the tree as an explicit root
    calls = [ln for ln in src.splitlines() if "from libs.ops import release" in ln]
    assert len(calls) == 4
    for ln in calls:
        assert "Path(sys.argv[" in ln and "$RepoRoot" in ln, ln
    # nothing else executes a path built from the tree
    for bad in ("& $py @pyArgs (Join-Path $desk", "& $py @pyArgs (Join-Path $RepoRoot"):
        for k in [i for i in range(len(src)) if src.startswith(bad, i)]:
            _branch(src, src[k:src.index("\n", k)])


def test_adopt_release_runs_guards_from_the_guard_checkout_when_pinned() -> None:
    src = _ps("desks/mt5/scripts/Adopt-Release.ps1")
    a, b = src.index("function Get-PinnedCode"), src.index("function Invoke-GuardedIndexCommit")
    helper = src[a:b]
    assert "QUANT_GUARD_ROOT" in helper and "QUANT_PINNED_PYTHON" in helper
    rest = src.replace(helper, "")
    assert '.venv\\Scripts\\python.exe' not in rest
    assert "Get-PinnedCode $relativeGuard" in rest
    assert 'Get-PinnedCode "scripts\\check_target_seal.py"' in rest


def test_the_guard_scripts_measure_the_live_tree_but_load_their_own_code(
        monkeypatch, tmp_path) -> None:
    import importlib.util
    monkeypatch.setenv("QUANT_ADOPT_PINNED", "1")
    monkeypatch.setenv("QUANT_LEDGER_ROOT", str(tmp_path))
    for rel in ("scripts/check_target_seal.py", "scripts/moneypath_precommit_guard.py",
                "scripts/check_protected_records.py"):
        name = "_pin_" + rel.replace("/", "_")[:-3]
        spec = importlib.util.spec_from_file_location(name, _REPO / rel)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert tmp_path.resolve() == mod.ROOT and mod.CODE == _REPO, rel
    monkeypatch.delenv("QUANT_ADOPT_PINNED")
    seal = _REPO / "scripts/check_target_seal.py"
    spec = importlib.util.spec_from_file_location("_unpinned", seal)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.ROOT == mod.CODE == _REPO


def test_the_identity_check_imports_the_guards_own_mt5desk() -> None:
    import inspect

    from libs.ops import adopt_guard as G
    body = inspect.getsource(G._identity)
    assert "code = code_root(root)" in body and "str(root)" not in body.split("ri.verdict")[0]


def test_the_runtime_fence_refuses_tree_imports_and_tree_scripts(tmp_path) -> None:
    import os
    import shutil
    import subprocess
    import sys
    live = tmp_path / "live"
    (live / "libs").mkdir(parents=True)
    (live / "evil.py").write_text("print('ran')\n")
    site = tmp_path / "site"
    site.mkdir()
    shutil.copy(_REPO / "ops/box_git/pinned_sitecustomize.py", site / "sitecustomize.py")
    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "fine.py").write_text("X = 1\n")
    probe = (
        "import sys, subprocess\n"
        "assert sys._quant_pinned_fence\n"
        "sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])\n"
        "import fine\n"
        "try:\n    import evil\n"
        "except ImportError as e:\n    print('IMPORT', 'pinned fence' in str(e))\n"
        "try:\n    subprocess.run([sys.executable, sys.argv[1] + '/evil.py'])\n"
        "except RuntimeError as e:\n    print('RUN', 'pinned fence' in str(e))\n"
        "subprocess.run(['git', '-C', sys.argv[1], '--version'], capture_output=True)\n"
        "print('GIT ok')\n"
    )
    env = {**os.environ, "PYTHONPATH": str(site), "QUANT_ADOPT_PINNED": "1",
           "QUANT_LEDGER_ROOT": str(live), "PYTHONSAFEPATH": "1"}
    out = subprocess.run([sys.executable, "-c", probe, str(live), str(tmp_path / "ok")], env=env,
                         capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    assert "IMPORT True" in out.stdout and "RUN True" in out.stdout and "GIT ok" in out.stdout
    env["QUANT_ADOPT_PINNED"] = "0"
    ask = "import sys; print(hasattr(sys, '_quant_pinned_fence'))"
    off = subprocess.run([sys.executable, "-c", ask],
                         env=env, capture_output=True, text=True, timeout=60, check=False)
    assert off.stdout.strip() == "False"


def test_install_guard_builds_its_own_python() -> None:
    src = _ps("ops/box_git/install_guard.ps1")
    i = src.index("THE PINNED PYTHON IS THE GUARD'S OWN")
    j = src.index("Set-Content -LiteralPath (Join-Path $adopt 'python.txt') -Value $pinnedPy")
    body = src[i:j]
    for need in ("-m venv --without-pip", "robocopy", "pinned_sitecustomize.py", "Stop-Here",
                 "PYTHONSAFEPATH", "c:\\opt\\"):
        assert need in body, need
    assert "Value $py -Encoding ascii" not in src[i:]  # the gateway's python is never the adopter's


# ------------------------------------------------- r24 r6: Audit MF1 on r5, the live .git seal
def test_the_live_git_is_sealed_before_any_system_git_reads_it() -> None:
    import re
    acl = _ps("ops/box_git/runas/git_acl.ps1")
    for need in ("BUILTIN\\\\Administrators|NT AUTHORITY\\\\SYSTEM", "ChangePermissions",
                 "TakeOwnership", "DeleteSubdirectoriesAndFiles", "commondir", "config.worktree",
                 "InheritOnly", "0x50000000", "-not $r.IsInherited"):
        assert need in acl, need
    ins = _ps("ops/box_git/install_guard.ps1")
    for need in ("/setowner '*S-1-5-32-544'", '/deny "${RunUser}:(D,WDAC,WO)"',
                 '/deny "${RunUser}:(W,D,WDAC,WO)"',
                 '& icacls $Live /deny "${RunUser}:(D,DC,WDAC,WO)"',
                 "& icacls $Live /setowner '*S-1-5-32-544'",
                 '& icacls (Split-Path -Parent $Live) /deny "${RunUser}:(WD,AD,DC,WDAC,WO)"',
                 "Test-GitAclSealed -RepoRoot $Live", "'runas\\git_acl.ps1'"):
        assert need in ins, need
    # the pinned adopter checks the seal before its first git invocation, and again before sealing
    src = _ps("desks/mt5/scripts/Adopt-And-Seal.ps1")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    first_git = re.search(r"(?m)(^|[\s(|;{])git (-C|rev-parse|diff|add|status|symbolic-ref)", code)
    assert first_git and code.index("Test-GitAclSealed -RepoRoot $RepoRoot") < first_git.start()
    assert code.count("Test-GitAclSealed -RepoRoot $RepoRoot") == 2
    assert code.index("Test-GitAclSealed") < code.index('git add -- "desks/mt5/data/RELEASE.json"')
    # and the RUN_AS proof carries it, measured by SYSTEM with the guard's own python
    mig = _ps("ops/box_git/runas/migrate.ps1")
    assert "$r['live .git sealed'] = ($why.Count -eq 0)" in mig
    sys_calls = re.findall(r"& \$(\w+) -I \$Plan", mig)
    assert sys_calls and set(sys_calls) == {"SysPy"}
    assert re.findall(r"-Execute \$(\w+)", mig) == ["Py", "Py"]  # only quantrun's probe tasks


def test_the_fence_refuses_unpickling(tmp_path) -> None:
    import os
    import shutil
    import subprocess
    import sys
    site = tmp_path / "site"
    site.mkdir()
    shutil.copy(_REPO / "ops/box_git/pinned_sitecustomize.py", site / "sitecustomize.py")
    probe = ("import pickle, collections\n"
             "b = pickle.dumps(collections.OrderedDict(a=1))\n"
             "try:\n    pickle.loads(b)\nexcept RuntimeError as e:\n"
             "    print('REFUSED', 'pinned fence' in str(e))\n"
             "print('PLAIN', pickle.loads(pickle.dumps({'a': [1, 2]})))\n")
    env = {**os.environ, "PYTHONPATH": str(site), "QUANT_ADOPT_PINNED": "1",
           "QUANT_LEDGER_ROOT": str(tmp_path / "live")}
    out = subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True,
                         timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    assert "REFUSED True" in out.stdout


def test_the_tree_root_cannot_be_swapped_after_the_check() -> None:
    """Audit hold on r6: the root row of Test-GitAclSealed requires an admin owner and refuses
    Delete, delete-child and re-ACL on the root, and create/delete-child on its parent."""
    acl = _ps("ops/box_git/runas/git_acl.ps1")
    root = acl[acl.index("@{ Path = $RepoRoot;"):acl.index("# its parent")]
    assert "Owner = $true" in root
    for bit in ("Delete", "DeleteSubdirectoriesAndFiles", "ChangePermissions", "TakeOwnership"):
        assert f"$F::{bit}" in root, bit
    parent = acl[acl.index("(Split-Path -Parent $RepoRoot)"):acl.index("$why = @()")]
    for bit in ("CreateFiles", "CreateDirectories", "DeleteSubdirectoriesAndFiles"):
        assert f"$F::{bit}" in parent, bit
    ins = _ps("ops/box_git/install_guard.ps1")
    # the root's deny lands after the Modify grant, and the check after both
    grant = ins.index('& icacls $Live /grant "${RunUser}:(OI)(CI)M"')
    deny = ins.index('& icacls $Live /deny "${RunUser}:(D,DC,WDAC,WO)"')
    assert grant < deny < ins.index("Test-GitAclSealed -RepoRoot $Live")
