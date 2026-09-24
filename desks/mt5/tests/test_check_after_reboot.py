"""The restart-readiness check: absence must be the finding, and it must never repair anything."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_after_reboot as car  # noqa: E402


def _snap(procs, tasks, *, limit=245.95, boot=1000.0, at="T"):
    return {"at": at, "boot_epoch": boot,
            "commit": {"status": "MEASURED", "commit_limit_gb": limit},
            "processes": {p: {"pid": 1, "started_epoch": 1.0, "instances": 1} for p in procs},
            "tasks": {t: {"status": "Ready"} for t in tasks}}


def test_everything_returning_is_the_clean_verdict():
    base = _snap(["terminal64.exe", "gateway_resident.py"], ["MT5-Gauntlet", "MT5-Hourly"])
    now = _snap(["terminal64.exe", "gateway_resident.py"], ["MT5-Gauntlet", "MT5-Hourly"],
                limit=400.0, boot=2000.0)
    out = car.compare(base, now)
    assert out["ok"] is True
    assert out["verdict"] == "EVERYTHING RETURNED"
    assert out["rebooted_since_capture"] is True
    assert out["commit_limit_rose"] is True


def test_a_process_that_did_not_come_back_is_named():
    """The whole point: the gateway not returning must be a NAME, not a silence."""
    base = _snap(["terminal64.exe", "gateway_resident.py"], ["MT5-Gauntlet"])
    now = _snap(["terminal64.exe"], ["MT5-Gauntlet"], boot=2000.0)
    out = car.compare(base, now)
    assert out["ok"] is False
    assert out["processes_missing"] == ["gateway_resident.py"]
    assert out["processes_returned"] == ["terminal64.exe"]


def test_a_task_that_did_not_come_back_is_named():
    base = _snap(["terminal64.exe"], ["MT5-Gauntlet", "MT5-ReapGitWriters", "MT5-GauntletGuard"])
    now = _snap(["terminal64.exe"], ["MT5-Gauntlet"], boot=2000.0)
    out = car.compare(base, now)
    assert out["tasks_missing"] == ["MT5-GauntletGuard", "MT5-ReapGitWriters"]
    assert out["ok"] is False


def test_a_task_that_came_back_disabled_did_not_come_back():
    """A task present in name and Disabled in fact is the quiet shape of a dark desk."""
    base = _snap(["terminal64.exe"], ["MT5-Gauntlet"])
    now = _snap(["terminal64.exe"], [], boot=2000.0)
    now["tasks"] = {"MT5-Gauntlet": {"status": "Disabled"}}
    out = car.compare(base, now)
    assert out["tasks_newly_disabled"] == ["MT5-Gauntlet"]
    assert out["ok"] is False


def test_a_task_already_disabled_before_the_restart_is_not_a_regression():
    base = _snap(["terminal64.exe"], [])
    base["tasks"] = {"MT5-CycleNoon": {"status": "Disabled"}}
    now = _snap(["terminal64.exe"], [], boot=2000.0)
    now["tasks"] = {"MT5-CycleNoon": {"status": "Disabled"}}
    out = car.compare(base, now)
    assert out["tasks_newly_disabled"] == []
    assert out["ok"] is True


def test_a_commit_limit_that_did_not_rise_is_reported_even_when_everything_returned():
    """The restart has a PURPOSE. Everything coming back while the ceiling is unchanged means
    the change did not take, and that must be visible rather than read as success."""
    base = _snap(["terminal64.exe"], ["MT5-Gauntlet"])
    now = _snap(["terminal64.exe"], ["MT5-Gauntlet"], boot=2000.0)
    out = car.compare(base, now)
    assert out["ok"] is True
    assert out["commit_limit_rose"] is False


def test_verify_without_a_baseline_refuses_rather_than_passing(tmp_path, monkeypatch):
    """Verifying against nothing is not a verification -- it must not return success."""
    monkeypatch.setattr(car, "BASELINE", tmp_path / "absent.json")
    assert car.main(["--verify"]) == 2


def test_capture_then_verify_round_trips_on_the_real_box(tmp_path, monkeypatch):
    monkeypatch.setattr(car, "BASELINE", tmp_path / "base.json")
    monkeypatch.setattr(car, "VERDICT", tmp_path / "verdict.json")
    assert car.main(["--capture"]) == 0
    doc = json.loads((tmp_path / "base.json").read_text("utf-8"))
    assert doc["commit"]["status"] in {"MEASURED", "UNMEASURED"}
    assert isinstance(doc["tasks"], dict)
    car.main(["--verify"])
    v = json.loads((tmp_path / "verdict.json").read_text("utf-8"))
    assert v["verdict"] in {"EVERYTHING RETURNED", "SOMETHING DID NOT RETURN"}


def test_it_never_starts_stops_or_repairs_anything():
    """A verifier that repairs is a second, unreviewed controller of the box that trades."""
    src = Path(car.__file__).read_text(encoding="utf-8")
    for forbidden in (".terminate(", ".kill(", "taskkill", "schtasks\", \"/run",
                      "/change", "Restart-Computer", "shutdown"):
        assert forbidden not in src, f"check_after_reboot must never {forbidden}"
    # CIM is reachable only through PowerShell or wmic here, and this module uses neither --
    # asserting on the STRING would fail on the docstring that explains why it is avoided.
    assert "powershell" not in src.lower(), "CIM has hung on this box; schtasks and psutil only"
    assert "wmic" not in src.lower()


def test_a_leg_that_merely_happened_to_be_running_is_not_an_inventory_item():
    """The first real run captured two hourly legs mid-pass and then reported them missing on a
    box that had not restarted. Only residents and the named seeds belong in the inventory."""
    assert car.MIN_AGE_S >= 60.0
    assert "gateway_resident.py" in car.SEED_PROCESSES
    assert "terminal64.exe" in car.SEED_PROCESSES
    src = Path(car.__file__).read_text(encoding="utf-8")
    assert "if age < MIN_AGE_S and key not in SEED_PROCESSES:" in src
