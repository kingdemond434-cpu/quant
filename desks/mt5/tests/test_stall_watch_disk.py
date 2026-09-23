"""The disk watchdog heals itself, and the four ways it must not.

    "no human decision shud be needed its autopromoted"        -- the principal, 2026-09-08

WHAT THIS PINS. On 2026-09-08 the watchdog found 0.5GB free, pruned its single reclaim pool,
freed exactly nothing, wrote "needs a human decision" and stopped. The desk publisher died ten
minutes later; the gauntlet, allocator, shadow lane and dashboard were stale for twelve hours.
The script is PowerShell and runs only on the box, so these tests assert on its source -- the
same way `test_self_certifying_caps` pins the walk direction in `missed_growth`. A behavioural
test would need Windows and a full C: drive; a source test catches the regression that matters,
which is somebody quietly restoring the single-tier version or the give-up line.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "scripts" / "stall_watch.ps1").read_text("utf-8")
BLOCK = SRC[SRC.index("# DESK DISK FLOOR"):]

#: EXECUTABLE lines only. The invariants below are about what the script DOES; the comment above
#: the block quotes the old give-up string on purpose, to record what the defect was, and a test
#: that forbade the WORDS rather than the behaviour would forbid explaining the bug at all.
CODE = "\n".join(ln for ln in BLOCK.splitlines() if not ln.lstrip().startswith("#"))


# --------------------------------------------------------------- it never waits to be rescued
def test_it_never_terminates_on_a_human_decision() -> None:
    """The exact string that took the desk down. It may appear only as the thing being escalated
    past, never as the last word."""
    assert "needs a human decision" not in CODE
    assert "escalating automatically on the next pass" in CODE


def test_the_critical_line_says_what_is_left_rather_than_stopping() -> None:
    crit = [ln for ln in CODE.splitlines() if "DISK CRITICAL" in ln]
    assert crit, "a breach below 2GB must still be loud"
    assert "every safe pool is already empty" in crit[0]


# ------------------------------------------------------------------------ the ladder escalates
def test_there_is_a_real_ladder_not_one_pool() -> None:
    names = re.findall(r"name\s*=\s*'([^']+)'", BLOCK)
    assert len(names) >= 6, f"only {len(names)} reclaim tiers: {names}"
    # the original two must survive, and be FIRST -- cheapest before anything more costly
    assert names[0] == "logs>14d"
    assert names[1] == "gauntlet_cache"


def test_it_stops_as_soon_as_the_floor_is_cleared() -> None:
    """A mild shortage must cost a cache and nothing more. Running every tier regardless would
    throw away days of reports to recover a gigabyte nobody needed."""
    assert "if ((Get-PSDrive C).Free / 1GB -ge $DiskFloorGB) { break }" in BLOCK


def test_each_tier_measures_what_it_actually_reclaimed() -> None:
    """The 0.5 -> 0.5 defect: nothing measured bytes freed, so a prune of nothing and a prune of
    a gigabyte printed the same line."""
    assert "$f0 = (Get-PSDrive C).Free" in BLOCK
    assert "$gained = ((Get-PSDrive C).Free - $f0) / 1GB" in BLOCK
    assert "reclaimed $([math]::Round($gained,2))GB" in BLOCK


def test_a_missing_pool_reads_differently_from_an_empty_one() -> None:
    """"the path does not exist" and "there was nothing to delete" demand opposite responses and
    were indistinguishable -- both printed a successful-looking prune."""
    assert "Test-Path -LiteralPath $t.path" in BLOCK
    assert "pool path missing" in BLOCK


# --------------------------------------------------------------------------- the moat is safe
@pytest.mark.parametrize("guarded", [
    "\\data\\tape", "\\data\\secrets", "\\data\\universe",
    "RELEASE.json", "LIVE_MANIFEST.jsonl", "sleeve_registry.json",
])
def test_the_unrecoverable_data_is_refused_at_every_threshold(guarded: str) -> None:
    assert guarded in BLOCK, f"{guarded} is not on the protected list"


def test_every_delete_consults_the_protected_list() -> None:
    """A guard that exists but is not wired into the deletes is decoration. Both prune shapes --
    the directory sweep and the age sweep -- must filter through it."""
    removes = [ln for ln in BLOCK.splitlines() if "Remove-Item" in ln]
    assert len(removes) >= 2
    assert BLOCK.count("Test-DeskProtected") >= 3   # the definition plus both call sites


def test_the_tape_is_named_as_unrecoverable_so_nobody_relaxes_it_later() -> None:
    assert "unrecoverable" in BLOCK
    assert "The floor is never worth the moat." in BLOCK


# ------------------------------------------------------------------ the trigger did not change
def test_the_floor_is_still_five_gigabytes() -> None:
    """This change is about what happens BELOW the floor, not about moving it."""
    assert "$DiskFloorGB = 5" in BLOCK
    assert "if ($free -lt $DiskFloorGB)" in BLOCK


# ------------------------------------------------------------------ the RAM census is published
RAM = SRC[SRC.index("# RAM FLOOR"):SRC.index("# PROGRESS, NOT JUST PULSE")]
RAM_CODE = "\n".join(ln for ln in RAM.splitlines() if not ln.lstrip().startswith("#"))


def test_the_box_publishes_what_it_has_not_only_what_is_free() -> None:
    """A day was spent arguing 80GB against "phys 142MB free". The counter that settles it was
    read on every pass and written nowhere."""
    assert "TotalVisibleMemorySize" in RAM_CODE
    assert "TotalVirtualMemorySize" in RAM_CODE
    for key in ("total_phys_mb", "free_phys_mb", "total_commit_mb", "free_commit_mb"):
        assert key in RAM_CODE, key


def test_the_largest_commit_holders_are_named_across_every_process() -> None:
    """Shedding sorts by commit; the census must show the same ranking, and it must include the
    terminal and the browser, which are never shed but are half the answer."""
    assert "top_commit" in RAM_CODE
    assert ("Get-CimInstance Win32_Process | Sort-Object -Property PageFileUsage -Descending"
            in RAM_CODE)
    assert "-First 6" in RAM_CODE


def test_the_census_travels_with_the_verdict_and_starts_unmeasured() -> None:
    assert "memory = $memCensus" in SRC
    assert "$memCensus = @{ status = 'UNMEASURED' }" in RAM_CODE   # a failed read is not zero


def test_the_shed_still_measures_the_smaller_of_ram_and_commit() -> None:
    """The census is additive; the floor's own arithmetic is untouched."""
    assert "$freeMB = [math]::Min($freePhysMB, $freeVirtMB)" in RAM_CODE
    assert "if ($freeMB -lt 500 -and $strikes -ge 2)" in RAM_CODE
