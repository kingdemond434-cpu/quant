from pathlib import Path


DESK = Path(__file__).resolve().parents[1]


def test_the_qquant_certifier_is_admitted_on_memory_not_queued_behind_the_judge() -> None:
    # The judge's sweep runs back to back and held the shared lane all day, so every QQuant
    # launch deferred with rc 0 (QQUANT_GATES.json 341 min old, contract 180, 2026-11-11).
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    qquant = (DESK / "research" / "certifier_launcher.py").read_text("utf-8")
    assert 'exclusive_job("certification_lane"' in external
    assert "certification_lane" not in qquant.split('"""', 2)[2]
    assert "exclusive_job(LANE, need_mb=NEED_MB)" in qquant


def test_expected_contention_defers_without_false_failure() -> None:
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert "another canonical certifier owns the lane" in external
    assert "return 0" in external


def _launcher():
    import importlib
    import sys
    if str(DESK) not in sys.path:
        sys.path.insert(0, str(DESK))
    return importlib.import_module("research.certifier_launcher")


def test_a_stand_down_is_recorded_with_its_reason(tmp_path) -> None:
    import json
    import os
    import time
    cl = _launcher()
    art = tmp_path / "QQUANT_GATES.json"
    art.write_text("{}", "utf-8")
    rep = tmp_path / "launch.json"
    rc = cl.stand_down({"pid": 42, "owner": "ALIVE"}, artifact=art, report=rep)
    doc = json.loads(rep.read_text("utf-8"))
    assert rc == 0, "fresh artifact: a duplicate launch is expected contention"
    assert doc["verdict"] == "STOOD_DOWN" and doc["reason"] == "DUPLICATE"
    assert doc["detail"]["pid"] == 42 and doc["contract_breached"] is False
    old = time.time() - (cl.CONTRACT_MIN + 1) * 60
    os.utime(art, (old, old))
    rc = cl.stand_down({"reason": "NO_ROOM", "need_mb": 3000, "free_mb": 900},
                       artifact=art, report=rep)
    doc = json.loads(rep.read_text("utf-8"))
    assert rc == cl.STANDDOWN_BREACH_EXIT, "a stand-down past the contract is a failure"
    assert doc["reason"] == "NO_ROOM" and doc["contract_breached"] is True


def test_a_missing_artifact_breaches_the_contract(tmp_path) -> None:
    cl = _launcher()
    rc = cl.stand_down(None, artifact=tmp_path / "absent.json", report=tmp_path / "l.json")
    assert rc == cl.STANDDOWN_BREACH_EXIT


def test_qquant_lease_is_taken_before_heavy_target_import() -> None:
    launcher = (DESK / "research" / "certifier_launcher.py").read_text("utf-8")
    qquant = (DESK / "research" / "qquant_gates.py").read_text("utf-8")
    installer = (DESK / "scripts" / "Install-QuantWindows.ps1").read_text("utf-8")
    assert "certifier_launcher.py" in installer
    assert "qquant_gates.py" in launcher
    assert "subprocess.run" in launcher
    assert "OPENBLAS_NUM_THREADS" in launcher
    assert 'exclusive_job("certification_lane"' not in qquant


def test_gauntlet_checks_broker_h1_availability_once_per_symbol() -> None:
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert "_LIVE_H1_AVAILABLE: dict[str, bool]" in external
    assert "if key not in _LIVE_H1_AVAILABLE:" in external


def test_the_age_is_read_from_the_reports_own_stamp(tmp_path) -> None:
    import json
    from datetime import UTC, datetime, timedelta
    cl = _launcher()
    art = tmp_path / "QQUANT_GATES.json"
    old = (datetime.now(UTC) - timedelta(minutes=cl.CONTRACT_MIN + 30)).isoformat()
    art.write_text(json.dumps({"swept_at": old}), "utf-8")   # fresh mtime, stale stamp
    rep = tmp_path / "l.json"
    assert cl.stand_down({}, artifact=art, report=rep) == cl.STANDDOWN_BREACH_EXIT
    doc = json.loads(rep.read_text("utf-8"))
    assert doc["artifact_age_basis"] == "swept_at" and doc["artifact_age_min"] > cl.CONTRACT_MIN
