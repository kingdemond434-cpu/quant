from pathlib import Path


SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "Adopt-Release.ps1").read_text(
    encoding="utf-8")


def test_recovery_permit_does_not_suppress_fetch_by_existence_alone() -> None:
    block = SCRIPT[SCRIPT.index("$preflightRecoveryPermit ="):SCRIPT.index(
        "# FETCH_HEAD, NOT origin")]
    assert "$preflightExpires -gt (Get-Date).ToUniversalTime()" in block
    assert "$preflightPermit.target -eq $preflightFetch" in block
    assert "stale or target-mismatched recovery permit ignored; fetching origin" in block
    assert block.index("$NoFetch = $true") > block.index("$preflightExpires -gt")
