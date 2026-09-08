"""A certificate can be REVOKED by a gate. It can no longer be LOST to a transient outage.

MEASURED 2026-09-08. The repo's canon held 66 certificates; the box's board showed 5, with 40
forward clocks RETIRED_ORPHAN ("no engine enrols this row"). Two mechanisms, both fixed here:

  1. `external_gauntlet` purges any certificate whose symbol fails `symbol_is_tradeable(sym,
     meta)` into `retired_certificates`. On 2026-09-04 the universe registry collapsed to a
     23-symbol stump (`universe.json.stump-20260904` is still on the box; commit 2dfcf3be names
     the day), ~60 certificates were retired on symbols the stump did not carry, the registry was
     restored the same day -- and nothing ever asked the question the other way. A purge with no
     restore turns one input's outage into a permanent loss of weeks of forward evidence.

  2. `universal_gate.retained_exact_survivors` returned {} whenever the survivors file's
     top-level attestation was not the current policy -- and its own docstring says what an
     empty starting dict does: "deletes every prior survivor". A header mismatch became the
     loss of the entire library on the next write.

  3. Nothing on the box ever PULLED. Every fix landed on origin and stayed there.
     Adopt-And-Seal.ps1 + MT5-AdoptRelease close that, hourly, unattended.
"""
from __future__ import annotations

import re
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
GAUNTLET = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
UGATE = (_DESK / "research" / "universal_gate.py").read_text("utf-8")
ADOPT = (_DESK / "scripts" / "Adopt-And-Seal.ps1").read_text("utf-8")
#: The script's CODE, after the comment-based help block. The help block names the things the
#: script must never do -- `git add -A`, `stash` -- and a test that forbade the WORDS would
#: forbid documenting the rule. The invariants below are about what the script does.
ADOPT_CODE = ADOPT.split("#>", 1)[1]
INSTALL = (_DESK / "scripts" / "Install-QuantWindows.ps1").read_text("utf-8")


def _block(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i:src.index(end, i)]


# --------------------------------------------------------------- 1. the purge has a restore
RESTORE = _block(GAUNTLET, "THE SAME PREDICATE, THE OTHER WAY", "doc = dict(old_doc)")


def test_the_restore_runs_in_the_same_pen_after_the_purge() -> None:
    purge = GAUNTLET.index('print(f"purged {len(retired)} uncashable certificate(s)')
    restore = GAUNTLET.index("THE SAME PREDICATE, THE OTHER WAY")
    write = GAUNTLET.index("doc = dict(old_doc)")
    assert purge < restore < write


def test_a_row_comes_back_only_when_the_reason_that_retired_it_no_longer_holds() -> None:
    assert "ok_now, _why_now = symbol_is_tradeable(sym, meta)" in RESTORE
    assert "if not ok_now:" in RESTORE
    assert "survivors_all[key] = back" in RESTORE
    assert "del retired[key]" in RESTORE


def test_a_row_without_a_full_gates_record_stays_retired() -> None:
    assert 'if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):' in RESTORE
    assert "from gate_policy import ATTESTATION, all_ten_pass" in GAUNTLET


def test_a_row_already_in_survivors_is_not_duplicated() -> None:
    assert "if not sym or key in survivors_all:" in RESTORE


def test_the_round_trip_is_stamped_so_it_is_visible() -> None:
    assert 'back["restored_at"] = stamp' in RESTORE
    assert 'back["restored_from"] = {"retired_at": back.pop("retired_at", None),' in RESTORE
    assert '"retired_reason": back.pop("retired_reason", None)}' in RESTORE
    assert "restored {len(restored)} certificate(s) whose retirement reason no longer" in RESTORE


def test_the_purge_itself_is_unchanged() -> None:
    """The restore does not weaken the purge: an untradeable symbol still leaves `survivors`."""
    assert ("ok, why = symbol_is_tradeable(sym, meta) if sym else "
            "(False, \"no symbol on the row\")") in GAUNTLET
    assert "row = dict(survivors_all.pop(key) or {})" in GAUNTLET


