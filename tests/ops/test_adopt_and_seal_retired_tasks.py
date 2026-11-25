"""Adopt-And-Seal step 1c disables retired ghost tasks, never unregisters them, on two conditions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1"
DECL = ROOT / "desks" / "mt5" / "ops" / "retired_tasks.json"


def _step() -> str:
    src = SCRIPT.read_text("utf-8", errors="ignore")
    assert "1c. RETIRED TASKS" in src
    return src.split("1c. RETIRED TASKS", 1)[1].split("2a. the box's release signing key", 1)[0]


def test_declaration_lists_deepen_universe() -> None:
    rows = json.loads(DECL.read_text("utf-8"))["retired"]
    assert "MT5-DeepenUniverse" in [r["task"] for r in rows]


def test_step_disables_never_unregisters() -> None:
    src = SCRIPT.read_text("utf-8", errors="ignore")
    assert "Unregister-ScheduledTask" not in src
    step = _step()
    assert "Disable-ScheduledTask" in step and "Export-ScheduledTask" in step


def test_step_requires_both_conditions_and_is_fail_soft() -> None:
    step = _step()
    assert "retired_tasks.json" in step          # condition 1: declared retired
    assert "Test-Path -LiteralPath $c" in step   # condition 2: target script absent
    assert step.index("if ($anyExists)") < step.index("Disable-ScheduledTask")
    assert step.count("catch {") >= 2
