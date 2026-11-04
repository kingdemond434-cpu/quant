"""intel_ship_adopt.ps1 never re-adopts a frozen ship over the box-written feed (2026-11-03).

hel8 shipped the intel feed last at 2026-11-03T02:50Z, and the box now writes it itself. Checking
out the frozen ref each hour would revert those box-written files to their stale copies and
refresh their mtimes, so the staleness contracts would read a reverted feed as fresh.
Split out of #601: a change under desks/mt5/scripts/ is money path, and it takes that path alone.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK / "side_channels") not in sys.path:
    sys.path.insert(0, str(DESK / "side_channels"))

# --------------------------------------------------------------------- intel_ship_adopt.ps1 skip
SHIP = (DESK / "scripts" / "intel_ship_adopt.ps1").read_text(encoding="utf-8")


def test_a_frozen_or_unchanged_ship_is_skipped_before_any_wait_or_lock() -> None:
    skip = SHIP.index("# 1b. SKIP A FROZEN OR UNCHANGED SHIP")
    assert SHIP.index("fetch --no-write-fetch-head") < skip
    assert skip < SHIP.index('Get-ScheduledTask -TaskName "MT5-ShadowSync"')
    assert skip < SHIP.index("$script:GitWriterHandle = Open-GitWriterMutex")
    assert skip < SHIP.index("& git checkout $shipRef --")
    assert "[double] $MaxShipAgeHours = 6" in SHIP
    block = SHIP[skip:SHIP.index("# 2. wait for MT5-ShadowSync")]
    assert "git log -1 --format=%ct $shipRef" in block
    assert "if ($shipAgeH -gt $MaxShipAgeHours)" in block
    assert "$lastSha -eq $shipSha" in block
    # each skip says why, in the log, and exits 0 (a skip is the organ working)
    assert block.count("Log $why") == 2 and block.count("exit 0") == 2
    assert "stopped" in block and "unchanged since the last adoption" in block
    # a ref whose time cannot be read is not adopted blind
    assert "not adopting what cannot be dated" in block


def test_the_adopted_sha_is_recorded_only_after_a_real_checkout() -> None:
    checkout = SHIP.index("& git checkout $shipRef --")
    write = SHIP.index("WriteAllText($adoptState")
    assert checkout < write
    assert 'if ($LASTEXITCODE -ne 0) { Log "git checkout failed' in SHIP[checkout:write]
    assert "last_adopted_sha = $shipSha" in SHIP[checkout:write]
    assert "intel_ship_adopt_state.json" in SHIP




def test_the_ship_checkout_never_lands_over_the_box_written_files() -> None:
    """Audit HOLD on 84e1e474b: a VPS that came back would check out over the files the box's
    feed rewrites every sweep."""
    assert "& git checkout $shipRef -- data/intelligence desks/mt5/data/intelligence @boxWritten" \
        in SHIP
    block = SHIP[SHIP.index("$boxWritten = @("):SHIP.index("# 2. wait for MT5-ShadowSync")]
    for rel in ("desks/mt5/data/intelligence/seed_miners_state.json",
                "desks/mt5/data/intelligence/latest_discoveries.json"):
        assert f"':!{rel}'" in block
    import seed_miners as sm
    assert sm.STATE.name == "seed_miners_state.json"
    assert (sm.INTEL / "latest_discoveries.json").parent == sm.STATE.parent


def test_the_exclusion_pathspecs_really_keep_git_off_the_box_written_files(tmp_path) -> None:
    """The same arguments the script passes, run through git: the shipped archive lands, the
    box-written state does not."""
    import subprocess
    block = SHIP[SHIP.index("$boxWritten = @("):SHIP.index("# 2. wait for MT5-ShadowSync")]
    excludes = re.findall(r"'(:![^']+)'", block)
    assert len(excludes) == 2

    def git(*a: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    intel = tmp_path / "desks" / "mt5" / "data" / "intelligence"
    intel.mkdir(parents=True)
    (tmp_path / "data" / "intelligence").mkdir(parents=True)
    (tmp_path / "data" / "intelligence" / "x.json").write_text("v1")
    for n in ("seed_miners_state.json", "latest_discoveries.json", "kimi.json"):
        (intel / n).write_text("ship")
    git("add", "-A")
    git("commit", "-qm", "ship")
    git("update-ref", "refs/remotes/intel-ship/send", "HEAD")
    for n in ("seed_miners_state.json", "latest_discoveries.json", "kimi.json"):
        (intel / n).write_text("box")
    git("checkout", "refs/remotes/intel-ship/send", "--", "data/intelligence",
        "desks/mt5/data/intelligence", *excludes)
    assert (intel / "seed_miners_state.json").read_text() == "box"
    assert (intel / "latest_discoveries.json").read_text() == "box"
    assert (intel / "kimi.json").read_text() == "ship"


