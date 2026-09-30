"""process_health never turns a failed scheduler read into NOT_SCHEDULED rows.

CRO noon 2026-09-30 measured "71 NOT_SCHEDULED" -- exactly the size of the contract table, so
every contracted organ, the hourly cycle included, was reported as unable to run. These pin the
three causes: a failed read, suffixed aspect rows joined by their whole name, and a contract
naming a task the box manifest does not declare.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ph = _load("process_health")
oc = _load("organ_contract")

CONTRACTS = {
    "MT5-Hourly": ("art/events.jsonl", 180, "legs"),
    "MT5-FrontierAudit": ("art/pit.json", 1560, "pit"),
    "MT5-FrontierAudit (orthogonality)": ("art/orth.json", 1560, "orth"),
    "MT5-Missing": ("art/missing.json", 60, "never registered"),
}


def _fresh(tmp_path: Path) -> None:
    for rel, _age, _p in CONTRACTS.values():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: dict(CONTRACTS))
    _fresh(tmp_path)
    return tmp_path


def _rows(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in doc["processes"]}


def test_a_failed_scheduler_read_is_unmeasured_never_not_scheduled(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ph, "_scheduler_read", lambda: ([], {
        "source": "schtasks", "read": False, "why": "schtasks /query did not answer"}))
    doc = ph.build()
    assert doc["counts"].get("NOT_SCHEDULED", 0) == 0
    assert doc["scheduler"]["read"] is False
    assert {r["verdict"] for r in doc["processes"]} == {"UNMEASURED"}
    assert doc["status"] == "UNMEASURED"


def test_an_unread_scheduler_still_judges_the_artifact_clock(
        box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (box / "art/missing.json").unlink()
    monkeypatch.setattr(ph, "_scheduler_read", lambda: ([], {"read": False, "why": "x"}))
    rows = _rows(ph.build())
    assert rows["MT5-Missing"]["verdict"] == "NO_ARTIFACT"


def test_aspect_rows_join_to_their_owning_task(box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = [{"TaskName": "\\MT5-Hourly", "Last Result": "0", "Status": "Ready"},
             {"TaskName": "\\MT5-FrontierAudit", "Last Result": "0", "Status": "Ready"}]
    monkeypatch.setattr(ph, "_scheduler_read", lambda: (tasks, {"read": True, "why": ""}))
    rows = _rows(ph.build())
    assert rows["MT5-FrontierAudit (orthogonality)"]["verdict"] == "OK"
    assert rows["MT5-FrontierAudit (orthogonality)"]["task"] == "MT5-FrontierAudit"
    # The one genuinely unregistered organ is still the loudest row.
    assert rows["MT5-Missing"]["verdict"] == "NOT_SCHEDULED"
    assert rows["MT5-Hourly"]["verdict"] == "OK"


def test_the_task_directory_is_the_second_opinion(box: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_dir = box / "Tasks"
    tasks_dir.mkdir()
    for n in ("MT5-Hourly", "MT5-FrontierAudit"):
        (tasks_dir / n).write_text("<Task/>", encoding="utf-8")
    monkeypatch.setattr(ph, "TASKS_DIR", tasks_dir)

    def _no_schtasks(*_a: Any, **_k: Any) -> Any:
        raise FileNotFoundError("schtasks")
    monkeypatch.setattr(ph.subprocess, "run", _no_schtasks)
    doc = ph.build()
    rows = _rows(doc)
    assert doc["scheduler"]["existence_only"] is True
    assert rows["MT5-Missing"]["verdict"] == "NOT_SCHEDULED"


def test_every_contract_owner_is_a_task_the_box_manifest_declares() -> None:
    """THE STATIC FENCE: a contract whose owner no manifest line declares is NOT_SCHEDULED on the
    box on every pass. Red here, before it ships, instead of red there every hour after."""
    text = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")
    declared = set(re.findall(r'^TASK\s+name="([^"]+)"', text, re.M))
    orphans = sorted(k for k in oc.CONTRACTS if ph.owner_task(k) not in declared)
    assert orphans == [], f"contracts with no declared box task: {orphans}"


def test_existence_only_never_reads_a_fresh_artifact_as_ok(box: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit: a task file plus a fresh artifact is not a known run result -- UNMEASURED."""
    tasks_dir = box / "Tasks"
    tasks_dir.mkdir()
    for n in ("MT5-Hourly", "MT5-FrontierAudit"):
        (tasks_dir / n).write_text("<Task/>", encoding="utf-8")
    monkeypatch.setattr(ph, "TASKS_DIR", tasks_dir)

    def _no_schtasks(*_a: Any, **_k: Any) -> Any:
        raise FileNotFoundError("schtasks")
    monkeypatch.setattr(ph.subprocess, "run", _no_schtasks)
    doc = ph.build()
    rows = _rows(doc)
    assert rows["MT5-Hourly"]["verdict"] == "UNMEASURED"
    assert rows["MT5-FrontierAudit (orthogonality)"]["verdict"] == "UNMEASURED"
    assert doc["status"] != "OK"


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
