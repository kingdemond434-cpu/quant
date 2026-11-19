"""The installer leg of replay-shadow (Governance ruling 2026-11-17 18:25Z, option (a)).

A PowerShell task installer under desks/mt5/scripts/ used to read UNMEASURED for ever, because the
replay imports only Python. It is MEASURED now only when its own text shows every target it runs
is one the replay vouches for; anything else stays UNMEASURED.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "replay_shadow_inst", ROOT / "ops/release/replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

INST = "desks/mt5/scripts/install_x_task.ps1"
GOOD = """# Installs the pager. It never touches MetaTrader (a comment: not code).
<# a block comment naming FTMO and gateway_paused #>
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\\..\\..')
$Script = Join-Path $RepoRoot 'scripts\\run_alerts.py'
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$Script`" --box"
if (Get-ScheduledTask -TaskName 'MT5-X' -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName 'MT5-X' -Confirm:$false
}
Register-ScheduledTask -TaskName 'MT5-X' -Action $action
Start-ScheduledTask -TaskName 'MT5-X'
"""


def _tree(tmp: Path, text: str, extra: dict[str, str] | None = None) -> Path:
    files = {INST: text, "scripts/run_alerts.py": "print(1)\n",
             "scripts/other_tool.py": "print(2)\n", **(extra or {})}  # fmt: skip
    for rel, body in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")
    return tmp


def test_an_installer_running_only_a_vouched_target_is_measured(tmp_path: Path) -> None:
    assert rs.installer_problems(_tree(tmp_path, GOOD), INST) == []


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (GOOD.replace("run_alerts.py", "other_tool.py"), "does not vouch"),  # unvouched target
        (GOOD.replace("run_alerts.py", "nowhere.py"), "does not hold"),  # unresolved target
        (GOOD + "Remove-Item gateway_paused\n", "venue or switch"),  # a switch in code
        (GOOD + "$n = 'FTMO'\n", "venue or switch"),  # a venue in code
        (GOOD + "Invoke-Expression $x\n", "dynamic execution"),
        (GOOD + "& $python other.py\n", "dynamic execution"),
        (GOOD + "Start-Process powershell\n", "dynamic execution"),
        (GOOD.replace("New-ScheduledTaskAction", "New-Thing"), "registers no"),
        ("$a = 1\n", "registers no"),
    ],
)  # fmt: skip
def test_anything_else_stays_unmeasured(tmp_path: Path, text: str, why: str) -> None:
    got = rs.installer_problems(_tree(tmp_path, text), INST)
    assert got and any(why in g for g in got), got


def test_only_the_harness_allowlist_vouches_never_the_replay_imports(tmp_path: Path) -> None:
    """#1249 audit MF1: an ENTRY_POINT or an imported file is not a vouched installer target."""
    gw = "desks/mt5/research/run_gateway_loop.py"
    text = GOOD.replace("scripts\\run_alerts.py", gw.replace("/", "\\"))
    got = rs.installer_problems(_tree(tmp_path, text, {gw: "x = 1\n"}), INST)
    assert any("does not vouch" in g for g in got), got


# The Auditor's three probes on 616741d98, each a one-line installer that read MEASURED.
PROBE_1 = (  # a second task for an ENTRY_POINT
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument "
    "'desks\\mt5\\research\\run_gateway_loop.py'\nRegister-ScheduledTask -TaskName X -Action $a\n"
)
PROBE_2 = (  # a cmd chain hidden behind ' # '
    "$a = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "
    '"/c scripts\\run_alerts.py # & python -m research.pf_allocator --mode fast"\n'
    "Register-ScheduledTask -TaskName X -Action $a\n"
)
PROBE_3 = (  # a module target, invisible to an extension scan
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument '-m research.run_gateway_loop'\n"
    "Register-ScheduledTask -TaskName X -Action $a  # see scripts/run_alerts.py\n"
)


@pytest.mark.parametrize("probe", [PROBE_1, PROBE_2, PROBE_3])
def test_the_audit_probes_stay_unmeasured(tmp_path: Path, probe: str) -> None:
    extra = {"desks/mt5/research/run_gateway_loop.py": "x = 1\n"}
    assert rs.installer_problems(_tree(tmp_path, probe, extra), INST)


@pytest.mark.parametrize(
    ("action", "why"),
    [
        ("-Execute 'powershell.exe' -Argument 'scripts\\run_alerts.py'", "not python"),
        ("-Execute $tool -Argument 'scripts\\run_alerts.py'", "not python"),
        ("-Execute 'python.exe' -Argument 'scripts\\run_alerts.py; x'", "shell chain"),
        ("-Execute 'python.exe' -Argument '-c print(1)'", "module flag"),
        ("-Execute 'python.exe' -Argument '--box'", "not a vouched target"),
    ],
)  # fmt: skip
def test_every_action_executes_python_on_a_vouched_script(
    tmp_path: Path, action: str, why: str
) -> None:
    text = f"$a = New-ScheduledTaskAction {action}\nRegister-ScheduledTask -TaskName X -Action $a\n"
    got = rs.installer_problems(_tree(tmp_path, "$tool = 'x.exe'\n" + text), INST)
    assert any(why in g for g in got), got


def test_the_allowlist_lives_in_the_harness_not_the_tree() -> None:
    """A PR cannot vouch for its own target: the rows are a constant of the harness module the
    base checkout runs, never a file read from the PR's tree."""
    assert "scripts/run_alerts.py" in rs.INSTALLER_TARGETS
    src = (ROOT / "ops/release/replay_shadow.py").read_text("utf-8")
    assert "INSTALLER_TARGETS = (" in src and "installer_targets.txt" not in src


_ROWS = (
    "# the box's tasks\n"
    'TASK name="MT5-Hourly" trigger="at logon" runs="desks/mt5/research/hourly.py" lane="ops"\n'
)
_ROW = ('TASK name="MT5-X" trigger="every 15 minutes" runs="scripts/run_alerts.py" '
        f'installer="{INST}" lane="ops"\n')  # fmt: skip


def _manifest_trees(tmp: Path) -> tuple[Path, Path]:
    b, h = tmp / "b", tmp / "h"
    for t, text in ((b, _ROWS), (h, _ROWS + _ROW)):
        (t / "desks/mt5/ops").mkdir(parents=True)
        (t / rs.COMPONENTS).write_text(
            'REQUIRED_TASKS: frozenset[str] = frozenset({"MT5-ClockFixer"})\n'
            'TASK_CANONICAL: dict[str, str] = {"MT5-Hourly": "x"}\n',
            "utf-8",
        )
        (t / rs.MANIFEST).write_text(text, "utf-8")
    return b, h


def test_a_manifest_row_for_a_measured_installer_is_not_money(tmp_path: Path) -> None:
    b, h = _manifest_trees(tmp_path)
    assert rs.manifest_is_money(b, h, set(), {INST}, set()) is True
    assert rs.manifest_is_money(b, h, set(), {INST}, set(), measured={INST}) is False


def test_measured_frees_only_the_installer_field(tmp_path: Path) -> None:
    """A measured installer named as the row's `runs` is still a money-path script there."""
    b, h = _manifest_trees(tmp_path)
    row = f'TASK name="MT5-X" trigger="every 15 minutes" runs="{INST}" lane="ops"\n'
    (h / rs.MANIFEST).write_text(_ROWS + row, "utf-8")
    assert rs.manifest_is_money(b, h, set(), {INST}, set(), measured={INST}) is True


# --------------------------------- the self-healer as a conditional target (Governance 18:45Z)

HEAL = r"""
import importlib.util
import ntpath
import subprocess
import sys

ENDABLE_TASKS: frozenset[str] = frozenset({"MT5-IndependenceIntake", "Quant-WorkflowGate"})
RUNNABLE_TASKS: frozenset[str] = frozenset({"Quant-WorkflowGate"})


def _on_windows():
    return sys.platform == "win32"


def _system32() -> str:
    'The System32 folder.'
    if _on_windows():
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260)
            if 0 < n < 260 and ntpath.isabs(buf.value):
                return str(buf.value)
        except Exception:
            pass
    return r"C:\Windows\System32"


SCHTASKS_EXE = ntpath.join(_system32(), "schtasks.exe")


def _dep(name, rel):
    return rel


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    return spec


def _schtasks(verb, task, xml=False):
    # the only subprocess
    allowed = {"/Query": ENDABLE_TASKS | RUNNABLE_TASKS, "/End": ENDABLE_TASKS,
               "/Run": RUNNABLE_TASKS}
    if verb not in allowed or task not in allowed[verb]:
        raise ValueError(task)
    tail = (["/XML"] if xml else ["/FO", "CSV", "/NH"]) if verb == "/Query" else []
    argv = [SCHTASKS_EXE, verb, "/TN", task, *tail]
    r = subprocess.run(argv, check=False)
    return {"rc": r.returncode, "argv": verb}


def main():
    _load("_box_self_heal_ph", _dep("process_health.py", "ops/process_health.py"))
    _schtasks("/End", "MT5-IndependenceIntake")
"""


# HOLD 4: the kill path as the harness pins it, and the one way the pass reaches it.
HEAL += (
    "\n\n"
    + rs.SELF_HEAL_PINS.read_text("utf-8")
    + "\n\ndef real_box():\n    return Box(procs=list, kill=_kill_tree)\n"
    + "\n\nclass Pass:\n    def stop(self, p):\n        return self.box.kill(p, [], None, None)\n"
)


def _heal(tmp: Path, text: str) -> Path:
    (tmp / "ops").mkdir(parents=True, exist_ok=True)
    (tmp / rs.SELF_HEAL).write_text(text, "utf-8")
    return tmp


def test_the_self_healer_is_vouched_while_it_only_stops_and_starts_literal_tasks(
    tmp_path: Path,
) -> None:
    assert rs.self_heal_problems(_heal(tmp_path, HEAL)) == []


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (HEAL.replace('"Quant-WorkflowGate"})\n', '"MT5-Gateway"})\n', 1), "outside the allowlist"),
        (HEAL.replace('frozenset({"Quant-WorkflowGate"})', "frozenset(load_names())"),
         "literal set"),
        (HEAL.replace('"/Run": RUNNABLE_TASKS', '"/Run": RUNNABLE_TASKS, "/Create": X'), "/Create"),
        (HEAL + "\nsubprocess.run(['python', 'x.py'])\n", "outside _schtasks"),
        (HEAL + "\nimport os\nos.system('x')\n", "calls os.system"),
        (HEAL + "\n_load('x', _dep('gw.py', 'desks/mt5/mt5desk/gateway.py'))\n", "SELF_HEAL_DEPS"),
        (HEAL + "\nX = 'Register-ScheduledTask'\n", "task-editing verb"),
    ],
)  # fmt: skip
def test_any_other_action_unvouches_it(tmp_path: Path, text: str, why: str) -> None:
    got = rs.self_heal_problems(_heal(tmp_path, text))
    assert got and any(why in g for g in got), got


def test_the_self_heal_allowlist_never_holds_an_order_path_task() -> None:
    """Governance condition 2, pinned on the base: no gateway, terminal, promoter or order task
    can join the tasks the self-healer may stop or start."""
    for task in rs.SELF_HEAL_TASKS:
        assert not rs.SELF_HEAL_FORBIDDEN.search(task), task
    for name in ("MT5-Gateway", "MT5-TerminalBoot", "MT5-Promoter", "E8-Executor",
                 "MT5-FTMO-Follower", "MT5-FusionDeadmanLive", "MT5-AdoptRelease",
                 "MT5-GatewayResident", "MT5-PfAllocator", "MT5-E8WindowGuard"):  # fmt: skip
        assert rs.SELF_HEAL_FORBIDDEN.search(name), name


def test_a_dotnet_process_launch_is_dynamic(tmp_path: Path) -> None:
    text = GOOD + "$p = [System.Diagnostics.Process]::Start($psi)\n"
    got = rs.installer_problems(_tree(tmp_path, text), INST)
    assert any("dynamic execution" in g for g in got), got


# The Auditor's probes on fa89cc752 (#1249 HOLD 19:07Z), each read MEASURED there.
_ACT = "Register-ScheduledTask -TaskName X -Action $a\n"
PROBES_V2 = [
    # MF1: a variable whose value is a module flag, expanded into the argument
    "$m = '-m research.run_gateway_loop'\n$s = 'scripts\\run_alerts.py'\n"
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument \"$m $s\"\n" + _ACT,
    # MF1: a typed binding the old assignment scan missed
    "[string]$m = '-m research.run_gateway_loop'\n"
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument $m\n" + _ACT,
    # MF1: Set-Variable
    "Set-Variable -Name m -Value '-m research.run_gateway_loop'\n"
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument $m  # scripts/run_alerts.py\n"
    + _ACT,
    # MF1: -Argument before -Execute
    "$a = New-ScheduledTaskAction -Argument '-m research.run_gateway_loop' -Execute 'python.exe'"
    "  # scripts/run_alerts.py\n" + _ACT,
    # a parameter's default is the caller's to override
    "param([string]$s = 'scripts\\run_alerts.py')\n"
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument $s\n" + _ACT,
    # a variable bound twice
    "$s = 'scripts\\run_alerts.py'\n$s = 'desks\\mt5\\research\\run_gateway_loop.py'\n"
    "$a = New-ScheduledTaskAction -Execute 'python.exe' -Argument $s\n" + _ACT,
]


@pytest.mark.parametrize("probe", PROBES_V2)
def test_the_second_audit_probes_stay_unmeasured(tmp_path: Path, probe: str) -> None:
    extra = {"desks/mt5/research/run_gateway_loop.py": "x = 1\n"}
    assert rs.installer_problems(_tree(tmp_path, probe, extra), INST)


def test_an_argument_before_execute_is_still_read(tmp_path: Path) -> None:
    text = "$a = New-ScheduledTaskAction -Argument 'scripts\\run_alerts.py' -Execute 'python.exe'\n"
    assert rs.installer_problems(_tree(tmp_path, text + _ACT), INST) == []


HEAL_ESCAPES = [
    # MF2: an alias escapes a check on the name `subprocess`
    HEAL.replace("import subprocess\n", "import subprocess as sp\n", 1),
    HEAL + "\nfrom subprocess import run\n",
    HEAL + "\ndef f():\n    subprocess.run(['python', 'x.py'])\n",
    HEAL + "\nrun = getattr(subprocess, 'run')\n",
    # MF2: the guard dropped, so a call site can name any task
    HEAL.replace(
        "    if verb not in allowed or task not in allowed[verb]:\n"
        "        raise ValueError(task)\n",
        "",
    )
    + "\n_schtasks('/End', 'MT5-Gateway')\n",
    # the guard weakened
    HEAL.replace("or task not in allowed[verb]", "and task not in allowed[verb]"),
    # task rebound inside _schtasks
    HEAL.replace("    r = subprocess.run(", "    task = 'MT5-Gateway'\n    r = subprocess.run("),
    # the task set rebound later
    HEAL + "\ndef g():\n    global ENDABLE_TASKS\n    ENDABLE_TASKS = frozenset({'MT5-Gateway'})\n",
    # a native launch through ctypes
    HEAL + "\nimport ctypes\nctypes.windll.kernel32.CreateProcessW(None)\n",
    # HOLD 3: the executable _schtasks launches rebound
    HEAL + '\nSCHTASKS_EXE = r"C:\\opt\\desks\\mt5\\research\\run_gateway.cmd"\n',
    HEAL.replace("argv = [SCHTASKS_EXE,", "argv = ['run_gateway.cmd',"),
    HEAL.replace("subprocess.run(argv,", "subprocess.run(argv, executable='cmd.exe',"),
    HEAL.replace('    return r"C:\\Windows\\System32"', '    return r"C:\\opt\\gw"'),
    # HOLD 3: launchers outside the import allowlist
    HEAL + "\nimport asyncio\n\nasync def _x():\n"
    "    await asyncio.create_subprocess_exec(\n"
    "        'python', 'desks/mt5/research/run_gateway_loop.py')\n",
    HEAL + "\nimport webbrowser\nwebbrowser.open('file:///C:/opt/x.bat')\n",
    HEAL + "\nimport multiprocessing\nmultiprocessing.Process(target=print).start()\n",
    # HOLD 3 follow-ons the allowlist also closes
    HEAL + "\nimport ctypes\n\ndef _y():\n    k = ctypes.WinDLL('kernel32')\n"
    "    return getattr(k, 'Create' + 'ProcessW')\n",
    HEAL + "\ndef _z():\n"
    "    return _load('subprocess', _dep('process_health.py', 'ops/process_health.py')).Popen\n",
    HEAL + "\nm = sys.modules['subprocess']\n",
    HEAL + "\nimport psutil\npsutil.Popen(['x'])\n",
    HEAL + "\nimport os\nos.system('x')\n",
    # HOLD 4: ending a process outside the pinned _kill_tree
    HEAL + "\nimport psutil\n\ndef _q():\n    for p in psutil.process_iter():\n"
    "        if p.name() == 'termi' + 'nal64.exe':\n            p.kill()\n",
    HEAL + "\nimport psutil\n\ndef _r(pid):\n    psutil.Process(pid).terminate()\n",
    HEAL + "\ndef _s(p):\n    getattr(p, 'kill')()\n",
    HEAL + "\ndef _v(p):\n    return p.__class__\n",
    HEAL + "\nDENY = ()\n",
    HEAL + "\ndef denied(p):\n    return None\n",
    HEAL.replace('            return f"{needle!r}: {why}"', "            return None"),
    HEAL.replace('("terminal64", "the MT5 terminal"),', ""),
    HEAL + "\ndef _t():\n    return Box(procs=list, kill=lambda *a: a[0])\n",
    HEAL + "\ndef _u(self):\n    self.box.kill = print\n",
]


def test_the_pinned_kill_guard_denies_every_forbidden_and_money_word() -> None:
    """HOLD 4, on the base: the deny list the harness pins refuses any process whose image or
    command line carries a word from SELF_HEAL_FORBIDDEN or MONEY_WORDS."""
    ns: dict[str, object] = {}
    exec(
        compile(
            "from __future__ import annotations\n"
            "import contextlib, ntpath, re, shlex, time\n"
            "from dataclasses import dataclass\n"
            "from typing import Any\n" + rs.SELF_HEAL_PINS.read_text("utf-8"),
            str(rs.SELF_HEAL_PINS),
            "exec",
        ),
        ns,
    )
    proc, denied = ns["Proc"], ns["denied"]
    words = [w.replace(".?", "_") for w in rs.SELF_HEAL_FORBIDDEN.pattern.split("|")]
    words += ["window guard", "window-guard", "windowguard", "terminal64", "metatrader",
              "autotrading", "mt5_gateway", "mt5-gateway", "ftmo", "fusion", "e8",
              "order_send", "order_check", "positions_get"]  # fmt: skip
    for w in words:
        assert rs.SELF_HEAL_FORBIDDEN.search(w) or rs.MONEY_WORDS.search(w), w
        for p in (
            proc(9, 1, "python.exe", f"python.exe C:\\opt\\quant\\x\\{w}.py", 0.0, 0.0),  # type: ignore[operator]
            proc(9, 1, f"{w}.exe", f"{w}.exe --once", 0.0, 0.0),  # type: ignore[operator]
            proc(9, 1, "python.exe", f"python.exe run.py --role {w.upper()}", 0.0, 0.0),  # type: ignore[operator]
        ):
            assert denied(p), (w, p)  # type: ignore[operator]


def test_the_harness_pins_the_kill_path() -> None:
    names = {rs._top_name(n) for n in ast.parse(rs.SELF_HEAL_PINS.read_text("utf-8")).body}
    assert {"DENY", "denied", "unreadable", "_deny_haystack", "_kill_tree", "_live_proc",
            "Proc"} <= names  # fmt: skip


@pytest.mark.parametrize("text", HEAL_ESCAPES)
def test_the_self_heal_escapes_unvouch_it(tmp_path: Path, text: str) -> None:
    assert rs.self_heal_problems(_heal(tmp_path, text))


DASH = "scripts/serve_dashboard.py"
DASH_GOOD = """
import subprocess
from http.server import SimpleHTTPRequestHandler
PUBLIC_FILES = frozenset({"index.html", "desk.html", "desk_state.json"})


def _public_name(p):
    n = p.lstrip("/")
    return n if n in PUBLIC_FILES else None


class H(SimpleHTTPRequestHandler):
    def send_head(self):
        name = _public_name(self.path)
        if name is None:
            self.send_error(404, "no")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "no")
        return None

    def do_GET(self):
        super().do_GET()


def main():
    subprocess.run(["build"], check=False)
"""
DASH_SET = 'frozenset({"index.html", "desk.html", "desk_state.json"})'
DASH_POST = (
    "\nclass H2(SimpleHTTPRequestHandler):\n    def do_POST(self):\n        pass\n"
    "    def send_head(self):\n        return _public_name(self.path)\n"
    "    def list_directory(self, p):\n        self.send_error(404)\n"
)
DASH_INST = GOOD.replace("run_alerts.py", "serve_dashboard.py").replace(" --box", " --port 8080")


def _dash(tmp: Path, src: str) -> Path:
    return _tree(tmp, DASH_INST, {DASH: src})


def test_the_dashboard_server_is_vouched_by_its_content(tmp_path: Path) -> None:
    assert rs.dashboard_problems(_dash(tmp_path, DASH_GOOD)) == []
    assert rs.installer_problems(_dash(tmp_path, DASH_GOOD), INST) == []


@pytest.mark.parametrize(
    ("src", "why"),
    [
        (DASH_GOOD + DASH_POST, "do_POST"),
        (DASH_GOOD.replace("    def list_directory", "    def other"), "list_directory"),
        (DASH_GOOD.replace("name = _public_name(self.path)", "name = self.path"), "send_head"),
        (DASH_GOOD.replace(DASH_SET, 'frozenset({"a/b.html"})'), "plain page"),
        (DASH_GOOD.replace(DASH_SET, "frozenset(x)"), "PUBLIC_FILES"),
        (DASH_GOOD.replace("return n if n in PUBLIC_FILES else None", "return n"), "membership"),
        (DASH_GOOD.replace("super().do_GET()", "subprocess.run(['x'])"), "subprocess"),
        (DASH_GOOD + "\nimport os\nos.system('x')\n", "os.system"),
        ("class H:\n    pass\n", "no request handler"),
        ("def (", "cannot be parsed"),
    ],
)  # fmt: skip
def test_a_dashboard_server_that_regresses_is_unmeasured(
    tmp_path: Path, src: str, why: str
) -> None:
    got = rs.dashboard_problems(_dash(tmp_path, src))
    assert got and any(why in g for g in got), got
    assert rs.installer_problems(_dash(tmp_path, src), INST), "the installer must follow"


def test_the_dashboard_is_not_vouched_unconditionally() -> None:
    assert DASH not in rs.INSTALLER_TARGETS
    assert rs.CONDITIONAL_TARGETS[DASH] is rs.dashboard_problems