# --------------------------------------- 2. an attestation mismatch never empties the library
def test_retained_exact_survivors_never_returns_empty_on_a_header_mismatch() -> None:
    fn = _block(UGATE, "def retained_exact_survivors", "\ndef ")
    # the catastrophic branch is gone ...
    assert not re.search(
        r"if not is_exact_policy\(current\.get\(\"gate_policy\"\)\):\s*\n\s*return \{\}", fn)
    # ... and replaced by keeping the rows, loudly
    assert "keeping " in fn and "its rows for recertification rather than starting from empty" in fn
    # the row-level filter still stands: a row without a full gates record is not retained
    assert 'if isinstance(row, dict) and all_ten_pass(row.get("gates"))' in fn


def test_the_only_empty_returns_left_are_for_an_unreadable_or_malformed_file() -> None:
    fn = _block(UGATE, "def retained_exact_survivors", "\ndef ")
    empties = [m.start() for m in re.finditer(r"return \{\}", fn)]
    assert len(empties) == 2
    assert "except (OSError, json.JSONDecodeError):" in fn
    assert "if not isinstance(survivors, dict):" in fn


# ------------------------------------------------------------- 3. the box pulls, unattended
def test_adopt_and_seal_runs_in_the_only_safe_order() -> None:
    steps = ["Adopt-Release.ps1", "if ($sealed -eq $head)", "git status --porcelain",
             "release.seal(by='Adopt-And-Seal')", 'git add -- "desks/mt5/data/RELEASE.json"',
             "git commit -q -m", 'Stop-ScheduledTask  -TaskName "MT5-Gateway"',
             'Start-ScheduledTask -TaskName "MT5-Gateway"']
    idx = [ADOPT.index(s) for s in steps]
    assert idx == sorted(idx), "adopt -> seal-if-needed -> commit alone -> restart"


def test_adopt_and_seal_refuses_a_partial_adoption_and_a_dirty_tree() -> None:
    assert "partial adoption; NOT sealing" in ADOPT
    assert "exit $adoptExit" in ADOPT
    assert "refusing to seal:" in ADOPT and "exit 3" in ADOPT


def test_adopt_and_seal_stages_exactly_one_path_and_never_stashes() -> None:
    assert ADOPT_CODE.count("git add") == 1
    assert 'git add -- "desks/mt5/data/RELEASE.json"' in ADOPT_CODE
    assert "git add -A" not in ADOPT_CODE
    assert "stash" not in ADOPT_CODE
    assert "--force" not in ADOPT_CODE and " -f " not in ADOPT_CODE


def test_adopt_and_seal_guards_native_stderr() -> None:
    """The trap that killed Adopt-Release on its first run."""
    assert '$ErrorActionPreference = "Continue"' in ADOPT


def test_adopt_and_seal_defaults_to_the_live_desk_branch() -> None:
    assert '[string] $Branch = "claude/llm-auto-upgrade-verify-gcjac3"' in ADOPT


def test_the_installer_registers_the_adoption_hourly_after_the_sync_slot() -> None:
    blk = _block(INSTALL, "$adoptSeal = Join-Path", "# MT5-ArtifactSync")
    assert 'Register-ScheduledTask -TaskName "MT5-AdoptRelease"' in blk
    assert 'scripts\\Adopt-And-Seal.ps1' in blk
    assert "-RepetitionInterval (New-TimeSpan -Hours 1)" in blk
    assert "(Get-Date).Date.AddMinutes(12)" in blk          # between the :05 and :20 sync slots
    assert "-ExecutionTimeLimit (New-TimeSpan -Minutes 20)" in blk
    assert "-MultipleInstances IgnoreNew" in blk
    assert "[DRY ] MT5-AdoptRelease" in blk                  # honoured in -WhatIfOnly


