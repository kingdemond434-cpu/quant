"""Every declared box task has a row, and a refused trigger with a fresh artifact is not FAILING.

Hourly pass gap audit, 2026-11-18: MT5-PlumbingPager (and six more manifest tasks) had no row at
all in process_health.json, so nobody could see whether they ran; and MT5-CycleNoon read
0x800710E0 every hour with no contract to judge it by."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
import organ_contract as oc  # noqa: E402
import process_health as ph  # noqa: E402

ART = "desks/mt5/data/cycle_state_noon.json"


@pytest.fixture
def box(monkeypatch: Any, tmp_path: Path) -> Path:
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    (tmp_path / "desks/mt5/data").mkdir(parents=True)
    monkeypatch.setattr(ph, "_artifact_age", lambda a: ph._age_min(ph.ROOT / a))
    monkeypatch.setattr(ph, "_read_report", lambda: None)
    return tmp_path


def _task(name: str, code: str = "0", status: str = "Ready") -> dict[str, str]:
    return {
        "TaskName": f"\\{name}",
        "Scheduled Task State": "Enabled",
        "Status": status,
        "Last Run Time": "now",
        "Next Run Time": "later",
        "Last Result": code,
    }


def _build(
    monkeypatch: Any,
    tasks: list[dict[str, str]],
    manifest: dict[str, Any],
    contracts: dict[str, Any],
    status: str = "OK schtasks",
) -> dict[str, Any]:
    monkeypatch.setattr(ph, "_tasks", lambda: (tasks, status))
    monkeypatch.setattr(ph, "_contracts", lambda: contracts)
    monkeypatch.setattr(ph, "_manifest", lambda: manifest)
    return {r["name"]: r for r in ph.build()["processes"]}


MANIFEST = {
    "MT5-PlumbingPager": {
        "trigger": "every 15 minutes",
        "lane": "ops",
        "installer": "desks/mt5/scripts/install_plumbing_pager_task.ps1",
    },
    "MT5-Known": {"trigger": "hourly", "lane": "research", "installer": "x.ps1"},
}


def test_a_declared_task_missing_from_the_scheduler_is_not_scheduled(
    box: Path, monkeypatch: Any
) -> None:
    rows = _build(monkeypatch, [_task("MT5-Known")], MANIFEST, {})
    row = rows["MT5-PlumbingPager"]
    assert row["verdict"] == "NOT_SCHEDULED" and "box_tasks.manifest" in row["why"]
    assert row["installer"] == "desks/mt5/scripts/install_plumbing_pager_task.ps1"
    assert rows["MT5-Known"]["verdict"] == "UNCONTRACTED"


def test_an_unread_scheduler_never_claims_a_task_is_missing(box: Path, monkeypatch: Any) -> None:
    rows = _build(monkeypatch, [], MANIFEST, {}, status="UNMEASURED: schtasks timed out")
    assert "MT5-PlumbingPager" not in rows


def test_a_contracted_missing_task_gets_one_row_not_two(box: Path, monkeypatch: Any) -> None:
    contracts = {"MT5-PlumbingPager": ("desks/mt5/reports/PLUMBING_PAGER.json", 45, "pager")}
    doc_rows = _build(monkeypatch, [_task("MT5-Known")], MANIFEST, contracts)
    assert doc_rows["MT5-PlumbingPager"]["verdict"] == "NOT_SCHEDULED"
    assert doc_rows["MT5-PlumbingPager"]["artifact"] == "desks/mt5/reports/PLUMBING_PAGER.json"


def _art(root: Path, age_min: float) -> None:
    f = root / ART
    f.write_text("{}", encoding="utf-8")
    t = time.time() - age_min * 60
    os.utime(f, (t, t))


def test_a_refused_trigger_with_a_fresh_artifact_is_not_failing(
    box: Path, monkeypatch: Any
) -> None:
    _art(box, 120)
    rows = _build(
        monkeypatch,
        [_task("MT5-CycleNoon", "2147946720")],
        {"MT5-CycleNoon": {"trigger": "hourly; window", "lane": "research"}},
        {"MT5-CycleNoon": (ART, 1560, "noon pass")},
    )
    row = rows["MT5-CycleNoon"]
    assert row["verdict"] == "OK" and "refused" in row["why"]


def test_a_refused_trigger_with_a_stale_artifact_is_still_judged_stale(
    box: Path, monkeypatch: Any
) -> None:
    _art(box, 2000)
    rows = _build(
        monkeypatch,
        [_task("MT5-CycleNoon", "2147946720")],
        {"MT5-CycleNoon": {"trigger": "hourly; window", "lane": "research"}},
        {"MT5-CycleNoon": (ART, 1560, "noon pass")},
    )
    assert rows["MT5-CycleNoon"]["verdict"] == "STALE"


def test_a_refused_trigger_with_no_contract_still_fails(box: Path, monkeypatch: Any) -> None:
    rows = _build(
        monkeypatch,
        [_task("MT5-Other", "2147946720")],
        {"MT5-Other": {"trigger": "hourly", "lane": "research"}},
        {},
    )
    assert rows["MT5-Other"]["verdict"] == "FAILING"


def test_the_pager_and_the_noon_cycle_are_contracted() -> None:
    assert oc.CONTRACTS["MT5-PlumbingPager"][0] == "desks/mt5/reports/PLUMBING_PAGER.json"
    assert oc.CONTRACTS["MT5-CycleNoon"][0] == ART
    pager = (ROOT / "scripts/run_alerts.py").read_text(encoding="utf-8")
    assert 'Path("desks/mt5/reports/PLUMBING_PAGER.json")' in pager
    cycle = (ROOT / "desks/mt5/scripts/Run-DeskCycle.ps1").read_text(encoding="utf-8")
    assert "data\\cycle_state_{0}.json" in cycle
