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


def test_the_desk_path_exists_before_either_recovery_permit_uses_it() -> None:
    init = SCRIPT.index('$desk = Join-Path $RepoRoot "desks\\mt5"')
    use = SCRIPT.index('$recoveryPermit = Join-Path $desk')
    assert init < use


def test_target_enumerated_paths_can_land_even_when_locally_ignored() -> None:
    assert '@("add", "-f", "--all", "--") + $chunk' in SCRIPT
    assert '@("add", "-f", "--all", "--", $p)' in SCRIPT
    assert '@("add", "-f", "--all", "--", $rel)' in SCRIPT
