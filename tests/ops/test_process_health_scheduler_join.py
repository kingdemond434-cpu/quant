"""The contract table and the box scripts name tasks the box actually declares.

CRO noon 2026-09-30 measured "71 NOT_SCHEDULED" -- exactly the size of the contract table. LIVE
rewrote ops/process_health.py with its own answer to the read-failure and aspect-row causes
(SCHEDULER_UNMEASURED rows; a parenthesised contract joined to its parent task) and its own tests
pin those. These pin the static half: a contract naming a task the box manifest does not declare,
and the retired MT5-Gateway task still named by a monitor or a box script.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


oc = _load("organ_contract")


def _owner(organ: str) -> str:
    """The task a contract row belongs to: `MT5-FrontierAudit (orthogonality)` -> its parent."""
    return organ.split(" (", 1)[0].strip()


def test_every_contract_owner_is_a_task_the_box_manifest_declares() -> None:
    """THE STATIC FENCE: a contract whose owner no manifest line declares is NOT_SCHEDULED on the
    box on every pass. Red here, before it ships, instead of red there every hour after."""
    text = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")
    declared = set(re.findall(r'^TASK\s+name="([^"]+)"', text, re.M))
    orphans = sorted(k for k in oc.CONTRACTS if _owner(k) not in declared)
    assert orphans == [], f"contracts with no declared box task: {orphans}"


def test_no_code_still_names_the_retired_gateway_task() -> None:
    """Audit R4: MT5-Gateway is Disabled; the monitors must name MT5-GatewayResident."""
    for rel in ("desks/mt5/scripts/check_desk_health.py", "desks/mt5/research/implementer.py",
                "ops/organ_contract.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r'"MT5-Gateway"', text), rel


def test_no_box_script_registers_requires_or_restarts_the_retired_gateway_task() -> None:
    """Audit 2026-09-30: the installer re-registered MT5-Gateway, the reboot drill required (and
    so re-ENABLED) it, and the migration restarted it. Executable lines must name the resident;
    comments may still tell the history."""
    for rel in ("desks/mt5/scripts/Install-QuantWindows.ps1", "ops/reboot_drill.ps1",
                "ops/migrate_to_new_box.ps1"):
        for n, line in enumerate((ROOT / rel).read_text(encoding="utf-8-sig").splitlines(), 1):
            code = line.split("#", 1)[0]
            assert not re.search(r"MT5-Gateway(?!Resident)", code), f"{rel}:{n}: {line.strip()}"
