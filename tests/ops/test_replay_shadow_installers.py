"""The installer leg of replay-shadow (Governance ruling 2026-11-17 18:25Z, option (a)).

A PowerShell task installer under desks/mt5/scripts/ used to read UNMEASURED for ever, because the
replay imports only Python. It is MEASURED now only when its own text shows every target it runs
is one the replay vouches for; anything else stays UNMEASURED.
"""

from __future__ import annotations

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
    assert rs.installer_problems(_tree(tmp_path, GOOD), INST, set()) == []


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
    got = rs.installer_problems(_tree(tmp_path, text), INST, set())
    assert got and any(why in g for g in got), got


def test_a_target_the_replay_imported_is_vouched(tmp_path: Path) -> None:
    text = GOOD.replace("run_alerts.py", "other_tool.py")
    tree = _tree(tmp_path, text)
    assert rs.installer_problems(tree, INST, set())
    assert rs.installer_problems(tree, INST, {"scripts/other_tool.py"}) == []


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

HEAL = """
import importlib.util
import subprocess

ENDABLE_TASKS: frozenset[str] = frozenset({"MT5-IndependenceIntake", "Quant-WorkflowGate"})
RUNNABLE_TASKS: frozenset[str] = frozenset({"Quant-WorkflowGate"})


def _dep(name, rel):
    return rel


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    return spec


def _schtasks(verb, task):
    allowed = {"/Query": ENDABLE_TASKS | RUNNABLE_TASKS, "/End": ENDABLE_TASKS,
               "/Run": RUNNABLE_TASKS}
    r = subprocess.run(["schtasks.exe", verb, "/TN", task], check=False)
    return {"rc": r.returncode, "argv": verb}


def main():
    _load("ph", _dep("process_health.py", "ops/process_health.py"))
    _schtasks("/End", "MT5-IndependenceIntake")
"""


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
         "not a literal"),
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
    got = rs.installer_problems(_tree(tmp_path, text), INST, set())
    assert any("dynamic execution" in g for g in got), got