def test_the_sync_slot_really_is_before_the_adoption_slot() -> None:
    assert "(Get-Date).Date.AddMinutes(5)" in INSTALL      # ShadowSync
    assert INSTALL.index("AddMinutes(5)") < INSTALL.index("AddMinutes(12)")


def _slot_minutes(src: str, task: str) -> tuple[int, int]:
    """(start minute, repetition interval in minutes) of `task`'s trigger in an installer."""
    i = src.index(f'Register-ScheduledTask -TaskName "{task}"') if f'"{task}"' in src \
        else src.index("Register-ScheduledTask -TaskName $TaskName")
    trig = src[:i]
    start = int(re.findall(r"\(Get-Date\)\.Date\.AddMinutes\((\d+)\)", trig)[-1])
    rep = re.findall(r"-RepetitionInterval \(New-TimeSpan -(Minutes|Hours) (\d+)\)", trig)[-1]
    return start, int(rep[1]) * (60 if rep[0] == "Hours" else 1)


def test_the_adoption_minute_is_never_a_sync_slot() -> None:
    """MEASURED 2026-09-08: MT5-ShadowSync is once-at-:05 repeating every 15 minutes -- :05,
    :20, :35, :50 -- and MT5-AdoptRelease was registered at :20 on the comment "after the :05
    slot". Two git writers in one repository in the same second: the sync's `git checkout --
    <path>` reverts the adoption's in-place writes, its commit sweeps the adoption's staged code,
    and whichever loses .git/index.lock throws -- for Adopt-Release that is exit 1 and no seal."""
    sync_start, sync_every = _slot_minutes(INSTALL, "MT5-ShadowSync")
    assert (sync_start, sync_every) == (5, 15)
    for src in (INSTALL, STANDALONE):
        adopt_start, adopt_every = _slot_minutes(src, "MT5-AdoptRelease")
        assert adopt_every == 60
        assert (adopt_start - sync_start) % sync_every != 0, \
            f"minute :{adopt_start:02d} is a ShadowSync slot"
        # and it sits after the :05 slot's ten-minute limit has run out, before the :20 slot
        assert sync_start < adopt_start < sync_start + sync_every


