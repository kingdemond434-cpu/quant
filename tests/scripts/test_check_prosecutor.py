"""Which statistical test judges whom: LIT on a clock, UNSCHEDULED, or DARK with no caller."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_prosecutor as cp  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "libs" / "validation").mkdir(parents=True)
    (tmp_path / "libs" / "autodiscovery").mkdir(parents=True)
    (tmp_path / "ops").mkdir()
    (tmp_path / "desks" / "mt5" / "research").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "ops").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    for name in ("dsr", "bootstrap", "ghost_test"):
        (tmp_path / "libs" / "validation" / f"{name}.py").write_text("x = 1\n", "utf-8")
    (tmp_path / "libs" / "validation" / "__init__.py").write_text("", "utf-8")
    (tmp_path / "libs" / "autodiscovery" / "validation.py").write_text(
        "from libs.validation import bootstrap\n", "utf-8")
    (tmp_path / "desks" / "mt5" / "research" / "hourly_cycle.py").write_text(
        'def daily():\n    pass\n_producer("judge", "scripts/judge.py")\n', "utf-8")
    (tmp_path / "scripts" / "judge.py").write_text(
        "from libs.validation import dsr\n", "utf-8")
    (tmp_path / "desks" / "mt5" / "ops" / "box_tasks.manifest").write_text(
        'TASK name="MT5-X" script="scripts/judge.py"\n', "utf-8")
    return tmp_path


def test_a_module_a_clock_reaches_is_lit_and_one_nothing_imports_is_dark(tmp_path: Path) -> None:
    doc = cp.census(_repo(tmp_path))
    mods = doc["modules"]
    assert mods["libs.validation.dsr"]["verdict"] == "LIT"
    assert mods["libs.validation.dsr"]["scheduled_callers"] == ["scripts/judge.py"]
    assert mods["libs.validation.bootstrap"]["verdict"] == "UNSCHEDULED", \
        "imported by the autodiscovery validator, which no clock runs in this fixture"
    assert mods["libs.validation.ghost_test"]["verdict"] == "DARK"
    assert doc["lit"] == ["libs.validation.dsr"]
    assert "libs.validation.ghost_test" in doc["dark"]


def test_the_stack_is_named_from_the_caller(tmp_path: Path) -> None:
    doc = cp.census(_repo(tmp_path))
    assert doc["modules"]["libs.validation.bootstrap"]["stack"] == "autodiscovery"
    assert doc["modules"]["libs.validation.ghost_test"]["stack"] == "none"
    assert set(doc["by_stack"]) <= {"ten_gates", "autodiscovery", "other", "none"}


def test_scheduled_files_reads_timers_tasks_and_cycle_legs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "ops" / "quant-x.service").write_text(
        "[Service]\nExecStart=/usr/bin/python3 scripts/judge.py\n", "utf-8")
    sched = cp.scheduled_files(repo)
    assert "scripts/judge.py" in sched
    assert "desks/mt5/research/hourly_cycle.py" in sched


def test_the_real_repo_census_is_measurable_and_writes_a_report(tmp_path: Path) -> None:
    out = tmp_path / "prosecutor.json"
    assert cp.main(["--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["n_modules"] >= 40, "libs/validation alone holds dozens of judges"
    assert doc["lit"], "at least one statistical module must be reachable from a clock"
    assert set(doc["modules"]["libs.validation.dsr"]) >= {"callers", "scheduled_callers", "stack"}
