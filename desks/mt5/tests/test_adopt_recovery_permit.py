import re
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
    # The SEALER no longer classifies paths at all (2026-09-24): its dirty check is
    # `git diff ... -- $releaseCodePaths`, the release's CODE ROOTS only, so it never sees a
    # runtime artifact unless one lives under a code root. Pin that none of these does.
    assert "git diff --name-only --no-ext-diff HEAD -- $releaseCodePaths" in SEAL_SCRIPT
    roots_src = SEAL_SCRIPT[SEAL_SCRIPT.index("$releaseCodePaths = @("):]
    roots = re.findall(r'"([^"]+)"', roots_src[:roots_src.index(")")])
    assert "desks/mt5/mt5desk" in roots
    for rel in exact:
        assert f'"{rel}"' in SCRIPT
        assert not any(rel == r or rel.startswith(r + "/") for r in roots), rel
