"""The box-infra fence: a never-run installer is NEVER, a silent task is STALE, a firing one is
REGISTERED, and off the trading box the verdict is UNMEASURED with exit 0 (absence is not PASS)."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_box_infra",
                                               ROOT / "scripts" / "check_box_infra.py")
assert _spec and _spec.loader
cbi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cbi)


def _tasks(tmp: Path) -> tuple[tuple[str, Path, int, str], ...]:
    return (("A", tmp / "a.json", 300, "ia.ps1"), ("B", tmp / "b.json", 300, "ib.ps1"),
            ("C", tmp / "c.json", 300, "ic.ps1"))


def test_states(tmp_path: Path) -> None:
    now = 1_000_000.0
    t = _tasks(tmp_path)
    t[0][1].write_text(json.dumps({"ping": {"status": "NOT_ARMED"}}))
    os.utime(t[0][1], (now - 100, now - 100))
    t[1][1].write_text(json.dumps({"verdict": "EXPOSED"}))
    os.utime(t[1][1], (now - 700, now - 700))
    doc = cbi.measure(now, t)
    st = {r["task"]: (r["state"], r["reported"]) for r in doc["tasks"]}
    assert st == {"A": ("REGISTERED", "NOT_ARMED"), "B": ("STALE", "EXPOSED"),
                  "C": ("NEVER", None)}
    assert doc["verdict"] == "FAIL" and doc["not_registered"] == ["B", "C"]


def test_all_firing_passes(tmp_path: Path) -> None:
    now = 1_000_000.0
    t = _tasks(tmp_path)
    for _, p, _, _ in t:
        p.write_text("{}")
        os.utime(p, (now - 10, now - 10))
    assert cbi.measure(now, t)["verdict"] == "PASS"


def test_off_box_is_unmeasured_not_pass(monkeypatch: pytest.MonkeyPatch,
                                        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cbi, "on_trading_box", lambda: False)
    assert cbi.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "UNMEASURED"


def test_every_task_has_an_installer_on_disk() -> None:
    for name, _, _, installer in cbi.TASKS:
        assert (ROOT / installer).exists(), name
