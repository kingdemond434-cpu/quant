from pathlib import Path


SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "Adopt-Release.ps1").read_text(
    encoding="utf-8")
SEAL_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "Adopt-And-Seal.ps1").read_text(
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


def test_root_level_runtime_state_is_state_in_adopter_and_sealer() -> None:
    """The final seal must use the same exact-file classifier as adoption.

    Prefix-only classification misses the legacy runtime artifacts stored beside source files;
    the box then adopts cleanly and refuses to seal forever on its own generated evidence.
    """
    exact = (
        "desks/mt5/gateway_state.json",
        "desks/mt5/regime_state.json",
        "desks/mt5/sync_marker.json",
        "desks/mt5/portfolio_projection.json",
        "desks/mt5/hunt11.json",
        "desks/mt5/mech_battery.json",
        "desks/mt5/mech_split.json",
        "desks/mt5/swap_exposure.json",
        "desks/mt5/docs/TRADE_PATH_REPORT.md",
    )
    for rel in exact:
        assert f'"{rel}"' in SCRIPT
        assert f'"{rel}"' in SEAL_SCRIPT
    assert "$isState = $stateFiles -contains $p" in SEAL_SCRIPT
