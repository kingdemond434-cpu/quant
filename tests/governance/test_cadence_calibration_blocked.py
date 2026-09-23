"""THE DETECTION FLOOR'S BLOCKER BECOMES AN ARTIFACT.

`scripts/calibrate_gauntlet.py` declares data/gauntlet_calibration.json and had never produced it
(measured 2026-09-08: absent, while data/ holds 215 other artifacts). The cadence leg ran it every
cycle, printed `NO ARTIFACT` and moved on, so the reason the one un-gameable progress metric was
never measured lived in a service log. Pinned here:

  * a failed run writes a BLOCKED record at the artifact's own path, in the shape
    scripts/certify_gauntlet.py uses for its own blocked run, plus rc and the last stderr line;
  * a measurement already on disk is carried under `previous`, never overwritten by a blocker;
  * a BLOCKED record is not a measurement: the leg does not count it as fired;
  * the leg itself calls the recorder on a non-zero exit and on a zero exit that wrote nothing.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "scripts/run_cadence.py"


def _mod():
    spec = importlib.util.spec_from_file_location("_cadence_calib", _SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules["_cadence_calib"] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def cadence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    m = _mod()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_CALIBRATION", tmp_path / "data" / "gauntlet_calibration.json")
    return m


_CERTIFY_SHAPE = {"generated_utc", "status", "blocker", "consequence", "resolution", "rows"}


def test_a_failed_run_writes_a_blocked_record_in_the_certify_gauntlet_shape(cadence) -> None:
    doc = cadence._record_blocked_calibration(
        1, "ModuleNotFoundError: No module named 'libs'", path=cadence._CALIBRATION)
    on_disk = json.loads(cadence._CALIBRATION.read_text("utf-8"))
    assert on_disk == doc
    assert set(on_disk) >= _CERTIFY_SHAPE, "same keys certify_gauntlet.py writes when blocked"
    assert on_disk["status"] == "BLOCKED" and on_disk["rows"] == []
    assert on_disk["rc"] == 1 and on_disk["at"] == on_disk["generated_utc"]
    assert on_disk["blocker"] == "ModuleNotFoundError: No module named 'libs'"
    assert "detection floor" in on_disk["consequence"]
    assert "calibrate_gauntlet.py" in on_disk["resolution"]
    assert not cadence._CALIBRATION.with_suffix(".json.tmp").exists(), "atomic write, no tmp left"


def test_a_silent_failure_and_a_silent_zero_exit_are_both_named(cadence) -> None:
    assert "without a line of stderr" in cadence._record_blocked_calibration(
        2, "", path=cadence._CALIBRATION)["blocker"]
    assert "exited 0 and wrote no artifact" in cadence._record_blocked_calibration(
        0, "", path=cadence._CALIBRATION)["blocker"]


def test_a_prior_measurement_is_carried_never_overwritten(cadence) -> None:
    cadence._CALIBRATION.parent.mkdir(parents=True)
    measured = {"generated_utc": "2026-09-01T00:00:00Z", "status": "MEASURED",
                "detection_floor": 3.0, "rows": [{"strength": 3.0, "power": 0.8}]}
    cadence._CALIBRATION.write_text(json.dumps(measured), "utf-8")
    first = cadence._record_blocked_calibration(1, "boom", path=cadence._CALIBRATION)
    assert first["previous"] == measured, "yesterday's floor is still the last floor measured"
    second = cadence._record_blocked_calibration(1, "boom again", path=cadence._CALIBRATION)
    assert second["previous"] == measured, "a second blocker carries the same measurement forward"
    assert "previous" not in cadence._record_blocked_calibration(
        1, "x", path=cadence._CALIBRATION.parent / "fresh.json"), "nothing to carry: none existed"


def test_a_blocked_record_is_not_a_measurement(cadence) -> None:
    assert cadence._calibration_measured(cadence._CALIBRATION) is False, "absent"
    cadence._record_blocked_calibration(1, "x", path=cadence._CALIBRATION)
    assert cadence._calibration_measured(cadence._CALIBRATION) is False, "BLOCKED"
    cadence._CALIBRATION.write_text(json.dumps({"status": "MEASURED", "rows": [1]}), "utf-8")
    assert cadence._calibration_measured(cadence._CALIBRATION) is True


def _completed(rc: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["x"], returncode=rc, stdout=stdout, stderr=stderr)


def test_the_leg_records_a_blocker_on_a_nonzero_exit_and_does_not_count_it_fired(
        cadence, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cadence, "_srun", lambda *a, **k: _completed(
        1, stdout="campaign: loading", stderr="Traceback\nModuleNotFoundError: libs"))
    fired: list[str] = []
    cadence._run_calibrate_gauntlet(fired)
    assert fired == []
    doc = json.loads(cadence._CALIBRATION.read_text("utf-8"))
    assert doc["status"] == "BLOCKED" and doc["rc"] == 1
    assert doc["blocker"] == "ModuleNotFoundError: libs", "the LAST stderr line, not stdout"
    assert "BLOCKED record" in capsys.readouterr().out


def test_the_leg_records_a_blocker_when_a_zero_exit_wrote_nothing(cadence, monkeypatch) -> None:
    monkeypatch.setattr(cadence, "_srun", lambda *a, **k: _completed(0, stdout="done"))
    fired: list[str] = []
    cadence._run_calibrate_gauntlet(fired)
    assert fired == []
    doc = json.loads(cadence._CALIBRATION.read_text("utf-8"))
    assert doc["status"] == "BLOCKED" and doc["rc"] == 0


def test_the_leg_counts_a_real_measurement_as_fired(cadence, monkeypatch) -> None:
    def _srun(*a, **k):
        cadence._CALIBRATION.parent.mkdir(parents=True, exist_ok=True)
        cadence._CALIBRATION.write_text(json.dumps({"status": "MEASURED", "rows": [1]}), "utf-8")
        return _completed(0, stdout="detection floor 3.0")
    monkeypatch.setattr(cadence, "_srun", _srun)
    fired: list[str] = []
    cadence._run_calibrate_gauntlet(fired)
    assert fired == ["gauntlet-calibration"]
    assert json.loads(cadence._CALIBRATION.read_text("utf-8"))["status"] == "MEASURED"


def test_a_stale_blocked_record_does_not_make_a_failed_run_look_fired(cadence,
                                                                     monkeypatch) -> None:
    """The old leg checked `.exists()`; a BLOCKED file at that path would have satisfied it."""
    cadence._record_blocked_calibration(1, "earlier", path=cadence._CALIBRATION)
    monkeypatch.setattr(cadence, "_srun", lambda *a, **k: _completed(0, stdout="nothing written"))
    fired: list[str] = []
    cadence._run_calibrate_gauntlet(fired)
    assert fired == []
