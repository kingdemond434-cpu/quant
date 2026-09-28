from pathlib import Path


DESK = Path(__file__).resolve().parents[1]


def test_both_heavy_certifiers_share_one_resource_lane() -> None:
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    qquant = (DESK / "research" / "qquant_gates.py").read_text("utf-8")
    token = 'exclusive_job("certification_lane"'
    assert token in external
    assert token in qquant


def test_expected_contention_defers_without_false_failure() -> None:
    external = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    qquant = (DESK / "research" / "qquant_gates.py").read_text("utf-8")
    assert "another canonical certifier owns the lane" in external
    assert "another canonical certifier owns the lane" in qquant
    assert "return 0" in external
    assert "return 0" in qquant
