from pathlib import Path


DESK = Path(__file__).resolve().parents[1]


def test_both_heavy_certifiers_share_one_resource_lane() -> None:
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    qquant = (DESK / "research" / "certifier_launcher.py").read_text("utf-8")
    token = 'exclusive_job("certification_lane"'
    assert token in external
    assert token in qquant


def test_expected_contention_defers_without_false_failure() -> None:
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    qquant = (DESK / "research" / "certifier_launcher.py").read_text("utf-8")
    assert "another canonical certifier owns the lane" in external
    assert "another canonical certifier owns the lane" in qquant
    assert "return 0" in external
    assert "return 0" in qquant


def test_qquant_lease_is_taken_before_heavy_target_import() -> None:
    launcher = (DESK / "research" / "certifier_launcher.py").read_text("utf-8")
    qquant = (DESK / "research" / "qquant_gates.py").read_text("utf-8")
    installer = (DESK / "scripts" / "Install-QuantWindows.ps1").read_text("utf-8")
    assert "certifier_launcher.py" in installer
    assert "qquant_gates.py" in launcher
    assert "subprocess.run" in launcher
    assert "OPENBLAS_NUM_THREADS" in launcher
    assert 'exclusive_job("certification_lane"' not in qquant
