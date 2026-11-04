"""Two misreadings process_health published on the box (2026-11-04).

1. 0x800710E0 on a task that is RUNNING under MultipleInstances=IgnoreNew is the scheduler
   declining a later trigger, not an operator refusal: MT5-TickRecorder carried it all day.
2. A contracted artifact that EXISTS but has no usable internal stamp was reported as
   "does not exist" (TAPE_RECORDER.json without `last_tick_utc`), which sent the box looking
   for a file it was holding.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_running_refusal", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)


def _row(name: str, status: str, code: str) -> dict[str, str]:
    return {"TaskName": f"\\{name}", "Status": status, "Scheduled Task State": "Enabled",
            "Last Result": code}


def _build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rows: list[dict[str, str]],
           contracts: dict[str, tuple[str, int, str]]) -> dict[str, Any]:
    (tmp_path / "fresh.json").write_text("{}", "utf-8")
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    monkeypatch.setattr(ph, "_contracts", lambda: dict(contracts))
    monkeypatch.setattr(ph, "_tasks", lambda: (rows, "OK schtasks"))
    return {r["name"]: r for r in ph.build()["processes"]}


@pytest.mark.parametrize("code", ["-2147020576", "2147946720", "0x800710E0"])
def test_refusal_on_a_running_task_reads_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: str
) -> None:
    by = _build(monkeypatch, tmp_path, [_row("MT5-TickRecorder", "Running", code)],
                {"MT5-TickRecorder": ("fresh.json", 120, "tape")})
    row = by["MT5-TickRecorder"]
    assert row["verdict"] == "OK"
    assert row["last_result"].startswith("RUNNING")
    assert "refused the request" not in row["last_result"]


def test_refusal_on_a_task_that_is_not_running_keeps_its_meaning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    by = _build(monkeypatch, tmp_path, [_row("MT5-LocalConvert", "Ready", "-2147020576")],
                {"MT5-LocalConvert": ("fresh.json", 180, "convert")})
    row = by["MT5-LocalConvert"]
    assert row["verdict"] == "FAILING"
    assert row["last_result"] == ph.RESULT_MEANING[2147946720]


def test_an_existing_file_with_no_stamp_is_not_called_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rel = "desks/mt5/reports/TAPE_RECORDER.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text('{"state": "RECORDING"}', "utf-8")   # the box's file: no last_tick_utc
    monkeypatch.setattr(ph, "_artifact_age", lambda artifact: None)
    by = _build(monkeypatch, tmp_path, [_row("MT5-TickRecorder", "Running", "267009")],
                {"MT5-TickRecorder": (rel, 120, "tape")})
    row = by["MT5-TickRecorder"]
    assert row["verdict"] == "NO_ARTIFACT"
    assert "does not exist" not in row["why"]
    assert "last_tick_utc" in row["why"] and "exists" in row["why"]


def test_a_missing_file_is_still_called_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rel = "desks/mt5/reports/TAPE_RECORDER.json"
    by = _build(monkeypatch, tmp_path, [_row("MT5-TickRecorder", "Running", "267009")],
                {"MT5-TickRecorder": (rel, 120, "tape")})
    assert by["MT5-TickRecorder"]["why"] == f"{rel} does not exist"
