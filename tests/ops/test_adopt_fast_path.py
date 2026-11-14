"""MT5-AdoptRelease every five minutes (2026-11-14): the cheap tick may only SKIP a run that would
have found nothing, never adopt, and never hide a run that failed."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1").read_text("utf-8")
FAST = SRC[SRC.index("-1. NOTHING NEW ON ORIGIN") :]
STARTED = 'Write-Heartbeat @{ finished_at = $null; exit_code = $null; stage = "started"'
FAST = FAST[: FAST.index(STARTED)]


def test_the_fast_path_runs_before_any_lock_wait_or_write() -> None:
    at = SRC.index("-1. NOTHING NEW ON ORIGIN")
    for later in ('stage = "started"', 'Get-ScheduledTask -TaskName "MT5-ShadowSync"',
                  "Open-GitWriterMutex", "release_promotion.py", "Invoke-AdoptGuard @("):
        assert at < SRC.index(later), later


def test_the_fast_path_only_reads_the_remote() -> None:
    calls = re.findall(r"git -C \$RepoRoot[^\n]*", FAST)
    assert len(calls) == 1 and "ls-remote origin" in calls[0], calls
    assert "Adopt-Release.ps1" not in FAST and "Done " not in FAST


def test_it_skips_only_an_unchanged_origin_within_the_hour() -> None:
    assert "$script:SettledMaxMin = 55" in FAST
    assert "[string]$settled.key -eq $script:RemoteKey" in FAST
    assert "$ageMin -ge 0 -and $ageMin -lt $script:SettledMaxMin" in FAST
    # both refs must be read, or no key is formed and the full path runs
    assert '"refs/heads/$Branch" "refs/heads/production"' in FAST
    assert "$ls.Count -eq 2" in FAST


def test_an_override_always_takes_the_full_path() -> None:
    assert "$AllowUnreleased -or ($env:QUANT_ADOPT_UNRELEASED -eq \"1\")" in FAST
    assert 'data\\ADOPT_UNRELEASED' in FAST
    assert "if (-not $override)" in FAST


def test_only_a_settled_success_is_remembered() -> None:
    stages = re.search(r"\$script:SettledStages = @\(([^)]*)\)", SRC)
    assert stages
    named = set(re.findall(r'"([a-z-]+)"', stages.group(1)))
    assert named == {"held-awaiting-release", "held-awaiting-audit", "already-sealed",
                     "accepts-nothing-to-seal", "sealed"}
    # a blackout or a rollback is time- or health-bound: the next tick must look again
    assert not named & {"held-blackout", "held-rolled-back"}
    done = SRC[SRC.index("function Done(") : SRC.index("exit $code", SRC.index("function Done("))]
    rule = "$code -eq 0 -and $script:RemoteKey -and ($script:SettledStages -contains $stage)"
    assert rule in done


def test_a_skipped_tick_is_a_witnessed_success() -> None:
    # check_adoption_freshness reads the heartbeat against the task's cadence; a silent skip
    # would read STALE after three five-minute ticks
    assert 'stage       = "no-new-release"' in FAST and "ok          = $true" in FAST
