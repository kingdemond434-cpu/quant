"""A scheduled task whose organ talks to the MT5 terminal must run as the interactive user.

MEASURED 2026-10-29 (MT5-ContractTerms rc 1 every hour). MetaTrader's Python IPC endpoint belongs
to the desktop session that owns terminal64 (session 2 on the box). A task under SYSTEM, or under
any user with LogonType S4U, runs in Session 0 and `initialize` fails with -10004/-10005 however
healthy the terminal is. install_contract_terms_task.ps1 copied MT5-MoatSilver's principal (SYSTEM)
with S4U, so the contract-terms recorder could never attach. Install-QuantWindows.ps1,
install_e8_tasks.ps1 and the FTMO installers had each learned this separately; nothing made it a
rule.

THE RULE. For every installer that registers a task, each organ it launches that imports
MetaTrader5 or calls `attach_or_initialize` must be registered with `-LogonType Interactive`.
Organs are judged on their own source (one level -- a module that reaches the terminal only through
an import is not seen). Three installer shapes are read: the Install-QuantWindows task table (an
`@{ Name = ...; Script = ... }` row is interactive iff its name is in the `$t.Name -in @(...)`
list), install_e8_tasks' `Set-E8Task ... -RequiresDesktop`, and the one-task installer (every
principal it builds must be Interactive).

KNOWN_HEADLESS names the registrations that break the rule TODAY and are not changed here; each is
an owner decision recorded in the failing-task sweep PR, and the list may only shrink.
"""
from __future__ import annotations

import re
import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.wrapper_invocations import (  # noqa: E402
    _join_continuations,
    _tracked,
    invocations,
    resolve_script,
)

_MT5 = re.compile(r"^\s*(?:import MetaTrader5|from MetaTrader5 import)|attach_or_initialize\(",
                  re.M)

#: (installer, task) -> why it is still headless. Shrink only.
KNOWN_HEADLESS: dict[tuple[str, str], str] = {
    ("desks/mt5/scripts/Install-QuantWindows.ps1", "MT5-AllocatorFast"):
        "pf_allocator opens the terminal only for live pricing and degrades without it; owner call",
    ("desks/mt5/scripts/Install-QuantWindows.ps1", "MT5-DeskState"):
        "build_zentech_state reads the account opportunistically; owner call",
    ("desks/mt5/scripts/Install-QuantWindows.ps1", "MT5-MoatRecorder"):
        "moat_recorder initialize() under SYSTEM; owner call (same failure class as ContractTerms)",
    ("desks/mt5/scripts/Install-QuantWindows.ps1", "MT5-FusionDeadmanDryRun"):
        "fusion_deadman is owned by another builder; owner call",
}


@cache
def talks_to_terminal(script: str) -> bool:
    return bool(_MT5.search((ROOT / script).read_text("utf-8", errors="replace")))


def registrations(rel: str) -> list[tuple[str, str, bool]]:
    """(task, organ, interactive) for each MT5-relevant registration the installer makes."""
    text = (ROOT / rel).read_text("utf-8", errors="replace")
    if "Register-ScheduledTask" not in text:
        return []
    out: list[tuple[str, str, bool]] = []
    rows = re.findall(r'@\{\s*Name\s*=\s*"([^"]+)"(.*?)\}', text, re.S)
    if rows:
        listed = re.search(r"\$t\.Name\s+-in\s+@\(([^)]*)\)", text)
        interactive = set(re.findall(r'"([^"]+)"', listed.group(1))) if listed else set()
        for name, body in rows:
            m = re.search(r'Script\s*=\s*"([^"]+\.py)"', body)
            script = resolve_script(m.group(1)) if m else None
            if script:
                out.append((name, script, name in interactive))
    for _, line in _join_continuations(text):
        m = re.search(r'Set-E8Task\s+-Name\s+"([^"]+)".*?"([\w/\\.]+\.py)"', line)
        if m and (script := resolve_script(m.group(2))):
            out.append((m.group(1), script, "-RequiresDesktop" in line))
    if rows or "Set-E8Task" in text:
        return out
    # The one-task installer: every principal it builds is the task's principal.
    name = re.search(r"\$TaskName\s*=\s*['\"]([^'\"]+)['\"]", text)
    logons = re.findall(r"-LogonType\s+(\S+)", text)
    interactive = bool(logons) and all(lt == "Interactive" for lt in logons)
    for _, script, _flags in invocations(rel):
        out.append((name.group(1) if name else rel, script, interactive))
    return out


def violations() -> list[str]:
    bad = []
    for rel in _tracked((".ps1",)):
        for task, script, interactive in registrations(rel):
            if interactive or not talks_to_terminal(script) or (rel, task) in KNOWN_HEADLESS:
                continue
            bad.append(f"{rel}: {task} runs {script}, which imports MetaTrader5, under a "
                       "non-interactive principal (SYSTEM / S4U cannot reach the terminal)")
    return sorted(set(bad))


def test_contract_terms_is_registered_interactive() -> None:
    regs = registrations("desks/mt5/scripts/install_contract_terms_task.ps1")
    assert regs and all(i for _, _, i in regs), regs
    assert any(s == "desks/mt5/mt5desk/tape.py" for _, s, _ in regs)


def test_the_quantwindows_table_is_read() -> None:
    regs = {t: i for t, _, i in registrations("desks/mt5/scripts/Install-QuantWindows.ps1")}
    assert regs.get("MT5-Shadow") is True and regs.get("MT5-MoatRecorder") is False


def test_every_terminal_task_runs_as_the_interactive_user() -> None:
    bad = violations()
    assert not bad, "\n  ".join(["MT5 organ under a headless principal:", *bad])


def test_the_exemption_list_names_only_live_registrations() -> None:
    """A fixed or removed registration must leave KNOWN_HEADLESS, or the list only grows."""
    live = {(rel, t) for rel in {r for r, _ in KNOWN_HEADLESS}
            for t, s, i in registrations(rel) if talks_to_terminal(s) and not i}
    stale = sorted(set(KNOWN_HEADLESS) - live)
    assert not stale, f"no longer headless MT5 registrations, drop them: {stale}"


def test_contract_terms_installer_refuses_the_machine_account() -> None:
    """Audit, 2026-10-29: run as SYSTEM, $env:USERNAME is `HOST$`; registered under it the task
    never fires. The installer must refuse a name ending in `$` as it refuses SYSTEM."""
    text = (ROOT / "desks/mt5/scripts/install_contract_terms_task.ps1").read_text("utf-8")
    assert re.search(r"\$bareUser\.EndsWith\('\$'\)", text)
    assert re.search(r"'SYSTEM',\s*'S-1-5-18'", text)
    guard = text.index("$bareUser.EndsWith")
    assert guard < text.index("New-ScheduledTaskPrincipal"), "refuse before registering"


def test_contract_terms_is_held_to_an_artifact() -> None:
    """An Interactive task does not fire while its user is logged off: only an aging artifact
    tells that silence from health, so MT5-ContractTerms must carry an organ contract on the
    report tape.py rewrites every pass."""
    sys.path.insert(0, str(ROOT / "ops"))
    from organ_contract import CONTRACTS

    artifact, max_age, _ = CONTRACTS["MT5-ContractTerms"]
    assert artifact == "desks/mt5/reports/BROKER_SWAPS_FRESHNESS.json"
    assert 60 < max_age <= 180
    tape = (ROOT / "desks/mt5/mt5desk/tape.py").read_text("utf-8")
    assert '"BROKER_SWAPS_FRESHNESS.json"' in tape
