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
    assert "ok, why = symbol_is_tradeable(sym, meta) if sym else (False, \"no symbol on the row\")" \
        in GAUNTLET
    assert "row = dict(survivors_all.pop(key) or {})" in GAUNTLET


# --------------------------------------- 2. an attestation mismatch never empties the library
def test_retained_exact_survivors_never_returns_empty_on_a_header_mismatch() -> None:
    fn = _block(UGATE, "def retained_exact_survivors", "\ndef ")
    # the catastrophic branch is gone ...
    assert not re.search(r"if not is_exact_policy\(current\.get\(\"gate_policy\"\)\):\s*\n\s*return \{\}", fn)
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
    assert ADOPT.count("git add") == 1
    assert 'git add -- "desks/mt5/data/RELEASE.json"' in ADOPT
    assert "git add -A" not in ADOPT
    assert "stash" not in ADOPT.replace("no `git stash`", "")
    assert "--force" not in ADOPT and "-f " not in ADOPT.split("param(")[1]


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
    assert "(Get-Date).Date.AddMinutes(20)" in blk          # after ShadowSync at :05
    assert "-ExecutionTimeLimit (New-TimeSpan -Minutes 20)" in blk
    assert "-MultipleInstances IgnoreNew" in blk
    assert "[DRY ] MT5-AdoptRelease" in blk                  # honoured in -WhatIfOnly


def test_the_sync_slot_really_is_before_the_adoption_slot() -> None:
    assert "(Get-Date).Date.AddMinutes(5)" in INSTALL      # ShadowSync
    assert INSTALL.index("AddMinutes(5)") < INSTALL.index("AddMinutes(20)")