SYNC = (_DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")


def test_the_sync_and_the_adoption_exclude_each_other() -> None:
    """The minute fix covers the schedule; these guards cover a sync still inside its limit, the
    adoption's RestartCount retries at :14/:16, and the first manual run of the installer."""
    # the adoption waits out a running sync BEFORE invoking Adopt-Release, and gives up loudly
    guard = ADOPT_CODE.index("Get-ScheduledTask -TaskName \"MT5-ShadowSync\"")
    assert guard < ADOPT_CODE.index("$adoptScript")
    assert '.State -eq "Running"' in ADOPT_CODE[guard:guard + 200]
    assert "not adopting under it" in ADOPT_CODE and "exit 6" in ADOPT_CODE
    # the sync yields to a running adoption before its first git operation (the pull)
    yield_at = SYNC.index("Get-ScheduledTask -TaskName \"MT5-AdoptRelease\"")
    assert yield_at < SYNC.index("Sync-Pull -RepoRoot $RepoRoot -Branch $branch")
    assert yield_at < SYNC.index("function Merge-FetchHead")
    assert "SKIP: MT5-AdoptRelease is adopting" in SYNC
    body = SYNC[yield_at:SYNC.index("SKIP: MT5-AdoptRelease is adopting")]
    assert '-eq "Running"' in body
    assert "exit 0" in SYNC[yield_at:yield_at + 700]


# ------------------------------------------- 4. the seal is taken between syncs, not never
def test_adopt_and_seal_s_dirty_check_ignores_state_and_untracked_paths() -> None:
    """On the box a tracked ledger is dirty for most of every hour by design; a check that
    refused on it could only seal in the seconds after a sync, and never did."""
    assert "git status --porcelain --untracked-files=no" in ADOPT_CODE
    import sys
    repo_root = str(_DESK.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from libs.ops import release
    for prefix in release.STATE_PREFIXES:
        assert f'"{prefix}"' in ADOPT_CODE, prefix
    assert "tracked code path(s) differ from HEAD after adoption" in ADOPT_CODE


STANDALONE = (_DESK / "scripts" / "install_adopt_release_task.ps1").read_text("utf-8")


def test_the_standalone_installer_agrees_with_the_full_one() -> None:
    """Re-running the whole installer on a live box has failed with "Access is denied" on the
    S4U principals, so the one task that unblocks the box gets its own installer -- which must
    register the SAME task, or the two routes would fight over its settings every install."""
    blk = _block(INSTALL, "$adoptSeal = Join-Path", "# MT5-ArtifactSync")
    for s in ("MT5-AdoptRelease", "Adopt-And-Seal.ps1",
              "-RepetitionInterval (New-TimeSpan -Hours 1)", "(Get-Date).Date.AddMinutes(12)",
              "-ExecutionTimeLimit (New-TimeSpan -Minutes 20)", "-MultipleInstances IgnoreNew",
              "-LogonType Interactive -RunLevel Limited", "-StartWhenAvailable"):
        assert s in blk, f"installer block lost {s}"
        assert s in STANDALONE, f"standalone installer lost {s}"


def test_the_standalone_installer_runs_the_first_adoption_now_and_is_idempotent() -> None:
    assert "Unregister-ScheduledTask -TaskName $TaskName" in STANDALONE
    assert "Start-ScheduledTask -TaskName $TaskName" in STANDALONE
    assert STANDALONE.index("Register-ScheduledTask") < STANDALONE.index("Start-ScheduledTask")
    assert "$ErrorActionPreference = 'Stop'" in STANDALONE


def test_adopt_and_seal_resolves_python_the_way_the_installer_does() -> None:
    """The box has no .venv and runs every task through `py -3`; a seal that fell straight to
    bare `python` would exit 4 on a box where that name is not on the task's PATH -- adopted,
    never sealed, gateway still refusing on the old seal."""
    order = ['.venv\\Scripts\\python.exe', "Get-Command py", "Get-Command python",
             "no python interpreter found"]
    idx = [ADOPT_CODE.index(s) for s in order]
    assert idx == sorted(idx), "venv, then the launcher, then bare python, then a loud exit"
    assert '$pyArgs = @("-3")' in ADOPT_CODE
    assert "& $py @pyArgs -c" in ADOPT_CODE


def test_every_git_writer_on_the_box_takes_the_same_process_level_lock() -> None:
    """A verifier refuted the task-state guards: sync_shadow_to_git.ps1 has a second invoker
    (hourly_cycle.publish_state launches it directly) and a third (a hand run), and neither
    shows as MT5-ShadowSync 'Running'. The lock must belong to the PROCESS, whoever started it."""
    for src, name in ((SYNC, "sync"), (ADOPT_CODE, "adopt")):
        assert 'New-Object System.Threading.Mutex($false, "Local\\MT5-GitWriter")' in src, name
        assert "catch [System.Threading.AbandonedMutexException] { $gotLock = $true }" in src, name
    # the sync takes it after its yield and before its first git operation; a miss yields (exit 0)
    lock_at = SYNC.index('"Local\\MT5-GitWriter"')
    assert SYNC.index("SKIP: MT5-AdoptRelease is adopting") < lock_at
    assert lock_at < SYNC.index("Sync-Pull -RepoRoot $RepoRoot -Branch $branch")
    assert "exit 0" in SYNC[lock_at:lock_at + 600]
    # the adoption takes it before invoking Adopt-Release and refuses loudly (exit 6) on a miss
    alock = ADOPT_CODE.index('"Local\\MT5-GitWriter"')
    assert alock < ADOPT_CODE.index("$adoptScript")
    assert "exit 6" in ADOPT_CODE[alock:alock + 600]
